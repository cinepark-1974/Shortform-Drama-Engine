"""그림 생성: OpenAI gpt-image-2.

요청 형식은 MakingShorts-Engine(rodoku.py)에서 실제로 매일 쓰고 있는 방식과 같다.
    POST https://api.openai.com/v1/images/generations → data[0].b64_json
기준 그림을 함께 넣는 컷 그림은 POST /v1/images/edits (공식 API 레퍼런스 확인, 2026-11-10):
    image 는 파일 1~16장 (png·webp·jpg, 장당 50MB 미만), gpt-image-2 는 input_fidelity 를 넣지 않는다,
    size 는 'WIDTHxHEIGHT'(16의 배수, 비율 1:3~3:1). 여러 장 전송 형식은 공식 openai 패키지에 맡긴다.
"""
from __future__ import annotations

import base64
import io
import time

import requests

MODEL = "gpt-image-2"
SIZES = {"9:16": "864x1536", "16:9": "1536x864", "1:1": "1024x1024", "3:4": "1024x1360"}

# 화면 톤 기준. 확정형 문장만 쓴다.
# 실사 질감 규칙은 Mr. MOON 참고 프롬프트(스트리트 포토, 2026-11-10)에서 가져옴: 피부 결, 필름 색, 자연광, 금지 목록.
# 참고 프롬프트의 워터마크 문구는 다른 사람의 표식이라 넣지 않는다.
SKIN = ("Real skin texture with fine visible pores and a healthy natural glow, natural expression lines, "
        "believable anatomy and natural facial proportions. ")
NEG = (" No beauty filter, no airbrushing, no plastic skin, no waxy skin, no CGI look, no 3D render look, "
       "no HDR, no oversharpening, no exaggerated features. "
       "No text, no letters, no logo, no watermark anywhere in the image.")
STYLES = {
    # 02 캐스팅 인물 기준 그림: 스튜디오 프로필 사진. 감정·장면은 넣지 않되, 화보처럼 매끈하지 않게
    # 작품 전체 톤(필름 색, 자연광)에 맞춘 자연스러운 사진으로.
    "ref": ("SUBJECT & IDENTITY: A high-end Korean actor casting portrait, ultra-photorealistic studio photography, "
            "a lead-role actor with an attractive, camera-friendly face. " + SKIN,
            " HAIR & FABRIC: individual hair fibers visible with realistic density, uneven highlights and naturally separated "
            "strands; real knit and fabric texture that follows the body with gentle tension and soft folds. "
            "POSE & COMPOSITION: front-facing, eye-level camera, relaxed shoulders, arms resting naturally at the sides, "
            "direct eye contact with the camera. Vertical 3:4 framing from the top of the head to the upper hips. "
            "Neutral bright grey seamless studio background. "
            "LIGHTING & PHOTOGRAPHY: soft diffused studio light with gentle directional shadows, natural skin highlights and "
            "real dimensionality without heavy beauty retouching. 85mm portrait lens, realistic depth of field, natural "
            "optical rendering, fine photographic grain, accurate skin and fabric texture, natural color grading." + NEG +
            " No artificial hair clumps, no plastic hair shine, no exaggerated anatomy, no distorted facial features, "
            "no artificial facial symmetry, no oversized head, no exaggerated jawline, no unnatural fabric deformation."),
    # 02 캐스팅 장소 마스터: 사람 없는 넓은 공간.
    "location": ("A real wide photograph of an empty location in Seoul, scouted for a Korean drama. ",
                 " Natural daylight with real shadows and uneven exposure, lived-in details, eye-level lens. "
                 "Medium-format film look with Kodak Portra 160 color, fine grain and soft highlight roll-off." + NEG),
    # 04 스틸 컷: 촬영장에서 찍힌 한 순간.
    "cut": ("A real frame captured on the set of a contemporary Korean drama, an unposed split-second moment. " + SKIN,
            " Real daylight mixing soft and hard light, true shadows under the chin and nose, uneven exposure. "
            "Shallow depth of field with a soft out-of-focus foreground object at the frame edge. "
            "Medium-format film look with Kodak Portra 160 color, visible organic film grain, soft highlight roll-off "
            "and a faint vignette. Imperfect natural framing with the subject off center." + NEG),
}
PHOTO_HEAD, PHOTO_TAIL = STYLES["cut"]   # 예전 이름 호환

# 이미지 지시문 금지어 (3 MINUTES 콘솔 BANNED 규칙 계승)
BANNED = [("살짝", "확정 표현으로"), ("약간", "확정 표현으로"), ("정도", "확정 표현으로"), ("또는", "하나만"),
          ("처럼 보", "확정 표현으로"), ("수 있", "확정 표현으로"),
          ("slightly", "definite wording"), (" or ", "one choice only"), ("maybe", "definite wording"),
          ("looks like", "definite wording"), ("might", "definite wording")]


def banned_in(text: str) -> list[str]:
    t = f" {text} "
    return [f"'{w.strip()}' → {why}" for w, why in BANNED if w in t]


def generate(key: str, prompt: str, aspect: str = "9:16", quality: str = "medium", photo: bool = True,
             style: str = "cut") -> bytes:
    """그림 한 장 → JPG 바이트. style: ref(인물 기준) / location(장소 마스터) / cut(스틸 컷)."""
    from PIL import Image
    head, tail = STYLES.get(style, STYLES["cut"])
    full = (head + prompt + tail) if photo else prompt
    body = {"model": MODEL, "prompt": full[:30000], "size": SIZES.get(aspect, SIZES["9:16"]),
            "quality": quality or "medium", "n": 1}
    r = None
    for attempt in range(3):
        r = requests.post("https://api.openai.com/v1/images/generations", json=body, timeout=300,
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        if r.status_code != 429:
            break
        time.sleep(20 * (attempt + 1))
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", "")
        except Exception:
            msg = r.text[:200]
        raise RuntimeError(f"GPT Image {r.status_code}: {msg}")
    d = (r.json().get("data") or [{}])[0]
    if d.get("b64_json"):
        raw = base64.b64decode(d["b64_json"])
    elif d.get("url"):
        raw = requests.get(d["url"], timeout=120).content
    else:
        raise RuntimeError("GPT Image 응답에 그림이 없습니다")
    out = io.BytesIO()
    Image.open(io.BytesIO(raw)).convert("RGB").save(out, "JPEG", quality=92)
    return out.getvalue()


MAX_REFS = 16


def _to_jpg(raw: bytes) -> bytes:
    from PIL import Image
    out = io.BytesIO()
    Image.open(io.BytesIO(raw)).convert("RGB").save(out, "JPEG", quality=92)
    return out.getvalue()


def edit(key: str, prompt: str, refs: list[tuple[str, bytes]], aspect: str = "9:16", quality: str = "medium",
         style: str = "cut", model: str = "", base_url: str | None = None) -> bytes:
    """기준 그림(인물·장소)을 함께 넣어 컷 그림 한 장 → JPG 바이트.
    refs = [(파일 이름, 바이트)], 앞에서부터 최대 16장. 기준 그림이 없으면 일반 생성으로."""
    if not refs:
        return generate(key, prompt, aspect, quality, style=style)
    from openai import OpenAI
    head, tail = STYLES.get(style, STYLES["cut"])
    client = OpenAI(api_key=key, base_url=base_url, max_retries=2, timeout=300)
    files = [(name, _to_jpg(data), "image/jpeg") for name, data in refs[:MAX_REFS]]
    r = client.images.edit(model=model or MODEL, image=files, prompt=(head + prompt + tail)[:30000],
                           size=SIZES.get(aspect, SIZES["9:16"]), quality=quality or "medium", n=1)
    d = r.data[0]
    if getattr(d, "b64_json", None):
        return _to_jpg(base64.b64decode(d.b64_json))
    if getattr(d, "url", None):
        return _to_jpg(requests.get(d.url, timeout=120).content)
    raise RuntimeError("GPT Image 편집 응답에 그림이 없습니다")
