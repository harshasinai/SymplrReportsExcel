param(
    [string]$TaskName = "Symplr Hire Report Download",
    [string]$ProjectDir = $PSScriptRoot,
    [string]$Time = "06:00"
)

$ErrorActionPreference = "Stop"
$PSDefaultParameterValues["*:ErrorAction"] = "Stop"

$projectPath = (Resolve-Path -LiteralPath $ProjectDir).Path
$runner = Join-Path $projectPath "run_hire_report.bat"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path -LiteralPath $runner)) {
    throw "Cannot find runner: $runner"
}

$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($Time, "HH:mm", $null))
$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$runner`"" `
    -WorkingDirectory $projectPath
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Downloads the Symplr hire report every morning and optionally copies it to a SharePoint synced library." `
    -Force

Write-Host "Scheduled task created/updated: $TaskName"
Write-Host "Schedule: daily at $Time"
Write-Host "Runner: $runner"
