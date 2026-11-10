"""인물·장소 프로필 초안: 대본 속 상황을 읽고 Claude 가 외모·의상·공간을 확정형으로 쓴다."""
from __future__ import annotations

import json

DEFAULT_MODEL = "claude-sonnet-4-6"   # MakingShorts-Engine 에서 쓰는 모델과 같게. secrets 의 CLAUDE_MODEL 로 바꿀 수 있음

SYSTEM = """당신은 한국 실사 드라마의 캐스팅 디렉터이자 미술감독입니다.
대본 발췌를 읽고 각 인물의 외모·고정 의상, 각 장소의 공간을 정합니다.

규칙
- 대본에 적힌 사실(나이, 직업, 처지, 관계)을 먼저 따르고, 없는 것은 그 인물의 처지에 맞게 정합니다.
- 모든 문장은 확정형. '살짝', '약간', '정도', '또는', '~처럼 보임', '~수 있음' 금지. 한 가지 상태만.
- 실존 배우·연예인을 언급하거나 닮게 하지 않습니다.
- 주연·주요 조연은 TV 드라마 주연 배우급의 매력적인 외모로 정합니다. 가난·피로·처지는 얼굴이 아니라 의상·소품·머리 손질로 보여 줍니다.
  얼굴은 또렷한 이목구비, 맑고 큰 눈, 생기 있는 표정, 건강한 피부로. '가는 눈', '얇은 입술', '창백한' 같은 평범하거나 지친 인상의 특징은 주연에게 쓰지 않습니다.
- 의상은 한 시즌 내내 입을 한 벌. 색은 베이지·아이보리·네이비·그레이·블랙 같은 차분한 색 위주.
- prompt_en 은 이미지 생성용 영어 한 문단. 인물만 씀(구도·배경·조명·필름 질감은 엔진이 붙임). 이 순서로:
  Face: 성별·나이대(예: a beautiful South Korean woman in her mid twenties), 얼굴형, 눈 색과 모양, 입술, 피부 톤.
  Hair: 색, 길이, 묶음, 앞머리·잔머리(예: medium-dark brown hair in a loose low ponytail with wispy bangs and face-framing strands).
  Clothing: 소재·색·핏까지(예: fitted light heather-grey wool-blend ribbed turtleneck, charcoal tailored trousers).
  Expression: 표정 하나(예: a gentle natural smile with lips closed).
  주연·주요 조연은 매력을 분명히 씀(beautiful / handsome, clear bright eyes 등). 'flawless', 'airbrushed', 'perfect skin', 'slightly', 'or' 금지.
- 장소 prompt_en: 사람 없는 넓은 마스터 샷, 눈높이, 낮의 창 자연광(밤 장소면 실제 조명), 서울의 실제 같은 공간.

JSON 만 출력:
{"characters":[{"name":"","role_ko":"","age":"","look_ko":"","outfit_ko":"","prompt_en":""}],
 "locations":[{"name":"","desc_ko":"","prompt_en":""}]}"""


def excerpt(parsed: dict, names: list[str], places, per: int = 6, bible: dict | None = None) -> str:
    """인물·장소별로 대본 줄 몇 개씩 모아 짧은 발췌를 만든다 (토큰 절약)."""
    out = [f"작품: {parsed.get('title','')}"]
    roles = {c["name"]: c for c in (bible or {}).get("characters", [])}
    for n in names:
        r = roles.get(n)
        if r:
            out.append(f"\n[인물 정보 {n}] {r.get('role','')} / {r.get('age','')} / 대본 표기: {', '.join(r.get('aliases', []))}")
        got = []
        forms = [n] + list((r or {}).get("aliases", []))
        for e in parsed["episodes"]:
            for s in e["scenes"]:
                for l in s["lines"]:
                    t = l["text"]
                    said = l.get("who") in forms
                    if (said or any(t.startswith(f + "이") or t.startswith(f + "가") or f"{f}의" in t for f in forms)) and len(got) < per:
                        got.append(f"EP{e['ep']} {s['place']}: " + (f"{n}: {t}" if said else t))
        out.append(f"\n[인물 {n}]\n" + "\n".join(got))
    if isinstance(places, dict):                      # {세트 이름: [장면 머리 …]} (작품 정리 후)
        descs = {l["name"]: l.get("desc", "") for l in (bible or {}).get("locations", [])}
        for p, slugs in places.items():
            out.append(f"\n[장소 {p}] {descs.get(p, '')}\n" + "\n".join(slugs))
    else:
        for p in places:
            got = [f"EP{e['ep']} S#{s['no']} {s['slug']}" for e in parsed["episodes"] for s in e["scenes"] if s["place"] == p][:4]
            out.append(f"\n[장소 {p}]\n" + "\n".join(got))
    return "\n".join(out)[:24000]


def draft(api_key: str, parsed: dict, names: list[str], places, model: str = "", bible: dict | None = None) -> dict:
    import anthropic
    from json_repair import repair_json
    c = anthropic.Anthropic(api_key=api_key)
    r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=6000, system=SYSTEM,
                          messages=[{"role": "user", "content": excerpt(parsed, names, places, bible=bible)}])
    txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    data = json.loads(repair_json(txt))
    data = data if isinstance(data, dict) else {}
    for group in ("characters", "locations"):          # 키 이름이 조금 달라도 prompt_en 으로 맞춤
        for it in data.get(group, []) or []:
            if isinstance(it, dict) and not it.get("prompt_en"):
                it["prompt_en"] = it.get("prompt") or it.get("image_prompt") or it.get("promptEn") or ""
    return data


def to_prompt(api_key: str, kind: str, name: str, info: dict, model: str = "") -> str:
    """한국어 외모·의상(또는 장소 설명) → 이미지 지시문 영어 한 문단. 칸 하나만 다시 쓸 때."""
    import anthropic
    if kind == "cast":
        src = f"인물 {name}, 나이 {info.get('age','')}. 외모: {info.get('look_ko','')} 의상: {info.get('outfit_ko','')}"
        rule = ("Face: … Hair: … Clothing: … Expression: … 순서로 인물만 씀. 구도·배경·조명 문장은 쓰지 않음(엔진이 붙임). "
                "드라마 주연 배우급의 매력적인 얼굴(beautiful / handsome)로 이목구비를 구체적으로. "
                "'flawless', 'airbrushed', 'slightly', 'or' 금지.")
    else:
        src = f"장소 {name}. {info.get('desc_ko','')}"
        rule = "사람 없는 넓은 마스터 샷, 눈높이. 'slightly', 'or' 금지."
    c = anthropic.Anthropic(api_key=api_key)
    r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=800,
                          system="이미지 생성용 영어 지시문 한 문단만 출력합니다. 확정형, 한 가지 상태만. 설명이나 따옴표 없이 본문만. " + rule,
                          messages=[{"role": "user", "content": src}])
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip().strip('"')
