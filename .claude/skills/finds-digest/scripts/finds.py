#!/usr/bin/env python3
"""찾은 글(content/finds/) 도우미.

  finds.py last              마지막 호의 날짜와 훑은 기간
  finds.py seen              이미 소개한 URL과 DOI 목록 (중복 거르기용)
  finds.py check FILE...     front matter 형식, 필수 칸, 이전 호와의 중복 검사
  finds.py links FILE...     항목 링크를 실제로 열어 본다 (네트워크 필요, CI에서 씀)

표준 라이브러리와 PyYAML만 쓴다.
"""
import datetime as dt
import pathlib
import re
import sys
import urllib.error
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[4]
FINDS = ROOT / "content" / "finds"

KINDS = {"논문", "책", "블로그", "학위논문", "자료", "기타"}
ACCESS = {"오픈 액세스", "무료 공개", "초록 공개", "출판사 소개"}
BASED_ON = {"전문", "초록", "소개문", "목차"}
FIELDS = {"음운", "형태", "통사", "어휘", "의미", "비교 재구", "언어 접촉",
          "문자와 문헌", "방언", "언어 유형", "일반언어학"}
REQUIRED = ["kind", "title", "venue", "url", "access", "based_on", "checked", "fields", "summary"]
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def front_matter(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValueError(f"{path}: front matter가 없습니다")
    return yaml.safe_load(m.group(1)) or {}


def issues(exclude=()):
    ex = {pathlib.Path(p).resolve() for p in exclude}
    for p in sorted(FINDS.glob("*.md")):
        if p.name == "_index.md" or p.resolve() in ex:
            continue
        yield p, front_matter(p)


def norm_url(u):
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = re.sub(r"[?#].*$", "", u)
    return u.rstrip("/")


def norm_doi(d):
    d = (d or "").strip().lower()
    return re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", d)


def seen_keys(exclude=()):
    keys = {}
    for p, fm in issues(exclude):
        for it in fm.get("items") or []:
            if it.get("url"):
                keys["url:" + norm_url(it["url"])] = p.name
            if it.get("doi"):
                keys["doi:" + norm_doi(it["doi"])] = p.name
    return keys


def cmd_last():
    rows = [(str(fm.get("date", ""))[:10], fm.get("window", ""), p.name) for p, fm in issues()]
    if not rows:
        print("아직 호가 없습니다. 첫 호는 최근 4주를 훑습니다.")
        return
    rows.sort()
    d, w, name = rows[-1]
    print(f"마지막 호: {name}  날짜 {d}  훑은 기간 {w}")
    print(f"이번 호는 {d} 다음 날부터 훑습니다.")


def cmd_seen():
    for k, v in sorted(seen_keys().items()):
        print(f"{k}\t{v}")


def cmd_check(files):
    bad = 0
    for f in files:
        errs = []
        fm = front_matter(f)
        items = fm.get("items") or []
        if not items:
            errs.append("items가 비어 있습니다")
        if any(q in str(fm.get("description") or "") for q in "\"'"):
            errs.append("description에 곧은 따옴표가 있습니다. 굽은 따옴표(“ ” ‘ ’)로 씁니다")
        if not fm.get("window"):
            errs.append("window(훑은 기간)가 비어 있습니다")
        prev = seen_keys(exclude=[f])
        here = set()
        for n, it in enumerate(items, 1):
            tag = f"항목 {n} ({(it.get('title') or '')[:30]})"
            for k in REQUIRED:
                if not it.get(k):
                    errs.append(f"{tag}: {k} 칸이 비어 있습니다")
            if it.get("kind") and it["kind"] not in KINDS:
                errs.append(f"{tag}: kind '{it['kind']}'는 {sorted(KINDS)} 가운데 하나여야 합니다")
            if it.get("access") and it["access"] not in ACCESS:
                errs.append(f"{tag}: access '{it['access']}'는 {sorted(ACCESS)} 가운데 하나여야 합니다")
            if it.get("based_on") and it["based_on"] not in BASED_ON:
                errs.append(f"{tag}: based_on '{it['based_on']}'는 {sorted(BASED_ON)} 가운데 하나여야 합니다")
            for fld in it.get("fields") or []:
                if fld not in FIELDS:
                    errs.append(f"{tag}: fields '{fld}'는 {sorted(FIELDS)} 가운데 하나여야 합니다")
            for k in ("published", "checked"):
                v = str(it.get(k) or "")
                if v and not DATE.match(v):
                    errs.append(f"{tag}: {k} '{v}'는 YYYY-MM-DD 꼴이어야 합니다")
            if it.get("url") and not str(it["url"]).startswith("https://"):
                errs.append(f"{tag}: url은 https://로 시작해야 합니다")
            if it.get("title_lang") not in (None, "", "ko") and not it.get("title_ko"):
                errs.append(f"{tag}: 원제가 한국어가 아니면 title_ko를 채웁니다")
            summ = it.get("summary") or ""
            if len(summ) > 600:
                errs.append(f"{tag}: summary가 {len(summ)}자입니다. 600자 안으로 줄입니다")
            for k in ("summary", "note", "title_ko"):
                if any(q in str(it.get(k) or "") for q in "\"'"):
                    errs.append(f"{tag}: {k}에 곧은 따옴표가 있습니다. 굽은 따옴표(“ ” ‘ ’)로 씁니다")
            if summ.count("“") + summ.count('"') > 2:
                errs.append(f"{tag}: summary에 인용이 많습니다. 원문 인용은 한 문장까지만 씁니다")
            for k in ("url", "doi"):
                if it.get(k):
                    key = k + ":" + (norm_url(it[k]) if k == "url" else norm_doi(it[k]))
                    if key in prev:
                        errs.append(f"{tag}: {prev[key]}에서 이미 소개했습니다")
                    if key in here:
                        errs.append(f"{tag}: 이 호 안에서 겹칩니다")
                    here.add(key)
        for e in errs:
            print(f"{f}: {e}")
        if not errs:
            print(f"{f}: 형식 이상 없음 ({len(items)}건)")
        bad += len(errs)
    sys.exit(1 if bad else 0)


def cmd_links(files):
    ua = "Mozilla/5.0 (compatible; jieon-chagi-linkcheck/1.0; +https://munjieon.github.io/)"
    bad = 0
    for f in files:
        for n, it in enumerate(front_matter(f).get("items") or [], 1):
            targets = [it.get("url")] + ([f"https://doi.org/{norm_doi(it['doi'])}"] if it.get("doi") else [])
            for u in filter(None, targets):
                req = urllib.request.Request(u, headers={"User-Agent": ua})
                try:
                    with urllib.request.urlopen(req, timeout=30) as r:
                        print(f"ok   {r.status} 항목 {n} {u}")
                except urllib.error.HTTPError as e:
                    # 403/429는 봇 차단일 때가 많아 경고로만 둔다.
                    level = "warn" if e.code in (401, 403, 429) else "FAIL"
                    bad += level == "FAIL"
                    print(f"{level} {e.code} 항목 {n} {u}")
                except Exception as e:  # noqa: BLE001
                    bad += 1
                    print(f"FAIL ---  항목 {n} {u} ({e})")
    sys.exit(1 if bad else 0)


def main(argv):
    if not argv:
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "last":
        cmd_last()
    elif cmd == "seen":
        cmd_seen()
    elif cmd == "check" and rest:
        cmd_check(rest)
    elif cmd == "links" and rest:
        cmd_links(rest)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
