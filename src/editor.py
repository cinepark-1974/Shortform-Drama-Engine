"""07 자막 · 08 편집: 컷(스틸·영상) + 더빙 + 자막을 9:16 한 화로 이어 붙인다 (2026-11-13, v1.1).

방식 (Streamlit 메모리 1GB 안에서 돌도록 컷 하나씩 따로 만든 뒤 이어 붙임)
1. 타임라인: 컷 길이 = max(콘티 길이, 더빙 길이 + 0.25초).
2. 컷마다 ffmpeg 한 번: 영상 컷은 잘라 쓰고, 정지 컷은 스틸에 카메라 움직임(줌·팬)을 넣는다.
   (2026-11-14) 영상 컷은 검수에서 찾은 '인물이 가장 많이 움직이는 구간'부터 쓴다 (클립 앞부분이 멈춰 있는 경우 대비).
   영상이 컷보다 짧으면 마지막 장면을 멈춰 늘리지 않고, 먼저 시작점을 당기고, 그래도 모자라면 최대 1.5배까지 천천히 재생한다.
   그래도 모자란 부분만 마지막 장면을 늘리고, 몇 초를 늘렸는지 기록한다 (frozen).
   자막(한/영)·첫머리 훅 자막은 투명 PNG로 만들어 위에 얹는다. 더빙은 0.1초 뒤에 시작한다.
3. 화면 글자 컷(휴대폰·모니터): 글자를 스틸의 화면 위치에 먼저 그려 넣은 뒤 카메라 움직임을 넣는다 (글자가 화면과 함께 움직임).
4. 이어 붙이기: 같은 규격(1080x1920, 30fps, AAC 44.1kHz)이라 다시 인코딩하지 않고 붙인다.
"""
from __future__ import annotations

import re

import base64
import io
import json
import os
import subprocess
import tempfile

W, H, FPS = 1080, 1920, 30
PAD = 0.25                     # 더빙 뒤 여유
FONTS = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
         "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"]
DEFAULT_MODEL = "claude-sonnet-4-6"


def font(size: int):
    from PIL import ImageFont
    for p in FONTS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size, index=1 if p.endswith(".ttc") else 0)   # ttc 의 1번이 한국어(KR)
            except Exception:
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
    raise RuntimeError("한글 글꼴이 없습니다 (packages.txt 에 fonts-noto-cjk 필요)")


def wrap(text: str, f, max_w: int, draw) -> list[str]:
    """글자 폭을 재서 줄을 나눈다. 띄어쓰기에서 먼저 끊고, 한 낱말이 너무 길면 글자 단위로."""
    lines = []
    for para in re.split(r"(?:\\n|[\r\n\u2028\u2029\v\f])+", str(text or "")):   # 줄바꿈이 든 글은 줄마다 따로 잰다
        lines += _wrap_line(" ".join(para.split()), f, max_w, draw)
    return lines


def _wrap_line(text: str, f, max_w: int, draw) -> list[str]:
    lines, cur = [], ""
    for word in text.split(" "):
        t = (cur + " " + word).strip()
        if draw.textlength(t, font=f) <= max_w:
            cur = t
            continue
        if cur:
            lines.append(cur)
        cur = word
        while draw.textlength(cur, font=f) > max_w:
            k = len(cur)
            while k > 1 and draw.textlength(cur[:k], font=f) > max_w:
                k -= 1
            lines.append(cur[:k])
            cur = cur[k:]
    if cur:
        lines.append(cur)
    return lines


def overlay_png(ko: str = "", en: str = "", hook: str = "", ko_size: int = 60, en_size: int = 38) -> bytes:
    """자막 한 컷분 투명 PNG (1080x1920). 한국어는 화면 높이 66% 근처(쇼츠 화면 아래 버튼에 가리지 않는 자리), 영어는 그 아래."""
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = int(H * 0.66)
    if ko:
        f = font(ko_size)
        for ln in wrap(ko, f, W - 160, d):
            w = d.textlength(ln, font=f)
            d.text(((W - w) / 2, y), ln, font=f, fill=(255, 255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0, 230))
            y += ko_size + 14
    if en:
        f = font(en_size)
        y += 6
        for ln in wrap(en, f, W - 180, d):
            w = d.textlength(ln, font=f)
            d.text(((W - w) / 2, y), ln, font=f, fill=(255, 230, 120, 255), stroke_width=4, stroke_fill=(0, 0, 0, 230))
            y += en_size + 10
    if hook:
        f = font(64)
        lines = wrap(hook, f, W - 200, d) or [" "]
        bh = len(lines) * 80 + 36
        bw = max(d.textlength(ln, font=f) for ln in lines) + 72
        x0, y0 = (W - bw) / 2, int(H * 0.13)
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 22, fill=(255, 203, 5, 240))
        yy = y0 + 16
        for ln in lines:
            w = d.textlength(ln, font=f)
            d.text(((W - w) / 2, yy), ln, font=f, fill=(25, 25, 112, 255))
            yy += 80
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def draw_screen_text(still: bytes, text: str, box: tuple | None = None) -> bytes:
    """화면 글자 컷: 스틸의 화면 위치(box = 0~1 비율 x0,y0,x1,y1)에 글자를 그려 넣는다. box 가 없으면 가운데."""
    from PIL import Image, ImageDraw
    im = Image.open(io.BytesIO(still)).convert("RGB")
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = box or (0.25, 0.38, 0.75, 0.6)
    bx, by, bw, bh = x0 * im.width, y0 * im.height, (x1 - x0) * im.width, (y1 - y0) * im.height
    parts = [p.strip() for p in str(text).replace("\\n", "\n").split("\n") if p.strip()] or [str(text)]
    size = int(min(bh / (len(parts) * 1.5), bw * 0.62 / max(len(max(parts, key=len)), 2)))   # 한글 한 글자 폭 ≈ 글자 크기, 화면 폭의 62% 안
    size = max(18, min(size, int(im.height * 0.042)))
    f = font(size)
    lines = [ln for p in parts for ln in wrap(p, f, int(bw * 0.8), d)]
    total = len(lines) * int(size * 1.35)
    y = by + (bh - total) / 2
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text((bx + (bw - w) / 2, y), ln, font=f, fill=(245, 245, 245), stroke_width=max(1, size // 18), stroke_fill=(0, 0, 0))
        y += int(size * 1.35)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=93)
    return buf.getvalue()


QUAD_SYSTEM = """사진에서 화면(휴대폰 화면, 노트북·모니터 화면) 하나의 네 모서리를 찾습니다. 화면이 여러 개면 가장 크게 보이는 것.
화면 유리 부분(테두리 제외)의 네 모서리를, 화면을 바로 세워 봤을 때의 왼쪽 위(tl) · 오른쪽 위(tr) · 오른쪽 아래(br) · 왼쪽 아래(bl) 순서로,
그림 크기에 대한 비율(0~1)의 [x, y] 로 답합니다. 휴대폰을 비스듬히 들었으면 기울어진 그대로의 모서리를 답합니다.
kind 는 phone(휴대폰) · laptop(노트북) · monitor(모니터) 중 하나. 화면이 없으면 found false.
JSON 만 출력: {"found": true, "kind": "phone", "tl": [0.0, 0.0], "tr": [1.0, 0.0], "br": [1.0, 1.0], "bl": [0.0, 1.0]}"""


def find_screen_quad(api_key: str, still: bytes, model: str = "") -> dict | None:
    """스틸에서 화면의 네 모서리와 종류를 찾는다. → {'kind','quad':[[x,y]×4]} 또는 None."""
    import anthropic
    from json_repair import repair_json
    from src.qc import small_jpg
    try:
        c = anthropic.Anthropic(api_key=api_key)
        r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=300, system=QUAD_SYSTEM, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(small_jpg(still)).decode()}},
            {"type": "text", "text": "화면의 네 모서리를 찾아 주세요."}]}])
        d = json.loads(repair_json("".join(b.text for b in r.content if getattr(b, "type", "") == "text")))
        if not d.get("found"):
            return None
        quad = [[max(0.0, min(1.0, float(d[k][0]))), max(0.0, min(1.0, float(d[k][1])))] for k in ("tl", "tr", "br", "bl")]
        return {"kind": d.get("kind") if d.get("kind") in ("phone", "laptop", "monitor") else "phone", "quad": quad} if quad_ok(quad) else None
    except Exception:
        return None


def quad_ok(quad) -> bool:
    """네 모서리가 볼록한 사각형이고 너무 작지 않은지."""
    try:
        pts = [(float(x), float(y)) for x, y in quad]
        if len(pts) != 4:
            return False
        area, sign = 0.0, 0
        for i in range(4):
            (x0, y0), (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % 4], pts[(i + 2) % 4]
            area += x0 * y1 - x1 * y0
            cr = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
            if abs(cr) < 1e-6:
                return False
            if sign == 0:
                sign = 1 if cr > 0 else -1
            elif (cr > 0) != (sign > 0):
                return False
        return abs(area) / 2 >= 0.01
    except Exception:
        return False


def _persp(dst, src):
    """PIL PERSPECTIVE 계수: 결과 그림의 점 dst → 원본(화면 그림)의 점 src."""
    import numpy as np
    a, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return [float(v) for v in np.linalg.solve(np.array(a, dtype="float64"), np.array(b, dtype="float64"))]


def screen_ui(text: str, kind: str, w: int, h: int):
    """화면에 띄울 그림을 엔진이 직접 그린다 (한글이 깨지지 않게). 휴대폰 + 짧은 글 = 전화 수신 화면, 휴대폰 + 긴 글 = 알림,
    노트북·모니터 = 문서 창."""
    from PIL import Image, ImageDraw
    parts = [p.strip() for p in str(text).replace("\\n", "\n").split("\n") if p.strip()] or [str(text).strip() or " "]
    im = Image.new("RGB", (w, h), (12, 14, 20))
    d = ImageDraw.Draw(im)
    if kind == "phone" and len(parts) == 1 and len(parts[0]) <= 10:          # 전화 수신 화면
        for y in range(h):                                                     # 위에서 아래로 어두워지는 바탕
            t = y / h
            d.line([(0, y), (w, y)], fill=(int(34 - 18 * t), int(40 - 22 * t), int(58 - 30 * t)))
        f_s, f_n = font(int(w * 0.075)), font(min(int(w * 0.8 / max(len(parts[0]), 2)), int(w * 0.2)))
        lab = "전화 수신 중"
        d.text(((w - d.textlength(lab, font=f_s)) / 2, h * 0.14), lab, font=f_s, fill=(170, 176, 190))
        d.text(((w - d.textlength(parts[0], font=f_n)) / 2, h * 0.21), parts[0], font=f_n, fill=(248, 248, 250))
        r = int(w * 0.105)
        for cx, col in ((w * 0.27, (232, 64, 60)), (w * 0.73, (52, 199, 89))):   # 거절 · 수락 버튼
            d.ellipse([cx - r, h * 0.80 - r, cx + r, h * 0.80 + r], fill=col)
            d.rounded_rectangle([cx - r * 0.5, h * 0.80 - r * 0.14, cx + r * 0.5, h * 0.80 + r * 0.14], radius=int(r * 0.14), fill=(255, 255, 255))
    elif kind == "phone":                                                      # 알림 · 메시지
        d.rectangle([0, 0, w, h], fill=(18, 20, 28))
        f = font(int(w * 0.07))
        lines = [ln for p_ in parts for ln in wrap(p_, f, int(w * 0.76), d)][:8]
        bh = int(len(lines) * w * 0.095 + w * 0.1)
        d.rounded_rectangle([w * 0.07, h * 0.2, w * 0.93, h * 0.2 + bh], radius=int(w * 0.05), fill=(44, 48, 60))
        y = h * 0.2 + w * 0.05
        for ln in lines:
            d.text((w * 0.12, y), ln, font=f, fill=(244, 244, 246))
            y += w * 0.095
    else:                                                                      # 문서 창
        d.rectangle([0, 0, w, h], fill=(250, 250, 252))
        d.rectangle([0, 0, w, int(h * 0.09)], fill=(226, 229, 236))
        for i, col in enumerate(((236, 106, 94), (244, 191, 79), (98, 197, 84))):
            d.ellipse([w * (0.02 + i * 0.028), h * 0.028, w * (0.04 + i * 0.028), h * 0.028 + w * 0.02], fill=col)
        size = int(min(h * 0.62 / (len(parts) * 1.5), w * 0.8 / max(len(max(parts, key=len)), 2), h * 0.16))
        f = font(max(14, size))
        lines = [ln for p_ in parts for ln in wrap(p_, f, int(w * 0.84), d)]
        y = h * 0.09 + (h * 0.91 - len(lines) * size * 1.5) / 2
        for ln in lines:
            d.text(((w - d.textlength(ln, font=f)) / 2, y), ln, font=f, fill=(28, 30, 36))
            y += size * 1.5
    return im


def _fit_dark(im, pts):
    """찾은 네 모서리가 화면보다 크거나 어긋나 있으면, 그 안의 꺼진 화면(어두운 영역)에 맞춰 사각형을 다시 잡는다 (화면 컷은 정면이 규칙)."""
    from PIL import Image, ImageDraw, ImageFilter
    poly = Image.new("L", im.size, 0)
    ImageDraw.Draw(poly).polygon(pts, fill=255)
    grow = Image.new("L", im.size, 0)                      # 모서리가 화면보다 작게 잡힌 경우도 있어 조금 넓혀서 찾는다
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    mx, my = (max(xs) - min(xs)) * 0.12, (max(ys) - min(ys)) * 0.08
    ImageDraw.Draw(grow).rectangle([min(xs) - mx, min(ys) - my, max(xs) + mx, max(ys) + my], fill=255)
    dark = im.convert("L").point(lambda v: 255 if v < 58 else 0).filter(ImageFilter.MinFilter(5))
    from PIL import ImageChops
    bb = ImageChops.multiply(grow, dark).getbbox()
    if not bb:
        return pts
    x0, y0, x1, y1 = bb
    area_d, area_p = (x1 - x0) * (y1 - y0), (max(xs) - min(xs)) * (max(ys) - min(ys))
    if not (0.4 * area_p <= area_d <= 1.6 * area_p):        # 어두운 영역이 화면 크기와 너무 다르면 원래 모서리를 믿는다
        return pts
    ix, iy = (x1 - x0) * 0.035, (y1 - y0) * 0.02            # 검은 케이스·테두리까지 잡히므로 안쪽으로 조금 들인다
    return [(x0 + ix, y0 + iy), (x1 - ix, y0 + iy), (x1 - ix, y1 - iy), (x0 + ix, y1 - iy)]


def draw_screen_ui(still: bytes, text: str, quad, kind: str = "phone") -> bytes:
    """화면 글자 컷: 엔진이 그린 화면을 스틸 속 화면의 네 모서리에 맞춰 기울여 붙인다. quad = [[x,y]×4] (0~1, tl·tr·br·bl)."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.open(io.BytesIO(still)).convert("RGB")
    pts = [(x * im.width, y * im.height) for x, y in quad]
    pts = _fit_dark(im, pts)
    import math
    wt, wb = math.dist(pts[0], pts[1]), math.dist(pts[3], pts[2])
    hl, hr = math.dist(pts[0], pts[3]), math.dist(pts[1], pts[2])
    uw = 720
    uh = max(240, min(1800, int(uw * ((hl + hr) / 2) / max(1.0, (wt + wb) / 2))))
    ui = screen_ui(text, kind, uw, uh)
    co = _persp(pts, [(0, 0), (uw, 0), (uw, uh), (0, uh)])
    warped = ui.transform(im.size, Image.PERSPECTIVE, co, Image.BICUBIC)
    poly = Image.new("L", im.size, 0)
    ImageDraw.Draw(poly).polygon(pts, fill=255)
    # 꺼진 화면(어두운 부분)에만 붙인다: 화면을 잡은 손가락·테두리·반사는 그대로 위에 남고, 모서리도 화면 모양(둥근 모서리)을 따른다
    dark = im.convert("L").point(lambda v: 255 if v < 58 else 0).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    from PIL import ImageChops
    mask = ImageChops.multiply(poly, dark)
    if sum(mask.histogram()[128:]) < 0.35 * sum(poly.histogram()[128:]):     # 화면이 어둡지 않은 스틸(흰 화면 등): 모서리 사각형 그대로
        mask = poly
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    im.paste(warped, (0, 0), mask)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=93)
    return buf.getvalue()


SCREEN_SYSTEM = """사진에서 화면(휴대폰 화면, 노트북·모니터 화면) 하나의 위치를 찾습니다. 화면이 여러 개면 가장 크게 보이는 것.
화면 유리 부분만(테두리 제외) 감싸는 사각형을 그림 크기에 대한 비율(0~1)로 답합니다. 화면이 없으면 found false.
JSON 만 출력: {"found": true, "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}"""


def find_screen(api_key: str, still: bytes, model: str = "") -> tuple | None:
    """스틸에서 화면 위치를 찾는다 (Claude 이미지 입력). 못 찾으면 None."""
    import anthropic
    from json_repair import repair_json
    from src.qc import small_jpg
    try:
        c = anthropic.Anthropic(api_key=api_key)
        r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=200, system=SCREEN_SYSTEM, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(small_jpg(still)).decode()}},
            {"type": "text", "text": "화면 위치를 찾아 주세요."}]}])
        d = json.loads(repair_json("".join(b.text for b in r.content if getattr(b, "type", "") == "text")))
        if not d.get("found"):
            return None
        box = tuple(max(0.0, min(1.0, float(d[k]))) for k in ("x0", "y0", "x1", "y1"))
        return box if box[2] - box[0] > 0.05 and box[3] - box[1] > 0.05 else None
    except Exception:
        return None


TRANSLATE_SYSTEM = """한국 드라마 숏폼의 영어 자막 번역가입니다. 한국어 대사를 자연스러운 구어체 영어 자막으로 옮깁니다.
- 한 줄은 짧게 (42자 이내 권장). 직역하지 않고 말하는 사람의 태도와 관계(존댓말·반말)를 살림.
- 인물 이름은 로마자로 (한세영 → Han Se-young, 오진혁 → Oh Jin-hyuk). 직함은 자연스러운 영어로.
- 줄 수와 id 를 그대로 유지. hook 은 첫머리 화면 자막이므로 짧고 강하게.
JSON 만 출력: {"hook": "", "lines": [{"id": "", "en": ""}]}"""


def translate(api_key: str, hook: str, lines: list[dict], model: str = "") -> dict:
    """lines = [{id, who, ko}] → {'hook': 영어, 'lines': {id: 영어}}"""
    import anthropic
    from json_repair import repair_json
    c = anthropic.Anthropic(api_key=api_key)
    r = c.messages.create(model=model or DEFAULT_MODEL, max_tokens=4000, system=TRANSLATE_SYSTEM,
                          messages=[{"role": "user", "content": json.dumps({"hook": hook, "lines": lines}, ensure_ascii=False)}])
    d = json.loads(repair_json("".join(b.text for b in r.content if getattr(b, "type", "") == "text")))
    out = {str(x.get("id")): str(x.get("en", "")).strip() for x in (d.get("lines") or []) if isinstance(x, dict)}
    return {"hook": str(d.get("hook", "")).strip(), "lines": out}


def timeline(cuts: list, dub: dict) -> list[dict]:
    """컷마다 편집 길이와 시작 시각. 더빙이 컷보다 길면 컷을 늘린다."""
    out, t = [], 0.0
    for c in cuts:
        sec = (dub.get(c["id"]) or {}).get("sec", 0) if c.get("dialogue") else 0
        dur = round(max(float(c["dur"]), sec + PAD if sec else 0), 2)
        out.append({"id": c["id"], "start": round(t, 2), "dur": dur})
        t += dur
    return out


def _zoom(camera: str, n: int) -> str:
    """정지 컷의 카메라 움직임 (zoompan 식). n = 프레임 수."""
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if camera in ("천천히 다가감", "줌인"):
        return f"z='1+0.10*on/{n}':x='{cx}':y='{cy}'"
    if camera == "천천히 물러남":
        return f"z='1.10-0.10*on/{n}':x='{cx}':y='{cy}'"
    if camera == "팬":
        return f"z='1.10':x='(iw-iw/zoom)*on/{n}':y='{cy}'"
    return f"z='1+0.04*on/{n}':x='{cx}':y='{cy}'"            # 고정·핸드헬드: 아주 느린 다가감 (완전히 멈춘 그림은 죽어 보임)


MAX_SLOW = 1.5                 # 영상이 모자랄 때 늘려 재생하는 최대 배율


def clip_plan(clip_len: float, dur: float, start: float = 0.0) -> dict:
    """영상 컷을 어디서부터, 몇 배 느리게 쓸지. → {'start','slow','frozen'(마지막 장면을 멈춰 늘린 초)}"""
    if clip_len <= 0:
        return {"start": 0.0, "slow": 1.0, "frozen": round(dur, 2)}
    start = max(0.0, min(float(start or 0), clip_len - 0.1))
    if clip_len - start < dur:                          # 1) 시작점을 당겨 뒷부분을 확보
        start = max(0.0, clip_len - dur)
    rest = clip_len - start
    slow = 1.0 if rest >= dur else min(MAX_SLOW, dur / rest)   # 2) 천천히 재생
    frozen = max(0.0, dur - rest * slow)                # 3) 그래도 모자란 초
    return {"start": round(start, 2), "slow": round(slow, 3), "frozen": round(frozen, 2)}


def probe_len(path: str) -> float:
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=60)
        return float(p.stdout.strip() or 0)
    except Exception:
        return 0.0


def render_cut(out_path: str, dur: float, still: bytes | None = None, clip: bytes | None = None, camera: str = "고정",
               overlay: bytes | None = None, audio: bytes | None = None, workdir: str = "", clip_start: float = 0.0,
               sync: bool = False, audio_delay: int = 100, voice: str = "") -> dict:
    """컷 하나를 1080x1920 mp4 로. clip 이 있으면 영상 컷, 없으면 still 정지 컷. → 영상 컷이면 clip_plan 결과."""
    d = workdir or os.path.dirname(out_path)
    n = max(1, int(round(dur * FPS)))
    args, fc, plan = ["ffmpeg", "-v", "error", "-y"], [], {}
    if clip:
        src = os.path.join(d, "src.mp4")
        open(src, "wb").write(clip)
        clen = probe_len(src)
        # 립싱크 영상은 음성과 한 몸: 처음부터, 제 속도로만 쓴다 (구간을 옮기거나 느리게 하면 입과 소리가 어긋남)
        plan = {"start": 0.0, "slow": 1.0, "frozen": round(max(0.0, dur - clen), 2)} if sync else clip_plan(clen, dur, clip_start)
        args += (["-ss", f"{plan['start']:.2f}"] if plan["start"] else []) + ["-i", src]
        slow = f"setpts={plan['slow']:.3f}*(PTS-STARTPTS)," if plan["slow"] > 1.0 else "setpts=PTS-STARTPTS,"
        # 입이 소리보다 빠른 립싱크 영상: 음성을 앞당길 수 없으므로 첫 장면을 그만큼 멈춰 붙여 영상을 늦춘다
        pre = f"start_mode=clone:start_duration={-audio_delay / 1000:.3f}:" if audio_delay < 0 else ""
        fc.append(f"[0:v]{slow}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                  f"tpad={pre}stop_mode=clone:stop_duration={dur:.2f},setsar=1[v0]")
    else:
        src = os.path.join(d, "src.jpg")
        open(src, "wb").write(still)
        args += ["-i", src]
        fc.append(f"[0:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
                  f"zoompan={_zoom(camera, n)}:d={n}:s={W}x{H}:fps={FPS},setsar=1[v0]")
    idx = 1
    if overlay:
        ov = os.path.join(d, "ov.png")
        open(ov, "wb").write(overlay)
        args += ["-i", ov]
        fc.append(f"[v0][{idx}:v]overlay=0:0[v]")
        idx += 1
    else:
        fc.append("[v0]null[v]")
    if audio:
        au = os.path.join(d, "a.mp3")
        open(au, "wb").write(audio)
        args += ["-i", au]
        ad = max(0, min(700, int(audio_delay)))
        tone = {"phone": "highpass=f=300,lowpass=f=3400,volume=1.4,"}.get(voice, "")      # 전화 목소리: 전화기 소리로 깎음
        fc.append(f"[{idx}:a]aresample=44100,{tone}adelay={ad}|{ad},apad[a]")
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        fc.append(f"[{idx}:a]anull[a]")
    args += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", out_path]
    p = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if p.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"ffmpeg: {p.stderr[-400:]}")
    return plan


def concat(paths: list[str], out_path: str) -> None:
    lst = out_path + ".txt"
    with open(lst, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                        "-movflags", "+faststart", out_path], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg concat: {p.stderr[-400:]}")


def cutter_is_phone(c: dict) -> bool:
    from src import cutter
    return cutter.is_phone(c)


def render_episode(cuts: list, get, stills: dict, clips: dict, dub: dict, subs: dict, hook: str = "", english: bool = True,
                   screen_box=None, on_step=None, sound: dict | None = None) -> tuple[bytes, list]:
    """한 화 렌더링. get(key) → 바이트. stills/clips/dub = 그 화의 기록. subs = {'hook_en', 'lines': {id: en}}.
    screen_box(cut, still_bytes) → 화면 위치 또는 None. → (mp4 바이트, 타임라인)"""
    tl = timeline(cuts, dub)
    with tempfile.TemporaryDirectory() as td:
        parts = []
        for i, (c, seg) in enumerate(zip(cuts, tl)):
            if on_step:
                on_step(i, len(cuts), c["id"])
            cell = clips.get(c["id"]) or {}
            use_clip = c["motion"] != "still" and cell.get("key") and not (cell.get("fallback") and not cell.get("qc_ok"))
            still = get(stills[c["id"]]["pick"]) if (stills.get(c["id"]) or {}).get("pick") else None
            if not use_clip and not still:
                raise RuntimeError(f"{c['id']}: 스틸이 없습니다")
            if not use_clip and c.get("screen_text"):
                sb = screen_box(c, still) if screen_box else None
                if isinstance(sb, dict) and sb.get("quad"):                    # 네 모서리를 찾았으면 화면 전체를 그려 붙인다
                    still = draw_screen_ui(still, c["screen_text"], sb["quad"], sb.get("kind", "phone"))
                    seg["screen"] = "quad"
                else:
                    still = draw_screen_text(still, c["screen_text"], tuple(sb) if sb else None)
                    seg["screen"] = "box" if sb else "none"
            d = c.get("dialogue") or {}
            ko = d.get("text", "")
            en = (subs.get("lines") or {}).get(c["id"], "") if english and ko else ""
            ov = overlay_png(ko, en, hook if seg["start"] < 2.4 else "") if (ko or (hook and seg["start"] < 2.4)) else None
            au = get(dub[c["id"]]["key"]) if ko and (dub.get(c["id"]) or {}).get("key") else None
            sub = os.path.join(td, f"c{i:02d}")
            os.makedirs(sub, exist_ok=True)
            out = os.path.join(td, f"p{i:02d}.mp4")
            q = (cell.get("qc_by") or {}).get(cell.get("key")) or cell.get("qc") or {}
            plan = render_cut(out, seg["dur"], still=None if use_clip else still, clip=get(cell["key"]) if use_clip else None,
                              camera=c.get("camera", "고정"), overlay=ov, audio=au, workdir=sub,
                              clip_start=float((q.get("motion") or {}).get("start", 0) or 0),
                              sync=bool(use_clip and cell.get("lipsync")),
                              # 엔진이 만든 립싱크 영상은 음성 앞에 0.1초 무음을 넣어 보냈고, 바깥에서 만들어 올린 립싱크 영상은 무음 없이 만든 것으로 본다
                              audio_delay=max(-700, (0 if use_clip and cell.get("lipsync") and cell.get("manual") else 100)
                                              + (int(cell.get("sync_ms") or 0) if use_clip and cell.get("lipsync") else 0)),
                              voice="phone" if cutter_is_phone(c) else "")
            seg["lipsync"] = bool(use_clip and cell.get("lipsync"))
            seg["kind"] = "clip" if use_clip else "still"
            if plan:
                seg.update({"clip_start": plan["start"], "slow": plan["slow"], "frozen": plan["frozen"]})
            parts.append(out)
        final = os.path.join(td, "final.mp4")
        concat(parts, final)
        if sound and (sound.get("bgm") or sound.get("sfx")):
            if on_step:
                on_step(len(cuts), len(cuts), "음악·효과음")
            starts = {c["id"]: seg["start"] for c, seg in zip(cuts, tl)}
            mixed = os.path.join(td, "mixed.mp4")
            mix_sound(final, mixed, sound.get("bgm"), [(b, starts[cid]) for cid, b in (sound.get("sfx") or []) if cid in starts],
                      tl[-1]["start"] + tl[-1]["dur"] if tl else 0.0, td)
            final = mixed
        return open(final, "rb").read(), tl


BGM_VOL, SFX_VOL = 0.30, 0.85          # 배경 음악은 대사 밑에 깔리게, 대사가 나오면 더 내려감(사이드체인)


def mix_sound(src: str, out: str, bgm: bytes | None, sfx: list, dur: float, workdir: str) -> None:
    """완성본에 배경 음악(대사가 나올 때 자동으로 낮아짐)과 효과음(컷 시작 시각)을 섞는다. 영상은 다시 인코딩하지 않음."""
    args, fc, mix = ["ffmpeg", "-v", "error", "-y", "-i", src], ["[0:a]aresample=44100,asplit=2[dlg][sc]"], ["[dlg]"]
    idx = 1
    if bgm:
        bp = os.path.join(workdir, "bgm.mp3")
        open(bp, "wb").write(bgm)
        args += ["-stream_loop", "-1", "-i", bp]
        fo = max(0.0, dur - 1.6)
        fc.append(f"[{idx}:a]aresample=44100,atrim=0:{dur:.2f},asetpts=PTS-STARTPTS,afade=t=in:d=0.6,afade=t=out:st={fo:.2f}:d=1.5,"
                  f"volume={BGM_VOL}[bg]")
        fc.append("[bg][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[bgd]")
        mix.append("[bgd]")
        idx += 1
    else:
        fc[0] = "[0:a]aresample=44100[dlg]"
    for i, (b, t0) in enumerate(sfx):
        fp = os.path.join(workdir, f"sfx{i}.mp3")
        open(fp, "wb").write(b)
        args += ["-i", fp]
        ms = int(max(0.0, t0) * 1000)
        fc.append(f"[{idx}:a]aresample=44100,adelay={ms}|{ms},volume={SFX_VOL}[s{i}]")
        mix.append(f"[s{i}]")
        idx += 1
    fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,alimiter=limit=0.95[a]")
    args += ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-t", f"{dur:.2f}", out]
    p = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if p.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"ffmpeg 음악·효과음: {p.stderr[-400:]}")
