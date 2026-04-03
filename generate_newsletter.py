# coding: utf-8
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import argparse
import os
import json
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
                             headers={'Content-Type': 'application/json'})
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
    try:
        response = requests.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"Error: URL을 가져오는 데 실패했습니다: {e}")
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
    content_html = ""
    for item in news_items:
        item_html = f'''
        <tr>
            <td style="padding: 20px 0; border-bottom: 1px solid #e9ecef;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                        <td valign="top">
                            <h3 style="margin: 0 0 10px; color: #212529; font-size: 18px; font-weight: 600;">
                                <a href="{item['url']}" style="color: #17325b; text-decoration: none;">{item['title']}</a>
                            </h3>
                            <p style="margin: 0 0 15px; color: #495057; font-size: 15px; line-height: 1.7;">
                                {item['summary']}
                            </p>
                            <a href="{item['url']}" style="background-color: #17325b; color: #ffffff; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-size: 14px; font-weight: bold; display: inline-block;">더 알아보기</a>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        '''
        content_html += item_html
    return content_html


def main(mode, send, slack):
    """메인 실행 함수"""
    print(f"'{mode}' 모드로 뉴스레터 생성을 시작합니다.")
    soup = get_soup(SOURCE_URL)
    if not soup: return

    news_data = parse_news(soup, mode)
    if not news_data:
        print("뉴스 데이터를 파싱하지 못했습니다.")
        return
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
        start_marker, end_marker = '<!-- CONTENT ROWS GO HERE -->', '<!-- End Example Content Block 2 -->'
        try:
            start_index = template_html.index(start_marker)
            end_index_search_area = template_html[start_index:]
            end_index = start_index + end_index_search_area.index('</tr>', end_index_search_area.index(end_marker)) + len('</tr>')
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
