Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$SourceDirectory = Join-Path (Join-Path $RepoRoot '.tools/av-vendor') 'upstream-sources'
New-Item -ItemType Directory -Force -Path $SourceDirectory | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Sources = @(
    [pscustomobject]@{
        Name = 'av-17.1.0.tar.gz'
        Uri = 'https://pypi.org/packages/source/a/av/av-17.1.0.tar.gz'
        SHA256 = '7f1e71ff621b66253333926f948e00faae11d855b2442133c65128bca64cdeb3'
    },
    [pscustomobject]@{
        Name = 'ffmpeg-8.1.2.tar.gz'
        Uri = 'https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.gz'
        SHA256 = '32faba5ef67340d54724941eae1425580791195312a4fd13bf6f820a2818bf22'
    },
    [pscustomobject]@{
        Name = 'qtbase-everywhere-src-6.12.0.tar.xz'
        Uri = 'https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtbase-everywhere-src-6.12.0.tar.xz'
        SHA256 = 'a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307'
    },
    [pscustomobject]@{
        Name = 'qtsvg-everywhere-src-6.12.0.tar.xz'
        Uri = 'https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtsvg-everywhere-src-6.12.0.tar.xz'
        SHA256 = 'e4ab39534ec97987b1b9b60ef7f4d3253d5912a69f8c713a01753174a4029331'
    },
    [pscustomobject]@{
        Name = 'qtimageformats-everywhere-src-6.12.0.tar.xz'
        Uri = 'https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtimageformats-everywhere-src-6.12.0.tar.xz'
        SHA256 = '0943132b5db8de6b6a7f1d162682173e8763c7ed94e80fd39113292845f67762'
    },
    [pscustomobject]@{
        Name = 'pyside-setup-v6.12.0.tar.gz'
        Uri = 'https://github.com/pyside/pyside-setup/archive/refs/tags/v6.12.0.tar.gz'
        SHA256 = 'dce2a944b34320e51a0ec8100cb983956399b97dec386f0fbe39e1b52571a336'
    },
    [pscustomobject]@{
        Name = 'openssl-3.5.9.tar.gz'
        Uri = 'https://github.com/openssl/openssl/releases/download/openssl-3.5.9/openssl-3.5.9.tar.gz'
        SHA256 = '603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a'
    },
    [pscustomobject]@{
        Name = 'cpython-3.11.18+20261124-x86_64-pc-windows-msvc-install_only.tar.gz'
        Uri = 'https://github.com/astral-sh/python-build-standalone/releases/download/20261124/cpython-3.11.18%2B20261124-x86_64-pc-windows-msvc-install_only.tar.gz'
        SHA256 = '3e4a35e3c238e5090d36bf95c041d9052bc82d6e298cb912ba7f70f6c66cf81a'
    },
    [pscustomobject]@{
        Name = 'Python-3.11.18.tgz'
        Uri = 'https://www.python.org/ftp/python/3.11.18/Python-3.11.18.tgz'
        SHA256 = '5f62711b12470fd435f83f1451c1b1ef4a179aebc715c716874b0967567d814e'
    },
    [pscustomobject]@{
        Name = 'python-build-standalone-48d61fcd7d85d7013b95576f62f779008c316a63.tar.gz'
        Uri = 'https://github.com/astral-sh/python-build-standalone/archive/48d61fcd7d85d7013b95576f62f779008c316a63.tar.gz'
        SHA256 = 'ca344c08ea7717d1b81fc915f4545098e0c60483137dbc47ce3c3588389e53dc'
    }
)

foreach ($Source in $Sources) {
    $Target = Join-Path $SourceDirectory $Source.Name
    if (Test-Path -LiteralPath $Target -PathType Leaf) {
        $ExistingHash = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($ExistingHash -ne $Source.SHA256) {
            throw "Existing source archive has an unexpected hash and was preserved: $Target"
        }
        Write-Host "Verified existing upstream source: $($Source.Name)"
        continue
    }

    $TemporaryPath = "$Target.download"
    try {
        Invoke-WebRequest -Uri $Source.Uri -OutFile $TemporaryPath
        $DownloadedHash = (Get-FileHash -LiteralPath $TemporaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($DownloadedHash -ne $Source.SHA256) {
            throw "Downloaded source hash mismatch for $($Source.Name): $DownloadedHash"
        }
        Move-Item -LiteralPath $TemporaryPath -Destination $Target
        Write-Host "Downloaded and verified upstream source: $($Source.Name)"
    } finally {
        if (Test-Path -LiteralPath $TemporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $TemporaryPath -Force
        }
    }
}
