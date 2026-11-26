param([switch]$Upgrade)
. (Join-Path $PSScriptRoot 'bootstrap-uv.ps1')
Push-Location $RepoRoot
try {
    $uvExe = Get-ProjectUv
    $compileArgs = @('pip', 'compile', 'pyproject.toml', '--group', 'dev',
        '--python-version', $PythonVersion, '--python-platform', 'x86_64-pc-windows-msvc',
        '--only-binary', ':all:', '--generate-hashes', '--no-python-downloads',
        '--default-index', 'https://pypi.org/simple', '--cache-dir', $UvCache,
        '--custom-compile-command', 'powershell -NoProfile -File scripts/update-lock.ps1',
        '--output-file', 'requirements.lock', '--quiet')
    if ($Upgrade) { $compileArgs += '--upgrade' }
    Invoke-Checked $uvExe $compileArgs
    Write-Host 'Updated requirements.lock; review the diff and rerun setup and checks.'
} finally {
    Pop-Location
}
