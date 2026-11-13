"""06 더빙: ElevenLabs 로 인물별 고정 목소리의 대사를 만든다 (2026-11-13, v1.0).

공식 문서(2026-11-13 확인)
- 목소리 목록  GET  {API}/v2/voices?page_size=100[&search=…]          → {"voices":[{voice_id,name,category,labels{gender,age,accent,language,…},
                                                                       description,preview_url,verified_languages[]}], "has_more", "next_page_token"}
- 대사 만들기  POST {API}/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128
               본문 {"text","model_id","voice_settings":{stability,similarity_boost,style,use_speaker_boost,speed},"previous_text","next_text"}
               응답 = 음성 파일 바이트. language_code 는 multilingual_v2 에서 지원하지 않으므로 보내지 않는다.
- 받아 적기    POST {API}/v1/speech-to-text  (multipart: model_id=scribe_v2, file, language_code=ko) → {"text": …}
- 인증: 헤더 xi-api-key

더빙 검수: 만든 음성을 다시 글자로 받아 적어 대본과 비교한다. 다르게 읽혔으면 다시 만든다 (사람이 하나하나 듣지 않아도 되게).
"""
from __future__ import annotations

import difflib
import os
import re
import subprocess
import tempfile

API = os.environ.get("ELEVEN_API_BASE", "https://api.elevenlabs.io")
TTS_MODEL = "eleven_multilingual_v2"
STT_MODEL = "scribe_v2"
FORMAT = "mp3_44100_128"
SETTINGS = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True, "speed": 1.0}
PASS = 0.8            # 받아 적은 글자와 대본이 이만큼 같으면 합격 (띄어쓰기·문장부호 제외)


def _h(key: str) -> dict:
    return {"xi-api-key": key}


def _err(r) -> str:
    try:
        d = r.json().get("detail")
        msg = d.get("message") if isinstance(d, dict) else d
    except Exception:
        msg = r.text[:200]
    return f"ElevenLabs {r.status_code}: {str(msg)[:200]}"


def voices(key: str, search: str = "") -> list[dict]:
    """쓸 수 있는 목소리 목록 (최대 300개). → [{id, name, gender, age, accent, language, desc, preview, category, ko}]"""
    import requests
    out, token = [], None
    for _ in range(3):
        params = {"page_size": 100, "include_total_count": "false"}
        if search:
            params["search"] = search
        if token:
            params["next_page_token"] = token
        r = requests.get(f"{API}/v2/voices", headers=_h(key), params=params, timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(_err(r))
        d = r.json()
        for v in d.get("voices", []):
            lb = v.get("labels") or {}
            langs = [x.get("language", "") for x in (v.get("verified_languages") or [])]
            out.append({"id": v.get("voice_id"), "name": v.get("name", ""), "gender": lb.get("gender", ""), "age": lb.get("age", ""),
                        "accent": lb.get("accent", ""), "language": lb.get("language", ""), "desc": (v.get("description") or "")[:120],
                        "preview": v.get("preview_url") or "", "category": v.get("category", ""),
                        "ko": "ko" in langs or lb.get("language") in ("ko", "korean", "Korean")})
        token = d.get("next_page_token")
        if not d.get("has_more") or not token:
            break
    return [v for v in out if v["id"]]


def voice_label(v: dict) -> str:
    g = {"male": "남", "female": "여"}.get(v.get("gender", ""), v.get("gender", ""))
    bits = [x for x in (g, v.get("age", ""), v.get("accent", ""), "한국어" if v.get("ko") else "") if x]
    return f"{v['name']}" + (f" · {' · '.join(bits)}" if bits else "")


def speak(key: str, voice_id: str, text: str, prev: str = "", nxt: str = "", model: str = "", speed: float = 1.0) -> bytes:
    """대사 한 줄 → mp3 바이트."""
    import requests
    body = {"text": text, "model_id": model or TTS_MODEL, "voice_settings": {**SETTINGS, "speed": float(speed)}}
    if prev:
        body["previous_text"] = prev
    if nxt:
        body["next_text"] = nxt
    r = requests.post(f"{API}/v1/text-to-speech/{voice_id}", headers={**_h(key), "Content-Type": "application/json"},
                      params={"output_format": FORMAT}, json=body, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(_err(r))
    if len(r.content) < 500:
        raise RuntimeError("ElevenLabs: 음성이 비어 있습니다")
    return r.content


def transcribe(key: str, mp3: bytes) -> str:
    """음성 → 받아 적은 글자."""
    import requests
    r = requests.post(f"{API}/v1/speech-to-text", headers=_h(key), data={"model_id": STT_MODEL, "language_code": "ko"},
                      files={"file": ("line.mp3", mp3, "audio/mpeg")}, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(_err(r))
    return str(r.json().get("text", "")).strip()


def _plain(t: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t or "")


def similarity(script: str, heard: str) -> float:
    a, b = _plain(script), _plain(heard)
    if not a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def seconds(mp3: bytes) -> float:
    """음성 길이(초). ffprobe 가 없으면 128kbps 기준으로 어림."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            f.write(mp3)
            f.flush()
            p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f.name],
                               capture_output=True, text=True, timeout=30)
            return round(float(p.stdout.strip()), 2)
    except Exception:
        return round(len(mp3) / 16000, 2)


def make_line(key: str, voice_id: str, text: str, prev: str = "", nxt: str = "", model: str = "", speed: float = 1.0,
              check: bool = True, tries: int = 2) -> dict:
    """대사 한 줄을 만들고 받아 적기로 검수한다. 다르게 읽혔으면 다시 만들어 가장 비슷한 것을 고른다.
    → {'mp3', 'sec', 'heard', 'score', 'pass', 'tries', 'note'}"""
    best = None
    for i in range(1 + (tries if check else 0)):
        mp3 = speak(key, voice_id, text, prev, nxt, model, speed)
        heard, score, note = "", 1.0, ""
        if check:
            try:
                heard = transcribe(key, mp3)
                score = similarity(text, heard)
            except Exception as ex:                  # 받아 적기가 실패하면 음성은 살리고 표시만
                note = f"받아 적기 실패: {str(ex)[:100]}"
        cur = {"mp3": mp3, "sec": seconds(mp3), "heard": heard, "score": round(score, 2), "pass": score >= PASS, "tries": i + 1, "note": note}
        if best is None or cur["score"] > best["score"]:
            best = cur
        if cur["pass"] or note:
            break
    return best


def context(cuts: list, i: int) -> tuple[str, str]:
    """같은 인물의 대사가 앞뒤 컷에 이어지면(한 문장을 두 컷으로 나눈 경우) 억양이 이어지도록 앞·뒤 글을 넘긴다."""
    d = cuts[i]["dialogue"]
    prev = nxt = ""
    if i > 0 and (cuts[i - 1].get("dialogue") or {}).get("who") == d["who"]:
        prev = cuts[i - 1]["dialogue"]["text"]
    if i + 1 < len(cuts) and (cuts[i + 1].get("dialogue") or {}).get("who") == d["who"]:
        nxt = cuts[i + 1]["dialogue"]["text"]
    return prev, nxt
