#!/bin/sh
# 빌드 결과(public/)에 풀리지 않은 숏코드 자리표시가 남았는지 확인한다.
# 소제목에 숏코드를 넣으면 목차에 HAHAHUGOSHORTCODE… 가 그대로 찍힌다.
dir="${1:-public}"
if grep -rIl "HAHAHUGOSHORTCODE" "$dir"; then
  echo "숏코드 자리표시가 남은 파일이 있습니다(위 목록). 소제목이나 front matter에 숏코드를 넣지 않았는지 보세요." >&2
  exit 1
fi
if grep -rn '^#\{1,6\} .*{{[<%]' content/; then
  echo "소제목에 숏코드가 있습니다(위 목록). 목차에서 깨지므로 빼 주세요." >&2
  exit 1
fi
echo "숏코드 자리표시 없음"
python3 scripts/check-rendered.py "$dir"
