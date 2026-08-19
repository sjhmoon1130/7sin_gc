# 주간 업데이트 자동 감지 & 반영

## 목표
넷마블 포럼에 새 패치노트가 올라오면, `index.html`(7대죄 그랜드크로스 업데이트 대시보드)에
들어갈 새 행을 자동으로 초안 작성하고, 사장 승인을 받은 뒤 실제로 반영 + git 커밋/푸시까지 한다.

보통 목요일에 새 패치노트가 올라온다. 하지만 없을 수도 있으니, "새 글이 있으면 처리, 없으면 조용히 종료"가 기본 동작이다.

## 필요한 도구
- Claude in Chrome (`navigate`, `get_page_text` 등) — 넷마블 포럼은 자바스크립트로 렌더링되기 때문에
  `web_fetch`로는 내용을 못 읽는다. **반드시 브라우저 도구를 써야 한다.**
  이 작업이 예약 실행일 때, 브라우저가 연결되어 있지 않으면 실패한다 — 이 경우 억지로 진행하지 말고
  "브라우저가 안 열려 있어서 이번엔 확인 못 했다"고 사장에게 보고하고 종료한다.
- `tools/add_update_row.py` — 새 행 HTML을 만들고 올바른 위치에 삽입하는 Tool (직접 HTML을 손으로 작성하지 말 것)
- 이 저장소(`index.html`, `.git`)에 대한 파일/bash 접근

## 절차

### 1. 현재 상태 확인
`index.html`의 `<tbody>` 안에서 가장 위에 있는 `data-date` 값을 확인한다 (연도 헤더, "+ 새 업데이트 날짜 추가" 행
다음에 나오는 첫 `<tr data-date="...">`). 이게 "마지막으로 반영된 업데이트 날짜"다.

```
grep -o 'data-date="[0-9]\{8\}"' index.html | head -5
```

### 2. 포럼에서 신규 게시글 확인
1. `https://forum.netmarble.com/7ds/list/34/1` (패치노트 게시판) 접속.
2. 목록 최상단 글의 날짜·제목·URL을 확인한다.
3. 그 날짜가 1번에서 확인한 "마지막 반영 날짜"보다 새로우면 → 신규. 아니면 → "아직 새 업데이트 없음"이라고
   사장에게 짧게 보고하고 종료 (파일 수정 없음).

### 3. 패치노트 본문 읽기
신규 게시글의 view 페이지로 들어가서 본문 전체를 읽는다 (`get_page_text`).

### 4. 영웅 게시판 확인
`https://forum.netmarble.com/7ds/list/139/1` (영웅 게시판)에서 같은 날짜(±1~2일) 근처에 올라온
신규 영웅 소개글이 있는지 확인한다.
- 있으면 그 글의 제목과 URL을 영웅 칩 링크로 쓴다.
- 패치노트 본문에 "LR 진화 개방", "초월 진화 개방" 같은 문구만 있고 별도 소개글이 없으면,
  영웅 칩 링크는 패치노트(34번 게시판) URL 그대로 써도 된다 — 과거 행들도 이런 경우가 섞여 있다.

### 5. 내용 분류
패치노트 본문을 읽고 아래 6개 카테고리로 나눠서, 각각 짧은 명사구로 요약한다 (원문을 그대로 복붙하지 말고
과거 행들처럼 핵심만 간결하게). 카테고리가 없으면 그냥 빈 배열로 둔다.

| 카테고리 | 기준 |
|---|---|
| hero | 신규 영웅 출시, LR/초월/전설 진화 개방 |
| chapter | 메인 스토리 챕터 추가 (예: "묵시록 6챕터") |
| content | 신규 상시 콘텐츠, 시즌제 콘텐츠(히어로 아레나·지하 미궁 등 시즌), 신규 시스템 |
| event | 기간 한정 이벤트, 뽑기, 출석, 미션, 콜라보 이벤트 |
| package | 유상 패키지/상품 추가 |
| bug | 버그 수정, 편의성/시스템 개선 (패치노트의 "개선사항"·"오류 수정" 섹션) |

애매하거나 판단이 안 서는 항목이 있으면 추측하지 말고, 사장에게 원문 링크와 함께 물어본다.

### 6. 초안 생성 (dry-run)
분류한 내용을 스펙 JSON으로 만들어서 `.tmp/spec_draft.json`에 저장하고, dry-run으로 미리보기를 뽑는다.
**절대 `--apply` 없이 먼저 확인한다.**

```
python3 tools/add_update_row.py --spec .tmp/spec_draft.json --file index.html
```

스펙 형식은 `tools/add_update_row.py` 상단 docstring 참고.

### 7. 사장 승인 요청
dry-run 결과를 기술 용어 없이 자연스러운 문장으로 정리해서 보여준다: 날짜, 새 영웅, 챕터, 콘텐츠, 이벤트,
패키지, 버그수정 요약 + 패치노트 원문 링크. "이대로 반영할까요?"라고 묻는다.

### 8. 반영 (파일 수정)
승인받으면 먼저 로컬 파일에 실제로 적용한다:
```
python3 tools/add_update_row.py --spec .tmp/spec_draft.json --file index.html --apply
```

### 9. GitHub에 push — 반드시 아래 방식대로 (일반 `git commit && git push`는 이 샌드박스에서 안 통함)
이 작업 환경(bash 샌드박스)에서 사용자 폴더는 네트워크로 마운트된 폴더라서, `.git` 안의 잠금 파일
(`index.lock`, `HEAD.lock`, `refs/heads/main.lock` 등)을 한 번 만들고 나면 **삭제가 안 되는** 경우가
있다 (`Operation not permitted`). 그래서 평범한 `git add / commit / push`는 잠금 충돌로 실패하기 쉽다.
대신 아래처럼 **로컬 ref(HEAD, refs/heads/main)를 건드리지 않는 방식**으로 커밋을 만들어서 원격에
직접 push한다. 인증 토큰은 `.env`의 `GITHUB_TOKEN`에 저장되어 있다 (다른 곳에 절대 출력하지 말 것,
로그에도 마스킹해서 남길 것).

**아래 전체를 하나의 bash 호출(한 번의 명령 블록)로 실행한다.** 호출을 여러 번 나누면 이전 호출에서
만든 잠금 파일을 다음 호출이 못 지우는 문제가 또 생긴다.

```bash
set -e
cd <저장소 경로>

GITHUB_TOKEN=$(grep '^GITHUB_TOKEN=' .env | cut -d= -f2-)
URL="https://${GITHUB_TOKEN}@github.com/sjhmoon1130/7sin_gc.git"

# 필수: 원격 최신 커밋 객체를 로컬로 먼저 가져온다.
# (이 단계를 빼면 read-tree가 "failed to unpack tree object" 로 실패한다 —
#  로컬 저장소에 원격 최신 커밋의 객체가 없기 때문. 2026-08-19 실행에서 발생)
git fetch --no-tags "$URL" main 2>&1 | sed "s/${GITHUB_TOKEN}/***TOKEN***/g"

REMOTE_TIP=$(git ls-remote "$URL" main | cut -f1)

export GIT_INDEX_FILE=/tmp/gitindex_push_$$
rm -f "$GIT_INDEX_FILE"
git read-tree "$REMOTE_TIP"
git add index.html          # 이번에 수정한 파일만 add (tools/workflows 등 다른 파일을 바꿨으면 같이 add)
NEWTREE=$(git write-tree)
NEWCOMMIT=$(git -c user.name="moonpan" -c user.email="moonpan@moonpanui-MacBookPro.local" \
  commit-tree "$NEWTREE" -p "$REMOTE_TIP" -m "add: N월 N일 업데이트 반영")

git push "$URL" "${NEWCOMMIT}:refs/heads/main" \
  2>&1 | sed "s/${GITHUB_TOKEN}/***TOKEN***/g"
```

- 실행 중 `unable to unlink '.git/objects/.../tmp_obj_...': Operation not permitted` 같은
  warning이 여러 줄 나오는 건 정상이다 (마운트된 폴더 특성). 마지막 push 결과만 확인하면 된다.
- `REMOTE_TIP`을 부모로 써야 한다 (로컬 `main`이 원격보다 뒤처져 있을 수 있어서, 로컬 HEAD를 부모로 쓰면
  push가 "fetch first" 오류로 거부된다).
- push 결과가 `<old>..<new>  <sha> -> main` 형태로 나오면 성공.
- 이 방식은 로컬 `refs/heads/main`을 갱신하지 않는다 (그래서 잠금 문제를 피할 수 있음). 로컬 브랜치가
  원격과 안 맞아도 다음 주 실행에는 지장 없다 — 매번 `REMOTE_TIP`을 원격에서 새로 읽어오기 때문이다.
- 사장님이 직접 터미널에서 이 폴더를 쓸 때 로컬 `main`이 뒤처져 보일 수 있는데, 그건
  `git pull --rebase origin main` 한 번으로 정리된다. 필요하면 이 사실을 보고에 한 줄 덧붙인다.

푸시까지 끝나면 완료 보고 (반영된 날짜, 커밋 sha, 커밋 링크: `https://github.com/sjhmoon1130/7sin_gc/commit/<sha>`).

### 10. 실패 처리
- 브라우저 접근 불가 → 위 "필요한 도구" 항목대로 보고 후 종료.
- `add_update_row.py`가 중복(exit 2)이나 새 연도 그룹 없음(exit 3) 등의 오류를 내면, 손으로 원인을 확인하고
  사장에게 상황을 설명한다. 억지로 파일을 직접 편집해서 우회하지 않는다.
- push가 계속 실패하면 (토큰 만료 등) 억지로 재시도하지 말고, 로컬 반영은 끝났다는 것과 실패 원인을
  사장에게 보고한다.
