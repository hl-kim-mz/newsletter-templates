# coding: utf-8
"""outputs/의 뉴스레터 아카이브로 outputs/sent_articles.json을 다시 만듭니다.

중복 기록이 손상되거나 오래 갱신되지 않아 필터가 무력화됐을 때 사용합니다.
파일 이름의 날짜(daily_newsletter_YYYY-MM-DD.html)를 그 기사의 발송일로 보고,
보관 기간(generate_newsletter.SENT_RETENTION_DAYS)이 지난 기록은 저장 시 정리됩니다.

    python rebuild_sent_articles.py [--dry-run]
"""
import argparse
import glob
import os
import re

import generate_newsletter as gn

FILENAME_RE = re.compile(r"_newsletter_(\d{4}-\d{2}-\d{2})\.html$")
HREF_RE = re.compile(r'<a href="(https?://[^"]+)"[^>]*style="color: #17325b;')
# 수집 실패 시 발송됐던 샘플 기사는 모두 이 URL을 쓰므로 기록에서 제외합니다.
PLACEHOLDER_URLS = {"https://news.hada.io/", "https://news.hada.io"}


def collect_from_archive():
    """아카이브를 훑어 {URL: 최근 발송일} 맵을 만듭니다."""
    records = {}
    for path in sorted(glob.glob(os.path.join(gn.OUTPUT_DIR, "*_newsletter_*.html"))):
        match = FILENAME_RE.search(os.path.basename(path))
        if not match:
            continue
        sent_on = match.group(1)
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        for url in HREF_RE.findall(html):
            if url in PLACEHOLDER_URLS:
                continue
            key = gn.article_key(url)
            # 같은 기사가 여러 번 나왔다면 가장 최근 발송일을 남깁니다.
            for identifier in {key, url}:
                if records.get(identifier, "") < sent_on:
                    records[identifier] = sent_on
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 결과만 출력합니다.")
    args = parser.parse_args()

    records = collect_from_archive()
    kept = gn.prune_sent_articles(records)
    print(f"아카이브에서 {len(records)}개 식별자 수집 → "
          f"보관 기간({gn.SENT_RETENTION_DAYS}일) 내 {len(kept)}개 유지")

    if args.dry_run:
        for identifier, sent_on in sorted(kept.items(), key=lambda kv: kv[1]):
            print(f"  {sent_on}  {identifier}")
        return 0

    gn.save_sent_articles(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
