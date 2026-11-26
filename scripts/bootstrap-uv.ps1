# Shared bootstrap. Downloads are confined to .tools; no global installation.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$UvVersion = '0.13.10'
$PythonVersion = (Get-Content (Join-Path $RepoRoot '.python-version') -Raw).Trim()
$ToolsRoot = Join-Path $RepoRoot '.tools'
$UvCache = Join-Path $ToolsRoot 'uv-cache'

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}

function Get-ProjectUv {
    if (-not [Environment]::Is64BitOperatingSystem -or
        -not [Environment]::Is64BitProcess -or
        [Environment]::OSVersion.Platform -ne 'Win32NT' -or
        $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
        throw 'Use x64 PowerShell on Windows x64 (not ARM64).'
    }
    $bootstrapRoot = Join-Path $ToolsRoot 'uv-bootstrap'
    $extracted = Join-Path $bootstrapRoot 'extracted'
    $uvExe = Join-Path $extracted "uv-$UvVersion.data/scripts/uv.exe"
    if (-not (Test-Path -LiteralPath $uvExe)) {
        New-Item -ItemType Directory -Force -Path $bootstrapRoot | Out-Null
        $archive = Join-Path $bootstrapRoot 'uv.zip'
        $url = 'https://files.pythonhosted.org/packages/cf/e4/d0704c116ada58e8450890e2defaaf2f07e8d264cf94669210e0823fbcb2/uv-0.13.10-py3-none-win_amd64.whl'
        $expectedHash = 'd87b9cf8165f2b3cc596e856b5bf794da9cfad6d1b110ca9d87eed42a15b3684'
        # TLS 1.2 is required on Windows PowerShell 5.1 as well.
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $archive
        $actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
        if ($actualHash -ne $expectedHash) { throw 'uv wheel SHA-256 mismatch; not extracted.' }
        Expand-Archive -LiteralPath $archive -DestinationPath $extracted -Force
    }
    $versionText = & $uvExe --version
    if ($LASTEXITCODE -ne 0 -or $versionText -notmatch "^uv $([regex]::Escape($UvVersion)) ") {
        throw "Expected uv $UvVersion, got: $versionText"
    }
    return $uvExe
}
