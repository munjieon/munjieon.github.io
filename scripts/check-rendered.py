"""빌드 결과(public/)에서 풀리지 않은 마크다운 강조 표시(*)를 찾는다.

CommonMark에서는 닫는 * 바로 앞이 문장부호이고 뒤가 글자(예: 한국어 조사)이면
강조가 닫히지 않아 별표가 그대로 찍힌다. 예: *swim through (a crowd)*나
재구형 표시 *(ipa 숏코드 안), 코드, 스크립트, 스타일 안의 *는 건너뛴다.
"""
import pathlib, re, sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "public")
skip = re.compile(r'<(script|style|pre|code)\b[\s\S]*?</\1>|<span class="?ipa"?>[^<]*</span>', re.I)
bad = 0
for f in sorted(root.rglob("*.html")):
    if "pagefind" in f.parts:
        continue
    s = skip.sub("", f.read_text(encoding="utf-8"))
    m = re.search(r"<body[\s\S]*</body>", s)
    text = re.sub(r"<[^>]+>", "", m.group(0) if m else s)
    for hit in re.finditer(r".{0,25}\*.{0,25}", text):
        print(f"{f.relative_to(root)}: {hit.group(0).strip()}")
        bad += 1
if bad:
    print("본문에 별표(*)가 그대로 남았습니다. 닫는 * 앞이 문장부호이고 뒤에 조사가 붙으면 기울임이 풀리지 않습니다. 문장부호를 기울임 밖으로 빼 주세요(예: *swim through* (*a crowd*)나).", file=sys.stderr)
    sys.exit(1)
print("남은 별표 없음")
