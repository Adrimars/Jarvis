# Run this script once as Administrator to register KAIA auto-start via Task Scheduler.
# It will start Docker Compose automatically when you log in to Windows.

$taskName  = "KAIA-AutoStart"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$startScript = Join-Path $scriptDir "start_kaia.bat"

# Write the launcher batch file next to this script
@"
@echo off
cd /d "$projectDir"
docker compose up -d
"@ | Set-Content $startScript -Encoding ASCII

$action  = New-ScheduledTaskAction -Execute $startScript
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -RunLevel  Highest `
    -Force

Write-Host "Task '$taskName' registered. KAIA will start automatically at next login."
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
