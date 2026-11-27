param([switch]$Offline)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot '.venv/Scripts/python.exe'
$setupDev = Join-Path $PSScriptRoot 'setup-dev.ps1'
Push-Location $RepoRoot
try {
    if (-not (Test-Path -LiteralPath $Python)) {
        if ($Offline) { throw 'Offline build requires the locked .venv to be prepared already.' }
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setupDev
        if ($LASTEXITCODE -ne 0) { throw 'The locked development environment could not be prepared.' }
    }

    $pyInstallerVersion = & $Python -m PyInstaller --version
    if ($LASTEXITCODE -ne 0 -or $pyInstallerVersion.Trim() -ne '6.22.3') {
        if ($Offline) { throw 'Offline build requires PyInstaller 6.22.3 in the locked .venv.' }
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setupDev
        if ($LASTEXITCODE -ne 0) { throw 'The locked development environment could not be prepared.' }
        $pyInstallerVersion = & $Python -m PyInstaller --version
        if ($LASTEXITCODE -ne 0 -or $pyInstallerVersion.Trim() -ne '6.22.3') {
            throw "Expected PyInstaller 6.22.3, got $pyInstallerVersion"
        }
    }

    $setupAv = Join-Path $PSScriptRoot 'setup-av-runtime.ps1'
    $avArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $setupAv, '-Python', $Python)
    if ($Offline) { $avArgs += '-Offline' }
    & powershell.exe @avArgs
    if ($LASTEXITCODE -ne 0) { throw 'The locked PyAV/FFmpeg runtime could not be staged.' }

    $sitePackages = Join-Path (Split-Path -Parent (Split-Path -Parent $Python)) 'Lib/site-packages'
    $licenseOutput = Join-Path (Join-Path $RepoRoot '.tools') 'python-license-bundle'
    & $Python (Join-Path $PSScriptRoot 'prepare-python-licenses.py') --site-packages $sitePackages --output $licenseOutput
    if ($LASTEXITCODE -ne 0) { throw 'Python license bundle preparation failed.' }

    $versionLine = Get-Content -LiteralPath (Join-Path $RepoRoot 'pyproject.toml') |
        Select-String -Pattern '^version = "(\d+\.\d+\.\d+)"' | Select-Object -First 1
    $version = $versionLine.Matches.Groups[1].Value
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid project version: $version" }

    $pyiRoot = Join-Path (Join-Path $RepoRoot '.tools') 'pyinstaller-build'
    $pyiRoot = [IO.Path]::GetFullPath($pyiRoot)
    $allowedPrefix = [IO.Path]::GetFullPath((Join-Path $RepoRoot '.tools')) + [IO.Path]::DirectorySeparatorChar
    if (-not $pyiRoot.StartsWith($allowedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Build output escaped the workspace: $pyiRoot"
    }
    if (Test-Path -LiteralPath $pyiRoot) { Remove-Item -LiteralPath $pyiRoot -Recurse -Force }
    $buildDist = Join-Path $pyiRoot 'dist'
    $workPath = Join-Path $pyiRoot 'work'
    New-Item -ItemType Directory -Force -Path $buildDist, $workPath | Out-Null

    $env:HF_HUB_OFFLINE = '1'
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    $buildCache = Join-Path (Join-Path $RepoRoot '.tools') 'build-cache'
    $env:HF_HOME = Join-Path $buildCache 'huggingface'
    $env:XDG_CACHE_HOME = Join-Path $buildCache 'xdg'
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $buildCache 'pyinstaller'
    New-Item -ItemType Directory -Force -Path $env:HF_HOME, $env:XDG_CACHE_HOME,
        $env:PYINSTALLER_CONFIG_DIR | Out-Null
    & $Python -m PyInstaller --noconfirm --clean --distpath $buildDist --workpath $workPath roboassist.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller one-directory build failed.' }

    $packageName = "RoboAssist-$version-windows-x64"
    $distRoot = Join-Path $RepoRoot 'dist'
    $packagePath = Join-Path $distRoot $packageName
    $zipPath = Join-Path $distRoot "$packageName.zip"
    $hashPath = "$zipPath.sha256"
    foreach ($target in @($packagePath, $zipPath, $hashPath)) {
        $fullTarget = [IO.Path]::GetFullPath($target)
        $distPrefix = [IO.Path]::GetFullPath($distRoot) + [IO.Path]::DirectorySeparatorChar
        if (-not $fullTarget.StartsWith($distPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to replace a path outside dist: $fullTarget"
        }
        if (Test-Path -LiteralPath $fullTarget) { Remove-Item -LiteralPath $fullTarget -Recurse -Force }
    }
    Copy-Item -LiteralPath (Join-Path $buildDist 'RoboAssist') -Destination $packagePath -Recurse
    Compress-Archive -LiteralPath $packagePath -DestinationPath $zipPath -CompressionLevel Fastest
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash *$packageName.zip" | Set-Content -LiteralPath $hashPath -Encoding ascii
    Write-Host "Created: $packagePath"
    Write-Host "ZIP: $zipPath"
    Write-Host "SHA-256: $hash"
    Write-Host 'The app package does not contain model weights; install/import a model offline from a separate verified bundle.'
} finally {
    Pop-Location
}
