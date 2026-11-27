param(
    [string]$Python = '.venv\Scripts\python.exe',
    [switch]$Offline
)

. (Join-Path $PSScriptRoot 'bootstrap-micromamba.ps1')
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot
try {
    $expectedMicromamba = Join-Path (Join-Path $RepoRoot '.tools') 'micromamba/micromamba.exe'
    if ($Offline -and -not (Test-Path -LiteralPath $expectedMicromamba)) {
        throw 'Offline mode requires the pinned project-local micromamba bootstrap to be present.'
    }
    $micromamba = Get-ProjectMicromamba
    $lock = Join-Path $RepoRoot 'conda-av-win64.lock'
    $lockHash = (Get-FileHash -LiteralPath $lock -Algorithm SHA256).Hash.ToLowerInvariant().Substring(0, 16)
    $prefix = Join-Path (Join-Path $RepoRoot '.tools') "av-runtime-$lockHash"
    $env:MAMBA_ROOT_PREFIX = Join-Path $RepoRoot '.tools/micromamba/root'
    $env:CONDA_PKGS_DIRS = Join-Path $env:MAMBA_ROOT_PREFIX 'pkgs'
    $env:CONDA_ENVS_PATH = Join-Path $RepoRoot '.tools/micromamba/envs'
    New-Item -ItemType Directory -Force -Path $env:CONDA_ENVS_PATH | Out-Null
    $arguments = @('--root-prefix', $env:MAMBA_ROOT_PREFIX, 'create', '--yes', '--prefix', $prefix, '--file', $lock)
    if ($Offline) { $arguments += '--offline' }

    if (-not (Test-Path -LiteralPath (Join-Path $prefix 'conda-meta'))) {
        & $micromamba @arguments
        if ($LASTEXITCODE -ne 0) {
            throw 'The locked PyAV/FFmpeg runtime could not be created. Offline mode requires the exact locked conda artifacts in the local micromamba cache.'
        }
    } else {
        $actual = & $micromamba --root-prefix $env:MAMBA_ROOT_PREFIX list --prefix $prefix --explicit --sha256
        if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the existing locked PyAV runtime prefix.' }
        $actualUrls = @($actual | Where-Object { $_ -match '^https://' })
        $expectedUrls = @(Get-Content -LiteralPath $lock | Where-Object { $_ -match '^https://' })
        if (($actualUrls -join "`n") -ne ($expectedUrls -join "`n")) {
            throw "Existing PyAV runtime prefix does not match $lock. Keep it for inspection and use a fresh checkout for a new lock."
        }
    }

    $pythonPath = (Resolve-Path -LiteralPath $Python).Path
    $venvRoot = Split-Path -Parent (Split-Path -Parent $pythonPath)
    $sitePackages = Join-Path $venvRoot 'Lib/site-packages'
    $distributionRoot = Join-Path (Join-Path $RepoRoot '.tools') 'av-vendor'
    $stageScript = Join-Path $RepoRoot 'scripts/stage-av-runtime.py'
    & $pythonPath $stageScript --conda-prefix $prefix --site-packages $sitePackages --distribution-root $distributionRoot
    if ($LASTEXITCODE -ne 0) { throw 'PyAV/FFmpeg runtime staging failed.' }
} finally {
    Pop-Location
}
