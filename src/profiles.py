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
- 의상은 한 시즌 내내 입을 한 벌. 색은 베이지·아이보리·네이비·그레이·블랙 같은 차분한 색 위주.
- prompt_en 은 이미지 생성용 영어 한 문단: 길에서 우연히 찍힌 상반신 한 순간. 얼굴은 카메라 쪽, 가리지 않음.
  그 인물이 평소 하는 작은 동작 하나(가방 끈을 고쳐 잡음, 사원증을 목에 거는 중 등)와 그 순간의 표정 하나를 확정형으로.
  배경·조명·필름 질감은 엔진이 자동으로 붙이므로 쓰지 않음.
  나이·얼굴형·눈매·머리 모양(길이, 묶음, 잔머리)·피부 톤·의상 소재와 색을 구체적으로. 예: 'loose low ponytail with flyaway strands framing the face, pale blue cotton blouse with a ruffled collar'.
  'beautiful', 'stunning', 'flawless' 같은 미화 단어 금지(인공 미인 얼굴이 나옴). 'slightly', 'or' 금지.
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
    return data if isinstance(data, dict) else {}
