#!/usr/bin/env python3
"""지언차기용 Zotero 웹 API 읽기 도구 (읽기 전용, 표준 라이브러리만 사용).

인증: 클라우드 환경의 Network secret이 api.zotero.org 요청에 `Zotero-API-Key`
헤더를 붙여 준다. 로컬에서 쓸 때는 환경 변수 ZOTERO_API_KEY를 둔다.
라이브러리는 ZOTERO_LIBRARY(예: users/123, groups/456)가 없으면 키의 권한으로
정한다: 개인 라이브러리 접근이 있으면 개인 라이브러리, 없고 그룹이 하나뿐이면 그 그룹.

명령:
  whoami                      키의 권한과 고른 라이브러리
  collections                 컬렉션 목록 (키, 이름, 항목 수)
  queue [--collection 이름]   컬렉션의 최상위 항목 + 이미 글이 된 것 표시
  item KEY                    항목 메타데이터(JSON)
  csl KEY                     CSL-JSON 서지
  children KEY                첨부와 노트 목록
  note KEY                    노트 본문(HTML)
  fulltext KEY                첨부 PDF의 색인된 전문 (첨부 키를 준다)
  file KEY OUT                첨부 파일 내려받기 (파일 저장소 호스트가 막혀 있으면 실패)
"""
import json, os, re, sys, urllib.request, urllib.error, urllib.parse, pathlib

API = "https://api.zotero.org"
REPO = pathlib.Path(__file__).resolve().parents[4]


def req(path, params=None, raw=False):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Zotero-API-Version": "3", "User-Agent": "jieon-chagi-reader"}
    key = os.environ.get("ZOTERO_API_KEY")
    if key:
        headers["Zotero-API-Key"] = key
    r = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {url}\n{e.read().decode('utf-8', 'replace')[:500]}")
    return data if raw else json.loads(data.decode("utf-8"))


_LIB = None


def lib():
    global _LIB
    if _LIB:
        return _LIB
    env = os.environ.get("ZOTERO_LIBRARY")
    if env:
        _LIB = "/" + env.strip("/")
        return _LIB
    k = req("/keys/current")
    access = k.get("access", {})
    if access.get("user", {}).get("library"):
        _LIB = f"/users/{k['userID']}"
        return _LIB
    groups = [g for g in access.get("groups", {}) if g != "all"]
    if len(groups) == 1:
        _LIB = f"/groups/{groups[0]}"
        return _LIB
    if "all" in access.get("groups", {}) or len(groups) > 1:
        mine = req(f"/users/{k['userID']}/groups")
        sys.exit("그룹이 여럿입니다. ZOTERO_LIBRARY=groups/<id>로 고르세요:\n" +
                 "\n".join(f"{g['id']}\t{g['data']['name']}" for g in mine))
    sys.exit("이 키로 읽을 수 있는 라이브러리가 없습니다.")


def paged(path, params=None):
    params = dict(params or {})
    params.setdefault("limit", 100)
    start = 0
    while True:
        params["start"] = start
        batch = req(path, params)
        yield from batch
        if len(batch) < params["limit"]:
            return
        start += params["limit"]


def done_keys():
    """content/notes/ 의 front matter에서 source.zotero 값을 모은다."""
    keys = set()
    for p in (REPO / "content" / "notes").glob("**/*.md"):
        m = re.search(r'^\s*zotero:\s*"?([A-Z0-9]{8})"?', p.read_text("utf-8"), re.M)
        if m:
            keys.add(m.group(1))
    return keys


def find_collection(name):
    for c in paged(lib() + "/collections"):
        if c["data"]["name"] == name:
            return c["key"]
    sys.exit(f"컬렉션 '{name}'을 찾지 못했습니다.")


def short(d):
    creators = d.get("creators", [])
    names = [c.get("lastName") or c.get("name", "") for c in creators]
    return f'{", ".join(names) or "?"} ({d.get("date", "?")}) {d.get("title", "")}'


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, *rest = argv
    if cmd == "whoami":
        k = req("/keys/current")
        k.pop("key", None)  # 키 값 자체는 출력하지 않는다
        print(json.dumps(k, ensure_ascii=False, indent=2))
        print("library:", lib())
    elif cmd == "collections":
        for c in paged(lib() + "/collections"):
            print(c["key"], c["data"]["name"], c["meta"].get("numItems", ""), sep="\t")
    elif cmd == "queue":
        name = rest[rest.index("--collection") + 1] if "--collection" in rest else "읽을거리"
        ck = find_collection(name)
        done = done_keys()
        for it in paged(f"{lib()}/collections/{ck}/items/top", {"sort": "dateAdded", "direction": "asc"}):
            mark = "완료" if it["key"] in done else "대기"
            print(mark, it["key"], it["data"]["itemType"], short(it["data"]), sep="\t")
    elif cmd == "item":
        print(json.dumps(req(f"{lib()}/items/{rest[0]}")["data"], ensure_ascii=False, indent=2))
    elif cmd == "csl":
        print(req(f"{lib()}/items/{rest[0]}", {"format": "csljson"}, raw=True).decode("utf-8"))
    elif cmd == "children":
        for c in req(f"{lib()}/items/{rest[0]}/children"):
            d = c["data"]
            print(c["key"], d["itemType"], d.get("contentType", ""), d.get("filename", d.get("title", "")), sep="\t")
    elif cmd == "note":
        print(req(f"{lib()}/items/{rest[0]}")["data"].get("note", ""))
    elif cmd == "fulltext":
        ft = req(f"{lib()}/items/{rest[0]}/fulltext")
        sys.stderr.write(f'pages: {ft.get("indexedPages")}/{ft.get("totalPages")}\n')
        print(ft.get("content", ""))
    elif cmd == "file":
        pathlib.Path(rest[1]).write_bytes(req(f"{lib()}/items/{rest[0]}/file", raw=True))
        print(rest[1])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
