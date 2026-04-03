# AI GeekNews 뉴스레터 자동화

[GeekNews(news.hada.io)](https://news.hada.io/)의 AI/기술 인기글을 자동 수집해 이메일·Slack으로 발송하는 뉴스레터 자동화 시스템입니다.

**지원 주기**: 일간 / 주간 / 월간
**발송 채널**: 이메일(SMTP) + Slack Webhook
**자동화**: GitHub Actions (매일 오전 9시 KST) + Windows 작업 스케줄러

---

## 디렉토리 구조

```
newsletter-templates/
├── .github/
│   └── workflows/
│       └── newsletter.yml        # GitHub Actions 자동 실행 워크플로우
├── generate_newsletter.py        # 뉴스 크롤링 → HTML 생성 → 발송 스크립트
├── newsletter_template.html      # 반응형 HTML 이메일 템플릿
├── newsletter_daily.md           # 일간 뉴스레터 콘텐츠 구조 예시
├── newsletter_weekly.md          # 주간 뉴스레터 콘텐츠 구조 예시
├── newsletter_monthly.md         # 월간 뉴스레터 콘텐츠 구조 예시
├── megazone_newsletter_img.png   # 이메일 헤더 로고 이미지
├── setup_env.ps1                 # SMTP 환경변수 초기 설정 (Windows)
├── setup_scheduler.ps1           # Windows 작업 스케줄러 등록
└── outputs/
    ├── *.html                    # 날짜별 생성된 뉴스레터 아카이브
    └── logs/                     # 실행 로그 (git 미추적)
```

---

## 빠른 시작

### 1단계: 환경 변수 설정

`setup_env.ps1`을 PowerShell(관리자)에서 실행하거나 직접 설정합니다.

```powershell
.\setup_env.ps1
```

| 환경 변수 | 설명 | 예시 |
|-----------|------|------|
| `SMTP_SERVER` | SMTP 서버 주소 | `smtp.office365.com` |
| `SMTP_PORT` | SMTP 포트 | `587` |
| `EMAIL_USER` | 발신자 이메일 | `yourname@company.com` |
| `EMAIL_PASSWORD` | 이메일 비밀번호 또는 앱 비밀번호 | — |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL | `https://hooks.slack.com/...` |

### 2단계: 로컬 실행

```bash
# 일간 뉴스레터 생성 (HTML 파일만)
python generate_newsletter.py daily

# 일간 뉴스레터 생성 + 이메일 발송
python generate_newsletter.py daily --send

# 일간 뉴스레터 생성 + Slack 발송
python generate_newsletter.py daily --slack

# 주간/월간
python generate_newsletter.py weekly --send --slack
python generate_newsletter.py monthly --send --slack
```

생성된 HTML은 `outputs/` 디렉토리에 날짜별로 저장됩니다.

### 3단계: Windows 자동 스케줄 등록 (선택)

```powershell
# 관리자 권한으로 실행
.\setup_scheduler.ps1
```

등록되는 작업:
- `GeekNews-Daily` — 매일 오전 9시
- `GeekNews-Weekly` — 매주 금요일 오전 9시
- `GeekNews-Monthly` — 매월 1일 오전 9시

---

## GitHub Actions 자동화

`.github/workflows/newsletter.yml`에 설정된 워크플로우는 **평일(월~금) 오전 9시 KST**에 자동 실행됩니다.

### Secrets 설정 필요

GitHub 레포지토리 → Settings → Secrets and variables → Actions에서 아래 값을 등록하세요.

| Secret 이름 | 설명 |
|-------------|------|
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |

> 이메일 발송이 필요한 경우 `EMAIL_USER`, `EMAIL_PASSWORD`도 추가하고 워크플로우에서 `--send` 옵션을 활성화하세요.

### 실행 결과

- Slack으로 뉴스레터 발송
- 생성된 HTML이 `outputs/` 디렉토리에 커밋·푸시되어 아카이빙됩니다.

---

## 의존성

```bash
pip install requests beautifulsoup4
```

Python 3.8 이상 권장.

---

## 템플릿 커스터마이징

| 파일 | 수정 목적 |
|------|-----------|
| `newsletter_template.html` | 이메일 디자인 (색상, 레이아웃, 로고) |
| `newsletter_daily/weekly/monthly.md` | 콘텐츠 섹션 구조 및 예시 참고 |
| `megazone_newsletter_img.png` | 헤더 로고 이미지 교체 |

헤더 그라디언트 색상 변경 시 `newsletter_template.html`의 `#17325b → #4a9fff` 값을 수정하세요.

---

## 데이터 소스

- **출처**: [GeekNews (news.hada.io)](https://news.hada.io/) — AI/개발/기술 분야 한국어 큐레이션 뉴스
- **크롤링 정책**: robots.txt 및 서비스 이용약관을 준수하세요.
