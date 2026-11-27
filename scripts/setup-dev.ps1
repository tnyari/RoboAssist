param([string]$Venv = '.venv')
. (Join-Path $PSScriptRoot 'bootstrap-uv.ps1')

# Only a project-local .venv or .venv-<name> can be selected. Never replace it.
if ($Venv -notmatch '^\.venv(?:-[A-Za-z0-9_-]+)?$') {
    throw 'Venv must be .venv or .venv-<name>, directly inside the repository.'
}
Push-Location $RepoRoot
try {
    $uvExe = Get-ProjectUv
    $pythonRoot = Join-Path $ToolsRoot 'python'
    Invoke-Checked $uvExe @('python', 'install', $PythonVersion,
        '--install-dir', $pythonRoot, '--cache-dir', $UvCache, '--no-bin')
    $python = Join-Path $pythonRoot "cpython-$PythonVersion-windows-x86_64-none/python.exe"
    $venvPath = Join-Path $RepoRoot $Venv
    $venvPython = Join-Path $venvPath 'Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $venvPath)) {
        Invoke-Checked $uvExe @('venv', $venvPath, '--python', $python,
            '--no-python-downloads', '--cache-dir', $UvCache)
    }
    # Reject an existing environment with the wrong interpreter, including 32-bit Python.
    Invoke-Checked $venvPython @('-c',
        "import platform, struct; assert platform.python_version() == '$PythonVersion' and struct.calcsize('P') == 8")
    Invoke-Checked $uvExe @('pip', 'sync', 'requirements.lock', '--python', $venvPython,
        '--require-hashes', '--only-binary', ':all:', '--default-index', 'https://pypi.org/simple',
        '--cache-dir', $UvCache, '--no-python-downloads')
    # Replace the transitively resolved PyPI PyAV/FFmpeg build with the exact LGPL conda-forge lock.
    Invoke-Checked 'powershell.exe' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        (Join-Path $PSScriptRoot 'setup-av-runtime.ps1'), '-Python', $venvPython)
    # Build backend and all its dependencies are already hash-locked above.
    Invoke-Checked $uvExe @('pip', 'install', '--python', $venvPython, '--no-deps',
        '--no-build-isolation', '--offline', '--cache-dir', $UvCache, '-e', '.')
    Invoke-Checked $uvExe @('pip', 'check', '--python', $venvPython, '--cache-dir', $UvCache)
    Invoke-Checked $venvPython @('-m', 'offline_stt', '--config', 'configs/default.toml')
    Write-Host "Ready: $venvPython (no activation required)."
} finally {
    Pop-Location
}
