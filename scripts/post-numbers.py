#!/usr/bin/env python3
"""글 번호(front matter `slug`) 도우미.

  python3 scripts/post-numbers.py next notes   # 그 갈래의 다음 번호를 찍는다
  python3 scripts/post-numbers.py check        # 모든 글의 번호가 있고 겹치지 않는지 본다

글 주소는 /<갈래>/<번호>/ 이다(hugo.toml [permalinks]의 :slug).
번호는 갈래마다 1부터 매기고, 한번 준 번호는 바꾸지 않는다.
"""
import re
import sys
from pathlib import Path

SECTIONS = ["essays", "notes", "finds"]
ROOT = Path(__file__).resolve().parent.parent / "content"


def slug_of(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return None
    s = re.search(r'^slug:\s*"?([^"\s#]*)"?', m.group(1), re.M)
    return s.group(1) if s else None


def posts(section):
    return [p for p in sorted((ROOT / section).glob("*.md")) if p.name != "_index.md"]


def check():
    errors = []
    for sec in SECTIONS:
        seen = {}
        for p in posts(sec):
            s = slug_of(p)
            rel = p.relative_to(ROOT.parent)
            if not s or not s.isdigit() or s.startswith("0"):
                errors.append(f"{rel}: slug가 번호가 아님 ({s!r})")
            elif s in seen:
                errors.append(f"{rel}: 번호 {s}가 {seen[s]}와 겹침")
            else:
                seen[s] = rel
    for e in errors:
        print(e)
    if errors:
        sys.exit(1)
    print("글 번호 이상 없음")


def next_no(section):
    nums = [int(s) for p in posts(section) if (s := slug_of(p)) and s.isdigit()]
    print(max(nums, default=0) + 1)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "check":
        check()
    elif len(sys.argv) == 3 and sys.argv[1] == "next" and sys.argv[2] in SECTIONS:
        next_no(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(2)
