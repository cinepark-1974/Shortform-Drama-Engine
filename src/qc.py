"""자동 검수: 스틸·영상을 Claude 가 보고 합격/불합격을 판정한다 (2026-11-12, v0.5).

사람이 매 컷을 보지 않도록, 생성 직후 엔진이 스스로 본다.
- 스틸: 방금 만든 그림 + 그 컷의 기준 그림(인물 확정·장소 마스터) + 지시문 → 항목별 판정.
  불합격이면 이유를 고치는 영어 문장(fix_en)을 지시문에 붙여 다시 만든다 (컷당 최대 2회, main.py).
- 영상: 테이크에서 뽑은 첫·중간·마지막 장면 3장 + 확정 스틸 → 얼굴·의상 유지, 인물 추가, 글자, 손 판정.
- 영상 움직임 (2026-11-14 추가): '정지 사진에 카메라만 움직인 영상'이 영상으로 통과되던 문제를 막는다.
  Claude 에게 보내기 전에 엔진이 직접 앞뒤 장면 차이를 잰다 (motion). 카메라 줌·팬을 맞춘 뒤에도 남는 변화 = 인물이 실제로 움직인 양.
  편집에서 실제로 쓰는 구간(컷 길이만큼)에서 재고, 클립 안에서 가장 많이 움직이는 구간의 시작 시각을 찾아 편집에 넘긴다.

Claude 이미지 입력 형식: messages content 에 {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":…}}.
그림은 긴 변 768px 로 줄여 보낸다 (판정에는 충분하고 비용을 줄임).
"""
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import tempfile

DEFAULT_MODEL = "claude-sonnet-4-6"
SIDE = 768

ITEMS = {
    "subject": "첫 장면에 적힌 대상(인물·사물·화면)이 모두 그림에 있다",
    "action": "첫 장면의 자세·시선·손에 든 것이 그림과 같고, 물건이 몸이나 기계에 파묻히는 등 물리적으로 말이 안 되는 곳이 없다",
    "props": "몸에 거는 소품이 없다 (사원증·출입증·방문증 목걸이, 명찰, 귀걸이·목걸이·반지·팔찌·시계, 머리핀, 이어폰, 글자·로고 있는 옷)",
    "identity": "기준 그림의 인물과 같은 사람이다 (얼굴, 머리 모양, 앞머리, 옷 색·종류)",
    "text": "그림 안 어디에도 글자·숫자가 없다: 벽 로고 옆 회사 이름, 간판, 화면, 종이 포함 (빈 화면·빈 종이·글자 없는 도형 엠블럼은 합격)",
    "set": "장소 기준 그림과 같은 공간이고, 벽 엠블럼·간판이 보이면 기준 그림과 같은 모양·같은 위치다 (새 로고를 지어내지 않았다)",
    "prop": "손에 든 소품이 소품 기준 그림·소품 설명과 같은 종류·색·모양의 물건이다 (노트북 가방이 클러치나 토트백으로 바뀌지 않았다)",
    "anatomy": "손가락·팔·얼굴이 자연스럽고, 지시보다 많은 인물이 앞쪽에 나오지 않았다",
}
CLIP_ITEMS = {
    "identity": "세 장면 모두 확정 스틸과 같은 얼굴·머리 모양·옷이다 (마지막 장면에서 얼굴이 바뀌지 않았다)",
    "people": "확정 스틸에 없던 인물이 새로 나타나지 않았다",
    "text": "화면에 글자·자막·로고가 생기지 않았다",
    "anatomy": "손가락·팔·얼굴이 뭉개지거나 녹지 않았다",
    "lips": "말하지 않는 컷에서 입을 크게 움직이지 않는다",
    "action": "'일어나야 할 움직임'이 일어난다 (정지된 채로 끝나거나 엉뚱한 동작이 아니다)",
    "motion": "인물·사물이 실제로 움직인다. 카메라만 다가가거나 흔들리고 사람은 사진처럼 멈춰 있으면 불합격 (편집에서 쓰는 구간 기준)",
}

# 검수 응답에 고치는 문장(fix_en)이 비었을 때 항목별로 붙이는 기본 문장
GENERIC_FIX = {
    "subject": "Every object and screen named in the scene is clearly visible in the frame.",
    "action": "The pose and action match the scene description exactly.",
    "props": "Nothing hangs around the neck and no accessories are worn; props are held in the hands only.",
    "identity": "The face, hairstyle, bangs and clothing match the reference image of the character exactly.",
    "text": "Every screen and paper in frame is blank with no letters.",
    "anatomy": "Natural hands with five fingers each; only the named characters appear in the foreground.",
    "set": "The room and any wall emblem match the location reference exactly: same shape, same position, no new logo.",
    "prop": "The hand prop is exactly the object described in the props line, same type, color and shape.",
    "people": "No new person enters the frame during the clip.",
    "lips": "Mouths stay closed for the whole clip.",
    "motion": "From the very first second the character physically performs the action with continuous, clearly visible body movement; live-action footage, not a still photo with camera movement.",
}

STILL_SYSTEM = """당신은 한국 실사 드라마 숏폼의 스크립터(연속성 담당)입니다. 방금 생성된 컷 그림 한 장을 검수합니다.
첫 번째 그림이 검수할 컷 그림입니다. 그 뒤의 그림은 기준 그림(인물 확정 그림, 장소 마스터)이며 이름표를 붙여 보냅니다.

항목마다 합격(true)/불합격(false)을 판정합니다. 애매하면 합격입니다. 분명히 틀린 것만 불합격으로 합니다.
- 기준 그림이 없는 항목(예: 단역, 인물 없음)은 합격.
- identity 는 얼굴형·눈·머리 모양·앞머리·옷 종류와 색으로 봅니다. 조명·표정·각도 차이는 불합격 사유가 아닙니다.
- 기준 그림에 장신구·목걸이가 있어도 컷 그림에는 없어야 합격입니다 (props).
- 지시문에 손에 든 소품(방문증, 휴대폰, 서류)이 있으면 손에 든 것은 합격, 목에 걸었으면 불합격입니다.
- 분장·의상: 인물 기준 그림은 그 컷에 배정된 룩의 그림입니다. 머리 모양·옷이 기준 그림과 다르면 identity 불합격입니다.
  다만 생성 지시문에 "replaced by this look"이 있으면 그 인물의 기준 그림은 얼굴만 기준이고, 머리·옷은 지시문의 look 설명과 비교합니다.
- 장소 기준 그림이 그 컷의 배경입니다. 벽·창·가구의 종류와 배치가 기준 그림과 다른 방처럼 보이면 set 불합격입니다.
  장소 기준 그림에 엠블럼이 없는데 컷 그림에 엠블럼이 생겼으면 set 불합격입니다. '@전경' 이름표 그림은 같은 방의 넓은 전경입니다.
- 방에 놓인 소품(전화기, 모니터 등)도 '소품:' 기준 그림과 다른 종류의 물건이면 prop 불합격입니다 (회의용 스피커폰이 일반 전화기로 바뀜).
- '엠블럼' 이름표가 붙은 기준 그림은 벽에 걸린 회사 엠블럼입니다. 그림 AI는 로고의 선 하나하나를 똑같이 그리지 못하므로 느슨하게 봅니다.
  컷 그림의 엠블럼이 글자 없는 은색 금속 패널 도형이고 전체 인상이 기준과 비슷하면 합격입니다 (패널의 각도·틈·개수가 조금 다른 것은 합격).
  전혀 다른 로고(원형·글자·다른 색), 엠블럼이 둘 이상, 옆에 글자가 있는 경우만 set 불합격입니다. 엠블럼이 화면에 안 보이는 것은 합격입니다.
- '소품:' 이름표가 붙은 기준 그림은 그 소품의 생김새입니다. 컷 그림 속 소품이 다른 종류의 물건이면 prop 불합격입니다. 소품이 없는 컷은 prop 합격.
- 생성 지시문에 "The only writing in the image is the printed text …" 가 있으면 그 글자가 소품에 인쇄된 것은 합격입니다.
  그 글자가 틀리게 쓰였거나(다른 글자, 깨진 한글) 그 밖의 글자가 있으면 text 불합격입니다. 소품이 작아 글자를 읽을 수 없는 크기면 합격입니다.
- 휴대폰·모니터 화면은 꺼진 검은 화면이어야 합니다. 화면에 글자·한자·깨진 글자·아이콘·통화 화면·사람 얼굴이 보이면 text 불합격이고,
  fix_en 은 "The phone screen is switched off: plain black glass with no characters, no icons and no interface." 처럼 씁니다.
- 글자는 엄격하게 봅니다. 벽 로고 옆에 회사 이름 같은 글자가 한 줄이라도 있으면 text 불합격이고,
  fix_en 은 "The wall shows only the abstract emblem from the location reference, with no lettering anywhere." 처럼 씁니다.

불합격 항목마다:
- reason: 무엇이 틀렸는지 한국어 한 문장 (예: "목에 사원증 목걸이가 걸려 있다").
- fix_en: 다시 만들 때 지시문 끝에 붙일 영어 확정형 한 문장 (예: "Nothing hangs around her neck; her neck and chest are bare above the turtleneck.").
  'slightly', 'or', 'maybe' 금지.

JSON 만 출력:
{"items":{"subject":true,"action":true,"props":true,"identity":true,"text":true,"set":true,"prop":true,"anatomy":true},
 "fails":[{"item":"","reason":"","fix_en":""}]}"""

CLIP_SYSTEM = """당신은 한국 실사 드라마 숏폼의 영상 검수자입니다. 이미지 생성 영상(첫 프레임 = 확정 스틸)의 한 테이크를 검수합니다.
첫 번째 그림은 확정 스틸, 이어지는 세 장은 테이크의 첫 장면·중간 장면·마지막 장면입니다.

항목마다 합격(true)/불합격(false)을 판정합니다. 애매하면 합격입니다. 분명히 틀린 것만 불합격으로 합니다.
- 카메라 이동으로 크기·구도가 바뀌는 것은 정상입니다. 얼굴과 옷이 다른 사람처럼 바뀐 것만 불합격입니다.
- 예외: action·motion 두 항목은 애매하면 불합격입니다. 장면들 사이에서 팔·손·고개·몸의 위치가 바뀌었는지 직접 비교합니다.
  카메라만 다가가거나 옆으로 흐르고 인물의 자세가 모든 장면에서 같으면 '정지 사진에 카메라만 움직인 것'이므로 motion 불합격입니다.
- 엔진이 잰 움직임 수치가 함께 오면 참고합니다 (인물 움직임 수치가 낮으면 정지일 가능성이 큽니다).

불합격 항목마다 reason(한국어 한 문장)과 fix_en(다시 만들 때 영상 지시문 끝에 붙일 영어 확정형 한 문장).

JSON 만 출력:
{"items":{"identity":true,"people":true,"text":true,"anatomy":true,"lips":true,"action":true,"motion":true},
 "fails":[{"item":"","reason":"","fix_en":""}]}"""


def small_jpg(data: bytes, side: int = SIDE) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _img(data: bytes) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.b64encode(small_jpg(data)).decode()}}


def _ask(api_key: str, system: str, content: list, model: str = "", base_url: str | None = None) -> dict:
    import anthropic
    from json_repair import repair_json
    c = anthropic.Anthropic(api_key=api_key, **({"base_url": base_url} if base_url else {}))
    r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=1500, system=system,
                          messages=[{"role": "user", "content": content}])
    txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    data = json.loads(repair_json(txt))
    return data if isinstance(data, dict) else {}


def clean_fix(t: str) -> str:
    """검수가 쓴 고치는 문장에서 지시문 금지어를 뺀다 (금지어가 있으면 그 컷을 다시 만들 수 없게 막히므로)."""
    import re
    t = re.sub(r"\s+or\s+", " and ", t.strip())
    t = re.sub(r"(?i)\b(slightly|maybe|somewhat|a bit|perhaps|approximately|about)\s+", "", t)
    return t


def _result(data: dict, keys: dict) -> dict:
    """응답 형식을 그대로 믿지 않는다: 항목은 정해진 이름만, 불합격 항목엔 이유가 있게."""
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    items = {k: bool(items.get(k, True)) for k in keys}
    fails = []
    for f in data.get("fails") or []:
        if isinstance(f, dict) and f.get("item") in keys:
            items[f["item"]] = False
            fails.append({"item": f["item"], "reason": str(f.get("reason", "")).strip(),
                          "fix_en": clean_fix(str(f.get("fix_en", "")))})
    for k, ok in items.items():                     # items 에선 불합격인데 fails 에 이유가 없을 때
        if not ok and k not in {f["item"] for f in fails}:
            fails.append({"item": k, "reason": keys[k] + " (불합격)", "fix_en": ""})
    return {"pass": all(items.values()), "items": items, "fails": fails}


def judge_still(api_key: str, still: bytes, refs: list[tuple[str, bytes]], cut: dict, prompt: str,
                model: str = "", base_url: str | None = None) -> dict:
    """컷 그림 한 장 검수 → {'pass', 'items', 'fails':[{'item','reason','fix_en'}]}.
    refs = [(이름, 바이트)] 인물 확정 그림·장소 마스터 (스틸 생성 때 넣은 것과 같은 것)."""
    d = cut.get("dialogue")
    head = (f"[컷 {cut.get('id')}] {cut.get('size')} · {cut.get('angle')}\n"
            f"첫 장면(이 그림이 보여 줘야 할 정지 상태): {cut.get('frame_ko') or cut.get('action')}\n"
            f"영어: {cut.get('frame_en') or cut.get('action_en')}\n"
            f"화면에 보이는 인물: {', '.join(cut.get('chars') or []) or '없음'}\n"
            f"손에 든 소품: {', '.join(cut.get('props') or []) or '없음'}\n"
            f"분장·의상(룩): {', '.join(f'{w} = {l}' for w, l in (cut.get('looks') or {}).items()) or '기본'}\n"
            + (f"화면 글자(편집에서 얹음, 그림엔 빈 화면): {cut['screen_text']}\n" if cut.get("screen_text") else "")
            + (f"대사: {d['who']} {d['text']}\n" if d else "")
            + "\n검수 항목:\n" + "\n".join(f"- {k}: {v}" for k, v in ITEMS.items())
            + f"\n\n생성 지시문(참고):\n{prompt[:2500]}")
    content = [{"type": "text", "text": head}, {"type": "text", "text": "검수할 컷 그림:"}, _img(still)]
    for name, data in refs:
        if data:
            content += [{"type": "text", "text": f"기준 그림 · {name}:"}, _img(data)]
    return _result(_ask(api_key, STILL_SYSTEM, content, model, base_url), ITEMS)


def frames(video: bytes, times: list[float] | None = None) -> list[bytes]:
    """영상에서 장면을 JPG 로 (ffmpeg). times 가 없으면 첫·중간·마지막 3장. 실패하면 빈 목록."""
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.mp4")
        with open(src, "wb") as f:
            f.write(video)
        dur = duration(src)
        if dur <= 0:
            return []
        out = []
        for i, t in enumerate(times or [0.05, dur / 2, max(0.0, dur - 0.15)]):
            t = max(0.0, min(float(t), dur - 0.1))
            dst = os.path.join(td, f"f{i}.jpg")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1",
                            "-vf", f"scale='min({SIDE},iw)':-2", dst], capture_output=True, timeout=60)
            if os.path.exists(dst):
                with open(dst, "rb") as f:
                    out.append(f.read())
        return out


def duration(path: str) -> float:
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=60)
        return float(p.stdout.strip() or 0)
    except Exception:
        return 0.0


# ── 움직임 측정 ──────────────────────────────────────────────
# 영상을 1초에 MFPS 장, 가로 MW x 세로 MH 흑백으로 줄인 뒤, 0.5초 떨어진 두 장면을 비교한다.
#  total   : 그냥 뺀 차이 (카메라가 움직여도 커짐)
#  subject : 앞 장면을 확대·축소(줌)하고 상하좌우로 밀어(팬) 뒤 장면에 가장 잘 맞춘 뒤에도 남는 차이
#            → 카메라 움직임을 빼고 남은 '인물·사물의 실제 움직임'
# 수치 단위: 0~255 밝기 차이의 평균. 압축 잡음만 있는 정지 영상은 대략 0.3 안팎.
MFPS, MW, MH, GAP = 6, 96, 160, 3            # GAP 장 = 0.5초 간격으로 비교
FROZEN_TOTAL = 0.6                          # 화면 전체 변화가 이보다 작으면 '화면 정지'
STILL_SUBJECT = 0.9                         # 카메라를 맞춘 뒤 남는 변화가 이보다 작으면 '카메라만 움직임'
WEAK_SUBJECT = 1.8                          # 이보다 작으면 움직임이 약함 → Claude 판정에 수치를 함께 보냄


def _gray_frames(path: str, start: float = 0.0, length: float = 0.0):
    import numpy as np
    args = ["ffmpeg", "-v", "error"] + (["-ss", f"{start:.2f}"] if start else []) + ["-i", path] \
        + (["-t", f"{length:.2f}"] if length else []) \
        + ["-vf", f"fps={MFPS},scale={MW}:{MH}:flags=area,format=gray", "-f", "rawvideo", "-"]
    p = subprocess.run(args, capture_output=True, timeout=120)
    n = len(p.stdout) // (MW * MH)
    if n < 2:
        return None
    return np.frombuffer(p.stdout[: n * MW * MH], dtype=np.uint8).reshape(n, MH, MW).astype(np.float32)


def _pair(a, b) -> tuple[float, float]:
    """두 장면 → (total, subject). 가운데 부분만 비교해 가장자리(줌·팬으로 새로 드러나는 곳)를 뺀다.
    subject: 앞 장면을 화면 가운데 기준으로 확대·축소하고 밀어서(소수 픽셀 단위) 뒤 장면에 가장 잘 맞춘 뒤 남는 차이."""
    import numpy as np
    from PIL import Image, ImageFilter
    m = 12                                       # 가장자리 여백(픽셀)
    ia = Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))
    cb = np.asarray(Image.fromarray(b.astype(np.uint8)).filter(ImageFilter.GaussianBlur(1)), dtype=np.float32)[m:MH - m, m:MW - m]
    cx, cy = MW / 2, MH / 2

    def diff(sc, tx, ty):
        w = ia.transform((MW, MH), Image.AFFINE, (1 / sc, 0, cx - (cx + tx) / sc, 0, 1 / sc, cy - (cy + ty) / sc), Image.BILINEAR)
        return float(np.abs(np.asarray(w, dtype=np.float32)[m:MH - m, m:MW - m] - cb).mean())

    total = diff(1.0, 0, 0)
    best = (total, 1.0, 0.0, 0.0)
    for sc in (0.96, 0.97, 0.98, 0.99, 1.01, 1.02, 1.03, 1.04):          # 1) 줌
        best = min(best, (diff(sc, 0, 0), sc, 0.0, 0.0))
    s0 = best[1]
    for ty in range(-6, 7):                                             # 2) 팬 (1픽셀 단위)
        for tx in range(-6, 7):
            best = min(best, (diff(s0, tx, ty), s0, float(tx), float(ty)))
    _, s1, x1, y1 = best
    for sc in (s1 - 0.005, s1, s1 + 0.005):                             # 3) 소수 단위 다듬기
        for ty in (y1 - 0.5, y1, y1 + 0.5):
            for tx in (x1 - 0.5, x1, x1 + 0.5):
                best = min(best, (diff(sc, tx, ty), sc, tx, ty))
    raw = float(np.abs(a[m:MH - m, m:MW - m] - b[m:MH - m, m:MW - m]).mean())
    return raw, best[0]


def motion(video: bytes, use_sec: float = 0.0) -> dict:
    """영상 움직임 측정 → {'ok','dur','start','use','total','subject','verdict'}.
    use_sec = 편집에서 실제로 쓰는 길이(컷 길이). 클립 안에서 인물이 가장 많이 움직이는 use_sec 구간을 찾고
    (start = 그 구간의 시작 초), 그 구간의 수치로 판정한다.
    verdict: 'frozen'(화면 정지) / 'camera_only'(카메라만 움직임) / 'weak'(약함) / 'moving'(정상) / 'error'(읽기 실패)"""
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.mp4")
        with open(src, "wb") as f:
            f.write(video)
        dur = duration(src)
        fr = _gray_frames(src) if dur > 0 else None
        if fr is None or len(fr) <= GAP:
            return {"ok": False, "verdict": "error", "dur": dur, "start": 0.0, "use": 0.0, "total": 0.0, "subject": 0.0}
        pairs = [_pair(fr[i], fr[i + GAP]) for i in range(len(fr) - GAP)]     # pairs[i] = i/MFPS 초 ~ +0.5초
        use = min(float(use_sec or dur), dur)
        span = max(1, int(round(use * MFPS)) - GAP)            # 구간 안에 들어가는 비교 쌍 수
        span = min(span, len(pairs))
        best_i, best_v = 0, -1.0
        for i in range(0, len(pairs) - span + 1):
            v = sum(p[1] for p in pairs[i:i + span]) / span
            if v > best_v + 0.05:                              # 비슷하면 앞쪽 구간을 고른다
                best_i, best_v = i, v
        win = pairs[best_i:best_i + span]
        total = sum(p[0] for p in win) / len(win)
        subject = sum(p[1] for p in win) / len(win)
        start = round(min(best_i / MFPS, max(0.0, dur - use)), 2)
        if total < FROZEN_TOTAL:
            verdict = "frozen"
        elif subject < STILL_SUBJECT:
            verdict = "camera_only"
        elif subject < WEAK_SUBJECT:
            verdict = "weak"
        else:
            verdict = "moving"
        return {"ok": verdict in ("weak", "moving"), "verdict": verdict, "dur": round(dur, 2), "start": start,
                "use": round(use, 2), "total": round(total, 2), "subject": round(subject, 2)}


MOTION_KO = {"frozen": "화면이 멈춰 있음 (정지화면)", "camera_only": "카메라만 움직이고 인물은 멈춰 있음 (정지 사진에 카메라 움직임)",
             "weak": "움직임 약함", "moving": "움직임 정상", "error": "영상을 읽지 못함"}


def gentle(cut: dict) -> bool:
    """움직임이 원래 작은 컷: 정지 컷에서 영상으로 올린 컷(숨·눈 깜빡임 정도), 말하는 얼굴 컷(입만 움직임).
    이런 컷은 '카메라만 움직임' 판정을 바로 불합격으로 하지 않고 Claude 가 장면을 보고 판정한다. 화면 정지는 그대로 불합격."""
    return cut.get("motion0") == "still" or bool(cut.get("talk"))


def hard_fail(m: dict, cut: dict) -> bool:
    """Claude 에게 묻지 않고 바로 불합격으로 할 움직임 판정."""
    return m["verdict"] in ("frozen", "error") or (m["verdict"] == "camera_only" and not gentle(cut))


def use_seconds(cut: dict) -> float:
    """편집에서 쓰는 길이: 말하는 컷은 대사 길이(clip_sec), 나머지는 컷 길이."""
    return float(cut.get("clip_sec") or cut.get("dur") or 0)


def motion_label(m: dict | None) -> str:
    if not m:
        return ""
    return (f"{MOTION_KO.get(m.get('verdict'), '')} · 인물 {m.get('subject', 0)} / 화면 {m.get('total', 0)}"
            + (f" · {m['start']}초부터 사용" if m.get("start") else ""))


def judge_clip(api_key: str, video: bytes, still: bytes, cut: dict, prompt: str,
               model: str = "", base_url: str | None = None, use_sec: float = 0.0) -> dict:
    """영상 테이크 검수 → judge_still 과 같은 형식 + 'motion'(움직임 수치).
    1) 엔진이 움직임을 직접 잰다. 화면 정지·카메라만 움직임·읽기 실패는 Claude 에게 묻지 않고 바로 불합격.
    2) 움직임이 있으면 편집에서 쓰는 구간의 장면 4장을 Claude 가 본다 (얼굴·인물·글자·손·입·동작·움직임)."""
    use = float(use_sec or use_seconds(cut))
    m = motion(video, use)
    if hard_fail(m, cut):
        fix = GENERIC_FIX["motion"]
        return {"pass": False, "items": {**{k: True for k in CLIP_ITEMS}, "motion": False},
                "fails": [{"item": "motion", "reason": MOTION_KO[m["verdict"]], "fix_en": fix}], "motion": m}
    a, b = m["start"], m["start"] + m["use"]
    fr = frames(video, [a + 0.05, a + (b - a) / 3, a + 2 * (b - a) / 3, b - 0.1])
    if len(fr) < 2:
        return {"pass": False, "items": {**{k: True for k in CLIP_ITEMS}, "motion": False},
                "fails": [{"item": "motion", "reason": MOTION_KO["error"], "fix_en": GENERIC_FIX["motion"]}], "motion": m}
    head = (f"[컷 {cut.get('id')}] 움직임 종류: {cut.get('motion')}\n"
            f"첫 장면: {cut.get('frame_ko') or cut.get('action')}\n"
            f"일어나야 할 움직임: {cut.get('motion_ko') or cut.get('motion_en') or cut.get('action')}\n"
            f"대사: {'있음 — 말하는 얼굴이 보이는 컷: 말하는 인물의 입이 움직이는 것이 정상(lips 합격)' if cut.get('talk') else '있음 (목소리는 편집에서, 입은 다문 채)' if cut.get('dialogue') else '없음'}\n"
            f"편집에서 쓰는 구간: {a:.1f}초 ~ {b:.1f}초 (아래 장면 4장이 이 구간)\n"
            f"엔진이 잰 움직임: 인물 {m['subject']} / 화면 전체 {m['total']} (인물 {STILL_SUBJECT} 미만 = 정지, {WEAK_SUBJECT} 미만 = 약함)\n"
            "\n검수 항목:\n" + "\n".join(f"- {k}: {v}" for k, v in CLIP_ITEMS.items())
            + f"\n\n영상 지시문(참고):\n{prompt[:2000]}")
    content = [{"type": "text", "text": head}, {"type": "text", "text": "확정 스틸:"}, _img(still)]
    for label, f in zip(["구간 첫 장면", "구간 1/3 장면", "구간 2/3 장면", "구간 마지막 장면"], fr):
        content += [{"type": "text", "text": f"테이크 {label}:"}, _img(f)]
    try:
        res = _result(_ask(api_key, CLIP_SYSTEM, content, model, base_url), CLIP_ITEMS)
    except Exception as ex:                     # Claude 오류: 움직임 수치는 통과했으므로 합격으로 두고 이유를 남김
        res = {"pass": True, "items": {k: True for k in CLIP_ITEMS}, "fails": [], "note": f"검수 오류: {str(ex)[:120]}"}
    res["motion"] = m
    return res


def fix_prompt(prompt: str, res: dict) -> str:
    """불합격 이유를 고치는 문장을 지시문 끝에 붙인다 (이미 붙은 문장은 다시 붙이지 않음)."""
    adds = []
    for f in res.get("fails", []):
        t = f.get("fix_en") or GENERIC_FIX.get(f.get("item"), "")
        if t and t not in prompt and t not in adds:
            adds.append(t)
    return (prompt + " " + " ".join(adds)).strip() if adds else prompt


def score(res: dict) -> int:
    """불합격 개수 (작을수록 좋음). 2회 다시 만들어도 모두 불합격이면 가장 적은 그림을 고른다."""
    return len(res.get("fails", [])) if res else 99


def label(res: dict) -> str:
    if not res:
        return ""
    if res.get("pass"):
        return "합격"
    return " · ".join(f["reason"] or f["item"] for f in res.get("fails", []))
