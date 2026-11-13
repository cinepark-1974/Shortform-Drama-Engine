"""회당 컷 분할: 한 화(60초 안팎)를 14~16컷으로 잘게 나누고, 컷마다 스틸·영상 지시문을 만든다.

AI(Claude)는 컷의 '내용'(크기·각도·행동·대사·움직임 종류)만 정하고,
스틸·영상 지시문 문장은 코드가 규칙대로 조립한다 (3 MINUTES 콘솔의 stillPrompt / vpPrompt 방식).

v0.5 (2026-11-12, Mr. MOON 결정)
- 컷을 잘게: 한 화 14~16컷, 컷 하나 1.5~3초. 화당 한 컷만 4~6초 '버티기 컷'(클라이맥스).
  빠른 컷 사이에 한 컷을 길게 버텨야 그 순간이 감정의 정점으로 읽힌다.
- 영상은 3초부터 만들 수 있으므로(Kling 3~15초) 짧은 컷은 3초로 만들고 편집에서 잘라 쓴다.
- 영상(짧은 움직임+완전 영상) 컷은 화당 7개까지. 나머지는 정지+카메라. 2초 안팎 정지 컷은 PPT처럼 보이지 않는다.
- 립싱크 모델이 없으므로 말하는 얼굴은 정지 컷으로 2.5초 이하만 보여 주고, 긴 대사는 듣는 사람 컷으로 넘겨 이어 간다.
- 몸에 거는 작은 소품(사원증 목걸이·장신구)은 쓰지 않는다. 이야기에 필요한 소품은 그 컷에서 손에만 든다.
"""
from __future__ import annotations

import json
import math
import re

DEFAULT_MODEL = "claude-sonnet-4-6"

SIZES = ["ECU", "CU", "MCU", "MS", "MLS", "WS", "INSERT", "2-SHOT", "OTS"]
ANGLES = ["정면", "3/4 측면", "측면", "뒤에서", "어깨 너머", "하이앵글", "로우앵글", "부감", "POV"]
MOTIONS = {"still": "정지+카메라", "move": "짧은 움직임", "video": "완전 영상"}
CUTS_LO, CUTS_HI = 12, 18      # 한 화 컷 수 허용 범위 (목표 14~16)
MAX_VIDEO = 4          # 한 화 완전 영상 컷 상한 (마지막 컷·클라이맥스 포함)
MAX_MOVING = 7         # 한 화 영상 생성 컷(짧은 움직임+완전 영상) 상한. 컷마다 최소 3초씩 과금되므로 비용 상한 역할
DUR_MIN, DUR_MAX = 1.5, 4.0    # 보통 컷 길이
STILL_MAX = 3.0                # 정지+카메라 컷 최대 길이 (3초를 넘으면 PPT처럼 보이기 시작)
HOLD_MAX = 6.0                 # 버티기 컷(클라이맥스) 최대 길이
TALK_MAX = 2.5                 # 말하는 얼굴이 보이는 컷 최대 길이 (립싱크 없음)
FLOW_WORDS = re.compile(r"(하고\s|고서|면서|다가|하자|열리자|되자|며\s|고\s?(들어|나가|나서|걸어|돌아|일어|앉|뛰|달려|떠나))")   # 첫 장면에 시간이 흐르는 표현
WEAR_WORDS = re.compile(r"목걸이|목에 (건|걸)|사원증을 (목|걸)|명찰|귀걸이|팔찌|손목시계|이어폰")

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

SYSTEM = """당신은 한국 실사 숏폼 드라마(세로 9:16, 한 화 60초 안팎)의 감독이자 편집자입니다.
한 화의 대본을 컷으로 나눕니다. 시청자는 휴대폰 세로 화면으로 봅니다. 호흡은 빠른 쇼츠 편집입니다.

컷 수·길이
- 컷 14~16개. 컷 길이 합계 50~70초(목표 56초). 보통 컷은 1.5~3초.
- 버티기 컷: 감정이 터지는 클라이맥스 한 컷만 4~6초로 길게 버팀(climax true). 화당 1개.
  빠른 컷이 이어지다 이 컷에서 멈춰야 감정의 정점으로 읽힘. 나머지 컷은 4초를 넘기지 않음.
- 1~3번 컷은 첫 3초 안에 훅을 보여 주는 1초 안팎의 빠른 컷 2~3개(얼굴 → 대상 → 반응).
- 마지막 컷은 대본의 '끊긴다' 순간이며 motion 은 반드시 "video", 3~4초.
- 대본의 모든 S#(장면)은 최소 1컷씩. scene 에는 그 컷이 속한 S# 번호를 정확히 씀.
- 같은 장면 안에서 컷 크기를 섞음: 넓은 컷(MS·MLS·WS), 얼굴(MCU·CU), 인서트(손·휴대폰·모니터·소품)를 골고루. 세로 화면이라 WS 는 화당 1개 이하.

대사 (립싱크 모델이 없음)
- 말하는 얼굴이 보이는 컷(on_screen true)은 motion "still", dur 2.5초 이하.
- 대사가 2.5초(10음절)를 넘으면 컷을 나눔: 앞 컷은 말하는 사람(on_screen true), 다음 컷은 듣는 사람의 반응·뒷모습·손(on_screen false)으로 대사를 이어 감.
  나눈 대사는 대본 문장을 그대로 끊어서 앞 컷과 뒷 컷 text 에 나눠 담음 (합치면 원문 그대로).
- 화면 밖 목소리·듣는 사람 컷은 on_screen false. 대사 컷 dur 는 (그 컷 대사 음절 수 ÷ 4) + 0.3초 이상.

움직임
- motion: "still"(정지 그림+카메라 움직임), "move"(짧은 움직임: 눈 깜빡임·고개 돌림·손 움직임, 입은 다묾), "video"(완전 영상).
- 영상 생성 컷("move"+"video")은 한 화에 최대 7개. "video" 는 그중 최대 4개(마지막 컷·클라이맥스 포함).
  나머지는 "still". 2초 안팎의 정지 컷은 빠른 편집 속에서 자연스러우므로 아끼지 말고 씀.
- "still" 이 3초를 넘는 컷이 연속 2개를 넘지 않음.

그림이 실패하지 않게
- 한 컷에 인물은 2명까지. 단역 무리(사원들, 행인)는 뒷모습이나 흐린 배경으로만.
- 손가락이 화면 가운데 크게 나오는 컷은 INSERT 로만, 행동 하나(쥔다·누른다)로.
- 몸에 거는 작은 소품(사원증·출입증·방문증 목걸이, 명찰, 장신구, 시계, 이어폰)은 쓰지 않음.
  대본에 소품이 필요하면 그 컷에서 손에 들고 있게 쓰거나 INSERT 컷으로 보여 줌. '목에 건' 같은 표현 금지.
- 휴대폰·모니터 화면은 화면이 카메라를 향하게만 쓰고, 화면 글자는 screen_text 에만 적음.
- 로고·간판·회사 이름은 그림 AI가 컷마다 다르게 그리므로 frame 에 쓰지 않음. 회사 로고가 보여야 하는 컷은 "벽의 엠블럼"이라고만 쓰고
  회사 이름·글자는 쓰지 않음 (엠블럼 모양은 장소 기준 그림이 정함).
- 장소 시점: [장소 시점] 목록에 그 장소의 시점(카메라가 향하는 쪽)이 있으면 컷의 view 에 시점 이름 하나를 적음. 없으면 "".
  같은 자리에서 같은 쪽을 보는 컷은 같은 시점. 한 장면에서 시점은 2개까지만 오감 (배경이 컷마다 바뀌면 다른 장소처럼 보임).
  frame 에 배경 묘사(벽, 창, 게이트, 로고)를 따로 쓰지 않음. 시점 그림이 배경을 정함.
- 분장·의상(Make-up & Costume): 인물의 머리·분장·옷은 [분장·의상] 목록의 '룩'이 정함. 컷의 looks 에 {"인물":"룩 이름"}을 적음.
  목록에 있는 이름만 그대로 쓰고, 적지 않으면 '기본'(확정 캐스팅 그림의 차림). 한 장면(S#) 안에서 한 인물의 룩은 하나.
  장소·시간에 맞는 룩을 고름(집 장면에 '집' 룩이 있으면 그것, 회사 장면은 그 시기의 출근 룩). frame 에는 옷·머리 묘사를 따로 쓰지 않음.
  목록에 없는 차림이 대본상 꼭 필요할 때만(잠옷, 환자복, 상복, 몇 년 뒤의 모습) 맨 위 new_looks 에 등록함:
  who(인물), name(짧은 한국어 이름 "집", "환자복"), note_ko(머리·분장·의상 한 줄), desc_en("Hair: …. Make-up: …. Clothing: …." 영어 확정형,
  장신구·로고·글자 없는 단색 옷). 새 룩은 한 화에 인물당 1개까지.
- 손에 드는 소품(가방, 휴대폰, 서류, 방문증, 컵)은 [소품 목록]의 이름을 그대로 쓰고, 그 컷의 props 에 이름을 적음.
  목록에 없는 소품이 필요하면 맨 위 props 에 새로 등록함: name(한국어, 주인 포함 "세영의 노트북 가방"), desc_en(영어 확정형 한 문장:
  종류·색·재질·크기·손잡이·드는 방법. 예 "a slim black nylon laptop briefcase with two short handles, carried by the handles in one hand").
  같은 물건은 화 전체에서 같은 이름 하나만 씀. 가방을 든 인물은 그 장면의 모든 컷에서 같은 가방을 같은 방법으로 듦.

필드
- size: ECU, CU, MCU, MS, MLS, WS, INSERT, 2-SHOT, OTS 중 하나.
- angle: 정면, 3/4 측면, 측면, 뒤에서, 어깨 너머, 하이앵글, 로우앵글, 부감, POV 중 하나.
- camera: 고정, 천천히 다가감, 천천히 물러남, 핸드헬드, 팬, 줌인 중 하나.
- action: 이 컷에서 일어나는 일 요약 (한국어 한 문장, 콘티표 표시용).
- frame_ko / frame_en: 첫 장면. 스틸(영상의 첫 프레임)로 찍을 사진 한 장. 정지된 한 순간, 동사 하나.
  누가 어디에 어떤 자세로 있고 무엇을 손에 들고 어디를 보는지, 화면에 보이는 사물을 빠짐없이 씀.
  '~하고 ~한다', '~하자', '~하면서', '~다가' 처럼 시간이 흐르는 문장 금지. 예: "세영이 열린 게이트 앞에 서서 방문증을 오른손에 쥐고 로비 안쪽을 본다."
- motion_ko / motion_en: 움직임. 첫 장면에서 시작해 영상에서 일어나는 움직임 하나 (3초 안에 끝나는 동작).
  예: "세영이 게이트 사이로 한 걸음 걸어 들어간다." motion 이 "still" 인 컷은 "카메라만 움직인다".
- 기계를 다루는 동작(카드 찍기, 게이트 열림, 키보드 입력, 버튼 누르기, 화면 터치)은 INSERT 컷으로 따로 뺌.
  그 INSERT 컷의 frame 은 "방문증을 쥔 손이 게이트 리더기 바로 앞에 있다" 같은 정지 상태.
- 확정형. '살짝·약간·정도·또는·처럼 보·수 있' 금지. 영어는 'slightly·maybe·or' 금지.
- dialogue: 이 컷에서 들리는 대사 {"who":통일 이름,"text":대사,"on_screen":입이 보이면 true}. 없으면 null.
- screen_text: 휴대폰·모니터·문서에 보이는 글자. 그림에는 글자를 넣지 않고 편집에서 얹으므로 글자만 적음. 없으면 "".
- chars: 화면에 보이는 인물(통일 이름). 손·뒷모습만 보이면 이름 뒤에 ':손' 또는 ':뒷모습'.
- loc: 주어진 장소 id. sfx: 효과음 한 단어(없으면 "").
- 대본에 없는 사건을 만들지 않음. 대사는 대본 문장 그대로.

JSON 만 출력:
{"props":[{"name":"","desc_en":""}],"new_looks":[{"who":"","name":"","note_ko":"","desc_en":""}],
"cuts":[{"no":1,"scene":1,"size":"","angle":"","camera":"","dur":1.5,"motion":"","climax":false,
"chars":[],"looks":{},"props":[],"loc":"L01","view":"","action":"","frame_ko":"","frame_en":"","motion_ko":"","motion_en":"","dialogue":null,"screen_text":"","sfx":""}]}"""

REVIEW = """당신은 한국 실사 숏폼 드라마의 콘티 감수자입니다. 감독이 짠 콘티(JSON)를 받아, 그림 생성 AI가 실패하지 않도록 고칩니다.

컷마다 점검:
1. frame(첫 장면)이 사진 한 장으로 찍을 수 있는 정지된 한 순간인가. 동사가 둘 이상이거나 시간이 흐르면(~하고, ~하자, ~하면서, ~다가) 실패.
   → 앞 동작을 frame 으로, 뒤 동작을 motion 으로 옮기거나, 컷을 둘로 나눔.
2. 기계를 다루는 동작(카드 찍기, 게이트 열림, 키보드 입력, 버튼·화면 터치)이 사람 컷의 frame 에 섞여 있으면 실패. → INSERT 컷을 따로 만듦.
3. frame 에 적힌 사물·화면이 action 에 나온 것과 같은가 (예: action 에 노트북이 있으면 frame 에도 노트북). 빠졌으면 채움.
4. 몸에 거는 소품(목걸이·사원증·명찰·장신구·시계·이어폰)이 있으면 손에 든 상태로 바꿈.
5. 얼굴이 보이는 인물이 3명 이상이면 2명 이하로 (나머지는 뒷모습·흐린 배경).
6. motion 이 3초 안에 끝나는 움직임 하나인가. 둘 이상이면 하나로 줄임.
7. frame 에 회사 이름·로고 글자·간판 글자가 있으면 "벽의 엠블럼"으로 바꾸거나 뺌.
8. 손에 든 소품이 frame 에 나오는데 그 컷 props 에 이름이 없으면 채움. 같은 가방·휴대폰이 컷마다 다른 말(가방/서류가방/노트북 가방)로
   적혀 있으면 [소품 목록]·props 의 이름 하나로 통일. 같은 장면에서 가방을 든 인물이 다음 컷에서 빈손이면 고침.
9. 같은 장면에서 한 인물의 looks 가 컷마다 다르면 하나로 통일. frame 에 옷·머리 묘사가 있으면 뺌 (looks 가 정함). looks 필드는 지우지 않음.

컷을 나누면 길이(dur)를 나눠 담고, 대사는 원문을 그대로 나눠 담음. 고칠 것이 없는 컷은 그대로 둠.
컷 번호(no)는 처음부터 다시 매김. 다른 필드 형식과 규칙(컷 수 14~16, 합계 50~70초)은 감독 콘티와 같음.

JSON 만 출력: {"cuts":[…고친 전체 콘티…], "changes":["무엇을 왜 고쳤는지 한 줄씩"]}"""


def syl(t: str) -> int:
    return len(re.findall(r"[가-힣]", re.sub(r"\([^)]*\)", "", t or "")))


def episode_text(ep: dict, bible: dict | None, props: dict | None = None, looks: dict | None = None, views: dict | None = None) -> str:
    from src import bible as bb
    names = [c["name"] for c in (bible or {}).get("characters", [])]
    plist = "; ".join(f"{n} = {d}" for n, d in (props or {}).items()) or "(아직 없음. 필요한 소품은 props 에 새로 등록)"
    out = [f"[인물 표기] {', '.join(names)}  (chars·dialogue.who 에는 이 이름만 그대로 씀. 목록에 없는 단역은 '신입A'처럼 짧게)",
           f"[소품 목록] {plist}",
           "[장소 시점] " + ("; ".join(f"{lid}: " + ", ".join(f"{k}({v})" for k, v in vs.items())
                                       for lid, vs in (views or {}).items() if vs) or "없음 (view 는 비워 둠)"),
           "[분장·의상] " + ("; ".join(f"{n}: 기본(확정 캐스팅 그림의 차림)" + "".join(f", {k}({v})" for k, v in lk.items())
                                        for n, lk in (looks or {}).items()) or "모든 인물 '기본' 하나"),
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


def _ask(api_key: str, system: str, text: str, model: str = "") -> dict:
    import anthropic
    from json_repair import repair_json
    c = anthropic.Anthropic(api_key=api_key)
    r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=16000, system=system,
                          messages=[{"role": "user", "content": text}])
    txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    data = json.loads(repair_json(txt))
    return data if isinstance(data, dict) else {}


def split(api_key: str, ep: dict, bible: dict | None, model: str = "", review: bool = True, props: dict | None = None,
          looks: dict | None = None, views: dict | None = None) -> dict:
    """looks = {인물: {룩 이름: 한 줄 설명}} (기본 룩 제외). 돌려주는 new_looks = 콘티가 새로 등록한 룩."""
    """콘티 만들기: ① 감독(컷 나누기) → ② 감수(첫 장면이 사진 한 장으로 찍히는지 점검·수정) → ③ 코드 규칙 정리."""
    src = episode_text(ep, bible, props, looks, views)
    first = _ask(api_key, SYSTEM, src, model)
    cuts = first.get("cuts", [])
    new_props = [x for x in (first.get("props") or []) if isinstance(x, dict) and x.get("name")]
    changes = []
    if review and cuts:
        try:
            r = _ask(api_key, REVIEW, f"[대본]\n{src}\n\n[감독 콘티]\n{json.dumps({'props': new_props, 'cuts': cuts}, ensure_ascii=False)}", model)
            if isinstance(r.get("cuts"), list) and len(r["cuts"]) >= max(1, len(cuts) // 2):
                cuts = r["cuts"]
                changes = [str(x) for x in (r.get("changes") or [])][:30]
        except Exception as ex:                       # 감수가 실패해도 감독 콘티는 살림
            changes = [f"감수 단계 오류로 감독 콘티를 그대로 씀: {str(ex)[:100]}"]
    known = dict(props or {})
    for x in new_props:                               # 이미 등록된 소품의 설명은 바꾸지 않는다 (화마다 같은 물건)
        known.setdefault(str(x["name"]).strip(), str(x.get("desc_en", "")).strip())
    out = normalize(cuts, ep, bible)
    nm = name_map(bible)
    new_looks, ok_looks = [], {n: set(lk) for n, lk in (looks or {}).items()}
    for x in (first.get("new_looks") or []):
        if isinstance(x, dict) and x.get("who") and x.get("name") and x.get("desc_en"):
            who, name = canon(str(x["who"]), nm), str(x["name"]).strip()
            if name != "기본" and name not in ok_looks.get(who, set()):
                ok_looks.setdefault(who, set()).add(name)
                new_looks.append({"who": who, "name": name, "note_ko": str(x.get("note_ko", "")).strip(), "desc_en": str(x["desc_en"]).strip()})
    for c in out:
        c["props"] = [n for n in c["props"] if n in known]
        c["looks"] = {w: l for w, l in c["looks"].items() if l in ok_looks.get(w, set())}
        if c["view"] not in (views or {}).get(c["loc"], {}):
            c["view"] = ""
    used = {n for c in out for n in c["props"]}
    return {"cuts": out, "model": model or DEFAULT_MODEL, "changes": changes, "new_looks": new_looks,
            "props": {n: d for n, d in known.items() if n in used or n in (props or {})}}


LOOK_SYSTEM = """한국 실사 드라마의 분장·의상(Make-up & Costume) 담당입니다. 인물의 룩 하나를 영어 확정형으로 씁니다.
그림 생성 AI가 매번 같은 차림을 그리도록 머리 모양, 분장, 옷을 구체적으로 정합니다.
- 형식: "Hair: …. Make-up: …. Clothing: …." 세 문장.
- 옷은 무늬 없는 단색, 차분한 색. 브랜드·로고·글자 없음. 장신구·시계·머리핀·이어폰 없음. 신발까지 정함.
- 얼굴 생김새·나이는 쓰지 않음 (확정 캐스팅 그림이 정함). 'or', 'slightly', 'maybe' 금지.
JSON 만 출력: {"desc_en": ""}"""


def look_desc(api_key: str, who: str, name: str, note: str = "", base: str = "", model: str = "") -> str:
    return str(_ask(api_key, LOOK_SYSTEM, f"인물: {who}\n룩 이름: {name}\n메모(머리·분장·의상): {note or '없음'}\n"
                                          f"기본 차림 참고: {base[:400]}", model).get("desc_en", "")).strip()


PROP_SYSTEM = """한국 실사 드라마의 소품 담당입니다. 소품 이름과 메모를 받아, 그림 생성 AI가 매번 같은 물건을 그리도록 영어 확정형 한 문장으로 씁니다.
종류, 색, 재질, 크기, 손잡이·끈, 드는 방법을 정합니다. 브랜드·로고·글자 없음. 'or', 'slightly', 'maybe' 금지.
예: "a slim black nylon laptop briefcase, about 40 cm wide, with two short black handles and a zipper along the top, carried by the handles in one hand"
JSON 만 출력: {"desc_en": ""}"""


def prop_desc(api_key: str, name: str, note: str = "", model: str = "") -> str:
    return str(_ask(api_key, PROP_SYSTEM, f"소품: {name}\n메모: {note or '없음'}", model).get("desc_en", "")).strip()


def prop_key(name: str) -> str:
    """'세영의 노트북 가방' → '노트북 가방' (콘티 문장에서 소품을 찾을 때 쓰는 말)."""
    return name.split("의 ", 1)[-1].strip()


def fill_props(cuts: list, props: dict, set_loc: dict | None = None) -> list:
    """① props 칸이 빈 컷(예전 콘티)에, 첫 장면 문장에 소품 이름이 나오면 그 소품을 붙인다 (긴 이름부터: '노트북 가방'이 '노트북'보다 먼저).
    ② 장소에 놓인 소품(set_loc = {소품: 장소 id})은 그 장소의 컷 중 얼굴 클로즈업이 아닌 모든 컷에 붙인다."""
    for c in cuts:
        if not c.get("props"):
            text = c.get("frame_ko", "") + " " + c.get("action", "")
            got = []
            for n in sorted(props, key=lambda x: -len(prop_key(x))):
                k = prop_key(n)
                if k and k in text:
                    got.append(n)
                    text = text.replace(k, "□")
            c["props"] = got
        for n, lid in (set_loc or {}).items():
            if lid == c.get("loc") and c.get("size") not in ("ECU", "CU") and n not in c["props"]:
                c["props"].append(n)
    return cuts


BREAKDOWN = """당신은 한국 실사 숏폼 드라마의 조감독입니다. 한 화의 대본을 읽고 촬영 준비물 목록(브레이크다운)을 만듭니다.
이 목록으로 기준 그림을 미리 만들어 두어야 컷마다 배경·소품·옷이 흔들리지 않습니다. 이미 등록된 것은 다시 적지 않습니다.

1. views (장소 시점): 이 화에 나오는 장소마다, 카메라가 실제로 향하게 될 쪽. 장소당 1~3개.
   인물이 서는 자리 뒤로 무엇이 보이는지가 기준. 예: 로비 → "게이트 쪽", "안내데스크 쪽". 회의실 → "세영 자리 쪽", "직원 자리 쪽".
   loc(장소 id), name(짧은 한국어), note_ko(한 줄), desc_en(영어 확정형 한 문장: 카메라가 향하는 쪽과 화면에 들어오는 것. 사람 없음, 글자 없음).
2. props (소품): 이 화에서 화면에 보이는 물건 가운데 두 컷 이상 나오거나 이야기에 중요한 것.
   kind "hand" = 인물이 손에 드는 것(가방, 휴대폰, 서류, 방문증). name 은 주인을 붙임("세영의 노트북 가방").
   kind "set" = 장소에 놓여 있는 것(회의실 전화기, 책상 위 노트북, 모니터). loc 에 장소 id. name 은 장소를 붙임("회의실 전화기").
   desc_en: 종류·색·재질·크기·생김새를 영어 확정형 한 문장. 브랜드·로고·글자 없음. 화면 내용은 쓰지 않음(빈 화면).
3. looks (분장·의상): 이 화에서 '기본' 차림(확정 캐스팅 그림)이 아닌 차림이 꼭 필요한 인물만. 집, 잠옷, 환자복, 상복, 몇 년 뒤.
   who, name, note_ko, desc_en("Hair: …. Make-up: …. Clothing: …." 무늬 없는 단색, 장신구 없음). 회사 장면뿐인 화는 빈 목록.

'or', 'slightly', 'maybe' 금지. 대본에 없는 것을 지어내지 않음.
JSON 만 출력:
{"views":[{"loc":"L01","name":"","note_ko":"","desc_en":""}],
 "props":[{"name":"","kind":"hand","loc":"","note_ko":"","desc_en":""}],
 "looks":[{"who":"","name":"","note_ko":"","desc_en":""}]}"""


def breakdown(api_key: str, ep: dict, bible: dict | None, props: dict | None = None, looks: dict | None = None,
              views: dict | None = None, model: str = "") -> dict:
    """한 화의 준비물(장소 시점·소품·분장의상)을 대본에서 뽑는다. 이미 등록된 이름은 빼고 돌려준다."""
    r = _ask(api_key, BREAKDOWN, episode_text(ep, bible, props, looks, views), model)
    nm = name_map(bible)
    locs = {l["id"] for l in (bible or {}).get("locations", [])}
    out = {"views": [], "props": [], "looks": []}
    for x in r.get("views") or []:
        if isinstance(x, dict) and x.get("loc") in locs and x.get("name") and x.get("desc_en") \
                and str(x["name"]).strip() not in (views or {}).get(x["loc"], {}):
            out["views"].append({k: str(x.get(k, "")).strip() for k in ("loc", "name", "note_ko", "desc_en")})
    for x in r.get("props") or []:
        if isinstance(x, dict) and x.get("name") and x.get("desc_en") and str(x["name"]).strip() not in (props or {}):
            kind = "set" if x.get("kind") == "set" and x.get("loc") in locs else "hand"
            out["props"].append({"name": str(x["name"]).strip(), "kind": kind, "loc": x.get("loc", "") if kind == "set" else "",
                                 "note_ko": str(x.get("note_ko", "")).strip(), "desc_en": str(x["desc_en"]).strip()})
    for x in r.get("looks") or []:
        if isinstance(x, dict) and x.get("who") and x.get("name") and x.get("desc_en"):
            who, name = canon(str(x["who"]), nm), str(x["name"]).strip()
            if name != "기본" and name not in (looks or {}).get(who, {}):
                out["looks"].append({"who": who, "name": name, "note_ko": str(x.get("note_ko", "")).strip(), "desc_en": str(x["desc_en"]).strip()})
    return out


VIEW_SYSTEM = """한국 실사 드라마의 미술 담당입니다. 한 장소의 '시점'(카메라가 서서 바라보는 쪽) 하나를 영어 확정형 한 문장으로 씁니다.
카메라가 어느 쪽을 향하고 화면에 무엇이 들어오는지 씁니다. 사람 없음. 글자·회사 이름 없음. 'or', 'slightly', 'maybe' 금지.
예: "the camera faces the row of security gates with the glass entrance doors behind them, the reception desk out of frame"
JSON 만 출력: {"desc_en": ""}"""


def view_desc(api_key: str, loc_name: str, name: str, note: str = "", model: str = "") -> str:
    return str(_ask(api_key, VIEW_SYSTEM, f"장소: {loc_name}\n시점 이름: {name}\n메모: {note or '없음'}", model).get("desc_en", "")).strip()


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


def unify_looks(cuts: list) -> list:
    """한 장면 안에서 한 인물의 룩은 하나: 그 장면에서 가장 많이 적힌 룩으로 통일한다 (옷이 컷마다 바뀌는 것을 막음)."""
    from collections import Counter
    by = {}
    for c in cuts:
        for ch in c["chars"]:
            w = ch.split(":")[0]
            by.setdefault((c["scene"], w), Counter())[c.get("looks", {}).get(w, "")] += 1
    for c in cuts:
        looks = {}
        for ch in c["chars"]:
            w = ch.split(":")[0]
            top = by[(c["scene"], w)].most_common(1)[0][0]
            if top:
                looks[w] = top
        c["looks"] = looks
    return cuts


def need_sec(c: dict) -> float:
    """대사가 들어갈 최소 길이 (한국어 1초 4음절 + 0.3초)."""
    return syl(c["dialogue"]["text"]) / 4 + 0.3 if c.get("dialogue") else DUR_MIN


def cap_sec(c: dict, last: bool = False) -> float:
    """컷 하나의 최대 길이: 버티기 컷 6초, 말하는 얼굴 2.5초, 정지 컷 3초, 보통 4초. 대사가 더 길면 대사 길이."""
    top = HOLD_MAX if c.get("climax") else STILL_MAX if c.get("motion") == "still" else DUR_MAX
    if c.get("dialogue") and c["dialogue"].get("on_screen"):
        top = TALK_MAX
    return max(top, need_sec(c))


def fit_durations(cuts: list, lo: float = 50, target: float = 56, hi: float = 70) -> list:
    """대사 길이를 먼저 맞추고, 합계가 50초 미만이면 56초 쪽으로, 70초 초과면 줄여서 맞춘다.
    컷마다 상한(cap_sec)이 있어서 늘릴 여유가 있는 컷만 늘어난다. 그래도 모자라면 점검에서 알린다."""
    n = len(cuts)
    for i, c in enumerate(cuts):
        c["dur"] = round(min(cap_sec(c, i == n - 1), max(c["dur"], need_sec(c), DUR_MIN)), 1)
    for _ in range(4):
        total = sum(c["dur"] for c in cuts)
        if not cuts or lo <= total <= hi:
            break
        k = target / total
        for i, c in enumerate(cuts):
            c["dur"] = round(min(cap_sec(c, i == n - 1), max(need_sec(c), DUR_MIN, c["dur"] * k)), 1)
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
            "view": str(c.get("view") or "").strip(),
            "props": [str(x).strip() for x in (c.get("props") or []) if str(x).strip()],
            "looks": {canon(str(k), nm): str(v).strip() for k, v in (c.get("looks") or {}).items()
                      if str(v).strip() and str(v).strip() != "기본"} if isinstance(c.get("looks"), dict) else {},
            "loc": str(c.get("loc", "")), "action": str(c.get("action", "")).strip(),
            "action_en": str(c.get("action_en", "")).strip(),
            "frame_ko": str(c.get("frame_ko") or c.get("action") or "").strip(),
            "frame_en": str(c.get("frame_en") or c.get("action_en") or "").strip(),
            "motion_ko": str(c.get("motion_ko") or "").strip(),
            "motion_en": str(c.get("motion_en") or c.get("action_en") or "").strip(), "dialogue": d,
            "screen_text": str(c.get("screen_text") or ""), "sfx": str(c.get("sfx") or ""),
        })
    return fit_durations(cap_video(unify_looks(out)))


def cap_video(cuts: list, limit: int = MAX_VIDEO, moving: int = MAX_MOVING) -> list:
    """움직임 규칙을 코드로 강제한다.
    - 마지막 컷·클라이맥스는 완전 영상. 클라이맥스(버티기 컷)는 화당 1개만 남김(가장 긴 컷).
    - 말하는 얼굴이 보이는 컷은 정지 (립싱크 없음).
    - 완전 영상이 상한을 넘으면 짧은 움직임으로, 영상 생성 컷 전체가 상한을 넘으면 짧은 컷부터 정지로 낮춘다."""
    if not cuts:
        return cuts
    clx = [c for c in cuts if c["climax"]]
    if len(clx) > 1:
        keep = max(clx, key=lambda c: c["dur"])
        for c in clx:
            c["climax"] = c is keep
    for c in cuts:
        if c.get("dialogue") and c["dialogue"].get("on_screen"):
            c["motion"] = "still"
    cuts[-1]["motion"] = "video"
    for c in cuts:
        if c["climax"]:
            c["motion"] = "video"
    locked = lambda c: c["climax"] or c is cuts[-1]
    vids = [c for c in cuts if c["motion"] == "video"]
    if len(vids) > limit:
        for c in sorted((c for c in vids if not locked(c)), key=lambda c: -c["dur"])[: len(vids) - limit]:
            c["motion"] = "move"
    mov = [c for c in cuts if c["motion"] in ("move", "video")]
    if len(mov) > moving:
        spare = sorted((c for c in mov if not locked(c)), key=lambda c: (c["motion"] == "video", c["dur"]))
        for c in spare[: len(mov) - moving]:
            c["motion"] = "still"
    return cuts


def check(cuts: list, known_chars: set, known_locs: set, scenes: list | None = None) -> list[dict]:
    """컷 목록 점검 → [{'id','level':'fix'|'todo'|'info','msg'}]"""
    from src.imagegen import banned_in
    issues = []
    if not cuts:
        return [{"id": "-", "level": "fix", "msg": "컷이 없습니다"}]
    total = sum(c["dur"] for c in cuts)
    if not (CUTS_LO <= len(cuts) <= CUTS_HI):
        issues.append({"id": "-", "level": "todo", "msg": f"컷 {len(cuts)}개 (기준 14~16개, 허용 {CUTS_LO}~{CUTS_HI}개)"})
    if not (50 <= total <= 70):
        issues.append({"id": "-", "level": "todo", "msg": f"합계 {total:.1f}초 (기준 50~70초)"})
    if scenes:
        miss = [n for n in scenes if n not in {c["scene"] for c in cuts}]
        if miss:
            issues.append({"id": "-", "level": "fix", "msg": "컷이 없는 장면: " + ", ".join(f"S#{n}" for n in miss)})
    nv = sum(1 for c in cuts if c["motion"] == "video")
    nm = sum(1 for c in cuts if c["motion"] in ("move", "video"))
    if nv > MAX_VIDEO:
        issues.append({"id": "-", "level": "todo", "msg": f"완전 영상 컷 {nv}개 (상한 {MAX_VIDEO}개, 비용·실패 위험)"})
    if nm > MAX_MOVING:
        issues.append({"id": "-", "level": "todo", "msg": f"영상 생성 컷 {nm}개 (상한 {MAX_MOVING}개, 컷마다 최소 3초 과금)"})
    if sum(1 for c in cuts if c["climax"]) > 1:
        issues.append({"id": "-", "level": "todo", "msg": "버티기 컷(클라이맥스)이 2개 이상"})
    if cuts[-1]["motion"] != "video":
        issues.append({"id": cuts[-1]["id"], "level": "fix", "msg": "마지막 '끊김' 컷은 완전 영상이어야 함"})
    run = 0
    for c in cuts:
        run = run + 1 if (c["motion"] == "still" and c["dur"] > 3.0) else 0
        if run > 2:
            issues.append({"id": c["id"], "level": "fix", "msg": "3초 넘는 정지 컷이 3개 연속 (PPT식으로 보임)"})
        if c["climax"] and c["motion"] != "video":
            issues.append({"id": c["id"], "level": "fix", "msg": "클라이맥스 컷은 완전 영상이어야 함"})
        if not c["climax"] and c["dur"] > DUR_MAX + 0.05 and not c.get("dialogue"):
            issues.append({"id": c["id"], "level": "todo", "msg": f"{c['dur']}초: 4초 넘는 보통 컷 (둘로 나누면 호흡이 빨라짐)"})
        if c["size"] not in SIZES:
            issues.append({"id": c["id"], "level": "todo", "msg": f"샷 크기 '{c['size']}' 확인"})
        if c["loc"] and known_locs and c["loc"] not in known_locs:
            issues.append({"id": c["id"], "level": "fix", "msg": f"장소 id '{c['loc']}' 가 바이블에 없음"})
        if len([x for x in c["chars"] if ":" not in x]) > 2:
            issues.append({"id": c["id"], "level": "todo", "msg": "얼굴이 보이는 인물 3명 이상 (얼굴이 흔들릴 위험)"})
        for ch in c["chars"]:
            base = ch.split(":")[0]
            if known_chars and base not in known_chars:
                issues.append({"id": c["id"], "level": "info", "msg": f"단역 '{base}' (바이블 밖 인물, 기준 이미지 없이 생성)"})
        d = c["dialogue"]
        if d:
            need = syl(d["text"]) / 4 + 0.2
            if need > c["dur"] + 0.05:
                issues.append({"id": c["id"], "level": "fix", "msg": f"대사 {syl(d['text'])}음절: 최소 {need:.1f}초 필요 (현재 {c['dur']}초)"})
            if d.get("on_screen") and c["motion"] != "still":
                issues.append({"id": c["id"], "level": "fix", "msg": "말하는 얼굴이 영상 컷 (립싱크 없음 → 정지 컷으로)"})
            if d.get("on_screen") and c["dur"] > TALK_MAX + 0.05:
                issues.append({"id": c["id"], "level": "todo", "msg": f"말하는 얼굴 {c['dur']}초 (2.5초 넘는 부분은 듣는 사람 컷으로 넘기기)"})
        if LOGO_WORDS.search(c.get("frame_ko", "") + " " + c.get("frame_en", "")):
            issues.append({"id": c["id"], "level": "todo", "msg": "첫 장면에 로고·간판 표현 (컷마다 다르게 그려짐 → '벽의 엠블럼'으로, 글자는 편집에서)"})
        if FLOW_WORDS.search(c.get("frame_ko", "")):
            issues.append({"id": c["id"], "level": "todo", "msg": "첫 장면에 동작이 둘 이상 (사진 한 장으로 찍히는 한 순간으로)"})
        if WEAR_WORDS.search(c["action"] + " " + c.get("frame_ko", "")):
            issues.append({"id": c["id"], "level": "fix", "msg": "몸에 거는 소품 표현 (손에 들거나 인서트로)"})
        for b in banned_in(" ".join([c["action"], c.get("frame_ko", ""), c.get("frame_en", ""), c.get("motion_en", "")])):
            issues.append({"id": c["id"], "level": "fix", "msg": f"행동 문장 금지어 {b}"})
    return issues


LOGO_WORDS = re.compile(r"로고|CI\b|간판|logo|signage", re.I)


EMBLEM_MASTER = ("The company emblem on the wall is exactly the emblem in the reference image: the same geometric shape made of "
                 "brushed metal panels, mounted once on the wall, with no letters, no company name and no other logo anywhere.")


def no_logo_words(text: str) -> str:
    """지시문에서 회사 이름이 붙은 로고 표현을 'company emblem' 으로 바꾼다 ("Daesung Group CI logo" → "company emblem")."""
    t = re.sub(r"\b(?:[A-Z][A-Za-z&]+ ){1,3}(?:CI |corporate |brand )?logo\b", "company emblem", text)
    return re.sub(r"(?i)\b(CI |company |corporate |brand )?logo\b", "company emblem", t)


def shows_emblem(c: dict) -> bool:
    """이 컷에 벽 엠블럼이 보이는가: 첫 장면에 로고·엠블럼이 적혀 있거나, 공간이 넓게 보이는 컷."""
    text = c.get("frame_ko", "") + " " + c.get("frame_en", "") + " " + c.get("action", "")
    return bool(LOGO_WORDS.search(text) or re.search(r"엠블럼|emblem", text, re.I)) or c.get("size") in ("WS", "MLS")


def still_prompt(c: dict, cast: dict, locs: dict, refs: list[str] | None = None, props: dict | None = None,
                 look_text: dict | None = None, set_props: set | None = None) -> str:
    """스틸(컷 그림) 지시문: 영어, 확정형. cast[name]=외모 영어 묘사, locs[id]=(이름, 영어 묘사).
    refs = 함께 넣는 기준 그림 순서 (인물 이름 또는 장소 id). 지시문에서 '기준 그림 몇 번'으로 짚어 준다."""
    refs = refs or []
    pos = {r: i for i, r in enumerate(refs, start=1)}
    who = []
    for ch in c["chars"]:
        base, _, part = ch.partition(":")
        desc = cast.get(base, base)
        lt = (look_text or {}).get(base)               # (룩 영어 설명, 룩 기준 그림이 있는가)
        if base in pos and lt and not lt[1]:           # 룩 그림이 아직 없음: 얼굴만 기준 그림에서, 머리·분장·옷은 글로
            tag = (f"the person in reference image {pos[base]}: the same face only; the hair, make-up and clothing of that "
                   f"reference are replaced by this look: {lt[0].rstrip('. ')}")
        elif base in pos and lt:
            tag = f"the person in reference image {pos[base]}, same face, hair, make-up and outfit as that reference ({lt[0].rstrip('. ')})"
        elif base in pos:
            tag = f"the person in reference image {pos[base]}, same face, hair and outfit"
        else:
            tag = desc + (f", {lt[0].rstrip('. ')}" if lt else "")
        if f"{base}@정면" in pos:
            tag += f" (reference image {pos[base + '@정면']} shows the same person from the front)"
        who.append(f"{tag}, only the hands visible" if part == "손" else f"{tag}, seen from behind" if part == "뒷모습" else tag)
    loc = locs.get(c["loc"], ("", ""))
    tight = c["size"] in ("ECU", "CU", "INSERT")
    if c["loc"] in pos:
        # 장소 기준 그림이 있으면 긴 장소 설명문을 다시 넣지 않는다: 설명문 속 로고·간판·게이트를 컷마다 새로 그려 넣는 원인.
        place = (f"the same room as reference image {pos[c['loc']]}: same architecture, materials, furniture and light. "
                 "The camera shows only the part of the room this shot needs. Every wall emblem and every sign keeps exactly the shape, "
                 "color and position it has in that reference, with no letters added and no new logo invented")
        if c["loc"] + "@전경" in pos:
            place += (f". Reference image {pos[c['loc'] + '@전경']} is the wide master of this same room, for layout and materials only; "
                      f"the background of this shot is the view in reference image {pos[c['loc']]}")
        if "엠블럼" in pos:
            place += (f". Where that location reference shows a wall emblem, it is exactly the emblem in reference image {pos['엠블럼']}: "
                      "the same geometric shape of brushed metal panels, in the same place, no letters beside it. "
                      "Where the location reference shows no emblem, this shot shows no emblem")
    else:
        place = (loc[1] or loc[0]).rstrip(". ") + ". Every sign and every emblem is a plain abstract shape with no letters"
    plist, slist = [], []
    for n in c.get("props", []):
        d = (props or {}).get(n) or n
        (slist if n in (set_props or set()) else plist).append(
            f"{d}, the same object as reference image {pos['소품:' + n]}" if "소품:" + n in pos else d)
    lines = [f"Vertical 9:16 still frame from a Korean drama. {SHOT_EN.get(c['size'], 'medium shot').capitalize()}, {ANG_EN.get(c['angle'], 'eye level')}.",
             "Scene, one frozen moment: " + re.sub(r"(?i)\b(CI |company |corporate |brand )?logo\b", "wall emblem",
                                                    c.get("frame_en") or c.get("action_en") or c["action"]),
             ("Characters: " + "; ".join(who) + ".") if who else "No people in frame.",
             f"Location: {place}" + (", background softly blurred." if tight else "."),
             ("Reference images are identity and set references only: keep faces, hair, clothing and the room exactly, "
              "wear no accessories even if a reference shows one, and take pose, framing and expression from this description.") if refs else "",
             ("Props, exactly these objects, with no other bag and no other item in the hands: " + "; ".join(plist) + ".") if plist else "",
             ("Objects that stand in the room and are never held; wherever one of them is in frame it is exactly this object, "
              "one of each: " + "; ".join(slist) + ".") if slist else "",
             "Any prop named in the scene is held in the hands only, never worn.",
             f"Any screen or paper in frame is blank; text is added in editing." if c["screen_text"] else "No text anywhere in the image."]
    return " ".join(x for x in lines if x)


def clip_seconds(dur: float) -> int:
    """컷 길이 → 영상 모델에 줄 초 (3~15초 정수, 남는 부분은 편집에서 자름)."""
    return max(3, min(15, math.ceil(float(dur or 3))))


def video_prompt(c: dict, cast: dict) -> str:
    who = [cast.get(ch.split(":")[0], ch) for ch in c["chars"]]
    dl = "Any voice is added in editing: nobody in frame moves their lips, mouths stay closed." if c["dialogue"] else ""
    mv = {"still": "Almost no motion: only a slow camera move on the still image.",
          "move": "One small, simple movement only, as described; everything else stays still. Mouth closed.",
          "video": "Full natural acting motion as described."}[c["motion"]]
    parts = [f"Shot: {SHOT_EN.get(c['size'], 'medium shot')}, {ANG_EN.get(c['angle'], 'eye level')}, vertical 9:16.",
             f"Camera: {CAM_EN.get(c['camera'], CAM_EN['고정'])}",
             ("Characters: " + "; ".join(who) + ".") if who else "",
             f"First frame: {c.get('frame_en') or c.get('action_en') or c['action']}",
             f"Motion from the first frame: {c.get('motion_en') or c.get('action_en') or c['action']}", mv, dl,
             "Keep the face, hair and clothing of the first frame unchanged for the whole clip; no new people enter the frame.",
             f"Duration: {clip_seconds(c['dur'])} seconds. Photoreal, natural light, no text on screen."]
    return " ".join(x for x in parts if x)
