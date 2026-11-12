"""05 영상: 확정 스틸을 첫 프레임으로 넣어 짧은 영상 클립을 만든다 (Replicate).

확인한 공식 자료 (2026-11-10):
- 모델 kwaivgi/kling-v3-video 입력: prompt(2500자), negative_prompt, start_image(JPG/PNG, 10MB 이하, 300px 이상,
  비율 1:2.5~2.5:1), mode(standard=720p / pro=1080p), duration(3~15초 정수), generate_audio(기본 False).
  start_image 를 넣으면 aspect_ratio 는 무시되고 그림 비율을 따른다. 출력은 영상 주소(URI) 하나.
- 공식 모델 예측 생성: POST https://api.replicate.com/v1/models/{owner}/{name}/predictions
  응답의 urls.get 을 주기적으로 조회해 succeeded / failed / canceled 가 될 때까지 기다린다.
- 파일 입력은 data URI 가능 (1MB 미만 권장) → 스틸을 1MB 아래로 줄여 보낸다.
대사·효과음은 06·07 단계에서 따로 얹으므로 영상 소리는 만들지 않는다.
"""
from __future__ import annotations

import base64
import io
import math
import os
import time

import requests

API = os.environ.get("REPLICATE_API_BASE", "https://api.replicate.com/v1")   # 시험용으로만 바꿈
DEFAULT_MODEL = "kwaivgi/kling-v3-video"
NEGATIVE = ("text, letters, subtitles, captions, watermark, logo, distorted face, face morphing, identity change, "
            "extra fingers, deformed hands, flicker, jitter, cartoon, CGI, 3D render, talking, lip movement, "
            "lanyard, ID badge, jewelry, wristwatch, earphones, new person entering, outfit change")
DONE = {"succeeded", "failed", "canceled"}


def data_uri(jpg: bytes, limit: int = 950_000) -> str:
    """스틸을 1MB 아래 JPG data URI 로 (화질을 조금씩 낮춤, 크기는 유지)."""
    from PIL import Image
    im = Image.open(io.BytesIO(jpg)).convert("RGB")
    for q in (92, 88, 84, 80, 75, 70, 65):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q)
        if buf.tell() < limit:
            break
    else:
        im.thumbnail((1080, 1920))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def clip_seconds(dur: float) -> int:
    """컷 길이 → 모델에 줄 초 (3~15초 정수, 남는 부분은 편집에서 자름)."""
    return max(3, min(15, math.ceil(float(dur or 3))))


def start(token: str, prompt: str, still_jpg: bytes, seconds: int, model: str = "", mode: str = "standard",
          api: str = API) -> dict:
    """예측 하나 시작 → {'id','status','get'} (기다리지 않음)."""
    model = model or DEFAULT_MODEL
    body = {"input": {"prompt": prompt[:2500], "negative_prompt": NEGATIVE, "start_image": data_uri(still_jpg),
                      "duration": int(seconds), "mode": mode, "generate_audio": False}}
    r = requests.post(f"{api}/models/{model}/predictions", json=body, timeout=60,
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    if r.status_code >= 400:
        raise RuntimeError(f"Replicate {r.status_code}: {r.text[:300]}")
    p = r.json()
    return {"id": p["id"], "status": p.get("status", "starting"), "get": p.get("urls", {}).get("get", f"{api}/predictions/{p['id']}")}


def check(token: str, get_url: str) -> dict:
    """예측 상태 한 번 조회 → {'status','output','error'}."""
    r = requests.get(get_url, timeout=30, headers={"Authorization": f"Bearer {token}"})
    if r.status_code >= 400:
        raise RuntimeError(f"Replicate {r.status_code}: {r.text[:300]}")
    p = r.json()
    out = p.get("output")
    if isinstance(out, list):
        out = out[0] if out else None
    return {"status": p.get("status"), "output": out, "error": p.get("error")}


def wait_all(token: str, jobs: dict, timeout: int = 900, every: float = 5.0, on_tick=None) -> dict:
    """jobs = {컷 id: get 주소} → 끝날 때까지 조회. {컷 id: check 결과}. 시간 초과면 그때까지의 상태."""
    res, t0 = {}, time.time()
    while time.time() - t0 < timeout:
        for cid, url in jobs.items():
            if res.get(cid, {}).get("status") in DONE:
                continue
            try:
                res[cid] = check(token, url)
            except Exception as ex:      # 일시적인 연결 오류는 다음 차례에 다시
                res[cid] = {"status": "processing", "output": None, "error": str(ex)}
        if on_tick:
            on_tick(res)
        if all(res.get(c, {}).get("status") in DONE for c in jobs):
            break
        time.sleep(every)
    return res


def download(url: str) -> bytes:
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return r.content
