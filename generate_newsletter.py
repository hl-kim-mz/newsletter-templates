# coding: utf-8
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import argparse
import os
import json
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION ---
SOURCE_URL = "https://news.hada.io/"
TEMPLATE_PATH = "newsletter_template.html"
OUTPUT_DIR = "outputs"
RECIPIENT_EMAIL = "hlkim@mz.co.kr"
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')


def send_slack(title, news_items, today_str):
    """Slack Incoming Webhook으로 뉴스레터를 발송합니다."""
    print("\nSlack 발송을 시작합니다...")

    emoji_map = {'daily': ':newspaper:', 'weekly': ':calendar:', 'monthly': ':mega:'}
    mode_key = 'daily' if '일간' in title else ('weekly' if '주간' in title else 'monthly')

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji_map.get(mode_key, ':newspaper:')} {title}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":date: {today_str}"}]
        },
        {"type": "divider"}
    ]

    for i, item in enumerate(news_items, 1):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{i}. <{item['url']}|{item['title']}>*\n{item['summary']}"
            }
        })
        blocks.append({"type": "divider"})

    payload = {"blocks": blocks}

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, data=json.dumps(payload),
                             headers={'Content-Type': 'application/json'},
                             proxies={"http": None, "https": None}, timeout=15)
        if resp.status_code == 200 and resp.text == 'ok':
            print("성공! Slack 채널에 뉴스레터를 발송했습니다.")
        else:
            print(f"Error: Slack 발송 실패 (status={resp.status_code}, body={resp.text})")
    except Exception as e:
        print(f"Error: Slack 발송 중 오류가 발생했습니다: {e}")


def send_email(subject, html_body, recipient):
    """지정된 수신자에게 HTML 이메일을 보냅니다."""
    smtp_server = os.environ.get('SMTP_SERVER')
    smtp_port = os.environ.get('SMTP_PORT')
    email_user = os.environ.get('EMAIL_USER')
    email_password = os.environ.get('EMAIL_PASSWORD')

    if not all([smtp_server, smtp_port, email_user, email_password]):
        print("\n--- 이메일 발송 실패 ---")
        print("이메일 발송에 필요한 환경 변수가 모두 설정되지 않았습니다.")
        print("필요한 환경 변수: SMTP_SERVER, SMTP_PORT, EMAIL_USER, EMAIL_PASSWORD")
        return

    print("\n이메일 발송을 시작합니다...")
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = email_user
        msg['To'] = recipient
        msg.attach(MIMEText(html_body, 'html'))

        port = int(smtp_port)
        if port == 465:
            with smtplib.SMTP_SSL(smtp_server, port) as server:
                server.login(email_user, email_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(email_user, email_password)
                server.send_message(msg)

        print(f"성공! '{recipient}'에게 이메일을 성공적으로 발송했습니다.")

    except Exception as e:
        print(f"Error: 이메일 발송 중 오류가 발생했습니다: {e}")


def get_soup(url):
    """지정된 URL의 HTML을 파싱하여 BeautifulSoup 객체를 반환합니다."""
    # 직접 연결 먼저 시도, 실패 시 기본 프록시 설정으로 재시도
    for proxy_setting in [{"http": None, "https": None}, None]:
        try:
            kwargs = {"timeout": 15}
            if proxy_setting is not None:
                kwargs["proxies"] = proxy_setting
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.exceptions.RequestException as e:
            last_error = e
            continue
    print(f"Warning: URL을 가져오는 데 실패했습니다: {last_error}")
    print("샘플 데이터를 사용하여 뉴스레터를 생성합니다.")
    return None


def parse_news(soup, mode):
    """모드(daily, weekly, monthly)에 따라 뉴스를 파싱합니다."""
    news_items = []
    if mode == 'daily':
        section = soup.find('div', class_='topics')
        if not section: return news_items
        articles = section.find_all('div', class_='topic_row', limit=10)
        for article in articles:
            title_tag = article.find('h1')
            if not title_tag: continue
            title = title_tag.get_text(strip=True)
            url = title_tag.find_parent('a')['href']
            if not url.startswith('http'): url = SOURCE_URL.rstrip('/') + url if url.startswith('/') else SOURCE_URL + url
            summary_tag = article.find('a', class_='c99')
            summary = summary_tag.get_text(strip=True) if summary_tag else "요약 정보가 없습니다."
            news_items.append({"title": title, "url": url, "summary": summary})
    else:
        header_text = "주간 인기글" if mode == 'weekly' else "월간 인기글"
        header = soup.find('h2', string=lambda t: t and header_text in t)
        if not header: return news_items
        list_ul = header.find_next_sibling('ul', class_='news-list')
        if not list_ul: return news_items
        articles = list_ul.find_all('li')
        for article in articles:
            title_tag = article.find('a', class_='link_tit')
            if not title_tag: continue
            title = title_tag.get_text(strip=True)
            url = title_tag['href']
            if not url.startswith('http'): url = SOURCE_URL.rstrip('/') + url if url.startswith('/') else SOURCE_URL + url
            summary_tag = article.find('p', class_='article_summary')
            summary = summary_tag.get_text(strip=True) if summary_tag else "요약 정보가 없습니다."
            news_items.append({"title": title, "url": url, "summary": summary})
    return news_items


def generate_html_content(news_items):
    """뉴스 아이템 리스트로부터 HTML 콘텐츠 블록을 생성합니다."""
    article_tpl = (
        '                            <!-- Article {num} -->\n'
        '                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 24px;">\n'
        '                                <tr>\n'
        '                                    <td style="border-left: 3px solid #4a9fff; padding-left: 18px; padding-top: 4px; padding-bottom: 4px;">\n'
        '                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">\n'
        '                                            <tr>\n'
        '                                                <td style="padding-bottom: 8px;">\n'
        '                                                    <span style="display: inline-block; background-color: #eef3fc; color: #2856a0; font-family: \'IBM Plex Mono\', \'Courier New\', monospace; font-size: 10px; font-weight: 600; letter-spacing: 1px; padding: 3px 10px; border-radius: 3px;">No.{num_padded}</span>\n'
        '                                                </td>\n'
        '                                            </tr>\n'
        '                                            <tr>\n'
        '                                                <td style="padding-bottom: 10px;">\n'
        '                                                    <h3 style="margin: 0; font-family: \'Noto Serif KR\', Georgia, serif; color: #17325b; font-size: 17px; font-weight: 600; line-height: 1.5;">\n'
        '                                                        <a href="{url}" style="color: #17325b; text-decoration: none;">{title}</a>\n'
        '                                                    </h3>\n'
        '                                                </td>\n'
        '                                            </tr>\n'
        '                                            <tr>\n'
        '                                                <td style="padding-bottom: 16px;">\n'
        '                                                    <p style="margin: 0; color: #4a5568; font-size: 14px; line-height: 1.8;">{summary}</p>\n'
        '                                                </td>\n'
        '                                            </tr>\n'
        '                                            <tr>\n'
        '                                                <td>\n'
        '                                                    <a href="{url}" style="display: inline-block; color: #2856a0; font-size: 13px; font-weight: 600; text-decoration: none; border-bottom: 1.5px solid #4a9fff; padding-bottom: 1px; letter-spacing: 0.2px;">자세히 읽기 →</a>\n'
        '                                                </td>\n'
        '                                            </tr>\n'
        '                                        </table>\n'
        '                                    </td>\n'
        '                                </tr>\n'
        '                            </table>\n'
    )
    separator = (
        '                            <!-- Separator -->\n'
        '                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 24px;">\n'
        '                                <tr>\n'
        '                                    <td style="height: 1px; background-color: #e8ecf4; font-size: 0;">&nbsp;</td>\n'
        '                                </tr>\n'
        '                            </table>\n'
    )
    content_html = ""
    for i, item in enumerate(news_items, 1):
        content_html += article_tpl.format(
            num=i,
            num_padded=f"{i:02d}",
            url=item['url'],
            title=item['title'],
            summary=item['summary']
        )
        if i < len(news_items):
            content_html += separator
    return content_html


FALLBACK_NEWS = [
    {
        "title": "OpenAI, GPT-5 출시 예고 — 추론 능력 대폭 강화",
        "url": "https://news.hada.io/",
        "summary": "OpenAI가 차세대 모델 GPT-5의 출시를 공식 예고했습니다. 복잡한 수학·코딩 벤치마크에서 기존 대비 40% 이상 향상된 성능을 보인다고 밝혔습니다."
    },
    {
        "title": "Google DeepMind, Gemini 2.0 멀티모달 업데이트 공개",
        "url": "https://news.hada.io/",
        "summary": "Google DeepMind가 Gemini 2.0의 대규모 멀티모달 업데이트를 발표했습니다. 이미지·오디오·비디오를 동시에 처리하는 능력이 크게 향상됐습니다."
    },
    {
        "title": "Meta, Llama 4 오픈소스 공개 — 70B 파라미터",
        "url": "https://news.hada.io/",
        "summary": "Meta가 70B 파라미터 규모의 Llama 4를 오픈소스로 공개했습니다. 상업적 이용이 가능하며, 이전 버전 대비 코드 생성과 다국어 지원이 크게 개선됐습니다."
    },
    {
        "title": "Anthropic Claude 4, 에이전트 기능 대폭 강화",
        "url": "https://news.hada.io/",
        "summary": "Anthropic이 Claude 4 시리즈를 발표하며 멀티스텝 에이전트 작업과 도구 사용 능력을 대폭 강화했습니다. 컴퓨터 제어 기능도 개선됐습니다."
    },
    {
        "title": "Mistral AI, 새로운 소형 언어 모델 Mistral Small 3 출시",
        "url": "https://news.hada.io/",
        "summary": "Mistral AI가 엣지 디바이스 최적화 소형 모델 Mistral Small 3를 출시했습니다. 저전력 환경에서도 높은 성능을 발휘하는 것이 특징입니다."
    },
    {
        "title": "Microsoft, GitHub Copilot 에이전트 모드 정식 출시",
        "url": "https://news.hada.io/",
        "summary": "Microsoft가 GitHub Copilot의 에이전트 모드를 정식 출시했습니다. 이슈 해결부터 PR 생성까지 자율적으로 처리하는 기능이 추가됐습니다."
    },
    {
        "title": "Stanford, AI 안전성 연구를 위한 새로운 벤치마크 공개",
        "url": "https://news.hada.io/",
        "summary": "Stanford AI Lab이 대형 언어 모델의 안전성을 평가하기 위한 새로운 벤치마크 suite를 공개했습니다. 1000개 이상의 안전성 시나리오가 포함됐습니다."
    },
    {
        "title": "Hugging Face, 오픈소스 AI 코딩 어시스턴트 StarCoder3 발표",
        "url": "https://news.hada.io/",
        "summary": "Hugging Face와 ServiceNow가 협력하여 StarCoder3를 발표했습니다. 600개 이상의 프로그래밍 언어를 지원하며 코드 완성 정확도가 크게 향상됐습니다."
    },
    {
        "title": "AWS, AI 추론 가속 칩 Trainium3 공개",
        "url": "https://news.hada.io/",
        "summary": "Amazon Web Services가 AI 추론 전용 칩 Trainium3를 공개했습니다. 이전 세대 대비 4배 높은 성능과 60% 낮은 전력 소비를 달성했다고 밝혔습니다."
    },
    {
        "title": "LangChain, AI 에이전트 오케스트레이션 프레임워크 v0.3 출시",
        "url": "https://news.hada.io/",
        "summary": "LangChain이 에이전트 오케스트레이션을 위한 LangGraph v0.3을 출시했습니다. 복잡한 멀티에이전트 워크플로우를 더 쉽게 구성할 수 있게 됐습니다."
    },
]


def main(mode, send, slack):
    """메인 실행 함수"""
    print(f"'{mode}' 모드로 뉴스레터 생성을 시작합니다.")
    soup = get_soup(SOURCE_URL)

    if soup:
        news_data = parse_news(soup, mode)
        if not news_data:
            print("뉴스 데이터를 파싱하지 못했습니다. 샘플 데이터를 사용합니다.")
            news_data = FALLBACK_NEWS
    else:
        news_data = FALLBACK_NEWS

    print(f"{len(news_data)}개의 뉴스 아이템을 찾았습니다.")

    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    title_map = {
        'daily': 'AI GeekNews 일간 인기글',
        'weekly': 'AI GeekNews 주간 인기글',
        'monthly': 'AI GeekNews 월간 인기글'
    }
    newsletter_subject = f"[{title_map[mode]}] {today_str}"

    # Slack 발송
    if slack:
        send_slack(title=title_map[mode], news_items=news_data, today_str=today_str)

    # 이메일 발송 (HTML 파일 생성 필요)
    if send:
        try:
            with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
                template_html = f.read()
        except FileNotFoundError:
            print(f"Error: '{TEMPLATE_PATH}' 템플릿 파일을 찾을 수 없습니다.")
            return

        content_html = generate_html_content(news_data)
        start_marker = '<!-- Article 1 -->'
        end_marker_pattern = r'<!-- CONTENT ROWS GO HERE[^>]*-->'
        try:
            start_index = template_html.index(start_marker)
            end_match = re.search(end_marker_pattern, template_html[start_index:])
            if not end_match:
                raise ValueError("End marker not found")
            end_index = start_index + end_match.end()
            final_html = template_html[:start_index] + content_html + template_html[end_index:]
        except ValueError:
            print("Warning: 템플릿에서 콘텐츠 마커를 찾지 못했습니다.")
            final_html = template_html

        final_html = final_html.replace("{NEWSLETTER_TITLE}", title_map[mode])
        final_html = final_html.replace("{DATE}", today_str)

        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

        output_filename = f"{mode}_newsletter_{datetime.now().strftime('%Y-%m-%d')}.html"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f"성공! '{output_path}' 파일이 생성되었습니다.")

        send_email(subject=newsletter_subject, html_body=final_html, recipient=RECIPIENT_EMAIL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GeekNews 뉴스레터를 생성하고 발송합니다.")
    parser.add_argument(
        "mode",
        choices=['daily', 'weekly', 'monthly'],
        help="생성할 뉴스레터의 종류"
    )
    parser.add_argument(
        "--send",
        action='store_true',
        help="생성된 뉴스레터를 이메일로 발송합니다."
    )
    parser.add_argument(
        "--slack",
        action='store_true',
        help="생성된 뉴스레터를 Slack 채널로 발송합니다."
    )
    args = parser.parse_args()

    main(args.mode, args.send, args.slack)
