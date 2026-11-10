"""작품 정리 (바이블): 대본 전체를 읽고 제작용으로 통일한다.

- 인물: 같은 사람의 여러 표기(진혁/오진혁)를 하나로, 화별 단역 이름(남자 → 윤회장) 정리
- 장소: 장면 머리 169개를 제작 세트 목록(L01, L02 …)으로 묶음
- 이슈: 대본 안의 설정 충돌(회사 이름, 집 형태, 이름 오기 등)을 찾아 '수정 제안'으로만 기록
  대본 문장은 고치지 않는다 (원고 수정은 감독님이 직접). 엔진은 제작 단계의 이름·장소만 통일한다.
"""
from __future__ import annotations

import json

DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM = """당신은 한국 숏폼 드라마의 스크립트 슈퍼바이저(연속성 담당)입니다.
AI 영상 제작에 들어가기 전에 대본 전체의 인물·장소를 통일하고 설정 충돌을 찾습니다.

입력: 장면 표 한 줄 = '화-장면|장면 머리|대사한 인물|첫 지문'

할 일
1. characters: 실제 인물 목록. 같은 사람의 다른 표기는 aliases 로 묶음(예: 진혁 → 오진혁, 도균 팀장 → 도균).
2. speaker_map.global: 대본 표기 → 통일 이름. speaker_map.by_ep: '남자'·'팀장'처럼 화마다 다른 사람인 표기를 화 번호별로.
3. locations: 제작 세트 목록. 같은 공간은 하나로(로비 / 1층 로비 / 로비 엘리베이터 앞 → 하나). 회사 이름이 바뀌어도
   주인공이 다니는 같은 회사라면 하나로. 세트 수는 줄이되 시청자가 다른 곳으로 알아야 하는 곳은 나눔.
   같은 인물의 사는 곳(원룸·집·자취방·방)은 대본에서 이사가 나오지 않는 한 하나로. 낮·밤처럼 시간만 다른 같은 곳도 하나로.
   id 는 L01부터, 등장 많은 순. desc 는 확정형 한 문장(공간을 이루는 물건들).
4. scene_loc: 모든 '화-장면' → 장소 id. 빠짐없이.
5. issues: 설정 충돌(회사 이름 변경, 집 형태 혼용, 이름 오기, 직함 충돌, 소속 변경). 문장은 고치지 말고
   eps, type, what(무엇이 어떻게 다른지 구체적으로), suggest(수정 제안 한 가지), applied(엔진에서 이미 묶은 것) 로 기록.
   eps 는 장면 표에서 그 표기가 실제로 나오는 줄의 화 번호만, 쉼표로. what 에 쓴 화 번호와 eps 는 반드시 같아야 함.
   what 에는 대본 표기를 따옴표로 그대로 인용(예: '대성미디어'(EP4) ↔ '대성그룹'(EP1)). 추측으로 만든 충돌은 쓰지 않음.

문장은 확정형. 대본에 없는 사실을 만들지 않음. JSON 만 출력:
{"characters":[{"name":"","aliases":[],"role":"","age":""}],
 "speaker_map":{"global":{},"by_ep":{}},
 "locations":[{"id":"L01","name":"","desc":""}],
 "scene_loc":{"1-1":"L01"},
 "issues":[{"eps":"","type":"","what":"","suggest":"","applied":""}]}"""


def scene_table(parsed: dict) -> str:
    rows = []
    for e in parsed["episodes"]:
        for s in e["scenes"]:
            first = next((l["text"] for l in s["lines"] if l["type"] == "action"), "")[:60]
            who = ",".join(sorted({l["who"] for l in s["lines"] if l["type"] == "dialogue"}))
            rows.append(f"{e['ep']}-{s['no']}|{s['slug']}|{who}|{first}")
    return "\n".join(rows)


def build(api_key: str, parsed: dict, model: str = "") -> dict:
    import anthropic
    from json_repair import repair_json
    c = anthropic.Anthropic(api_key=api_key)
    user = f"작품: {parsed.get('title','')}\n\n" + scene_table(parsed)
    r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=16000, system=SYSTEM,
                          messages=[{"role": "user", "content": user}])
    txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    data = json.loads(repair_json(txt))
    return validate(data, parsed)


def validate(b: dict, parsed: dict) -> dict:
    """빠진 장면·없는 장소 id 를 표시해 둔다 (AI 응답을 그대로 믿지 않음)."""
    b = b if isinstance(b, dict) else {}
    for k, d in (("characters", []), ("locations", []), ("scene_loc", {}), ("issues", []), ("speaker_map", {})):
        b.setdefault(k, d)
    b["speaker_map"].setdefault("global", {})
    b["speaker_map"].setdefault("by_ep", {})
    ids = {l.get("id") for l in b["locations"]}
    keys = [f"{e['ep']}-{s['no']}" for e in parsed["episodes"] for s in e["scenes"]]
    b["_missing_scenes"] = [k for k in keys if k not in b["scene_loc"]]
    b["_bad_loc"] = sorted({v for v in b["scene_loc"].values() if v not in ids})
    b["_issue_warn"] = issue_warnings(b, parsed)
    return b


def _eps_of(text: str) -> set[int]:
    import re
    out = set()
    for a, z in re.findall(r"(\d+)\s*[~\-–]\s*(\d+)", text or ""):
        if int(z) - int(a) < 120:
            out |= set(range(int(a), int(z) + 1))
    out |= {int(x) for x in re.findall(r"\d+", text or "")}
    return out


def issue_warnings(b: dict, parsed: dict) -> list[str]:
    """AI 수정 제안 점검: what 에 적힌 화 번호가 eps 에 없거나, 인용한 표기가 그 화 대본에 없으면 표시."""
    import re
    n_ep = len(parsed["episodes"])
    text_of = {e["ep"]: " ".join([s["slug"] for s in e["scenes"]] + [l["text"] + " " + l.get("who", "") for s in e["scenes"] for l in s["lines"]])
               for e in parsed["episodes"]}
    warns = []
    for i, it in enumerate(b.get("issues", []), start=1):
        eps = {x for x in _eps_of(str(it.get("eps", ""))) if 1 <= x <= n_ep}
        said = {int(x) for x in re.findall(r"(?:EP\s*|에피소드\s*)(\d+)|(\d+)\s*화", str(it.get("what", ""))) for x in x if x}
        said = {x for x in said if 1 <= x <= n_ep}
        if said - eps:
            warns.append(f"{i}번 제안: 설명에 나온 EP {sorted(said - eps)} 가 대상 화 목록({it.get('eps','')})에 없음")
        for q in re.findall(r"'([^']{2,20})'", str(it.get("what", ""))):
            if any(ch in q for ch in ",·—-–()") or " " in q.strip():   # 장면 머리·화자 목록 인용은 대조하지 않음 (오탐 방지)
                continue
            hit = [e for e in (eps or text_of) if q.replace(" ", "") in text_of.get(e, "").replace(" ", "")]
            if not hit:
                warns.append(f"{i}번 제안: 인용한 '{q}' 가 대상 화 대본에서 보이지 않음")
    return warns


def who(b: dict | None, ep: int, name: str) -> str:
    """대본 표기 → 통일 이름 (화별 지정이 먼저)."""
    if not b:
        return name
    sm = b.get("speaker_map", {})
    return sm.get("by_ep", {}).get(str(ep), {}).get(name) or sm.get("global", {}).get(name) or name


def loc_of(b: dict | None, ep: int, sc: int) -> dict | None:
    if not b:
        return None
    lid = b.get("scene_loc", {}).get(f"{ep}-{sc}")
    return next((l for l in b.get("locations", []) if l.get("id") == lid), None)


def stats(b: dict, parsed: dict) -> dict:
    """장소별 장면 수 · 인물별 대사 줄 수 (통일 이름 기준)."""
    loc_n, line_n = {}, {}
    for e in parsed["episodes"]:
        for s in e["scenes"]:
            lid = b.get("scene_loc", {}).get(f"{e['ep']}-{s['no']}")
            if lid:
                loc_n[lid] = loc_n.get(lid, 0) + 1
            for l in s["lines"]:
                if l["type"] == "dialogue":
                    n = who(b, e["ep"], l["who"])
                    line_n[n] = line_n.get(n, 0) + 1
    return {"loc": loc_n, "lines": line_n}


def export_text(b: dict, parsed: dict) -> str:
    """AI 숏폼용 정리본: 통일된 인물·장소 표기 + 바이블 + 수정 제안. Shortform-Engine 에 다시 넣을 수 있는 텍스트."""
    out = [f"{parsed.get('title','')}", "AI 숏폼 제작용 정리본", ""]
    out.append("[인물]")
    for c in b.get("characters", []):
        al = f" (표기: {', '.join(c.get('aliases', []))})" if c.get("aliases") else ""
        out.append(f"- {c['name']}{al}: {c.get('role','')} / {c.get('age','')}")
    out.append("")
    out.append("[장소 세트]")
    for l in b.get("locations", []):
        out.append(f"- {l['id']} {l['name']}: {l.get('desc','')}")
    out.append("")
    out.append("[수정 제안: 감독님 확인 필요]")
    for i in b.get("issues", []):
        out.append(f"- EP {i.get('eps','')} · {i.get('type','')}: {i.get('what','')} → 제안: {i.get('suggest','')}")
    out.append("")
    out.append("[대본]")
    for e in parsed["episodes"]:
        out.append("")
        out.append(f"EP {e['ep']} | {e['emotion']}")
        out.append(f"[자막] \"{e['hook']}\"")
        for s in e["scenes"]:
            loc = loc_of(b, e["ep"], s["no"])
            tag = f"  [세트 {loc['id']} {loc['name']}]" if loc else ""
            out.append("")
            out.append(f"S#{s['no']}. {s['slug']}{tag}")
            for l in s["lines"]:
                if l["type"] == "dialogue":
                    note = f" ({l['note']})" if l["note"] else ""
                    out.append(f"{who(b, e['ep'], l['who'])}{note} {l['text']}")
                else:
                    out.append(l["text"])
    return "\n".join(out)
