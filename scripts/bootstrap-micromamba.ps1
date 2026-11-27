# Project-local micromamba bootstrap. The conda archive is pinned and hash-checked.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ToolsRoot = Join-Path $RepoRoot '.tools'
$BootstrapRoot = Join-Path $ToolsRoot 'micromamba'
$MicromambaExe = Join-Path $BootstrapRoot 'micromamba.exe'
$MicromambaVersion = '2.10.0'
$ArchiveHash = '6283f25f8142606d86e81a43c7103b5d4f1d5c2027e3f9d7326eff23b33930d8'

function Invoke-MicromambaChecked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}

function Get-ProjectMicromamba {
    if (-not [Environment]::Is64BitOperatingSystem -or
        -not [Environment]::Is64BitProcess -or
        [Environment]::OSVersion.Platform -ne 'Win32NT' -or
        $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
        throw 'Use x64 PowerShell on Windows x64 (not ARM64).'
    }
    if (Test-Path -LiteralPath $MicromambaExe) {
        $current = (& $MicromambaExe --version).Trim()
        if ($LASTEXITCODE -eq 0 -and $current -eq $MicromambaVersion) { return $MicromambaExe }
        throw "Unexpected project-local micromamba version: $current"
    }

    New-Item -ItemType Directory -Force -Path $BootstrapRoot | Out-Null
    $archive = Join-Path $BootstrapRoot 'micromamba-2.10.0-win-64.tar.bz2'
    $unpackRoot = Join-Path $BootstrapRoot 'extracted'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing `
        -Uri 'https://conda.anaconda.org/conda-forge/win-64/micromamba-2.10.0-0.tar.bz2' `
        -OutFile $archive
    $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $ArchiveHash) { throw 'micromamba conda archive SHA-256 mismatch; not extracted.' }
    New-Item -ItemType Directory -Force -Path $unpackRoot | Out-Null
    & tar.exe -xjf $archive -C $unpackRoot 'Library/bin/micromamba.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Could not extract micromamba from its verified conda archive.' }
    $extracted = Join-Path $unpackRoot 'Library/bin/micromamba.exe'
    if (-not (Test-Path -LiteralPath $extracted)) { throw 'Verified micromamba executable is missing.' }
    Copy-Item -LiteralPath $extracted -Destination $MicromambaExe
    $actualVersion = (& $MicromambaExe --version).Trim()
    if ($LASTEXITCODE -ne 0 -or $actualVersion -ne $MicromambaVersion) {
        throw "Expected micromamba $MicromambaVersion, got: $actualVersion"
    }
    return $MicromambaExe
}
