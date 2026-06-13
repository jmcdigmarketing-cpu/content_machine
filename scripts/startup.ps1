# Content OS — print startup commands (does not run the pipeline).
# Usage:  .\scripts\startup.ps1
#         .\scripts\startup.ps1 -RunWorker

param(
    [switch]$RunWorker
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host ""
Write-Host "Content OS — project root: $Root" -ForegroundColor Cyan
Write-Host ""

$blocks = @(
    @{
        Title = "Activate venv (optional)"
        Lines = @(
            ".\.venv\Scripts\Activate.ps1"
        )
    }
    @{
        Title = "One-time / after git pull"
        Lines = @(
            "py -m scripts.ops all-setup --channel tapin"
            "alembic upgrade head"
        )
    }
    @{
        Title = "Terminal 1 — interactive pipeline"
        Lines = @(
            "py main.py"
        )
    }
    @{
        Title = "Terminal 2 — upload worker (keep open)"
        Lines = @(
            "py -m jobs.worker --loop 30"
        )
    }
    @{
        Title = "Checks"
        Lines = @(
            "py -m scripts.ops status --channel tapin"
            "py -m youtube.check_setup --channel tapin"
        )
    }
    @{
        Title = "After crash — upload existing MP4 for run N"
        Lines = @(
            "py -m scripts.requeue_upload --channel tapin --run-id 13 --queue"
            "py -m jobs.worker"
        )
    }
)

foreach ($block in $blocks) {
    Write-Host "-- $($block.Title) --" -ForegroundColor Yellow
    foreach ($line in $block.Lines) {
        Write-Host "  $line"
    }
    Write-Host ""
}

Write-Host "Full guide: docs\startup-powershell.md" -ForegroundColor DarkGray
Write-Host ""

if ($RunWorker) {
    Write-Host "Starting worker..." -ForegroundColor Green
    & py -m jobs.worker --loop 30
}
