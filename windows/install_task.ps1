#Requires -Version 5.1
<#
.SYNOPSIS
    Cài đặt Windows Task Scheduler đồng bộ Antigravity mỗi 10 phút lên Kindle Dashboard.
#>
param(
    [string]$TaskName = "KindleDashboard-AntigravitySync",
    [int]$IntervalMinutes = 10
)

$ErrorActionPreference = "Stop"

$UrlFile = Join-Path $HOME ".kindle-dashboard-url"
if (-not (Test-Path $UrlFile)) {
    Write-Host "Chưa tìm thấy file cấu hình DATA_URL tại: $UrlFile" -ForegroundColor Yellow
    Write-Host "Hãy tạo file này bằng lệnh PowerShell sau khi triển khai Apps Script (Phần 1):"
    Write-Host '  Set-Content "$HOME\.kindle-dashboard-url" "https://script.google.com/macros/s/YOUR_ID/exec?token=YOUR_TOKEN" -NoNewline' -ForegroundColor Cyan
    exit 1
}

$DataUrl = (Get-Content $UrlFile -Raw).Trim()
if ($DataUrl -notmatch '^https://script\.google\.com/.*\?token=') {
    Write-Host "Nội dung trong $UrlFile chưa đúng định dạng Web App URL (?token=...)." -ForegroundColor Red
    exit 1
}

$ScriptPath = Join-Path $PSScriptRoot "antigravity_sync.py"
if (-not (Test-Path $ScriptPath)) {
    Write-Host "Không tìm thấy $ScriptPath" -ForegroundColor Red
    exit 1
}

$PythonCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
}
if (-not $PythonCmd) {
    Write-Host "Không tìm thấy pythonw.exe hoặc python.exe trong PATH." -ForegroundColor Red
    exit 1
}

$VbsPath = Join-Path $PSScriptRoot "launch_sync_hidden.vbs"
$PythonExeEscaped = $PythonCmd.Source.Replace('"', '""')
$ScriptPathEscaped = $ScriptPath.Replace('"', '""')
$RootEscaped = $PSScriptRoot.Replace('"', '""')

$VbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$RootEscaped"
WshShell.Run """$PythonExeEscaped"" ""$ScriptPathEscaped""", 0, True
"@
[System.IO.File]::WriteAllText($VbsPath, $VbsContent, [System.Text.Encoding]::ASCII)

$Action = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument "//B //NoLogo `"$VbsPath`"" `
    -WorkingDirectory $PSScriptRoot

$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Đồng bộ quota và trạng thái phiên Antigravity lên Kindle Dashboard mỗi $IntervalMinutes phút" `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Host "Đã cài đặt và kích hoạt Task '$TaskName' chạy ngầm mỗi $IntervalMinutes phút." -ForegroundColor Green
Write-Host "Xem log tại: $(Join-Path $PSScriptRoot 'antigravity_sync.log')"
