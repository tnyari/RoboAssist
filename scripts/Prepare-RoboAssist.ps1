[CmdletBinding()]
param([switch]$StartApplication)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RuntimeDirectory = Join-Path $PSScriptRoot '_internal/runtime'
$ManifestPath = Join-Path $RuntimeDirectory 'vc-runtime.json'
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$minimumVersion = [version]$manifest.minimum_version
$registryPath = 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64'

function Get-InstalledRuntimeVersion {
    try {
        $runtime = Get-ItemProperty -LiteralPath $registryPath -ErrorAction Stop
        if ($runtime.Installed -ne 1 -or [string]::IsNullOrWhiteSpace($runtime.Version)) {
            return $null
        }
        return [version]$runtime.Version.TrimStart('v')
    } catch {
        return $null
    }
}

$installedVersion = Get-InstalledRuntimeVersion
if ($null -eq $installedVersion -or $installedVersion -lt $minimumVersion) {
    $installer = Join-Path $RuntimeDirectory $manifest.filename
    $actualHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $manifest.sha256) {
        throw 'A csomagolt Microsoft VC Redistributable SHA-256 értéke eltér a rögzítettől.'
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -ne $manifest.signer) {
        throw 'A csomagolt Microsoft VC Redistributable aláírása nem ellenőrizhető.'
    }
    $installerVersion = [version][System.Diagnostics.FileVersionInfo]::GetVersionInfo($installer).FileVersion
    if ($installerVersion -lt $minimumVersion) {
        throw "A csomagolt VC Redistributable túl régi: $installerVersion"
    }

    Write-Host "A Microsoft Visual C++ x64 futtatókörnyezet telepítése szükséges ($($manifest.minimum_version)+)."
    Write-Host 'A Windows rendszergazdai jóváhagyást kérhet. A telepítő nem használ hálózatot.'
    try {
        $process = Start-Process -FilePath $installer -ArgumentList '/install', '/passive', '/norestart' -Verb RunAs -Wait -PassThru
    } catch {
        throw 'A VC runtime telepítése nem indult el. Hagyd jóvá a Windows UAC-kérését, majd próbáld újra.'
    }

    $installedVersion = Get-InstalledRuntimeVersion
    if ($null -eq $installedVersion -or $installedVersion -lt $minimumVersion) {
        throw "A VC runtime telepítése nem igazolható (telepítő kilépési kód: $($process.ExitCode))."
    }
    Write-Host "A szükséges VC runtime telepítve: $installedVersion"
} else {
    Write-Host "Megfelelő VC runtime már telepítve: $installedVersion"
}

if ($StartApplication) {
    $application = Join-Path $PSScriptRoot 'RoboAssist.exe'
    if (-not (Test-Path -LiteralPath $application -PathType Leaf)) {
        throw "A RoboAssist.exe fájl nem található: $application"
    }
    Start-Process -FilePath $application
}

