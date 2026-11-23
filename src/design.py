"""프리프로덕션 설계: 의상 · 헤어메이크업 · 미술 (작품 전체를 한 번에).

- 의상(Costume plot): 인물마다 룩(머리·분장·옷 묶음)과 그 룩을 입는 장면 목록. 같은 이야기 날(D-숫자)은 같은 옷.
- 헤어메이크업: 룩마다 머리·분장을 따로 적고, 화가 흐르며 바뀌는 것(병색, 상처, 울고 난 얼굴)을 진행표로.
- 미술(Art): 장소마다 세트 드레싱(놓여 있는 물건)과 이야기에 중요한 소품(누가 들고, 어디 있고, 화마다 어떻게 바뀌는지).
대본 문장은 고치지 않는다. 결과는 기존 분장·의상(cast.looks) · 소품(props) · 장소(loc)에 등록되어 콘티·스틸이 그대로 쓴다.
"""
from __future__ import annotations

import re

SYSTEM = """당신은 한국 실사 숏폼 드라마의 프리프로덕션 팀(의상 실장 · 헤어메이크업 실장 · 미술 감독)입니다.
대본 전체의 장면 표를 읽고, AI 영상 제작에서 화면이 흔들리지 않도록 의상·헤어메이크업·미술을 한 번에 설계합니다.

입력: 인물 목록, 장소 목록, 장면 표 한 줄 = '화-장면|D-날|장소 id|말한 인물|지문'
D-날은 이야기 속 날짜입니다. 같은 D-날의 장면은 같은 날입니다.

1. costume (의상 · 헤어메이크업): 인물마다 룩 목록. 룩 = 머리 + 분장 + 옷 한 벌.
   - 각 인물의 첫 룩 이름은 반드시 "기본". 가장 많이 나오는 평소 차림. 캐스팅 그림이 이 차림으로 그려진다.
   - 기본이 아닌 룩은 대본에 근거가 있을 때만: 잠옷·외출복·상복·환자복·앞치마 차림·병색이 짙어진 얼굴·상처 등.
     지문에 옷·머리·얼굴이 적힌 장면, 장소(골프장·호텔·구치소)와 시간(밤 침실)이 근거다.
   - 같은 D-날 같은 인물은 같은 옷. 시간이 밤이고 침실이면 잠옷 룩으로 바꿀 수 있다.
   - 인물당 룩 최대 6개. 이름은 짧은 한국어(예: "외출복", "잠옷", "병색 짙음").
   - costume_ko(옷), hair_ko(머리), makeup_ko(분장), when_ko(언제 입는지 한 줄)
   - desc_en: "Hair: …. Make-up: …. Clothing: …." 세 문장. 옷은 무늬 없는 단색, 차분한 색, 브랜드·로고·글자·장신구 없음, 신발까지.
     얼굴 생김새와 나이는 쓰지 않는다.
   - scenes: 이 룩을 입는 '화-장면' 목록. 기본 룩은 비워 둔다(목록에 없는 장면은 모두 기본).
2. hmu_progress (헤어메이크업 진행표): 화가 흐르며 얼굴·머리가 바뀌는 인물만. who, eps("1-30"), note_ko(그 구간의 얼굴·머리).
   예: 시한부 인물의 병색이 짙어지는 단계. 진행 단계가 룩으로 필요하면 costume 에 룩으로도 넣고 scenes 를 채운다.
3. sets (미술 · 세트 드레싱): 장소 id 마다 그 공간에 늘 놓여 있는 물건. dressing_ko(한 줄), dressing_en(영어 확정형 한 문장, 사람·글자 없음),
   continuity_ko(화가 흐르며 바뀌는 것. 예: 벽 달력의 빨간 줄 수가 하루에 하나씩 는다. 없으면 빈칸).
4. props (미술 · 이야기 소품): 두 장면 이상 나오거나 이야기에 중요한 물건만. 최대 20개.
   name(주인을 붙임: "한복순의 약봉투" / 장소를 붙임: "서재 도장 금고"), kind("hand" 손에 드는 것 / "set" 장소에 놓인 것),
   loc(set 이면 장소 id), eps(나오는 화 "16, 26, 31"), note_ko(한 줄), desc_en(종류·색·재질·크기 영어 확정형 한 문장, 브랜드·로고·글자 없음),
   continuity_ko(누가 가지고 있다가 누구에게 넘어가는지, 상태가 어떻게 바뀌는지. 없으면 빈칸).

규칙: 대본에 없는 사건·물건을 만들지 않는다. 'or', 'slightly', 'maybe', '또는', '정도' 금지. 확정형.
JSON 만 출력:
{"costume":[{"who":"","look":"기본","when_ko":"","costume_ko":"","hair_ko":"","makeup_ko":"","desc_en":"","scenes":[]}],
 "hmu_progress":[{"who":"","eps":"","note_ko":""}],
 "sets":[{"loc":"L01","dressing_ko":"","dressing_en":"","continuity_ko":""}],
 "props":[{"name":"","kind":"hand","loc":"","eps":"","note_ko":"","desc_en":"","continuity_ko":""}]}"""

D_RE = re.compile(r"D\s*-\s*(\d+)")


def story_day(ep: dict) -> str:
    """훅 자막의 [D-88] → 'D-88'. 없으면 ''."""
    m = D_RE.search(ep.get("hook", "") or "")
    return f"D-{m.group(1)}" if m else ""


def design_table(parsed: dict, bible: dict, cast: dict | None = None) -> str:
    from src import bible as bb, cutter
    out = ["[인물]"]
    for c in bible.get("characters", []):
        base = (cast or {}).get(c["name"], {})
        extra = f" · 캐스팅 차림: {base.get('outfit_ko', '')}" if base.get("outfit_ko") else ""
        out.append(f"- {c['name']}: {c.get('role', '')}{extra}")
    out.append("[장소]")
    out += [f"- {l['id']} {l['name']}: {l.get('desc', '')}" for l in bible.get("locations", [])]
    out.append("[장면 표]")
    nm = cutter.name_map(bible)
    day = ""
    for e in parsed["episodes"]:
        day = story_day(e) or day
        for s in e["scenes"]:
            who = ",".join(sorted({nm.get(l["who"].replace(" ", ""), l["who"]) for l in s["lines"] if l["type"] == "dialogue"}))
            loc = (bb.loc_of(bible, e["ep"], s["no"]) or {}).get("id", "")
            acts = " / ".join(l["text"] for l in s["lines"] if l["type"] == "action")
            out.append(f"{e['ep']}-{s['no']}|{day}|{loc}|{s.get('time', '')}|{who}|{acts[:420]}")
    return "\n".join(out)


def build(api_key: str, parsed: dict, bible: dict, cast: dict | None = None, model: str = "") -> dict:
    import anthropic
    import json
    from json_repair import repair_json
    c = anthropic.Anthropic(api_key=api_key)
    # 출력이 길어(장면별 룩 목록) 스트리밍으로 받는다 (긴 응답은 SDK 가 비스트리밍을 막음)
    with c.messages.stream(model=model or "claude-sonnet-4-6", max_tokens=32000, system=SYSTEM,
                           messages=[{"role": "user", "content": f"작품: {parsed.get('title', '')}\n\n" + design_table(parsed, bible, cast)}]) as stream:
        r = stream.get_final_message()
    txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    data = json.loads(repair_json(txt))
    return validate(data if isinstance(data, dict) else {}, parsed, bible)


def validate(d: dict, parsed: dict, bible: dict) -> dict:
    """AI 결과를 그대로 믿지 않는다: 없는 인물·장소·장면을 버리고, 인물마다 '기본' 룩을 보장하고, 장면별 룩 표를 만든다."""
    names = {c["name"] for c in bible.get("characters", [])}
    locs = {l["id"] for l in bible.get("locations", [])}
    scenes = {f"{e['ep']}-{s['no']}" for e in parsed["episodes"] for s in e["scenes"]}
    s_ = lambda x: str(x or "").strip()
    costume = []
    for x in d.get("costume") or []:
        if not isinstance(x, dict) or s_(x.get("who")) not in names or not s_(x.get("look")):
            continue
        sc = [k for k in (x.get("scenes") or []) if s_(k) in scenes] if s_(x.get("look")) != "기본" else []
        costume.append({"who": s_(x["who"]), "look": s_(x["look"]), "when_ko": s_(x.get("when_ko")),
                        "costume_ko": s_(x.get("costume_ko")), "hair_ko": s_(x.get("hair_ko")), "makeup_ko": s_(x.get("makeup_ko")),
                        "desc_en": s_(x.get("desc_en")), "scenes": [s_(k) for k in sc]})
    for n in names:
        if not any(c["who"] == n and c["look"] == "기본" for c in costume):
            costume.insert(0, {"who": n, "look": "기본", "when_ko": "평소", "costume_ko": "", "hair_ko": "", "makeup_ko": "",
                               "desc_en": "", "scenes": []})
    # 장면별 룩: 같은 장면에 한 인물 룩이 둘이면 먼저 적힌 것
    scene_looks: dict = {}
    for c in costume:
        for k in c["scenes"]:
            scene_looks.setdefault(k, {}).setdefault(c["who"], c["look"])
    sets = [{"loc": s_(x.get("loc")), "dressing_ko": s_(x.get("dressing_ko")), "dressing_en": s_(x.get("dressing_en")),
             "continuity_ko": s_(x.get("continuity_ko"))}
            for x in d.get("sets") or [] if isinstance(x, dict) and s_(x.get("loc")) in locs]
    props = []
    for x in d.get("props") or []:
        if isinstance(x, dict) and s_(x.get("name")) and s_(x.get("desc_en")):
            kind = "set" if x.get("kind") == "set" and s_(x.get("loc")) in locs else "hand"
            props.append({"name": s_(x["name"]), "kind": kind, "loc": s_(x.get("loc")) if kind == "set" else "", "eps": s_(x.get("eps")),
                          "note_ko": s_(x.get("note_ko")), "desc_en": s_(x["desc_en"]), "continuity_ko": s_(x.get("continuity_ko"))})
    hmu = [{"who": s_(x.get("who")), "eps": s_(x.get("eps")), "note_ko": s_(x.get("note_ko"))}
           for x in d.get("hmu_progress") or [] if isinstance(x, dict) and s_(x.get("who")) in names]
    return {"costume": costume, "hmu_progress": hmu, "sets": sets, "props": props[:20], "scene_looks": scene_looks}


def look_note(c: dict) -> str:
    return " / ".join(x for x in (c.get("costume_ko"), c.get("hair_ko"), c.get("makeup_ko")) if x)


def register(work: dict, d: dict, frozen: tuple = ("1",), cuts: bool = True) -> list:
    """설계를 작품에 등록한다 (여러 번 불러도 같은 결과).
    - 기본이 아닌 룩 → cast[인물].looks (캐스팅이 된 인물만. 안 된 인물은 캐스팅 뒤 다음 실행에서 등록)
    - 기본 룩 설명 → cast[인물].design_base (캐스팅 화면에 보여 줌)
    - 소품 → props (이미 있으면 그대로), 세트 드레싱 → loc[id].dressing_en
    - 이미 만든 콘티의 컷 → 장면별 룩 반영 (바뀐 컷의 스틸은 지움, 1화는 동결)"""
    notes = []
    cast = work.setdefault("cast", {})
    for c in d.get("costume", []):
        if c["who"] not in cast:
            continue
        if c["look"] == "기본":
            cast[c["who"]]["design_base"] = look_note(c)
            continue
        lk = cast[c["who"]].setdefault("looks", {})
        if c["look"] not in lk and c.get("desc_en"):
            lk[c["look"]] = {"prompt_en": c["desc_en"], "note": look_note(c)}
            notes.append(f"{c['who']} · {c['look']}")
    for p in d.get("props", []):
        if p["name"] not in work.setdefault("props", {}):
            work["props"][p["name"]] = {"prompt_en": p["desc_en"], "note": p["note_ko"], "kind": p["kind"], "loc": p["loc"]}
            notes.append(f"소품 {p['name']}")
    for s in d.get("sets", []):
        li = work.setdefault("loc", {}).setdefault(s["loc"], {})
        if s.get("dressing_en") and li.get("dressing_en") != s["dressing_en"]:
            li["dressing_en"], li["dressing_ko"] = s["dressing_en"], s["dressing_ko"]
            notes.append(f"세트 {s['loc']}")
    if cuts:
        notes += apply_scene_looks(work, d, frozen=frozen)
    return notes


def apply_scene_looks(work: dict, d: dict, eps: list | None = None, frozen: tuple = ("1",)) -> list:
    """콘티 컷에 장면별 룩을 넣는다. 설계에 없는 장면의 인물은 '기본'. 등록되지 않은 룩(캐스팅 전)은 건너뜀."""
    sl = (d or {}).get("scene_looks") or {}
    notes = []
    for ek, rec in (work.get("cuts") or {}).items():
        if ek in frozen or (eps is not None and ek not in eps):
            continue
        for c in rec.get("cuts", []):
            want = sl.get(f"{ek}-{c.get('scene')}", {})
            for ch in c.get("chars", []):
                who = ch.split(":")[0]
                ln = want.get(who, "기본")
                if ln != "기본" and ln not in (work.get("cast", {}).get(who, {}).get("looks") or {}):
                    continue
                cur = (c.get("looks") or {}).get(who, "기본")
                if cur != ln:
                    if ln == "기본":
                        c.get("looks", {}).pop(who, None)
                    else:
                        c.setdefault("looks", {})[who] = ln
                    work.get("stills", {}).get(ek, {}).pop(c.get("id"), None)
                    notes.append(f"EP{ek} {c.get('id')} {who}·{ln}")
    return notes
