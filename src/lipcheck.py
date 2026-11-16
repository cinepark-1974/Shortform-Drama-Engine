"""말하는 컷 검사: 입이 대사에 맞춰 움직이는지 숫자로 잰다 (사람이 완성본을 보지 않아도 되게).

방법: 영상에서 입 주변 화면이 프레임마다 얼마나 변하는지(입 움직임 세기)와 더빙 음성의 세기를 같은 시간축에 놓고
      서로 얼마나 같이 오르내리는지(상관) · 얼마나 어긋났는지(지연)를 계산한다.
기준은 EP1 실제 완성본으로 맞춤 (2026-11-16):
  립싱크가 맞은 컷 0.83, 느리게 재생돼 어긋난 컷 0.38~0.42, 입을 다문 채 수화기만 내려놓는 컷 0.14.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile

FPS = 25
W, H = 270, 480
OK, WEAK = 0.45, 0.25          # 상관: 이상이면 맞음 / 그 사이는 약함 / 미만은 입이 음성과 무관
RATIO_MIN = 1.25               # 말할 때 입 움직임 ÷ 말하지 않을 때 입 움직임
MAX_LAG = 10                   # 지연을 찾는 범위 (프레임, ±0.4초)
SHIFT_MIN = 240                # 이만큼(ms) 넘게 어긋나고 상관이 높을 때만 음성 위치를 자동으로 옮긴다 (그 아래는 측정 오차 범위)
VERDICT_KO = {"ok": "입과 소리 맞음", "weak": "입과 소리가 약하게 맞음", "none": "입이 대사에 맞춰 움직이지 않음", "skip": "잴 수 없음"}

MOUTH_SYSTEM = """사진에서 '말하는 사람'의 입 위치를 찾습니다. 말하는 사람은 사용자 글에 적혀 있습니다.
그 사람의 입술과 턱 사이를 넉넉히 감싸는 사각형(코 아래부터 턱 끝까지, 얼굴 폭의 2/3)을 그림 크기에 대한 비율(0~1)로 답합니다.
그 사람의 입이 보이지 않으면(뒷모습·화면 밖·가려짐) found false.
JSON 만 출력: {"found": true, "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}"""


def find_mouth(api_key: str, still: bytes, who: str, model: str = "") -> tuple | None:
    """스틸에서 말하는 사람의 입 위치 (0~1 비율 x0,y0,x1,y1). 못 찾으면 None."""
    import anthropic
    from json_repair import repair_json
    from src.qc import small_jpg, DEFAULT_MODEL
    try:
        c = anthropic.Anthropic(api_key=api_key)
        r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=200, system=MOUTH_SYSTEM, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(small_jpg(still)).decode()}},
            {"type": "text", "text": f"말하는 사람: {who}"}]}])
        d = json.loads(repair_json("".join(b.text for b in r.content if getattr(b, "type", "") == "text")))
        if not d.get("found"):
            return None
        x0, y0, x1, y1 = (max(0.0, min(1.0, float(d[k]))) for k in ("x0", "y0", "x1", "y1"))
        if x1 - x0 < 0.02 or y1 - y0 < 0.01:
            return None
        px, py = (x1 - x0) * 0.6, (y1 - y0) * 0.6             # 고개를 돌려도 입이 안에 있게 넉넉히
        return (max(0.0, x0 - px), max(0.0, y0 - py), min(1.0, x1 + px), min(1.0, y1 + py))
    except Exception:
        return None


def _gray(path: str, t0: float = 0.0, dur: float | None = None):
    import numpy as np
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{t0:.3f}"] if t0 else []) + (["-t", f"{dur:.3f}"] if dur else []) + \
          ["-i", path, "-vf", f"fps={FPS},scale={W}:{H},format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, timeout=120).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype("float32")


def _gray_box(path: str, box: tuple, t0: float = 0.0, dur: float | None = None):
    """입 상자만 원본 화질에서 잘라 본다 (전신 구도처럼 입이 작게 찍힌 컷도 재려고)."""
    import numpy as np
    x0, y0, x1, y1 = box
    bw, bh = 96, max(16, int(96 * (y1 - y0) * 16 / max(1e-6, (x1 - x0) * 9)) // 2 * 2)
    bh = min(bh, 192)
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{t0:.3f}"] if t0 else []) + (["-t", f"{dur:.3f}"] if dur else []) + \
          ["-i", path, "-vf", f"fps={FPS},crop=iw*{x1 - x0:.4f}:ih*{y1 - y0:.4f}:iw*{x0:.4f}:ih*{y0:.4f},scale={bw}:{bh},format=gray",
           "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, timeout=120).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, bh, bw).astype("float32")


def _envelope(path: str, t0: float = 0.0, dur: float | None = None):
    """음성 세기를 영상 프레임 간격으로."""
    import numpy as np
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{t0:.3f}"] if t0 else []) + (["-t", f"{dur:.3f}"] if dur else []) + \
          ["-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, timeout=120).stdout
    s = np.frombuffer(raw, np.int16).astype("float32") / 32768
    n = 16000 // FPS
    k = len(s) // n
    return np.sqrt((s[:k * n].reshape(k, n) ** 2).mean(1)) if k else np.zeros(0, "float32")


def _z(x):
    import numpy as np
    x = np.convolve(x, np.ones(3) / 3, "same")
    return (x - x.mean()) / (x.std() + 1e-6)


def _best(m, a):
    """입 움직임 m 과 음성 세기 a 의 가장 높은 상관과 그때의 지연(프레임; +면 입이 소리보다 늦음)."""
    n = len(m)
    zm, za = _z(m), _z(a)
    best = (-9.0, 0)
    for lag in range(-MAX_LAG, MAX_LAG + 1):
        c = float((zm[lag:] * za[:n - lag]).mean()) if lag >= 0 else float((zm[:n + lag] * za[-lag:]).mean())
        if c > best[0]:
            best = (c, lag)
    return best


def compare(frames, env, box: tuple | None, mouth=None) -> dict:
    """그레이 프레임 묶음과 음성 세기 → {'verdict','corr','lag_ms','ratio','speech','box'}. mouth = 입 상자만 원본 화질로 자른 프레임."""
    import numpy as np
    d = np.abs(np.diff(frames, axis=0))
    a = env[1:]
    n = min(len(d), len(a))
    if n < 12:
        return {"verdict": "skip", "why": "너무 짧음"}
    d, a = d[:n], a[:n]
    if a.max() < 0.01:
        return {"verdict": "skip", "why": "음성이 없음"}
    sp = a > max(0.02, 0.25 * a.max())
    if sp.mean() < 0.05 or sp.all():
        return {"verdict": "skip", "why": "말하는 구간을 가를 수 없음"}

    def score(m):
        c, lag = _best(m, a)
        r = float(m[sp].mean() / (m[~sp].mean() + 1e-6))
        return c, lag, r

    used = box
    if box:
        if mouth is not None and len(mouth) > n:
            m = np.abs(np.diff(mouth, axis=0)).mean((1, 2))[:n]
        else:
            x0, y0, x1, y1 = (int(v * s) for v, s in zip(box, (W, H, W, H)))
            m = d[:, y0:max(y1, y0 + 4), x0:max(x1, x0 + 4)].mean((1, 2))
        c, lag, r = score(m)
    else:                                   # 입 위치를 모를 때: 화면을 칸으로 나눠 음성과 가장 같이 움직이는 칸을 찾는다 (위쪽 70%만)
        c, lag, r, used = -9.0, 0, 0.0, None
        gx_n, gy_n = 9, 16
        for gy in range(int(gy_n * 0.7)):
            for gx in range(gx_n):
                m = d[:, gy * H // gy_n:(gy + 1) * H // gy_n, gx * W // gx_n:(gx + 1) * W // gx_n].mean((1, 2))
                if m.mean() < 0.3:
                    continue
                c2, lag2, r2 = score(m)
                if r2 >= RATIO_MIN and c2 > c:
                    c, lag, r, used = c2, lag2, r2, (gx / gx_n, gy / gy_n, (gx + 1) / gx_n, (gy + 1) / gy_n)
        if used is None:
            c, lag, r = 0.0, 0, 0.0
        elif n < 75:                        # 짧은 컷은 칸 찾기가 우연히 맞기 쉬움 → 한 단계 낮춰 본다
            c *= 0.7
    verdict = "ok" if c >= OK and r >= 1.0 else "none" if (c < WEAK or r < 0.9) else "weak"
    return {"verdict": verdict, "corr": round(c, 2), "lag_ms": int(round(lag * 1000 / FPS)), "ratio": round(r, 2),
            "speech": round(float(sp.mean()), 2), "box": [round(v, 3) for v in used] if used else None, "found_box": bool(box)}


def check_clip(video: bytes, audio: bytes, box: tuple | None = None) -> dict:
    """립싱크 영상 한 개와 그 영상에 넣은 음성(앞 무음 포함)을 비교."""
    try:
        with tempfile.TemporaryDirectory() as d:
            v, a = os.path.join(d, "v.mp4"), os.path.join(d, "a.mp3")
            open(v, "wb").write(video)
            open(a, "wb").write(audio)
            return compare(_gray(v), _envelope(a), box, _gray_box(v, box) if box else None)
    except Exception as ex:
        return {"verdict": "skip", "why": f"측정 오류: {str(ex)[:100]}"}


def check_segment(final_path: str, t0: float, dur: float, box: tuple | None = None) -> dict:
    """완성본의 한 컷 구간(영상과 소리가 이미 합쳐진 상태)을 검사."""
    try:
        return compare(_gray(final_path, t0, dur), _envelope(final_path, t0, dur), box, _gray_box(final_path, box, t0, dur) if box else None)
    except Exception as ex:
        return {"verdict": "skip", "why": f"측정 오류: {str(ex)[:100]}"}


def label(r: dict | None) -> str:
    if not r:
        return ""
    if r.get("verdict") == "skip":
        return f"입 검사 생략 ({r.get('why', '')})"
    return f"{VERDICT_KO.get(r.get('verdict'), '')} · 일치 {r.get('corr')} · 어긋남 {r.get('lag_ms', 0):+d}ms"
