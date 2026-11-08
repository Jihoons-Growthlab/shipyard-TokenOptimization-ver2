# 빌드 실행 매뉴얼

## 시작 전

1. 이 폴더 전체를 빌드할 위치에 붙여넣는다. 숨김 폴더(`.claude`, `.experiment`)와 `.mcp.json`, `.gitignore`까지 복사됐는지 확인한다.
2. 위치와 폴더 이름을 확정한다. **시작한 뒤에는 옮기거나 이름을 바꾸지 않는다.** 경로가 바뀌면 세션 로그를 찾지 못한다.
3. 상위 폴더에 `CLAUDE.md`가 없는 곳을 고른다. 있으면 함께 로드되어 조건이 달라진다.
4. 필요한 도구: Claude Code, Node, npm, uv, Google Chrome, Unity 6000.5.10f1(WebGL 지원, 라이선스).

```sh
cd <붙여넣은 폴더>
bash .experiment/setup.sh
claude --model claude-opus-5-5 --effort medium --permission-mode auto
```

폴더 신뢰 창이 뜨면 **Yes, I trust this folder**를 고른다. 기본 선택은 No다.

## 진행

첫 입력은 `/build`다. 세션이 끝나면 `다음: /clear 입력 후 /build`가 표시된다. 표의 S6까지 반복한다.

| 세션 | 단계 | 내용 |
| --- | --- | --- |
| S1 | 1~3 | 프로젝트 구성, 스키마, 시드, 인증, 공통 셸 |
| S2 | 4~6 | 호선, 공정 계획, 공정 실적 |
| S3 | 7~8 | 도면, 결재 |
| S4 | 9~10 | 회원관리, 대시보드 |
| S5 | 11 | Unity 뷰어 |
| S6 | 12 | 최종 수용 검증 |

| 상황 | 할 일 |
| --- | --- |
| 다음 세션 시작 | `/clear` 입력 후 `/build` |
| 터미널을 닫은 뒤 다음 세션 | 위 `claude ...` 실행 후 `/build` |
| 세션 도중 끊겨 대화째 이어야 함 | `claude --continue` |
| 세션 도중 끊겼고 대화가 필요 없음 | `claude ...` 실행 후 `/build` (`PROGRESS.md` 지점부터 시작) |

**첫 전환 직후 반드시 확인한다.** S2가 시작되면 아래 값이 2여야 한다. 1이면 `/exit` 후 `claude ...`로 새로 시작하고 `/build`를 입력한다.

```sh
cut -d' ' -f2 .experiment/sessions.log | sort -u | wc -l
```

## 주의

- 다음 세션을 `--continue`나 `/resume`으로 시작하지 않는다. 이전 컨텍스트가 다시 들어가 세션 분리 효과가 사라진다.
- 세션이 끝나면 프롬프트를 더 보내지 말고 바로 `/clear`를 입력한다.
- 모델과 effort를 바꾸지 않는다. 1차와 비교하는 조건이다.
- `specs/`와 `reference/`를 수정하지 않는다. 입력 조건이 달라진다.
- 이 폴더에서는 빌드 외의 작업을 하지 않는다. 다른 세션은 집계에서 제외되며 경고로 표시된다.
- `.experiment/`와 `~/.claude/projects/`의 세션 로그를 지우지 않는다.
- Ponytail 플러그인을 갱신하거나 끄지 않는다. v5.3.3 full로 고정돼 있다.
- 빌드 중에는 커밋하지 않는다. 세션 끝의 `git add -A`만 실행한다.
- Unity 설치나 라이선스 문제로 멈추면 안내대로 조치한다. S5만 막히면 기록을 남기고 S6으로 넘어간다.

## 끝난 뒤

S6의 보고에서 통과, 실패, 미실행 항목을 확인한다. 그다음 **기존 저장소 루트**에서 집계한다. 로그가 정리되기 전에 바로 실행한다.

```sh
python3 experiments/2-ponytail/aggregate_usage.py --target <붙여넣은 폴더> \
  --baseline usage-final.json -o experiments/2-ponytail/result.json
```

경고가 없는지 확인하고, 결과를 `experiments/2-ponytail/README.md`의 구현 비용 표에 적는다. 설치·설정 비용은 구현 비용에 더하지 않는다.
