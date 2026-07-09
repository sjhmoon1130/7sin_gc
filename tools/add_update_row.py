#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_update_row.py
==================
index.html(7대죄 그랜드크로스 업데이트 대시보드)에 새 주간 업데이트 행(<tr>)을
기존 포맷과 100% 동일한 마크업으로 만들어서 올바른 위치에 삽입하는 Tool.

사용 목적:
- Agent(Claude)는 "무슨 내용을 어떤 카테고리에 넣을지" 판단만 하고,
  실제 HTML 마크업 생성·삽입·정렬은 이 Tool이 담당한다.
  (thinking vs. execution 분리 — claude.md 원칙)

입력: JSON 스펙 (파일 경로 또는 stdin)
{
  "date": "2026.07.09",                       // 필수, YYYY.MM.DD
  "title": "7월 9일 업데이트",                    // 선택, 기본값은 "N월 N일 업데이트"
  "tag_big": "그랜드 시즌 시작",                   // 선택, 특별 배지 텍스트
  "note_url": "https://forum.netmarble.com/7ds/view/34/xxxxx",  // 필수, 날짜 제목 링크
  "big_update": false,                          // 선택, true면 tr.big-update
  "hero": [{"name": "...", "url": "https://forum.netmarble.com/7ds/view/139/xxxxx"}],
  "chapter": ["묵시록 6챕터"],
  "content": ["..."],
  "event": ["..."],
  "package": ["..."],
  "bug": ["..."]
}

hero 항목의 url이 없으면 링크 없는 칩(다른 카테고리처럼)으로 들어간다.
hero/chapter/content/event/package/bug 는 전부 선택 항목(없으면 "—" 빈 칸).

사용법:
  python add_update_row.py --spec spec.json --file index.html            # dry-run (미리보기만, 파일 변경 없음)
  python add_update_row.py --spec spec.json --file index.html --apply    # 실제 파일에 반영

종료 코드:
  0 = 정상 (dry-run 미리보기 성공 또는 apply 성공)
  1 = 입력 오류
  2 = 이미 같은 날짜 행이 존재함 (중복)
  3 = 대상 연도 그룹을 못 찾음 (새 연도는 아직 미지원, 수동 처리 필요)
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

CATEGORY_ORDER = ["hero", "chapter", "content", "event", "package", "bug"]


def esc(text: str) -> str:
    """HTML 텍스트 노드용 이스케이프 (속성 아님)."""
    return html.escape(text, quote=False)


def esc_attr(text: str) -> str:
    return html.escape(text, quote=True)


def build_cell(category: str, items) -> str:
    """카테고리 하나의 <td> 내부(칩들 or empty)를 만든다. <td>...</td> 자체는 감싸지 않는다."""
    if not items:
        return '<span class="empty">—</span>'

    chips = []
    for item in items:
        if category == "hero":
            name = item["name"] if isinstance(item, dict) else item
            url = item.get("url") if isinstance(item, dict) else None
            chip = (
                '<span class="chip chip-hero" '
                'data-tip="클릭: 포럼 이동 | 길게: 필터">' + esc(name) + "</span>"
            )
            if url:
                chip = (
                    '<a href="' + esc_attr(url) + '" target="_blank" class="hero-link">'
                    + chip
                    + "</a>"
                )
            chips.append(chip)
        else:
            chips.append('<span class="chip chip-' + category + '">' + esc(item) + "</span>")

    return '<div class="cell-items">' + "".join(chips) + "</div>"


def build_row_html(spec: dict) -> tuple:
    """spec -> (data_date 'YYYYMMDD', year 'YYYY', tr_html)"""
    date_str = spec["date"].strip()
    m = re.match(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})$", date_str)
    if not m:
        raise ValueError(f"date 형식이 잘못됨 (YYYY.MM.DD 필요): {date_str!r}")
    year, month, day = m.group(1), int(m.group(2)), int(m.group(3))
    data_date = f"{year}{month:02d}{day:02d}"

    title = spec.get("title") or f"{month}월 {day}일 업데이트"
    note_url = spec["note_url"].strip()
    tag_big = spec.get("tag_big")
    big_update = bool(spec.get("big_update"))

    has_categories = [c for c in CATEGORY_ORDER if spec.get(c)]
    data_has = " ".join(has_categories)

    title_html = '<a class="title-link" href="' + esc_attr(note_url) + '" target="_blank">' + esc(title)
    if tag_big:
        title_html += '<span class="tag-big">' + esc(tag_big) + "</span>"
    title_html += "</a>"

    cells = [
        f'<td class="td-date"><span class="month">{year}</span>{month:02d}.{day:02d}</td>',
        f'<td class="td-title">{title_html}</td>',
    ]
    for cat in CATEGORY_ORDER:
        cells.append(f"<td>{build_cell(cat, spec.get(cat))}</td>")

    tr_class = ' class="big-update"' if big_update else ""
    tr_open = f'<tr{tr_class} data-date="{data_date}" data-year="{year}" data-has="{esc_attr(data_has)}">'
    tr_html = tr_open + "\n" + "\n".join(cells) + "\n</tr>"

    return data_date, year, tr_html


ROW_RE = re.compile(
    r'<tr\b(?P<attrs>[^>]*\bdata-date="(?P<date>\d{8})"[^>]*\bdata-year="(?P<year>\d{4})"[^>]*|'
    r'[^>]*\bdata-year="(?P<year2>\d{4})"[^>]*\bdata-date="(?P<date2>\d{8})"[^>]*)>',
)

YEAR_HEADER_RE = re.compile(r'<tr class="year-group" data-year-header="(?P<year>\d{4})">.*?</tr>', re.S)


def find_insert_position(html_text: str, year: str, data_date: str):
    """
    삽입 위치(문자 offset)를 찾는다.
    규칙(연도 그룹 안에서 날짜 내림차순 유지, 기존 웹페이지의 addRow() JS 로직과 동일):
      1. 같은 연도의 기존 행들을 순서대로 보면서, 그 행의 date < 새 date 인 첫 행을 만나면 그 행 바로 앞에 삽입.
      2. 그런 행이 없으면(새 날짜가 그 해 중 가장 최신), 연도 헤더 바로 다음
         (및 그 다음에 오는 '+ 새 업데이트 날짜 추가' 행이 있다면 그 다음)에 삽입.
    """
    year_header_matches = list(YEAR_HEADER_RE.finditer(html_text))
    header_match = next((m for m in year_header_matches if m.group("year") == year), None)
    if not header_match:
        return None  # 새 연도 그룹 — 이 Tool에서는 수동 처리 요망

    search_start = header_match.end()

    # add-row-tr 퀵버튼 행이 헤더 바로 뒤에 있으면 건너뛴다
    add_row_re = re.compile(r'\s*<tr class="add-row-tr">.*?</tr>', re.S)
    m_add = add_row_re.match(html_text, search_start)
    default_insert_pos = search_start
    if m_add:
        default_insert_pos = m_add.end()

    pos = default_insert_pos
    for rm in ROW_RE.finditer(html_text, default_insert_pos):
        row_year = rm.group("year") or rm.group("year2")
        row_date = rm.group("date") or rm.group("date2")
        if row_year != year:
            # 연도 그룹이 끝남 (다음 연도 시작) -> 이 지점 이전에 삽입
            break
        if row_date == data_date:
            return "duplicate"
        if int(row_date) < int(data_date):
            return rm.start()
        pos = rm.start()  # 계속 탐색

    # 같은 연도 안에서 새 날짜보다 오래된 행을 못 찾음 -> 그 연도 마지막 행 다음? 아님 헤더 다음(연도 안이 비었거나 전부 최신)
    # 여기까지 왔다는건 새 날짜가 해당 연도에서 가장 최신이거나, 연도 그룹에 행이 아예 없다는 뜻.
    return default_insert_pos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="새 업데이트 스펙 JSON 파일 경로")
    ap.add_argument("--file", required=True, help="index.html 경로")
    ap.add_argument("--apply", action="store_true", help="실제로 파일에 반영 (기본은 dry-run 미리보기만)")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    html_path = Path(args.file)
    original = html_path.read_text(encoding="utf-8")

    try:
        data_date, year, tr_html = build_row_html(spec)
    except (ValueError, KeyError) as e:
        print(f"[입력 오류] {e}", file=sys.stderr)
        sys.exit(1)

    if re.search(r'data-date="' + data_date + r'"', original):
        print(f"[중복] {data_date} 날짜 행이 이미 index.html에 있습니다. 건너뜁니다.", file=sys.stderr)
        sys.exit(2)

    pos = find_insert_position(original, year, data_date)
    if pos is None:
        print(f"[미지원] {year}년 그룹을 찾을 수 없습니다 (새 연도는 수동으로 연도 헤더부터 만들어야 함).", file=sys.stderr)
        sys.exit(3)
    if pos == "duplicate":
        print(f"[중복] {data_date} 날짜 행이 이미 index.html에 있습니다. 건너뜁니다.", file=sys.stderr)
        sys.exit(2)

    print("=== 삽입될 행 미리보기 ===")
    print(tr_html)
    print("=== 삽입 위치 주변 컨텍스트 ===")
    print(original[max(0, pos - 120):pos] + "  <<< 여기에 삽입 >>>  " + original[pos:pos + 160])

    if not args.apply:
        print("\n(dry-run) 실제 파일은 변경하지 않았습니다. --apply 를 붙이면 반영됩니다.")
        return

    new_content = original[:pos] + tr_html + original[pos:]
    html_path.write_text(new_content, encoding="utf-8")
    print(f"\n[완료] {html_path} 에 {data_date} 행을 추가했습니다.")


if __name__ == "__main__":
    main()
