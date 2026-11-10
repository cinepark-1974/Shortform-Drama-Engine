"""회당 컷 분할: 한 화(60초 안팎)를 6~8컷으로 나누고, 컷마다 스틸·영상 지시문을 만든다.

AI(Claude)는 컷의 '내용'(크기·각도·행동·대사·움직임 종류)만 정하고,
스틸·영상 지시문 문장은 코드가 규칙대로 조립한다 (3 MINUTES 콘솔의 stillPrompt / vpPrompt 방식).
"""
from __future__ import annotations

import json
import re

DEFAULT_MODEL = "claude-sonnet-4-6"

SIZES = ["ECU", "CU", "MCU", "MS", "MLS", "WS", "INSERT", "2-SHOT", "OTS"]
ANGLES = ["정면", "3/4 측면", "측면", "뒤에서", "어깨 너머", "하이앵글", "로우앵글", "부감", "POV"]
MOTIONS = {"still": "정지+카메라", "move": "짧은 움직임", "video": "완전 영상"}

SHOT_KO = {"ECU": "익스트림 클로즈업. 피사체의 한 부분이 화면을 꽉 채운다.", "CU": "클로즈업. 얼굴과 어깨 위가 화면을 꽉 채운다.",
           "MCU": "미디엄 클로즈업. 가슴 위 상반신이 화면을 채운다.", "MS": "미디엄 샷. 허리 위 상반신과 주변 공간 일부가 보인다.",
           "MLS": "미디엄 롱 샷. 무릎 위 인물과 주변 공간이 보인다.", "WS": "와이드 샷. 인물 전신과 공간 전체가 보인다.",
           "INSERT": "인서트 샷. 사물 하나가 화면 가운데를 크게 채운다.", "2-SHOT": "투 샷. 두 인물이 허리 위까지 한 화면에 함께 들어온다.",
           "OTS": "어깨 너머 샷. 앞 인물의 어깨 너머로 맞은편 인물의 얼굴이 보인다."}
SHOT_EN = {"ECU": "extreme close-up", "CU": "close-up", "MCU": "medium close-up", "MS": "medium shot", "MLS": "medium long shot",
           "WS": "wide shot", "INSERT": "insert close-up", "2-SHOT": "two-shot", "OTS": "over-the-shoulder shot"}
ANG_EN = {"정면": "front, eye level", "3/4 측면": "three-quarter, eye level", "측면": "side profile, eye level", "뒤에서": "from behind",
          "어깨 너머": "over the shoulder", "하이앵글": "high angle", "로우앵글": "low angle", "부감": "top-down overhead", "POV": "point of view"}
CAM_EN = {"고정": "Static locked-off camera. No camera movement, no zoom.", "천천히 다가감": "Slow dolly in over the full clip.",
          "천천히 물러남": "Slow dolly out over the full clip.", "핸드헬드": "Subtle handheld camera, small natural sway.",
          "팬": "Slow pan following the subject.", "줌인": "Slow optical zoom in; the camera body stays in place."}

SYSTEM = """당신은 한국 실사 숏폼 드라마(세로 9:16, 한 화 60초 안팎)의 감독입니다.
한 화의 대본을 컷으로 나눕니다. 시청자는 휴대폰 세로 화면으로 봅니다.

규칙
- 컷 6~8개. 컷 길이 합계 50~70초(목표 56초). 컷 하나 3~10초. 합계가 50초 미만이면 컷을 늘리지 말고 각 컷 dur 를 늘림.
- 대사 컷의 dur 는 (대사 음절 수 ÷ 4) + 1초 이상.
- 1번 컷은 첫 3초 안에 화의 훅을 보여 주는 컷. 마지막 컷은 대본의 '끊긴다' 순간이며 motion 은 반드시 "video".
- 감정이 터지는 클라이맥스 컷은 climax true, motion "video".
- motion: "still"(정지 그림+카메라 움직임), "move"(짧은 움직임: 눈 깜빡임·고개 돌림·손 움직임), "video"(완전 영상).
  "still" 은 한 화에 연속 2개를 넘지 않음. 대사하는 얼굴이 보이는 컷은 "move" 또는 "video".
- size: ECU, CU, MCU, MS, MLS, WS, INSERT, 2-SHOT, OTS 중 하나. 세로 화면이라 WS 는 화당 1개 이하.
- angle: 정면, 3/4 측면, 측면, 뒤에서, 어깨 너머, 하이앵글, 로우앵글, 부감, POV 중 하나.
- camera: 고정, 천천히 다가감, 천천히 물러남, 핸드헬드, 팬, 줌인 중 하나.
- action: 한 컷에 한 가지 상태·한 가지 행동. 확정형 한국어 문장. '살짝·약간·정도·또는·처럼 보·수 있' 금지.
- action_en: action 과 같은 내용의 영어 한 문장 (이미지·영상 생성용). 인물은 영어 이름 대신 역할로 써도 됨. 'slightly·maybe·or' 금지.
- dialogue: 이 컷에서 들리는 대사 하나 {"who":통일 이름,"text":대사,"on_screen":입이 보이면 true}. 없으면 null.
  대사 길이는 컷 길이 안에 들어가게(한국어 1초에 4음절).
- screen_text: 휴대폰·모니터·문서에 보이는 글자. 그림에는 글자를 넣지 않고 편집에서 얹으므로 글자만 적음. 없으면 "".
- chars: 화면에 보이는 인물(통일 이름). 손·뒷모습만 보이면 이름 뒤에 ':손' 또는 ':뒷모습'.
- loc: 주어진 장소 id. sfx: 효과음 한 단어(없으면 "").
- 대본에 없는 사건을 만들지 않음. 대사는 대본 문장 그대로.

JSON 만 출력:
{"cuts":[{"no":1,"scene":1,"size":"","angle":"","camera":"","dur":3.0,"motion":"","climax":false,
"chars":[],"loc":"L01","action":"","action_en":"","dialogue":null,"screen_text":"","sfx":""}]}"""


def syl(t: str) -> int:
    return len(re.findall(r"[가-힣]", re.sub(r"\([^)]*\)", "", t or "")))


def episode_text(ep: dict, bible: dict | None) -> str:
    from src import bible as bb
    names = [c["name"] for c in (bible or {}).get("characters", [])]
    out = [f"[인물 표기] {', '.join(names)}  (chars·dialogue.who 에는 이 이름만 그대로 씀. 목록에 없는 단역은 '신입A'처럼 짧게)",
           f"EP {ep['ep']} | {ep['emotion']}", f"[훅 자막] {ep['hook']}"]
    for s in ep["scenes"]:
        loc = bb.loc_of(bible, ep["ep"], s["no"])
        out.append(f"\nS#{s['no']}. {s['slug']}  → 장소 id {loc['id'] if loc else '?'} ({loc['name'] if loc else ''})")
        for l in s["lines"]:
            if l["type"] == "dialogue":
                out.append(f"{bb.who(bible, ep['ep'], l['who'])}{' (' + l['note'] + ')' if l['note'] else ''} {l['text']}")
            else:
                out.append(l["text"])
    return "\n".join(out)


def split(api_key: str, ep: dict, bible: dict | None, model: str = "") -> dict:
    import anthropic
    from json_repair import repair_json
    c = anthropic.Anthropic(api_key=api_key)
    r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=6000, system=SYSTEM,
                          messages=[{"role": "user", "content": episode_text(ep, bible)}])
    txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    data = json.loads(repair_json(txt))
    cuts = data.get("cuts", []) if isinstance(data, dict) else []
    return {"cuts": normalize(cuts, ep, bible), "model": model or DEFAULT_MODEL}


def name_map(bible: dict | None) -> dict:
    """'안내직원'·'한세영'·'진혁' 같은 표기 → 바이블 통일 이름 (띄어쓰기 무시)."""
    m = {}
    for c in (bible or {}).get("characters", []):
        for f in [c["name"], *c.get("aliases", [])]:
            m[f.replace(" ", "")] = c["name"]
    for f, n in (bible or {}).get("speaker_map", {}).get("global", {}).items():
        m.setdefault(f.replace(" ", ""), n)
    return m


def canon(name: str, nm: dict) -> str:
    base, sep, part = name.partition(":")
    return nm.get(base.strip().replace(" ", ""), base.strip()) + (sep + part if sep else "")


def fit_durations(cuts: list, lo: float = 50, target: float = 56, hi: float = 70) -> list:
    """대사 길이를 먼저 맞추고, 합계가 50초 미만이면 56초로, 70초 초과면 줄여서 맞춘다 (컷 하나 3~10초)."""
    def need(c):
        return syl(c["dialogue"]["text"]) / 4 + 1.0 if c.get("dialogue") else 3.0
    for c in cuts:
        c["dur"] = round(min(10.0, max(c["dur"], need(c), 3.0)), 1)
    total = sum(c["dur"] for c in cuts)
    if cuts and (total < lo or total > hi):
        k = target / total
        for c in cuts:
            c["dur"] = round(min(10.0, max(need(c), 3.0, c["dur"] * k)), 1)
    return cuts


def normalize(cuts: list, ep: dict, bible: dict | None = None) -> list:
    """AI 응답을 그대로 믿지 않고 형식을 맞춘다: 이름은 바이블 표기로, 길이는 규칙대로."""
    nm = name_map(bible)
    out = []
    for i, c in enumerate(cuts if isinstance(cuts, list) else [], start=1):
        if not isinstance(c, dict):
            continue
        d = c.get("dialogue")
        if isinstance(d, dict) and d.get("text"):
            d = {"who": canon(str(d.get("who", "")), nm), "text": str(d["text"]), "on_screen": bool(d.get("on_screen", True))}
        else:
            d = None
        try:
            dur = round(float(c.get("dur", 3)), 1)
        except (TypeError, ValueError):
            dur = 3.0
        out.append({
            "id": f"{ep['ep']}-{i}", "no": i, "scene": int(c.get("scene") or 1),
            "size": str(c.get("size", "MS")).upper().replace(" ", ""), "angle": str(c.get("angle", "정면")),
            "camera": str(c.get("camera", "고정")), "dur": dur,
            "motion": c.get("motion") if c.get("motion") in MOTIONS else "move",
            "climax": bool(c.get("climax", False)), "chars": [canon(str(x), nm) for x in (c.get("chars") or [])],
            "loc": str(c.get("loc", "")), "action": str(c.get("action", "")).strip(),
            "action_en": str(c.get("action_en", "")).strip(), "dialogue": d,
            "screen_text": str(c.get("screen_text") or ""), "sfx": str(c.get("sfx") or ""),
        })
    return fit_durations(out)


def check(cuts: list, known_chars: set, known_locs: set) -> list[dict]:
    """컷 목록 점검 → [{'id','level':'fix'|'todo','msg'}]"""
    from src.imagegen import banned_in
    issues = []
    if not cuts:
        return [{"id": "-", "level": "fix", "msg": "컷이 없습니다"}]
    total = sum(c["dur"] for c in cuts)
    if not (6 <= len(cuts) <= 8):
        issues.append({"id": "-", "level": "todo", "msg": f"컷 {len(cuts)}개 (기준 6~8개)"})
    if not (50 <= total <= 70):
        issues.append({"id": "-", "level": "todo", "msg": f"합계 {total:.1f}초 (기준 50~70초)"})
    if cuts[-1]["motion"] != "video":
        issues.append({"id": cuts[-1]["id"], "level": "fix", "msg": "마지막 '끊김' 컷은 완전 영상이어야 함"})
    run = 0
    for c in cuts:
        run = run + 1 if c["motion"] == "still" else 0
        if run > 2:
            issues.append({"id": c["id"], "level": "fix", "msg": "정지 컷이 3개 연속 (PPT식으로 보임)"})
        if c["climax"] and c["motion"] != "video":
            issues.append({"id": c["id"], "level": "fix", "msg": "클라이맥스 컷은 완전 영상이어야 함"})
        if c["size"] not in SIZES:
            issues.append({"id": c["id"], "level": "todo", "msg": f"샷 크기 '{c['size']}' 확인"})
        if c["loc"] and known_locs and c["loc"] not in known_locs:
            issues.append({"id": c["id"], "level": "fix", "msg": f"장소 id '{c['loc']}' 가 바이블에 없음"})
        for ch in c["chars"]:
            base = ch.split(":")[0]
            if known_chars and base not in known_chars:
                issues.append({"id": c["id"], "level": "info", "msg": f"단역 '{base}' (바이블 밖 인물, 기준 이미지 없이 생성)"})
        d = c["dialogue"]
        if d:
            need = syl(d["text"]) / 4 + 0.5
            if need > c["dur"] + 0.05:
                issues.append({"id": c["id"], "level": "fix", "msg": f"대사 {syl(d['text'])}음절: 최소 {need:.1f}초 필요 (현재 {c['dur']}초)"})
            if d.get("on_screen") and c["motion"] == "still":
                issues.append({"id": c["id"], "level": "fix", "msg": "입이 보이는 대사 컷이 정지 컷"})
        for b in banned_in(c["action"] + " " + c.get("action_en", "")):
            issues.append({"id": c["id"], "level": "fix", "msg": f"행동 문장 금지어 {b}"})
    return issues


def still_prompt(c: dict, cast: dict, locs: dict) -> str:
    """스틸(컷 그림) 지시문: 영어, 확정형. cast[name]=외모 영어 묘사, locs[id]=(이름, 영어 묘사)."""
    who = []
    for ch in c["chars"]:
        base, _, part = ch.partition(":")
        desc = cast.get(base, base)
        who.append(f"{desc}, only the hands visible" if part == "손" else f"{desc}, seen from behind" if part == "뒷모습" else desc)
    loc = locs.get(c["loc"], ("", ""))
    tight = c["size"] in ("ECU", "CU", "INSERT")
    lines = [f"Vertical 9:16 still frame from a Korean drama. {SHOT_EN.get(c['size'], 'medium shot').capitalize()}, {ANG_EN.get(c['angle'], 'eye level')}.",
             f"Scene: {c.get('action_en') or c['action']}",
             ("Characters: " + "; ".join(who) + ".") if who else "No people in frame.",
             f"Location: {loc[1] or loc[0]}" + (", background softly blurred." if tight else "."),
             "Same faces, outfits and room as the attached reference images." if (who or loc[0]) else "",
             f"Any screen or paper in frame is blank; text is added in editing." if c["screen_text"] else "No text anywhere in the image."]
    return " ".join(x for x in lines if x)


def video_prompt(c: dict, cast: dict) -> str:
    who = [cast.get(ch.split(":")[0], ch) for ch in c["chars"]]
    d = c["dialogue"]
    if not d:
        dl = ""
    elif d.get("on_screen"):
        dl = f"Dialogue: {d['who']} speaks one short line in Korean; lips move naturally for {syl(d['text']) / 4 + 0.3:.1f} seconds."
    else:
        dl = "Dialogue: off-screen voice added in editing; nobody in frame moves their lips."
    mv = {"still": "Almost no motion: only a slow camera move on the still image.",
          "move": "Small natural motion only: blinking, breathing, a slight turn of the head or hand.",
          "video": "Full natural acting motion as described."}[c["motion"]]
    parts = [f"Shot: {SHOT_EN.get(c['size'], 'medium shot')}, {ANG_EN.get(c['angle'], 'eye level')}, vertical 9:16.",
             f"Camera: {CAM_EN.get(c['camera'], CAM_EN['고정'])}",
             ("Characters: " + "; ".join(who) + ".") if who else "",
             f"Action: {c.get('action_en') or c['action']}", mv, dl,
             f"Duration: {c['dur']} seconds. Photoreal, natural light, no text on screen."]
    return " ".join(x for x in parts if x)
