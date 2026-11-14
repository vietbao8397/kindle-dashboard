#Requires -Version 5.1
<#
.SYNOPSIS
    Kết nối Google Apps Script Web App URL với Kindle Dashboard trên GitHub và Windows.
#>
param(
    [Parameter(Mandatory = $false)]
    [string]$WebAppUrl
)

$ErrorActionPreference = "Stop"

if (-not $WebAppUrl) {
    $WebAppUrl = Read-Host "Dan Web app URL (https://script.google.com/macros/s/.../exec)"
}
$WebAppUrl = $WebAppUrl.Trim()

$TokenFile = Join-Path $HOME ".kindle-dashboard-token"
$UrlFile = Join-Path $HOME ".kindle-dashboard-url"

if ($WebAppUrl -match '^https://script\.google\.com/macros/s/[^/?]+/exec\?token=(.+)$') {
    $DataUrl = $WebAppUrl
} elseif ($WebAppUrl -match '^https://script\.google\.com/macros/s/[^/?]+/exec$') {
    if (-not (Test-Path $TokenFile)) {
        throw "Không tìm thấy file token tại $TokenFile. Hãy kiểm tra lại TOKEN trong Apps Script."
    }
    $Token = (Get-Content $TokenFile -Raw).Trim()
    if (-not $Token) {
        throw "File token tại $TokenFile bị rỗng."
    }
    $DataUrl = "${WebAppUrl}?token=${Token}"
} else {
    throw "URL chưa đúng định dạng Web app URL (https://script.google.com/macros/s/.../exec)."
}

[System.IO.File]::WriteAllText($UrlFile, $DataUrl, [System.Text.UTF8Encoding]::new($false))
Write-Host "Đã lưu DATA_URL cục bộ vào $UrlFile (ẩn token)." -ForegroundColor Green

Write-Host "Đang kiểm tra kết nối tới Google Apps Script..."
$Resp = Invoke-RestMethod -Uri $DataUrl -Method Get -TimeoutSec 30
if ($Resp.PSObject.Properties.Name -contains "error") {
    throw "Apps Script trả về lỗi: $($Resp.error). Hãy kiểm tra lại TOKEN trong Apps Script đã khớp và deploy New version chưa."
}
if (-not ($Resp.PSObject.Properties.Name -contains "events")) {
    throw "Phản hồi từ Apps Script không có trường 'events'."
}
$EvCount = @($Resp.events).Count
$TaskCount = @($Resp.tasks).Count
Write-Host "Kết nối thành công! Đọc được $EvCount sự kiện và $TaskCount việc cần làm." -ForegroundColor Green

Write-Host "Đang đẩy dữ liệu Antigravity hiện tại lên Apps Script..."
python (Join-Path $PSScriptRoot "antigravity_sync.py")
if ($LASTEXITCODE -ne 0) {
    throw "Đồng bộ Antigravity thất bại (mã thoát $LASTEXITCODE)."
}

Write-Host "Đang cập nhật secret DATA_URL lên GitHub và chạy lại workflow..."
python -c "import pathlib, subprocess; subprocess.run(['gh','secret','set','DATA_URL','-R','vietbao8397/kindle-dashboard'], input=pathlib.Path(r'$UrlFile').read_text(encoding='utf-8-sig').strip(), text=True, check=True)"
if ($LASTEXITCODE -ne 0) {
    throw "Không cập nhật được secret DATA_URL trên GitHub."
}
gh workflow run update.yml -R vietbao8397/kindle-dashboard
if ($LASTEXITCODE -ne 0) {
    throw "Không kích hoạt được workflow update.yml."
}

& (Join-Path $PSScriptRoot "install_task.ps1")
Write-Host "Hoàn tất kết nối Google Calendar + Tasks + Antigravity!" -ForegroundColor Green
