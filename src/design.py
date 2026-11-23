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
3. change_signals (룩이 바뀌는 신호): 장면마다 아래 신호를 찾는다.
   시간 경과(날짜·시간대, 다음 날) / 장소 성격(집·외출·병원·장례식장·구치소) / 행동(잠, 씻기, 싸움, 비 맞음, 울음) /
   관계 변화(복수 결심, 신분 노출, 주도권 이동) / 신분·위장(계급 이동, 변장) / 신체 흔적(상처·멍·피·땀) / 소품 착용(반지·안경·장갑·앞치마)
   scene('화-장면'), who, signal(위 일곱 가지 중 하나), verdict, evidence(대본 문장 짧게), note_ko.
   verdict: "확정" = 대본에 옷·머리·얼굴이 직접 쓰여 있음 / "추론" = 장소·행동으로 바뀌어야 맞음 / "유지" = 바꾸면 연속성이 깨짐.
4. 항목 (옷·머리·메이크업·몸에 지니는 소품은 따로 정하고, 룩에서 조합한다):
   - wardrobe: id "W-01"…, who, desc_ko(위·아래·겉옷·신발), desc_en(영어 확정형: 색·소재·길이·핏·신발, 무늬·로고·글자 없음),
     ban_en(그 옷이 다른 문화권·시대로 읽히지 않게 금지 요소. 예: "No hanbok, no lace, no frills, no sportswear").
   - hair: id "H-01"…, who, desc_ko, desc_en(길이·묶음 위치·앞머리 + 결 문장 필수: 예 "lying flat against the scalp, dry matte strands, no volume"
     — 젖은 장면만 wet). ban_en(예: "No hair accessories").
   - makeup: id "M-01"…, who, desc_ko, desc_en(기본 / 화장함 / 울고 난 뒤 / 상처: 위치와 색 단계까지).
   - worn: id "P-01"…, who, desc_ko, desc_en. 몸에 지니는 소품(안경·선글라스·장갑·앞치마·반지). 대본이 요구할 때만.
5. looks (룩 = 인물 + W + H + M + P): id "LK-01"…, who, name(짧은 한국어. 각 인물의 첫 룩은 반드시 "기본" = 가장 많이 나오는 평소 차림),
   wardrobe, hair, makeup(위 id), worn([id]), days("D-100~D-71"), when_ko, reason_ko(대본 근거),
   verdict("확정"/"추론": 그 룩을 만든 신호의 판정), hook(true = 반전 화의 첫 3초에 변화가 보여야 하는 룩: 변신·상처·머리 자르기·결말의 새 옷),
   filter("보통"/"높음": 씻기·침대·노출이면 높음), filter_alt_ko(높음일 때 대체 표현: 뒷모습, 어깨 위 프레임, 김, 손 접촉),
   scenes(이 룩의 '화-장면' 목록. 기본 룩은 비움 = 목록에 없는 장면은 모두 기본).
   - 같은 D-날 같은 인물은 같은 룩(같은 날 갈아입는 장면이 대본에 있을 때만 예외).
   - 세로 9:16 화면은 상반신이 차지한다: 변화의 우선순위는 헤어·메이크업 > 상의 > 하의. 같은 옷에 머리만 푸는 변화도 별도 룩.
   - 주연 한 명의 룩은 10화마다 3개 이하가 되게 묶는다(룩마다 기준 그림과 검수가 늘어남).
6. hmu_progress (헤어메이크업 진행): 화가 흐르며 얼굴·머리가 바뀌는 인물만. who, eps, note_ko.
   병·시한부 설정이 있어도 대본에서 회복하거나 끝까지 기력이 있으면 병색을 짙게 진행하지 않는다. 대본에 적힌 얼굴(붉은 눈, 터진 입술, 헝클어진 머리)만.
7. continuity (연속성 메모): 장면을 넘나드는 상태. who, item(옷·머리·상처·소품), eps, note_ko.
   예: 앞치마 주머니에 서류를 넣고 단추를 채움, 젖은 소매, 맨발/슬리퍼/구두, 뺨의 멍이 다음 장면까지.
8. extras (단역): 대사가 없어도 화면에 나오는 사람(경찰·교도관 등). who, eps, costume_ko, desc_en.

규칙: 대본에 없는 사건을 만들지 않는다. 대본에 단서가 없는 부분은 인물의 처지에 맞게 정하되 확정형으로.
'or', 'slightly', 'maybe', '또는', '정도' 금지.
JSON 만 출력:
{"season_ko":"",
 "analysis":[{"who":"","status_ko":"","arc_ko":"","clues":[{"ep":0,"text":""}],"concept_ko":"","palette":[],"silhouette_ko":"","contrast_ko":""}],
 "stages":[{"who":"","eps":"","concept_ko":""}],
 "change_signals":[{"scene":"","who":"","signal":"","verdict":"확정","evidence":"","note_ko":""}],
 "wardrobe":[{"id":"W-01","who":"","desc_ko":"","desc_en":"","ban_en":""}],
 "hair":[{"id":"H-01","who":"","desc_ko":"","desc_en":"","ban_en":""}],
 "makeup":[{"id":"M-01","who":"","desc_ko":"","desc_en":""}],
 "worn":[{"id":"P-01","who":"","desc_ko":"","desc_en":""}],
 "looks":[{"id":"LK-01","who":"","name":"기본","wardrobe":"W-01","hair":"H-01","makeup":"M-01","worn":[],"days":"","when_ko":"","reason_ko":"",
           "verdict":"확정","hook":false,"filter":"보통","filter_alt_ko":"","scenes":[]}],
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
    costume = compile_looks(d, names, scenes)
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
            "change_signals": rows("change_signals", ("scene", "who", "signal", "verdict", "evidence", "note_ko")),
            "confirmed": list(d.get("confirmed") or []),
            "sets": sets, "props": props[:20], "scene_looks": scene_looks}


def compile_looks(d: dict, names: set, scenes: set) -> list:
    """옷(W)·머리(H)·메이크업(M)·몸에 지니는 소품(P)을 룩(LK)으로 조립한다. 룩 하나 = 콘티·스틸에 넘기는 한 덩어리.
    예전 형식(costume 목록)도 그대로 받는다."""
    s_ = lambda x: str(x or "").strip()
    items = {}
    for key in ("wardrobe", "hair", "makeup", "worn"):
        for x in d.get(key) or []:
            if isinstance(x, dict) and s_(x.get("id")):
                items[s_(x["id"])] = {k: s_(x.get(k)) for k in ("id", "who", "desc_ko", "desc_en", "ban_en")}
    out = []
    if d.get("looks"):
        base_parts = {s_(x.get("who")): x for x in d["looks"] if isinstance(x, dict) and s_(x.get("name")) == "기본"}
        for x in d["looks"]:
            if not isinstance(x, dict) or s_(x.get("who")) not in names or not s_(x.get("name")):
                continue
            bp = base_parts.get(s_(x.get("who")), {})      # 룩에 빠진 항목은 그 인물의 기본 룩 것을 씀
            w, h, m = (items.get(s_(x.get(k)) or s_(bp.get(k)), {}) for k in ("wardrobe", "hair", "makeup"))
            worn = [items[s_(i)] for i in (x.get("worn") or []) if s_(i) in items]
            bans = " ".join(b for b in (w.get("ban_en"), h.get("ban_en")) if b)
            desc = (f"Hair: {h.get('desc_en', '')} Make-up: {m.get('desc_en', '')} Clothing: {w.get('desc_en', '')}"
                    + "".join(f" Wearing {p['desc_en']}" for p in worn) + (f" {bans}" if bans else "")).strip()
            name = s_(x["name"])
            out.append({"id": s_(x.get("id")), "who": s_(x["who"]), "look": name, "days": s_(x.get("days")),
                        "when_ko": s_(x.get("when_ko")), "reason_ko": s_(x.get("reason_ko")),
                        "verdict": "추론" if s_(x.get("verdict")) == "추론" else "확정",
                        "hook": bool(x.get("hook")), "filter": "높음" if s_(x.get("filter")) == "높음" else "보통",
                        "filter_alt_ko": s_(x.get("filter_alt_ko")),
                        "parts": {"W": w.get("id", ""), "H": h.get("id", ""), "M": m.get("id", ""), "P": [p["id"] for p in worn]},
                        "costume_ko": w.get("desc_ko", ""), "hair_ko": h.get("desc_ko", ""), "makeup_ko": m.get("desc_ko", ""),
                        "worn_ko": ", ".join(p["desc_ko"] for p in worn),
                        "desc_en": desc if (w or h or m) else "",
                        "scenes": [s_(k) for k in (x.get("scenes") or []) if s_(k) in scenes] if name != "기본" else []})
    else:
        for x in d.get("costume") or []:
            if not isinstance(x, dict) or s_(x.get("who")) not in names or not s_(x.get("look")):
                continue
            out.append({"id": "", "who": s_(x["who"]), "look": s_(x["look"]), "days": s_(x.get("days")), "when_ko": s_(x.get("when_ko")),
                        "reason_ko": s_(x.get("reason_ko")), "verdict": "확정", "hook": False, "filter": "보통", "filter_alt_ko": "",
                        "parts": {}, "costume_ko": s_(x.get("costume_ko")), "hair_ko": s_(x.get("hair_ko")),
                        "makeup_ko": s_(x.get("makeup_ko")), "worn_ko": "", "desc_en": s_(x.get("desc_en")),
                        "scenes": [s_(k) for k in (x.get("scenes") or []) if s_(k) in scenes] if s_(x.get("look")) != "기본" else []})
    # 같은 인물 안에서 룩 이름이 겹치면 id 를 붙여 구별
    seen = set()
    for c in out:
        if (c["who"], c["look"]) in seen and c["id"]:
            c["look"] = f"{c['look']} {c['id']}"
        seen.add((c["who"], c["look"]))
    for n in names:
        if not any(c["who"] == n and c["look"] == "기본" for c in out):
            out.insert(0, {"id": "", "who": n, "look": "기본", "days": "", "when_ko": "평소", "reason_ko": "", "verdict": "확정",
                           "hook": False, "filter": "보통", "filter_alt_ko": "", "parts": {}, "costume_ko": "", "hair_ko": "",
                           "makeup_ko": "", "worn_ko": "", "desc_en": "", "scenes": []})
    return out


def look_usable(c: dict, d: dict) -> bool:
    """확정 룩이거나, 추론 룩을 감독님이 확인한 경우만 작품에 등록·적용한다."""
    return c.get("verdict") != "추론" or c.get("id") in set(d.get("confirmed") or []) or c.get("look") in set(d.get("confirmed") or [])


def look_count_warnings(d: dict, parsed: dict, limit: int = 3) -> list:
    """인물마다 10화 묶음에 쓰이는 룩 수(기본 포함)가 limit 를 넘으면 경고."""
    out = []
    by = {}
    for c in d.get("costume", []):
        for k in c["scenes"]:
            ep = int(k.split("-")[0])
            by.setdefault((c["who"], (ep - 1) // 10), set()).add(c["look"])
    for (who, blk), looks in sorted(by.items()):
        n = len(looks | {"기본"})
        if n > limit:
            out.append(f"{who} · EP{blk * 10 + 1}~{blk * 10 + 10}: 룩 {n}개 ({', '.join(sorted(looks))} + 기본). {limit}개 이하로 묶는 것을 권합니다.")
    return out


def sheets(d: dict, parsed: dict, bible: dict) -> dict:
    """프리프로덕션 출력물: 브레이크다운 시트(장면별) · 연속성 표(항목 × 장면) · 생성 블록(룩별 장면 묶음)."""
    from src import bible as bb, cutter
    nm = cutter.name_map(bible)
    look_of = {(c["who"], c["look"]): c for c in d.get("costume", [])}
    base = {c["who"]: c for c in d.get("costume", []) if c["look"] == "기본"}
    sl = d.get("scene_looks") or {}
    props = d.get("props", [])
    breakdown, cont_cols, cont = [], [], {}
    for e in parsed["episodes"]:
        for s in e["scenes"]:
            k = f"{e['ep']}-{s['no']}"
            cont_cols.append(k)
            who = sorted({nm.get(l["who"].replace(" ", ""), l["who"]) for l in s["lines"] if l["type"] == "dialogue"} | set(sl.get(k, {})))
            loc = (bb.loc_of(bible, e["ep"], s["no"]) or {})
            pr = [p["name"] for p in props if str(e["ep"]) in [x.strip() for x in p.get("eps", "").split(",")]]
            for w in who:
                c = look_of.get((w, sl.get(k, {}).get(w, "기본"))) or base.get(w) or {}
                breakdown.append({"장면": k, "장소": loc.get("name", ""), "배역": w, "룩": f"{c.get('id', '')} {c.get('look', '기본')}".strip(),
                                  "의상": c.get("costume_ko", ""), "헤어": c.get("hair_ko", ""), "메이크업": c.get("makeup_ko", ""),
                                  "몸 소품": c.get("worn_ko", ""), "소품": ", ".join(pr),
                                  "필터": c.get("filter", "보통") + (f" → {c['filter_alt_ko']}" if c.get("filter") == "높음" else ""),
                                  "훅 룩": "●" if c.get("hook") else ""})
                parts = c.get("parts") or {}
                for item, val in (("의상", parts.get("W") or c.get("costume_ko", "")[:12]), ("헤어", parts.get("H") or c.get("hair_ko", "")[:12]),
                                  ("메이크업", parts.get("M") or c.get("makeup_ko", "")[:12]), ("몸 소품", ",".join(parts.get("P") or []))):
                    cont.setdefault((w, item), {})[k] = val
    blocks = []
    for c in d.get("costume", []):
        sc = c["scenes"] if c["look"] != "기본" else [r["장면"] for r in breakdown if r["배역"] == c["who"] and r["룩"].endswith("기본")]
        if sc:
            blocks.append({"룩": f"{c.get('id', '')} {c['who']} · {c['look']}".strip(), "장면 수": len(sc),
                           "화": ", ".join(dict.fromkeys(x.split("-")[0] for x in sc))})
    return {"breakdown": breakdown, "cont_cols": cont_cols, "continuity": cont, "blocks": blocks}


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
        if not look_usable(c, d):          # 추론 룩은 감독님 확인 뒤에 등록
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
