# coding: utf-8
"""오늘의 최신 AI 뉴스로 뉴스레터를 생성합니다 (news.hada.io 접근 불가 시 사용)."""
import generate_newsletter as gn
import sys
import os

TODAY_NEWS = [
    {
        "title": "OpenAI, ChatGPT·Codex·개발자 API 통합 조직 재편 — Greg Brockman 전략 총괄",
        "url": "https://thenextweb.com/news/openai-brockman-chatgpt-codex-unified-agentic-platform",
        "summary": "OpenAI가 Google I/O 2026 개막 3일 전, ChatGPT·Codex·개발자 API를 단일 조직으로 통합하고 공동창업자 Greg Brockman이 전제 제품 전략을 총괄하게 됐습니다. 멀티스텝 에이전트 작업을 한 앱에서 처리하는 슈퍼앱 출시를 목표로 합니다."
    },
    {
        "title": "Anthropic, Claude 에이전트 '드리밍(Dreaming)' 기능 공개 — AI가 스스로 실수에서 학습",
        "url": "https://venturebeat.com/technology/anthropic-introduces-dreaming-a-system-that-lets-ai-agents-learn-from-their-own-mistakes",
        "summary": "Anthropic이 Claude Managed Agents에 '드리밍(Dreaming)' 기술을 도입했습니다. 에이전트가 이전 세션을 검토해 패턴을 추출하고 플레이북을 작성해 다음 세션의 성능을 자동으로 개선하는 방식으로, 법률 AI 기업 Harvey는 도입 후 작업 완료율이 약 6배 향상됐습니다."
    },
    {
        "title": "Google, Gemini Intelligence로 Android 재설계 — 앱 간 멀티스텝 AI 에이전트 탑재",
        "url": "https://techcrunch.com/2026/05/12/google-brings-agentic-ai-and-vibe-coded-widgets-to-android/",
        "summary": "Google이 Android Show에서 'Gemini Intelligence'를 공개하며 OS에서 에이전트 플랫폼으로의 전환을 선언했습니다. 음성 명령으로 여러 앱에 걸친 복잡한 작업을 자동 처리하고, AI 생성 위젯 및 Rambler 받아쓰기 정제 기능도 선보였습니다."
    },
    {
        "title": "xAI, SpaceX에 공식 통합 — 'SpaceXAI' 사업부로 재편, Grok 스페이스X 제품화",
        "url": "https://techcrunch.com/2026/02/02/elon-musk-spacex-acquires-xai-data-centers-space-merger/",
        "summary": "Elon Musk가 xAI를 SpaceX 자회사로 공식 흡수하며 'SpaceXAI' 사업부를 출범했습니다. 총 기업가치 1조 2,500억 달러 규모의 이번 합병으로 Grok은 SpaceX 제품이 됐고, xAI의 300MW급 Colossus 1 데이터센터는 Anthropic에 임대됩니다."
    },
    {
        "title": "Google I/O 2026 개막 (5월 19~20일) — Gemini 2.5 Ultra·Android XR 안경 공개 예정",
        "url": "https://io.google/2026/explore/pa-keynote-1",
        "summary": "Google I/O 2026이 5월 19~20일 열립니다. Gemini 2.5 Ultra 멀티모달 업그레이드, Android XR 안경 프리뷰, Chrome AI 에이전트, 멀티모달 미디어 생성 등 개발자 중심의 AI 발표가 집중될 예정입니다."
    },
    {
        "title": "미국 정부, Google·Microsoft·xAI 모델 출시 전 사전 평가 합의 체결",
        "url": "https://www.cnbc.com/2026/05/05/ai-oversight-trump-google-microsoft-xai.html",
        "summary": "미국 상무부 산하 CAISI(AI 표준·혁신 센터)가 Google DeepMind·Microsoft·xAI와 프론티어 AI 모델의 공개 출시 전 정부 사전 평가를 허용하는 협약을 체결했습니다. 사이버보안 위협 평가와 AI 안전성 연구가 핵심 목적입니다."
    },
    {
        "title": "Snap, AI 자동화로 약 1,000명 감원 — '더 작은 팀이 더 많은 성과 가능'",
        "url": "https://www.businessinsider.com/snap-layoffs-ai-2026",
        "summary": "Snap CEO가 AI 기술의 급속한 발전으로 소규모 팀이 동일한 산출물을 낼 수 있게 됐다며 약 1,000명 감원 계획을 발표했습니다. 빅테크 전반에서 AI로 인한 인력 재편이 본격화되는 신호로 해석됩니다."
    },
    {
        "title": "Mozilla Firefox, AI 학습 데이터 옵트아웃 원클릭 프라이버시 도구 출시",
        "url": "https://blog.mozilla.org/en/firefox/firefox-ai-privacy-tool-2026/",
        "summary": "Mozilla가 Firefox에 AI 학습 데이터셋 옵트아웃 및 삭제를 한 번의 클릭으로 처리하는 프라이버시 도구를 추가했습니다. 사용자가 자신의 데이터가 AI 학습에 사용되지 않도록 간편하게 통제할 수 있는 기능입니다."
    },
    {
        "title": "OpenAI Codex, ChatGPT 모바일 앱 정식 탑재 — 주간 활성 사용자 400만 돌파",
        "url": "https://www.eweek.com/news/openai-codex-mobile-chatgpt-app/",
        "summary": "OpenAI가 코딩 에이전트 Codex를 ChatGPT 모바일 앱에 정식 통합해 스마트폰에서도 자율 코딩 작업을 지시할 수 있게 됐습니다. 주간 활성 사용자는 400만 명을 넘어섰습니다."
    },
    {
        "title": "Musk의 xAI, 월가 금융사에 Grok 도입 확대 추진 — 엔터프라이즈 시장 공략 본격화",
        "url": "https://www.japantimes.co.jp/business/2026/05/14/tech/musk-xai-wall-street-grok-chatbot/",
        "summary": "SpaceXAI(구 xAI)가 월가 주요 금융사를 대상으로 Grok 챗봇 도입 확대를 적극 추진 중입니다. 금융 특화 AI 서비스로 포지셔닝하며 기업용 AI 시장에서 OpenAI·Anthropic과의 경쟁을 강화하고 있습니다."
    },
]

def main():
    gn.FALLBACK_NEWS.clear()
    gn.FALLBACK_NEWS.extend(TODAY_NEWS)

    mode = "daily"
    send = True
    slack = True

    print(f"'{mode}' 모드로 뉴스레터 생성을 시작합니다.")
    gn.main(mode, send, slack)

if __name__ == "__main__":
    main()
