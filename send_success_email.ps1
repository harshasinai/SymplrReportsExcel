param(
    [string]$DownloadDir = $(if ($env:DOWNLOAD_DIR) { $env:DOWNLOAD_DIR } else { Join-Path $env:USERPROFILE "Downloads\Symplr" }),
    [string]$SharePointDir = $env:SHAREPOINT_SYNC_DIR,
    [string]$To = $env:SUCCESS_EMAIL_TO,
    [string]$From = $(if ($env:SUCCESS_EMAIL_FROM) { $env:SUCCESS_EMAIL_FROM } else { $env:SMTP_FROM }),
    [string]$SmtpServer = $env:SMTP_SERVER,
    [int]$SmtpPort = $(if ($env:SMTP_PORT) { [int]$env:SMTP_PORT } else { 587 }),
    [string]$SmtpUser = $env:SMTP_USER,
    [string]$SmtpPass = $env:SMTP_PASS,
    [bool]$UseSsl = $(if ($env:SMTP_USE_SSL) { [System.Convert]::ToBoolean($env:SMTP_USE_SSL) } else { $true })
)

$ErrorActionPreference = "Stop"

if (-not $To) {
    Write-Host "Success email skipped. Set SUCCESS_EMAIL_TO to enable notifications."
    exit 0
}

if (-not $From) {
    throw "SUCCESS_EMAIL_FROM or SMTP_FROM is required."
}

if (-not $SmtpServer) {
    throw "SMTP_SERVER is required."
}

$latest = Get-Item -LiteralPath (Join-Path $DownloadDir "Symplr_Import.xlsx") -ErrorAction SilentlyContinue

if (-not $latest) {
    throw "Symplr_Import.xlsx not found in $DownloadDir"
}

$computer = $env:COMPUTERNAME
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$subject = "Symplr hire import completed - $($latest.Name)"
$sharePointText = if ($SharePointDir) { $SharePointDir } else { "Not configured" }

$body = @"
Symplr hire import workbook completed successfully.

Completed: $timestamp
Machine: $computer
Excel file: $($latest.FullName)
Excel size: $([math]::Round($latest.Length / 1KB, 1)) KB
SharePoint sync folder: $sharePointText

This is an automated notification from the scheduled Symplr hire report task.
"@

$message = [System.Net.Mail.MailMessage]::new()
$message.From = $From
foreach ($recipient in $To.Split(";,".ToCharArray(), [System.StringSplitOptions]::RemoveEmptyEntries)) {
    $message.To.Add($recipient.Trim())
}
$message.Subject = $subject
$message.Body = $body

$client = [System.Net.Mail.SmtpClient]::new($SmtpServer, $SmtpPort)
$client.EnableSsl = $UseSsl

if ($SmtpUser -and $SmtpPass) {
    $client.Credentials = [System.Net.NetworkCredential]::new($SmtpUser, $SmtpPass)
} else {
    $client.UseDefaultCredentials = $true
}

try {
    $client.Send($message)
    Write-Host "Success email sent to: $To"
} finally {
    $message.Dispose()
    $client.Dispose()
}
