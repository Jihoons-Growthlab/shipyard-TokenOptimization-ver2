#!/usr/bin/env python3
"""Claude Code 세션 트랜스크립트(.jsonl)에서 입력 프롬프트 / 토큰 사용량 / Skill·MCP 호출을 추출한다.

사용법:
  python extract_usage.py                      # 현재 폴더에 해당하는 프로젝트의 모든 세션
  python extract_usage.py <프로젝트폴더 or .jsonl> [-o report_data.json]

표준 라이브러리만 사용. 결과는 report_data.json 으로 저장되고 콘솔에 요약표를 출력한다.
completion_report_sample.html 에서 이 JSON 을 불러오면 보고서 표가 채워진다.
"""
import argparse
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def project_dir_for(cwd: Path) -> Path:
    # Claude Code 는 경로의 영문/숫자 외 문자를 '-' 로 바꿔 폴더명을 만든다.
    name = re.sub(r"[^0-9A-Za-z]", "-", str(cwd))
    return Path.home() / ".claude" / "projects" / name


def find_files(target):
    if target:
        p = Path(target).expanduser()
        return [p] if p.is_file() else sorted(p.glob("*.jsonl"))
    d = project_dir_for(Path.cwd())
    if not d.exists():
        sys.exit(f"프로젝트 트랜스크립트 폴더를 찾지 못했습니다: {d}\n경로를 인자로 직접 지정하세요.")
    return sorted(d.glob("*.jsonl"))


def user_text(msg):
    """사람이 직접 입력한 프롬프트만 반환 (tool_result·시스템 주입 텍스트 제외)."""
    c = msg.get("content")
    if isinstance(c, str):
        text = c
    elif isinstance(c, list):
        if any(b.get("type") == "tool_result" for b in c if isinstance(b, dict)):
            # 도구 승인 거절 시 사용자가 남긴 코멘트는 사용자 입력이므로 살린다
            for b in c:
                r = b.get("content") if isinstance(b, dict) else None
                r = "\n".join(x.get("text", "") for x in r if isinstance(x, dict)) if isinstance(r, list) else r
                if isinstance(r, str) and "the user said:\n" in r:
                    return r.split("the user said:\n", 1)[1].strip()
            return ""
        text = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    else:
        return ""
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    text = re.sub(r"<(ide_[a-z_]+|command-[a-z-]+|local-command-[a-z-]+)>.*?</\1>", "", text, flags=re.S)
    text = text.strip()
    return "" if text.startswith("[Request interrupted") else text


def parse(files):
    prompts, usage_by_msg, models = [], OrderedDict(), Counter()
    skills, mcps, tools = Counter(), Counter(), Counter()
    first_ts = last_ts = None
    for f in files:
        for line in f.open(encoding="utf-8", errors="replace"):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("isSidechain"):
                pass  # 서브에이전트 토큰도 사용량에 포함하되 프롬프트로는 세지 않는다
            ts = o.get("timestamp")
            if ts:
                first_ts = min(first_ts or ts, ts)
                last_ts = max(last_ts or ts, ts)
            t, msg = o.get("type"), o.get("message") or {}
            if t == "user" and not o.get("isSidechain") and not o.get("isMeta"):
                txt = user_text(msg)
                if txt:
                    prompts.append({"no": len(prompts) + 1, "time": ts, "session": f.stem[:8], "text": txt})
            elif t == "assistant":
                mid = msg.get("id") or o.get("uuid")
                u = msg.get("usage") or {}
                if u and msg.get("model") != "<synthetic>":
                    usage_by_msg[mid] = (u, msg.get("model"), len(prompts), f.stem[:8])  # 같은 id 는 마지막 값으로 덮어씀
                for b in msg.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        n = b.get("name", "")
                        tools[n] += 1
                        if n == "Skill":
                            skills[(b.get("input") or {}).get("skill", "?")] += 1
                        elif n.startswith("mcp__"):
                            mcps[n] += 1
    total = dict.fromkeys(TOKEN_KEYS, 0)
    per_prompt = {}
    per_session = {}
    for u, model, pno, sid in usage_by_msg.values():
        models[model] += 1
        for k in TOKEN_KEYS:
            v = u.get(k) or 0
            total[k] += v
            per_prompt.setdefault(pno, dict.fromkeys(TOKEN_KEYS, 0))[k] += v
            per_session.setdefault(sid, dict.fromkeys(TOKEN_KEYS, 0))[k] += v
    for p in prompts:
        p["tokens"] = per_prompt.get(p["no"], dict.fromkeys(TOKEN_KEYS, 0))
        p["preview"] = re.sub(r"\s+", " ", p["text"])[:80]
    return {
        "period": {"start": first_ts, "end": last_ts},
        "sessions": [{"id": k, **v} for k, v in per_session.items()],
        "models": dict(models),
        "total": {**total, "api_calls": len(usage_by_msg), "sum_all": sum(total.values())},
        "prompts": prompts,
        "skills": dict(skills),
        "mcp": dict(mcps),
        "tools": dict(tools.most_common()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="프로젝트 트랜스크립트 폴더 또는 .jsonl 파일")
    ap.add_argument("-o", "--out", default="report_data.json")
    a = ap.parse_args()
    files = find_files(a.target)
    if not files:
        sys.exit("분석할 .jsonl 파일이 없습니다.")
    data = parse(files)
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    t = data["total"]
    print(f"세션 {len(files)}개 · 프롬프트 {len(data['prompts'])}개 · API 호출 {t['api_calls']}회")
    print(f"모델: {', '.join(f'{m}({n})' for m, n in data['models'].items())}")
    print(f"입력 {t['input_tokens']:,} | 출력 {t['output_tokens']:,} | 캐시생성 {t['cache_creation_input_tokens']:,} | 캐시읽기 {t['cache_read_input_tokens']:,}")
    print(f"Skill: {data['skills'] or '없음'}")
    print(f"MCP  : {data['mcp'] or '없음'}")
    print(f"\n{'#':>3} {'입력':>9} {'출력':>8}  프롬프트")
    for p in data["prompts"]:
        k = p["tokens"]
        print(f"{p['no']:>3} {k['input_tokens'] + k['cache_creation_input_tokens'] + k['cache_read_input_tokens']:>9,} {k['output_tokens']:>8,}  {p['preview']}")
    print(f"\n→ {a.out} 저장 완료")


if __name__ == "__main__":
    main()
