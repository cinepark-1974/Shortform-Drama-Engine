"""숏폼 드라마 대본 읽기.

Shortform-Engine 출력 형식을 화·장면·지문·대사로 나눈다.
    EP 1 | 💢 굴욕 (Humiliation)
    [자막] "[충격] 당일 해고"
    S#1. 대성그룹 본사 — 로비. 낮.
    세영 (안내 직원에게) 마케팅기획팀 인턴 오리엔테이션이요.
    세영이 QR 방문증을 찍는다. ...            ← 지문
AI 를 쓰지 않는 규칙 기반 파서라 같은 대본은 언제나 같은 결과가 나온다.
"""
from __future__ import annotations

import io
import re
from collections import Counter

EP_RE = re.compile(r"^EP\s*(\d+)\s*\|\s*(.+)$")
HOOK_RE = re.compile(r'^\[자막\]\s*["“]?(.+?)["”]?\s*$')
SCENE_RE = re.compile(r"^S#\s*(\d+)\.\s*(.+)$")
TIME_WORDS = ("낮", "밤", "아침", "저녁", "새벽", "오후", "오전", "점심", "해질녘", "늦은 밤", "이른 아침")
PARTICLES = ("이", "가", "의", "은", "는", "을", "를", "에게", "도", "와", "과")
FOOTER_RE = re.compile(r"^©")
# 줄머리에 자주 오지만 사람이 아닌 낱말 (화면 인서트, 장소 표기 등)
NON_PERSON = {"화면", "핸드폰", "휴대폰", "모니터", "문자", "카톡", "메일", "노트북", "전화", "자막", "인서트",
              "몽타주", "회상", "플래시백", "복도", "로비", "회의실", "사무실", "엘리베이터", "시계", "편지", "사진"}


def read_text(data: bytes, filename: str) -> str:
    """docx 또는 txt 바이트를 문단 단위 텍스트로."""
    if filename.lower().endswith(".docx"):
        import docx  # python-docx
        d = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs)
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _paragraphs(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", p).strip() for p in text.splitlines() if p.strip()]


def _split_slug(slug: str) -> dict:
    """'대성그룹 본사 — 로비. 낮. (이어서)' → place='대성그룹 본사', sub='로비', time='낮'."""
    s = re.sub(r"\((이어서|시간 경과|회상|플래시백)[^)]*\)", "", slug).strip()
    parts = [x.strip() for x in s.split(".") if x.strip()]
    time = ""
    if parts and any(parts[-1].startswith(w) for w in TIME_WORDS):
        time = parts.pop()
    where = ". ".join(parts)
    place, _, sub = where.partition("—")
    return {"place": place.strip(" -"), "sub": sub.strip(" -"), "time": time}


def detect_speakers(paras: list[str]) -> list[str]:
    """대사 줄의 화자 이름을 대본에서 스스로 찾는다.

    규칙: 줄 맨 앞 낱말이 (1) 3번 이상 줄머리에 오고 (2) 지문에서 '이름+조사'(세영이, 세영의…)로도 쓰이면 화자.
    '안내 직원 (…)'처럼 두 낱말 이름은 괄호 앞 두 낱말이 2번 이상 나오면 화자.
    """
    body = [p for p in paras if not (EP_RE.match(p) or HOOK_RE.match(p) or SCENE_RE.match(p))]
    joined = "\n".join(body)
    first = Counter(p.split(" ", 1)[0] for p in body if " " in p)
    names = set()
    for tok, n in first.items():
        if n < 3 or len(tok) > 6 or tok in NON_PERSON or not re.fullmatch(r"[가-힣A-Za-z]+", tok):
            continue
        if tok.endswith(PARTICLES) and len(tok) > 2 and tok[:-1] in first:
            continue
        uses = sum(joined.count(tok + pa) for pa in PARTICLES)
        if uses >= 3:
            names.add(tok)
    two = Counter(m.group(1) for p in body if (m := re.match(r"^([가-힣]+ [가-힣]+) \(", p)))
    names.update(k for k, v in two.items() if v >= 2 and k.split(" ")[0] not in NON_PERSON)
    return sorted(names, key=len, reverse=True)


def parse(text: str, speakers: list[str] | None = None) -> dict:
    paras = _paragraphs(text)
    title = paras[1] if len(paras) > 1 and not EP_RE.match(paras[1]) else (paras[0] if paras else "")
    speakers = speakers or detect_speakers(paras)
    sp_re = re.compile(r"^(" + "|".join(map(re.escape, speakers)) + r")(?: \(([^)]*)\))? (.+)$") if speakers else None

    episodes, ep, sc = [], None, None
    for p in paras:
        if FOOTER_RE.match(p):
            continue
        m = EP_RE.match(p)
        if m:
            ep = {"ep": int(m.group(1)), "emotion": m.group(2).strip(), "hook": "", "scenes": []}
            episodes.append(ep)
            sc = None
            continue
        if ep is None:
            continue
        m = HOOK_RE.match(p)
        if m and not ep["hook"]:
            ep["hook"] = m.group(1).strip()
            continue
        m = SCENE_RE.match(p)
        if m:
            sc = {"no": int(m.group(1)), "slug": m.group(2).strip(), **_split_slug(m.group(2)), "lines": []}
            ep["scenes"].append(sc)
            continue
        if sc is None:
            continue
        m = sp_re.match(p) if sp_re else None
        if m:
            sc["lines"].append({"type": "dialogue", "who": m.group(1), "note": m.group(2) or "", "text": m.group(3)})
        else:
            sc["lines"].append({"type": "action", "text": p})
    return {"title": title, "speakers": speakers, "episodes": episodes}


def summarize(parsed: dict) -> dict:
    eps = parsed["episodes"]
    lines = Counter(l["who"] for e in eps for s in e["scenes"] for l in s["lines"] if l["type"] == "dialogue")
    first_ep = {}
    for e in eps:
        for s in e["scenes"]:
            for l in s["lines"]:
                if l["type"] == "dialogue":
                    first_ep.setdefault(l["who"], e["ep"])
    places = Counter(s["place"] for e in eps for s in e["scenes"] if s["place"])
    place_eps: dict[str, list[int]] = {}
    for e in eps:
        for s in e["scenes"]:
            if s["place"]:
                place_eps.setdefault(s["place"], [])
                if e["ep"] not in place_eps[s["place"]]:
                    place_eps[s["place"]].append(e["ep"])
    return {
        "episodes": len(eps),
        "scenes": sum(len(e["scenes"]) for e in eps),
        "missing_hook": [e["ep"] for e in eps if not e["hook"]],
        "no_scene": [e["ep"] for e in eps if not e["scenes"]],
        "dialogue_lines": dict(lines.most_common()),
        "first_ep": first_ep,
        "places": dict(places.most_common()),
        "place_eps": place_eps,
    }


def alias_suggestions(names: list[str]) -> list[tuple[str, str]]:
    """'오진혁'과 '진혁'처럼 한쪽이 다른 쪽 끝에 붙는 이름 쌍 → (긴 이름, 짧은 이름)."""
    out = []
    for a in names:
        for b in names:
            if a == b or len(a) <= len(b) or len(b) < 2:
                continue
            if (a.endswith(b) and len(a) - len(b) <= 2 and " " not in a) or a.startswith(b + " "):
                out.append((a, b))   # 오진혁/진혁, 도균 팀장/도균
    return out
