"""그림 생성: OpenAI gpt-image-2.

요청 형식은 MakingShorts-Engine(rodoku.py)에서 실제로 매일 쓰고 있는 방식과 같다.
    POST https://api.openai.com/v1/images/generations → data[0].b64_json
참고 그림을 함께 넣는 편집(images/edits) 호출은 공식 문서·실제 응답 확인 후 추가한다.
"""
from __future__ import annotations

import base64
import io
import time

import requests

MODEL = "gpt-image-2"
SIZES = {"9:16": "864x1536", "16:9": "1536x864", "1:1": "1024x1024", "3:4": "1024x1360"}

# 화면 톤 기준 (Mr. MOON 예시 5장에서 뽑은 규칙). 확정형 문장만 쓴다.
PHOTO_HEAD = ("A real photograph taken on the set of a contemporary Korean TV drama. "
              "Natural skin texture with visible pores, no retouching, no plastic smoothness. ")
PHOTO_TAIL = (" Soft natural daylight from a window. Shallow depth of field. Muted colors. "
              "No text, no letters, no logo, no watermark anywhere in the image.")

# 이미지 지시문 금지어 (3 MINUTES 콘솔 BANNED 규칙 계승)
BANNED = [("살짝", "확정 표현으로"), ("약간", "확정 표현으로"), ("정도", "확정 표현으로"), ("또는", "하나만"),
          ("처럼 보", "확정 표현으로"), ("수 있", "확정 표현으로"),
          ("slightly", "definite wording"), (" or ", "one choice only"), ("maybe", "definite wording"),
          ("looks like", "definite wording"), ("might", "definite wording")]


def banned_in(text: str) -> list[str]:
    t = f" {text} "
    return [f"'{w.strip()}' → {why}" for w, why in BANNED if w in t]


def generate(key: str, prompt: str, aspect: str = "9:16", quality: str = "medium", photo: bool = True) -> bytes:
    """그림 한 장 → JPG 바이트."""
    from PIL import Image
    full = (PHOTO_HEAD + prompt + PHOTO_TAIL) if photo else prompt
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
