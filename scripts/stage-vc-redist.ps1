[CmdletBinding()]
param([switch]$Offline)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $RepoRoot 'docs/package/vc-runtime.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$destination = Join-Path (Join-Path $RepoRoot '.tools') $manifest.filename

function Test-StagedRuntime([string]$Path, $RuntimeManifest) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing VC Redistributable: $Path"
    }

    $actualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $RuntimeManifest.sha256) {
        throw "VC Redistributable SHA-256 mismatch: $actualHash"
    }

    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -ne $RuntimeManifest.signer) {
        throw "VC Redistributable Authenticode signer/status mismatch: $($signature.Status), $($signature.SignerCertificate.Subject)"
    }

    $versionInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($Path)
    if ([version]$versionInfo.FileVersion -lt [version]$RuntimeManifest.minimum_version) {
        throw "VC Redistributable is older than $($RuntimeManifest.minimum_version): $($versionInfo.FileVersion)"
    }

    Write-Host "Verified VC Redistributable $($versionInfo.FileVersion): $actualHash"
}

if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
    if ($Offline) {
        throw 'Offline staging requires the Microsoft VC Redistributable to be present already.'
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Invoke-WebRequest -Uri $manifest.source_url -OutFile $destination -TimeoutSec 120
}

Test-StagedRuntime -Path $destination -RuntimeManifest $manifest

