#!/usr/bin/env python3
"""글 원고(.md)를 편집장이 손질하기 쉬운 문서용 마크다운으로 바꾼다.

  to_doc.py FILE            표준 출력으로 내보낸다

Hugo 숏코드처럼 편집장이 고치다 깨뜨리기 쉬운 문법을 걷어 내고 읽기 좋은 꼴로 바꾼다.
되돌리는 스크립트는 없다. 편집장이 고친 내용은 에이전트가 원고(.md)에 손으로 옮긴다
(SKILL.md 4단계). 그래서 이 변환은 읽기 좋게 하는 데만 신경 쓰고, 원고는 브랜치에 그대로 둔다.

표준 라이브러리와 PyYAML만 쓴다.
"""
import pathlib
import re
import sys

import yaml

LANG = re.compile(r'\{\{<\s*lang\s+"?[\w-]+"?\s*>\}\}(.*?)\{\{<\s*/lang\s*>\}\}', re.S)
IPA = re.compile(r'\{\{<\s*ipa\s+"([^"]*)"\s*>\}\}')
RUBY_POS = re.compile(r'\{\{<\s*ruby\s+"([^"]*)"\s+"([^"]*)"\s*>\}\}')
RUBY_KW = re.compile(r'\{\{<\s*ruby\s+base="([^"]*)"\s+text="([^"]*)"[^>]*>\}\}')
GLOSS = re.compile(r'\{\{<\s*gloss([^>]*)>\}\}\n(.*?)\n\{\{<\s*/gloss\s*>\}\}', re.S)
EDITOR = re.compile(r'\{\{<\s*editor\s*>\}\}\n?(.*?)\n?\{\{<\s*/editor\s*>\}\}', re.S)


def split(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit("front matter가 없습니다")
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]


FN_DEF = re.compile(r"^\[\^([^\]]+)\]:[ \t]*(.*)$", re.M)
FN_REF = re.compile(r"\[\^([^\]]+)\]")


def footnotes(text):
    """Claude 문서에는 각주가 없으므로 각주를 본문 속 〔 〕로 풀어 넣는다."""
    defs = {m.group(1): m.group(2).strip() for m in FN_DEF.finditer(text)}
    text = FN_DEF.sub("", text)
    text = FN_REF.sub(lambda m: f"〔{defs.get(m.group(1), m.group(1))}〕", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def body(text):
    text = footnotes(text)
    text = LANG.sub(r"\1", text)
    text = IPA.sub(r"\1", text)
    text = RUBY_POS.sub(r"\1(\2)", text)
    text = RUBY_KW.sub(r"\1(\2)", text)

    def gloss(m):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        head = f"예문 {attrs.get('n', '')}".strip()
        if attrs.get("src"):
            head += f" ({attrs['src']})"
        return f"{head}\n\n```text\n{m.group(2).strip()}\n```"

    text = GLOSS.sub(gloss, text)
    text = EDITOR.sub(lambda m: "[편집장] " + m.group(1).strip().replace("\n\n", "\n\n[편집장] "), text)
    return text.strip()


def finds(fm, rest):
    out = [rest.strip(), ""] if rest.strip() else []
    for i, it in enumerate(fm.get("items") or [], 1):
        title = it.get("title", "")
        if it.get("title_ko"):
            title += f" ({it['title_ko']})"
        out += [f"## {i}. {title}", ""]
        bib = ", ".join(x for x in [" · ".join(it.get("authors") or []), it.get("venue", ""), it.get("published", "")] if x)
        out += [f"{bib}", "", f"링크: {it.get('url', '')}", "", f"읽은 범위: {it.get('based_on', '')}", ""]
        out += ["요약: " + (it.get("summary") or "").strip(), ""]
        out += ["문지언: " + (it.get("note") or "").strip(), ""]
        out += ["편집장: " + (it.get("editor") or "").strip(), ""]
    return "\n".join(out).strip()


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    path = pathlib.Path(sys.argv[1])
    fm, rest = split(path.read_text(encoding="utf-8"))
    head = [f"제목: {fm.get('title', '')}", "", f"한 줄 소개: {fm.get('description', '')}", ""]
    if path.parent.name == "finds":
        print("\n".join(head) + "\n" + finds(fm, rest))
    else:
        print("\n".join(head) + "\n" + body(rest))


if __name__ == "__main__":
    main()
