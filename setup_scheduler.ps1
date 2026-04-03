# setup_scheduler.ps1 - 작업 스케줄러 등록 스크립트
# 실행 방법: PowerShell을 관리자 권한으로 열고 .\setup_scheduler.ps1 실행
# 등록 작업:
#   - GeekNews-Daily  : 매일 오전 9시
#   - GeekNews-Weekly : 매주 금요일 오전 9시
#   - GeekNews-Monthly: 매월 1일 오전 9시

Write-Host "=== GeekNews 뉴스레터 작업 스케줄러 등록 ===" -ForegroundColor Cyan
Write-Host ""

# Python 경로 자동 탐지
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Host "Error: Python을 찾을 수 없습니다. PATH를 확인하세요." -ForegroundColor Red
    exit 1
}
Write-Host "Python 경로: $pythonPath" -ForegroundColor Gray

$scriptPath  = "C:\Users\MZ01-HLKIM\newsletter_templates\generate_newsletter.py"
$workingDir  = "C:\Users\MZ01-HLKIM"
$logDir      = "C:\Users\MZ01-HLKIM\newsletter_templates\outputs\logs"

# 로그 디렉토리 생성
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

# 공통 설정
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# 현재 로그인 사용자로 실행 (환경변수 접근을 위해 사용자 세션 필요)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Highest

function Register-NewsletterTask {
    param(
        [string]$TaskName,
        [string]$Mode,
        [object]$Trigger
    )

    $logFile = "$logDir\${Mode}_%date:~0,4%%date:~5,2%%date:~8,2%.log"
    $action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"$pythonPath`" `"$scriptPath`" $Mode --slack > `"$logFile`" 2>&1" `
        -WorkingDirectory $workingDir

    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath "\GeekNews\" `
        -Action $action `
        -Trigger $Trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "GeekNews 뉴스레터 자동 발송 - $Mode" `
        -Force | Out-Null

    Write-Host "✅ '$TaskName' 등록 완료" -ForegroundColor Green
}

# 1. 일간: 매일 오전 9시
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At "09:00"
Register-NewsletterTask -TaskName "GeekNews-Daily" -Mode "daily" -Trigger $dailyTrigger

# 2. 주간: 매주 금요일 오전 9시
$weeklyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "09:00"
Register-NewsletterTask -TaskName "GeekNews-Weekly" -Mode "weekly" -Trigger $weeklyTrigger

# 3. 월간: 매월 1일 오전 9시
$monthlyTrigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1 -At "09:00"
Register-NewsletterTask -TaskName "GeekNews-Monthly" -Mode "monthly" -Trigger $monthlyTrigger

Write-Host ""
Write-Host "=== 등록 완료 ===" -ForegroundColor Cyan
Write-Host "작업 스케줄러 확인: Win+R → taskschd.msc → 작업 스케줄러 라이브러리 → GeekNews"
Write-Host ""
Write-Host "수동 테스트 방법 (터미널에서):" -ForegroundColor Yellow
Write-Host "  python `"$scriptPath`" daily --send"
Write-Host "  python `"$scriptPath`" weekly --send"
Write-Host "  python `"$scriptPath`" monthly --send"
