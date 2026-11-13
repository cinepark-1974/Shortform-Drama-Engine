"""07 자막 · 08 편집: 컷(스틸·영상) + 더빙 + 자막을 9:16 한 화로 이어 붙인다 (2026-11-13, v1.1).

방식 (Streamlit 메모리 1GB 안에서 돌도록 컷 하나씩 따로 만든 뒤 이어 붙임)
1. 타임라인: 컷 길이 = max(콘티 길이, 더빙 길이 + 0.25초).
2. 컷마다 ffmpeg 한 번: 영상 컷은 잘라 쓰고(모자라면 마지막 장면을 늘림), 정지 컷은 스틸에 카메라 움직임(줌·팬)을 넣는다.
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


def render_cut(out_path: str, dur: float, still: bytes | None = None, clip: bytes | None = None, camera: str = "고정",
               overlay: bytes | None = None, audio: bytes | None = None, workdir: str = "") -> None:
    """컷 하나를 1080x1920 mp4 로. clip 이 있으면 영상 컷, 없으면 still 정지 컷."""
    d = workdir or os.path.dirname(out_path)
    n = max(1, int(round(dur * FPS)))
    args, fc = ["ffmpeg", "-v", "error", "-y"], []
    if clip:
        src = os.path.join(d, "src.mp4")
        open(src, "wb").write(clip)
        args += ["-i", src]
        fc.append(f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                  f"tpad=stop_mode=clone:stop_duration={dur:.2f},setsar=1[v0]")
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
        fc.append(f"[{idx}:a]aresample=44100,adelay=100|100,apad[a]")
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        fc.append(f"[{idx}:a]anull[a]")
    args += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", out_path]
    p = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if p.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"ffmpeg: {p.stderr[-400:]}")


def concat(paths: list[str], out_path: str) -> None:
    lst = out_path + ".txt"
    with open(lst, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                        "-movflags", "+faststart", out_path], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg concat: {p.stderr[-400:]}")


def render_episode(cuts: list, get, stills: dict, clips: dict, dub: dict, subs: dict, hook: str = "", english: bool = True,
                   screen_box=None, on_step=None) -> tuple[bytes, list]:
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
                still = draw_screen_text(still, c["screen_text"], screen_box(c, still) if screen_box else None)
            d = c.get("dialogue") or {}
            ko = d.get("text", "")
            en = (subs.get("lines") or {}).get(c["id"], "") if english and ko else ""
            ov = overlay_png(ko, en, hook if seg["start"] < 2.4 else "") if (ko or (hook and seg["start"] < 2.4)) else None
            au = get(dub[c["id"]]["key"]) if ko and (dub.get(c["id"]) or {}).get("key") else None
            sub = os.path.join(td, f"c{i:02d}")
            os.makedirs(sub, exist_ok=True)
            out = os.path.join(td, f"p{i:02d}.mp4")
            render_cut(out, seg["dur"], still=None if use_clip else still, clip=get(cell["key"]) if use_clip else None,
                       camera=c.get("camera", "고정"), overlay=ov, audio=au, workdir=sub)
            parts.append(out)
        final = os.path.join(td, "final.mp4")
        concat(parts, final)
        return open(final, "rb").read(), tl
