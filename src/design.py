"""프리프로덕션 설계: 의상 팀장(의상·헤어메이크업) + 미술 감독(세트·소품), 작품 전체를 한 번에.

- 의상(Costume plot): 인물마다 룩(머리·분장·옷 묶음)과 그 룩을 입는 장면 목록. 같은 이야기 날(D-숫자)은 같은 옷.
- 헤어메이크업: 룩마다 머리·분장을 따로 적고, 화가 흐르며 바뀌는 것(병색, 상처, 울고 난 얼굴)을 진행표로.
- 미술(Art): 장소마다 세트 드레싱(놓여 있는 물건)과 이야기에 중요한 소품(누가 들고, 어디 있고, 화마다 어떻게 바뀌는지).
대본 문장은 고치지 않는다. 결과는 기존 분장·의상(cast.looks) · 소품(props) · 장소(loc)에 등록되어 콘티·스틸이 그대로 쓴다.
"""
from __future__ import annotations

import re

COSTUME_SYSTEM = """당신은 한국 실사 드라마의 의상 팀장입니다. 헤어메이크업 실장과 함께 대본 전체를 분석하고 의상 플롯을 짭니다.
AI 영상은 장면마다 그림을 새로 그리므로, 당신이 정한 옷이 컷마다 그대로 반복되어야 합니다.

입력: 작품 소개, 인물 목록, 장소 목록, 장면 표.
장면 표 한 줄 = '화-장면|D-날|장소 id|시간|말한 인물|지문(의상·머리·얼굴 단서가 있는 줄 우선)'. 같은 D-날은 같은 날입니다.

의상 팀장이 하는 순서대로 씁니다.

0. season_ko (계절): 대본의 계절 단서(겨울 외투, 꽃 피기 전, 눈, 더위)를 찾아 D-날 구간별 계절을 한 줄로. 옷 두께·겉옷을 이 계절에 맞춘다.

1. analysis (인물 분석): 주요 인물마다
   - status_ko: 계층·재력·직업·집안 안의 위계(누가 위, 누가 아래인지)
   - arc_ko: 이야기 속 처지가 화 구간마다 어떻게 바뀌는지(예: "EP1~30 집안에서 가장 아래 → EP31~70 반격 → EP71~100 주도권")
   - clues: 대본에 적힌 의상·머리·얼굴·몸에 거는 물건 단서. [{"ep":12,"text":"미령이 가방에서 통장을 꺼낸다"}] 대본 문장 그대로 짧게.
     앞치마·가방·구두·슬리퍼·안경·장갑·코트처럼 몸에 거는 물건은 누가, 몇 화부터 쓰는지 빠짐없이.
   - concept_ko: 의상 컨셉 한 문장. palette: 대표 색 3개(한국어). silhouette_ko: 실루엣·소재.
   - contrast_ko: 함께 서는 인물과 화면에서 어떻게 구별되는지(색·실루엣).
   - 처지가 바뀌면 옷도 바뀐다: 색이 짙어지거나 실루엣이 정돈되는 식으로 단계(stage)를 나눈다.
   - 소품성 의상(앞치마, 가방)의 주인이 바뀌거나 처음 등장하면 그 화를 적는다. 권력·역할이 옮겨 가는 표시다.
2. stages (단계): 인물별 의상 단계. who, eps("1-30"), concept_ko(그 단계의 옷 방향).
3. costume (룩 = 체인지): 인물마다 룩 목록. 룩 = 머리 + 메이크업 + 옷 한 벌.
   - 각 인물의 첫 룩 이름은 반드시 "기본"(가장 많이 나오는 평소 차림. 캐스팅 그림이 이 차림). 단계가 바뀌면 "기본"과 다른 룩으로 만든다.
   - 다른 룩은 대본 근거가 있을 때만: 단계 변화, 외출(골프장·호텔·병원), 밤 침실, 장례, 수감, 회상·죽음 장면, 결말의 새 옷.
   - 같은 D-날 같은 인물은 같은 룩(같은 날 갈아입는 장면이 대본에 있을 때만 예외).
   - 인물당 룩 최대 7개. look 이름은 짧은 한국어. days 는 입는 D-날 범위("D-100~D-71").
   - costume_ko(옷: 위·아래·겉옷·신발), hair_ko(머리), makeup_ko(메이크업), when_ko(언제), reason_ko(대본 근거 한 줄)
   - desc_en: "Hair: …. Make-up: …. Clothing: …." 세 문장. 옷은 무늬 없는 단색, 브랜드·로고·글자 없음, 신발까지. 얼굴 생김새·나이는 쓰지 않는다.
     장신구는 대본이 요구할 때만(선글라스, 안경) 하나로 고정.
   - scenes: 이 룩을 입는 '화-장면' 목록. 기본 룩은 비운다(목록에 없는 장면은 모두 기본).
4. hmu_progress (헤어메이크업 진행): 화가 흐르며 얼굴·머리가 바뀌는 인물만. who, eps, note_ko.
   병·시한부 설정이 있어도 대본에서 회복하거나 끝까지 기력이 있으면 병색을 짙게 진행하지 않는다. 대본에 적힌 얼굴(붉은 눈, 터진 입술, 헝클어진 머리)만.
5. continuity (연속성 메모): 장면을 넘나드는 의상 상태. who, item, eps, note_ko.
   예: 앞치마 주머니에 서류를 넣고 단추를 채움, 젖은 소매, 맨발/슬리퍼/구두, 코트를 입고 들어와 단추를 푼다.
6. extras (단역): 대사가 없어도 화면에 나오는 사람(경찰·교도관 등). who, eps, costume_ko, desc_en.

규칙: 대본에 없는 사건을 만들지 않는다. 대본에 단서가 없는 부분은 인물의 처지에 맞게 정하되 확정형으로.
'or', 'slightly', 'maybe', '또는', '정도' 금지.
JSON 만 출력:
{"season_ko":"",
 "analysis":[{"who":"","status_ko":"","arc_ko":"","clues":[{"ep":0,"text":""}],"concept_ko":"","palette":[],"silhouette_ko":"","contrast_ko":""}],
 "stages":[{"who":"","eps":"","concept_ko":""}],
 "costume":[{"who":"","look":"기본","days":"","when_ko":"","reason_ko":"","costume_ko":"","hair_ko":"","makeup_ko":"","desc_en":"","scenes":[]}],
 "hmu_progress":[{"who":"","eps":"","note_ko":""}],
 "continuity":[{"who":"","item":"","eps":"","note_ko":""}],
 "extras":[{"who":"","eps":"","costume_ko":"","desc_en":""}]}"""

ART_SYSTEM = """당신은 한국 실사 숏폼 드라마의 미술 감독입니다. 대본 전체의 장면 표를 읽고 세트 드레싱과 이야기 소품을 정합니다.
AI 영상은 장면마다 그림을 새로 그리므로, 당신이 정한 물건이 컷마다 같은 모양으로 반복되어야 합니다.

1. sets (세트 드레싱): 장소 id 마다 그 공간에 늘 놓여 있는 물건. 그 집의 재력·주인의 성격이 보이게 구체적으로.
   dressing_ko(한 줄), dressing_en(영어 확정형 한 문장, 사람·글자 없음),
   continuity_ko(화가 흐르며 바뀌는 것. 예: 벽 달력의 빨간 줄 수가 하루에 하나씩 는다. 빈 의자. 없으면 빈칸).
2. props (이야기 소품): 두 장면 이상 나오거나 이야기에 중요한 물건만. 최대 20개.
   name(주인을 붙임: "한복순의 약봉투" / 장소를 붙임: "서재 도장 금고"), kind("hand" 손에 드는 것 / "set" 장소에 놓인 것),
   loc(set 이면 장소 id), eps(나오는 화 "16, 26, 31"), note_ko(한 줄), desc_en(종류·색·재질·크기 영어 확정형 한 문장, 브랜드·로고·글자 없음),
   continuity_ko(누가 가지고 있다가 누구에게 넘어가는지, 상태가 어떻게 바뀌는지. 없으면 빈칸).
   옷·앞치마·가방처럼 몸에 거는 것은 의상 팀이 맡으므로 넣지 않는다.

규칙: 대본에 없는 물건을 만들지 않는다. 'or', 'slightly', 'maybe', '또는', '정도' 금지. 확정형.
JSON 만 출력:
{"sets":[{"loc":"L01","dressing_ko":"","dressing_en":"","continuity_ko":""}],
 "props":[{"name":"","kind":"hand","loc":"","eps":"","note_ko":"","desc_en":"","continuity_ko":""}]}"""

D_RE = re.compile(r"D\s*-\s*(\d+)")
# 의상 팀장에게 우선 보여 줄 지문·대사 (옷·머리·얼굴·몸에 거는 물건)
WARDROBE_RE = re.compile(r"앞치마|잠옷|코트|재킷|카디건|셔츠|블라우스|원피스|치마|바지|정장|상복|한복(?!순)|니트|가운|슬리퍼|구두|운동화|"
                         r"선글라스|장갑|목도리|스카프|소매|단추|머리[를가카칼]|쪽진|묶|풀어|화장|립스틱|민낯|안경|반지|목걸이|귀걸이|"
                         r"환자복|수의|제복|넥타이|가방|외출복|갈아입|입고|입은|벗[는고어]|맨발|젖[은어]|눈이 붉|입술이 터|헝클")


def story_day(ep: dict) -> str:
    """훅 자막의 [D-88] → 'D-88'. 없으면 ''."""
    m = D_RE.search(ep.get("hook", "") or "")
    return f"D-{m.group(1)}" if m else ""


def design_table(parsed: dict, bible: dict, cast: dict | None = None, per_scene: int = 420) -> str:
    from src import bible as bb, cutter
    out = []
    if parsed.get("intro"):
        out += ["[작품 소개]"] + list(parsed["intro"])
    out.append("[인물]")
    for c in bible.get("characters", []):
        base = (cast or {}).get(c["name"], {})
        extra = f" · 캐스팅 차림: {base.get('outfit_ko', '')}" if base.get("outfit_ko") else ""
        out.append(f"- {c['name']}: {c.get('role', '')} {c.get('age', '')}{extra}")
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
            acts = [l["text"] for l in s["lines"] if l["type"] == "action"]
            hits = [("" if l["type"] == "action" else f"{l['who']}: ") + l["text"] for l in s["lines"] if WARDROBE_RE.search(l["text"])]
            body = " / ".join(dict.fromkeys(hits + acts))
            out.append(f"{e['ep']}-{s['no']}|{day}|{loc}|{s.get('time', '')}|{who}|{body[:per_scene]}")
    return "\n".join(out)


def _ask_stream(api_key: str, system: str, text: str, model: str, max_tokens: int) -> dict:
    import anthropic
    import json
    from json_repair import repair_json
    c = anthropic.Anthropic(api_key=api_key)
    # 출력이 길어 스트리밍으로 받는다 (긴 응답은 SDK 가 비스트리밍을 막음)
    with c.messages.stream(model=model or "claude-sonnet-4-6", max_tokens=max_tokens, system=system,
                           messages=[{"role": "user", "content": text}]) as stream:
        r = stream.get_final_message()
    txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    data = json.loads(repair_json(txt))
    return data if isinstance(data, dict) else {}


def build(api_key: str, parsed: dict, bible: dict, cast: dict | None = None, model: str = "") -> dict:
    """의상 팀장(의상·헤어메이크업)과 미술 감독(세트·소품)을 따로, 동시에 돌린다."""
    from concurrent.futures import ThreadPoolExecutor
    head = f"작품: {parsed.get('title', '')}\n\n"
    with ThreadPoolExecutor(2) as ex:
        fc = ex.submit(_ask_stream, api_key, COSTUME_SYSTEM, head + design_table(parsed, bible, cast, 520), model, 48000)
        fa = ex.submit(_ask_stream, api_key, ART_SYSTEM, head + design_table(parsed, bible, cast, 360), model, 16000)
        d = {**fc.result(), **{k: v for k, v in fa.result().items() if k in ("sets", "props")}}
    return validate(d, parsed, bible)


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
                        "days": s_(x.get("days")), "reason_ko": s_(x.get("reason_ko")),
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
    analysis = []
    for x in d.get("analysis") or []:
        if isinstance(x, dict) and s_(x.get("who")) in names:
            analysis.append({"who": s_(x["who"]), "status_ko": s_(x.get("status_ko")), "arc_ko": s_(x.get("arc_ko")),
                             "clues": [{"ep": c.get("ep"), "text": s_(c.get("text"))} for c in (x.get("clues") or []) if isinstance(c, dict)][:20],
                             "concept_ko": s_(x.get("concept_ko")), "palette": [s_(p) for p in (x.get("palette") or [])][:4],
                             "silhouette_ko": s_(x.get("silhouette_ko")), "contrast_ko": s_(x.get("contrast_ko"))})
    rows = lambda key, fields: [{f: s_(x.get(f)) for f in fields} for x in d.get(key) or [] if isinstance(x, dict) and s_(x.get(fields[0]))]
    return {"season_ko": s_(d.get("season_ko")), "analysis": analysis, "stages": rows("stages", ("who", "eps", "concept_ko")),
            "costume": costume, "hmu_progress": hmu, "continuity": rows("continuity", ("who", "item", "eps", "note_ko")),
            "extras": rows("extras", ("who", "eps", "costume_ko", "desc_en")),
            "sets": sets, "props": props[:20], "scene_looks": scene_looks}


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
