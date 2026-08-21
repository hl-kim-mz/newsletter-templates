# coding: utf-8
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import argparse
import os
import json
import re
import smtplib
import sys
import time
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION ---
SOURCE_URL = "https://news.hada.io/"
RSS_URL = "https://news.hada.io/rss/news"
TEMPLATE_PATH = "newsletter_template.html"
OUTPUT_DIR = "outputs"
SENT_ARTICLES_PATH = "outputs/sent_articles.json"
# 중복 기록 보관 기간. 이 기간이 지난 기사는 기록에서 제거되어 다시 발송될 수 있습니다.
SENT_RETENTION_DAYS = 30
MAX_ITEMS = 10
FETCH_RETRIES = 3
# news.hada.io가 봇 User-Agent를 403으로 차단하므로 일반 브라우저와 동일한 헤더를 사용합니다.
REQUEST_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://news.hada.io/",
}
TOPIC_ID_RE = re.compile(r"topic\?id=(\d+)")
RECIPIENT_EMAIL = "hlkim@mz.co.kr"
SLACK_WEBHOOK_URLS = [
    url for url in [
        os.environ.get('SLACK_WEBHOOK_URL', ''),
        os.environ.get('SLACK_WEBHOOK_URL_2', ''),
    ] if url
]


def prune_sent_articles(records):
    """보관 기간이 지난 발송 기록을 제거합니다."""
    cutoff = (datetime.now() - timedelta(days=SENT_RETENTION_DAYS)).strftime('%Y-%m-%d')
    return {key: sent_on for key, sent_on in records.items() if sent_on >= cutoff}


def load_sent_articles():
    """이전에 발송된 기사 식별자와 발송일을 {식별자: 'YYYY-MM-DD'} 형태로 로드합니다."""
    if not os.path.exists(SENT_ARTICLES_PATH):
        return {}
    try:
        with open(SENT_ARTICLES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: sent_articles.json 로드 실패: {e}")
        return {}

    records = dict(data.get('articles', {}))

    # 구 형식({'urls': [...]}) 호환: 발송일을 알 수 없으므로 마지막 갱신일로 간주합니다.
    legacy_urls = data.get('urls', [])
    if legacy_urls:
        legacy_date = (data.get('updated_at') or datetime.now().isoformat())[:10]
        for url in legacy_urls:
            records.setdefault(url, legacy_date)

    pruned = prune_sent_articles(records)
    dropped = len(records) - len(pruned)
    if dropped:
        print(f"발송 기록 {dropped}개가 보관 기간({SENT_RETENTION_DAYS}일)을 지나 정리되었습니다.")
    return pruned


def save_sent_articles(records):
    """발송된 기사 기록을 저장합니다."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    records = prune_sent_articles(records)
    try:
        with open(SENT_ARTICLES_PATH, 'w', encoding='utf-8') as f:
            json.dump({
                'retention_days': SENT_RETENTION_DAYS,
                'updated_at': datetime.now().isoformat(),
                'articles': dict(sorted(records.items())),
            }, f, ensure_ascii=False, indent=2)
        print(f"sent_articles.json 업데이트 완료 (총 {len(records)}개 식별자 기록)")
    except Exception as e:
        print(f"Warning: sent_articles.json 저장 실패: {e}")


def article_key(*urls):
    """기사 식별자를 만듭니다. GeekNews 토픽 ID가 있으면 우선 사용합니다.

    같은 기사라도 HTML 파싱은 원문 URL을, RSS는 news.hada.io 토픽 URL을 주기 때문에
    토픽 ID를 공통 키로 삼아야 수집 경로가 바뀌어도 중복 판정이 유지됩니다.
    """
    for url in urls:
        if not url:
            continue
        match = TOPIC_ID_RE.search(url)
        if match:
            return f"hada:{match.group(1)}"
    return next((url for url in urls if url), '')


def is_already_sent(item, sent_records):
    """식별자와 URL 중 하나라도 기록에 있으면 이미 발송된 기사로 봅니다."""
    return item.get('key') in sent_records or item['url'] in sent_records


def mark_as_sent(sent_records, news_items):
    """발송한 기사를 기록에 추가합니다."""
    today_key = datetime.now().strftime('%Y-%m-%d')
    for item in news_items:
        if item.get('key'):
            sent_records[item['key']] = today_key
        sent_records[item['url']] = today_key
    return sent_records


def send_slack(title, news_items, today_str):
    """Slack Incoming Webhook으로 뉴스레터를 발송합니다."""
    if not SLACK_WEBHOOK_URLS:
        print("Error: SLACK_WEBHOOK_URL 환경 변수가 설정되지 않았습니다.")
        return False

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
    any_ok = False

    for i, webhook_url in enumerate(SLACK_WEBHOOK_URLS, 1):
        try:
            resp = requests.post(webhook_url, data=json.dumps(payload),
                                 headers={'Content-Type': 'application/json'},
                                 timeout=15)
            if resp.status_code == 200 and resp.text == 'ok':
                print(f"성공! Slack 채널 #{i}에 뉴스레터를 발송했습니다.")
                any_ok = True
            else:
                print(f"Error: Slack 채널 #{i} 발송 실패 (status={resp.status_code}, body={resp.text})")
        except Exception as e:
            print(f"Error: Slack 채널 #{i} 발송 중 오류가 발생했습니다: {e}")

    # 채널 하나라도 실제로 발송됐으면 성공으로 본다.
    # (죽은 웹훅 하나 때문에 전체를 실패로 처리하면 중복 기록이 갱신되지 않는다)
    return any_ok


def send_slack_simple(message):
    """단순 텍스트 메시지를 Slack으로 발송합니다."""
    if not SLACK_WEBHOOK_URLS:
        return False
    for webhook_url in SLACK_WEBHOOK_URLS:
        try:
            resp = requests.post(webhook_url, data=json.dumps({"text": message}),
                                 headers={'Content-Type': 'application/json'},
                                 timeout=15)
            if not (resp.status_code == 200 and resp.text == 'ok'):
                return False
        except Exception as e:
            print(f"Error: Slack 알림 발송 중 오류가 발생했습니다: {e}")
            return False
    return True


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
        return False

    print("\n이메일 발송을 시작합니다...")
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = email_user
        msg['To'] = recipient
        msg.attach(MIMEText(html_body, 'html'))

        port = int(smtp_port)
        if port == 465:
            with smtplib.SMTP_SSL(smtp_server, port, timeout=30) as server:
                server.login(email_user, email_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(email_user, email_password)
                server.send_message(msg)

        print(f"성공! '{recipient}'에게 이메일을 성공적으로 발송했습니다.")
        return True

    except Exception as e:
        print(f"Error: 이메일 발송 중 오류가 발생했습니다: {e}")
        return False


def http_get(url, accept=None):
    """URL 본문을 가져옵니다. 실패하면 None을 반환합니다."""
    headers = dict(REQUEST_HEADERS)
    if accept:
        headers["Accept"] = accept

    last_error = None
    for attempt in range(1, FETCH_RETRIES + 1):
        # 첫 번째 시도: 환경변수 프록시 자동 적용(None 전달 안 함)
        # 두 번째 시도: 프록시 명시 비활성화(직접 연결 강제)
        for proxy_setting in [None, {"http": None, "https": None}]:
            try:
                kwargs = {"timeout": 20, "headers": headers}
                if proxy_setting is not None:
                    kwargs["proxies"] = proxy_setting
                response = requests.get(url, **kwargs)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                last_error = e
        if attempt < FETCH_RETRIES:
            wait = 2 ** attempt
            print(f"Warning: '{url}' 요청 실패({last_error}). {wait}초 후 재시도합니다. ({attempt}/{FETCH_RETRIES - 1})")
            time.sleep(wait)

    print(f"Error: '{url}'을(를) 가져오지 못했습니다: {last_error}")
    return None


def get_soup(url):
    """지정된 URL의 HTML을 파싱하여 BeautifulSoup 객체를 반환합니다."""
    html = http_get(url)
    return BeautifulSoup(html, "html.parser") if html else None


def clean_summary(raw_html):
    """RSS description의 HTML 태그를 제거하고 요약 문구로 다듬습니다."""
    text = BeautifulSoup(raw_html or '', "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "요약 정보가 없습니다."
    return text if len(text) <= 300 else text[:297].rstrip() + "..."


def parse_rss(xml_text, limit=MAX_ITEMS):
    """GeekNews RSS 피드에서 뉴스 아이템을 파싱합니다."""
    news_items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"Warning: RSS 파싱에 실패했습니다: {e}")
        return news_items

    for node in root.iter('item'):
        title = (node.findtext('title') or '').strip()
        url = (node.findtext('link') or '').strip()
        if not title or not url:
            continue
        news_items.append({
            "title": title,
            "url": url,
            "summary": clean_summary(node.findtext('description')),
            "key": article_key(url),
        })
        if len(news_items) >= limit:
            break
    return news_items


def fetch_news(mode):
    """뉴스를 수집합니다. (news_items, source) 튜플을 반환하며 실패 시 ([], None)."""
    soup = get_soup(SOURCE_URL)
    if soup:
        news_items = parse_news(soup, mode)
        if news_items:
            return news_items, 'html'
        print("Warning: HTML에서 뉴스 목록을 파싱하지 못했습니다. (사이트 구조 변경 가능성)")

    # 본문 크롤링이 차단(403)되거나 구조가 바뀐 경우 RSS로 대체합니다.
    # RSS는 일간 최신글만 제공하므로 주간/월간 인기글에는 사용할 수 없습니다.
    if mode == 'daily':
        print("RSS 피드로 대체 수집을 시도합니다...")
        xml_text = http_get(RSS_URL, accept="application/rss+xml, application/xml;q=0.9, */*;q=0.8")
        if xml_text:
            news_items = parse_rss(xml_text)
            if news_items:
                return news_items, 'rss'
            print("Warning: RSS에서 뉴스 목록을 파싱하지 못했습니다.")

    return [], None


def parse_news(soup, mode):
    """모드(daily, weekly, monthly)에 따라 뉴스를 파싱합니다."""
    news_items = []
    if mode == 'daily':
        section = soup.find('div', class_='topics')
        if not section: return news_items
        articles = section.find_all('div', class_='topic_row', limit=MAX_ITEMS)
        for article in articles:
            title_tag = article.find(['h1', 'h2'], class_='topic-title-heading')
            if not title_tag:
                title_tag = article.find(['h1', 'h2'])
            if not title_tag: continue
            title = title_tag.get_text(strip=True)
            link_tag = title_tag.find_parent('a')
            if not link_tag or not link_tag.get('href'): continue
            url = link_tag['href']
            if not url.startswith('http'): url = SOURCE_URL.rstrip('/') + url if url.startswith('/') else SOURCE_URL + url
            summary_tag = article.find('a', class_='c99')
            summary = summary_tag.get_text(strip=True) if summary_tag else "요약 정보가 없습니다."
            topic_tag = article.find('a', href=TOPIC_ID_RE)
            topic_url = topic_tag['href'] if topic_tag else None
            news_items.append({"title": title, "url": url, "summary": summary,
                               "key": article_key(topic_url, url)})
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
            topic_tag = article.find('a', href=TOPIC_ID_RE)
            topic_url = topic_tag['href'] if topic_tag else None
            news_items.append({"title": title, "url": url, "summary": summary,
                               "key": article_key(topic_url, url)})
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


def main(mode, send, slack, news_override=None):
    """메인 실행 함수. 정상 종료 시 0, 발송할 것이 없거나 실패하면 0이 아닌 값을 반환합니다."""
    print(f"'{mode}' 모드로 뉴스레터 생성을 시작합니다.")

    if news_override:
        news_data = [dict(item, key=item.get('key') or article_key(item['url'])) for item in news_override]
        source = 'override'
    else:
        news_data, source = fetch_news(mode)

    # 수집 실패 시 예전에는 하드코딩된 샘플 기사를 대신 발송했기 때문에
    # 며칠 동안 똑같은 뉴스가 나갔다. 이제는 조용히 대체하지 않고 중단하고 알린다.
    if not news_data:
        msg = (f"❌ [뉴스레터봇] news.hada.io에서 뉴스를 가져오지 못했습니다(크롤링·RSS 모두 실패). "
               f"발송을 중단합니다. ({datetime.now().strftime('%Y-%m-%d')})")
        print(msg)
        if slack:
            send_slack_simple(msg)
        return 2

    print(f"{len(news_data)}개의 뉴스 아이템을 찾았습니다. (수집 경로: {source})")

    # --- 중복 제거 ---
    sent_records = load_sent_articles()
    new_news_data = [item for item in news_data if not is_already_sent(item, sent_records)]
    skipped = len(news_data) - len(new_news_data)

    if skipped > 0:
        print(f"최근 {SENT_RETENTION_DAYS}일 내 발송된 기사 {skipped}개 제외 → 새 기사 {len(new_news_data)}개")

    if not new_news_data:
        msg = f"ℹ️ [뉴스레터봇] 오늘은 새로운 기사가 없습니다. 발송을 건너뜁니다. ({datetime.now().strftime('%Y-%m-%d')})"
        print(msg)
        if slack:
            send_slack_simple(msg)
        return 0

    news_data = new_news_data
    # --- 중복 제거 끝 ---

    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    title_map = {
        'daily': 'AI GeekNews 일간 인기글',
        'weekly': 'AI GeekNews 주간 인기글',
        'monthly': 'AI GeekNews 월간 인기글'
    }
    newsletter_subject = f"[{title_map[mode]}] {today_str}"
    delivery_succeeded = False

    # Slack 발송
    if slack:
        delivery_succeeded = send_slack(title=title_map[mode], news_items=news_data, today_str=today_str) or delivery_succeeded

    # HTML 파일 생성 및 이메일 발송
    if send:
        try:
            with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
                template_html = f.read()
        except FileNotFoundError:
            print(f"Error: '{TEMPLATE_PATH}' 템플릿 파일을 찾을 수 없습니다.")
            return 3

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

        delivery_succeeded = send_email(subject=newsletter_subject, html_body=final_html, recipient=RECIPIENT_EMAIL) or delivery_succeeded

    # 실제 발송 성공 후에만 sent_articles.json 업데이트
    if delivery_succeeded:
        save_sent_articles(mark_as_sent(sent_records, news_data))
        return 0
    if send or slack:
        print("발송 성공이 확인되지 않아 sent_articles.json을 업데이트하지 않습니다.")
        return 4
    print("생성 전용 실행이므로 sent_articles.json을 업데이트하지 않습니다.")
    return 0


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

    sys.exit(main(args.mode, args.send, args.slack))
