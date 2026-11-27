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
