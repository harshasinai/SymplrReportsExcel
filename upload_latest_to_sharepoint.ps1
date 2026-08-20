param(
    [string]$DownloadDir = $(if ($env:DOWNLOAD_DIR) { $env:DOWNLOAD_DIR } else { Join-Path $env:USERPROFILE "Downloads\Symplr" }),
    [string]$SyncDir = $env:SHAREPOINT_SYNC_DIR,
    [string]$WebDavDir = $(if ($env:SHAREPOINT_WEBDAV_DIR) { $env:SHAREPOINT_WEBDAV_DIR } else { "\\sinaichicago.sharepoint.com@SSL\DavWWWRoot\sites\OnboardingProject\Shared Documents\SymplrEntries" })
)

$ErrorActionPreference = "Stop"

$latest = Get-Item -LiteralPath (Join-Path $DownloadDir "Symplr_Import.xlsx") -ErrorAction SilentlyContinue

if (-not $latest) {
    throw "Symplr_Import.xlsx not found in $DownloadDir"
}

if ($SyncDir) {
    if (-not (Test-Path -LiteralPath $SyncDir)) {
        throw "SHAREPOINT_SYNC_DIR does not exist: $SyncDir"
    }

    Copy-Item -LiteralPath $latest.FullName -Destination $SyncDir -Force
    Write-Host "Uploaded through OneDrive sync: $(Join-Path $SyncDir $latest.Name)"
    exit 0
}

if (-not (Test-Path -LiteralPath $WebDavDir)) {
    throw "SharePoint WebDAV target is not reachable: $WebDavDir"
}

Copy-Item -LiteralPath $latest.FullName -Destination $WebDavDir -Force
Write-Host "Uploaded through SharePoint WebDAV: $(Join-Path $WebDavDir $latest.Name)"
