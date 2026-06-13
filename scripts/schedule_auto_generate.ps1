# Register a daily auto-generate task in Windows Task Scheduler.
# Run this script ONCE from an elevated PowerShell prompt.
#
# Usage:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\scripts\schedule_auto_generate.ps1
#
# The task runs daily at 8:00 AM, picks best-bet topic, generates + renders,
# and queues the video for upload. Start the worker separately:
#   py -m jobs.worker --loop 30

$ProjectDir = "C:\Users\jonma\OneDrive\Desktop\content_machine"
$Python     = "py"
$TaskName   = "ContentMachine_AutoGenerate"
$LogFile    = "$ProjectDir\logs\auto_generate.log"

# Create logs dir if missing
New-Item -ItemType Directory -Force -Path "$ProjectDir\logs" | Out-Null

$Action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "-m scripts.auto_generate --channel tapin --sync-analytics" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Daily -At "08:00AM"

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Daily Content Machine auto-generate for TapIn Media" `
    -Force

Write-Host ""
Write-Host "Task '$TaskName' registered — runs daily at 8:00 AM."
Write-Host "To run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To remove:  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host ""
Write-Host "Worker (upload queue processor):"
Write-Host "  py -m jobs.worker --loop 30"
