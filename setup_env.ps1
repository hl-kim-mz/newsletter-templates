# setup_env.ps1 - SMTP 환경변수 설정 스크립트
# 관리자 권한 없이 현재 사용자 범위로 설정합니다.
# 실행 방법: PowerShell에서 .\setup_env.ps1

Write-Host "=== GeekNews 뉴스레터 SMTP 환경변수 설정 ===" -ForegroundColor Cyan

# -------------------------------------------------------
# 설정값 - 회사 Exchange/O365 환경에 맞게 수정하세요
# -------------------------------------------------------
# Office 365 사용 시: smtp.office365.com / 587
# 사내 Exchange 사용 시: IT팀에 SMTP 서버 주소 확인 필요
$smtpServer   = "smtp.office365.com"
$smtpPort     = "587"
$emailUser    = "hlkim@mz.co.kr"
$emailPassword = Read-Host "이메일 계정 비밀번호를 입력하세요 (입력 내용 숨김)" -AsSecureString

# SecureString → 일반 문자열 변환 (환경변수 저장용)
$plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($emailPassword)
)

# 사용자 범위 환경변수로 저장 (재부팅 후에도 유지)
[System.Environment]::SetEnvironmentVariable("SMTP_SERVER",   $smtpServer,   "User")
[System.Environment]::SetEnvironmentVariable("SMTP_PORT",     $smtpPort,     "User")
[System.Environment]::SetEnvironmentVariable("EMAIL_USER",    $emailUser,    "User")
[System.Environment]::SetEnvironmentVariable("EMAIL_PASSWORD",$plainPassword,"User")

Write-Host ""
Write-Host "환경변수 설정 완료:" -ForegroundColor Green
Write-Host "  SMTP_SERVER   = $smtpServer"
Write-Host "  SMTP_PORT     = $smtpPort"
Write-Host "  EMAIL_USER    = $emailUser"
Write-Host "  EMAIL_PASSWORD= (설정됨)"
Write-Host ""
Write-Host "주의: 설정된 환경변수는 새 터미널/프로세스에서 적용됩니다." -ForegroundColor Yellow
Write-Host "      사내 Exchange 서버 사용 시 IT팀에 SMTP 주소를 확인하세요." -ForegroundColor Yellow
