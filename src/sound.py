"""배경 음악 · 효과음 (ElevenLabs).

- 효과음: POST {API}/v1/sound-generation?output_format=mp3_44100_128
  본문 {"text", "duration_seconds"(0.5~22), "prompt_influence"(0~1)} → mp3 바이트
- 음악:   POST {API}/v1/music?output_format=mp3_44100_128
  본문 {"prompt", "music_length_ms"(3000~600000), "force_instrumental": true} → mp3 바이트
- 인증: 헤더 xi-api-key (더빙과 같은 ELEVENLABS_API_KEY)
어떤 소리를 넣을지는 Claude 가 콘티를 읽고 정한다 (plan).
"""
import json
import os

import requests

API = os.environ.get("ELEVEN_API_BASE", "https://api.elevenlabs.io")
SFX_MAX = 5            # 한 화 효과음 상한: 많으면 대사가 묻힌다


def _post(key: str, path: str, body: dict, timeout: int) -> bytes:
    r = requests.post(f"{API}{path}", params={"output_format": "mp3_44100_128"}, json=body,
                      headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"}, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {path} {r.status_code}: {r.text[:300]}")
    return r.content


def sfx(key: str, text: str, sec: float) -> bytes:
    return _post(key, "/v1/sound-generation",
                 {"text": text, "duration_seconds": round(max(0.5, min(22.0, float(sec))), 2), "prompt_influence": 0.6}, 120)


def music(key: str, prompt: str, sec: float) -> bytes:
    return _post(key, "/v1/music",
                 {"prompt": prompt, "music_length_ms": int(max(3000, min(600000, sec * 1000))), "force_instrumental": True}, 600)


PLAN_SYSTEM = f"""한국어 1분 세로 숏폼 드라마 한 화의 콘티를 읽고 배경 음악 한 곡과 효과음을 정합니다.

배경 음악 (bgm)
- 영어 프롬프트 한 문장. 가사 없음(instrumental). 장르·분위기·템포·악기를 확정형으로.
- 대사를 덮지 않는 낮은 밀도의 음악. 화의 감정 흐름(예: 평온한 출근 → 불안 → 충격)을 한 곡 안의 변화로 적음.
- 예: "Tense minimal Korean drama underscore, soft piano and low strings, 80 BPM, calm opening that grows uneasy, ends on a suspended dark chord, no vocals."

효과음 (sfx) — 최대 {SFX_MAX}개
- 화면에서 실제로 나는 소리 중 이야기에 중요한 것만: 휴대폰 진동·벨소리(화면 글자 컷이 전화 수신이면 반드시), 게이트 카드 찍는 소리, 문 닫힘, 서류 내려놓는 소리.
- 클라이맥스 컷과 마지막 컷에는 숏폼 드라마의 충격음 하나씩 넣어도 됨: "deep cinematic impact hit with short reverb tail".
- 사무실 웅성거림 같은 배경 소음은 넣지 않음.
- 각 항목: id(컷 id), en(영어 효과음 설명, 한 문장), sec(0.5~4초).

JSON 만 출력: {{"bgm": "...", "sfx": [{{"id": "1-3", "en": "...", "sec": 1.5}}]}}"""


def plan(api_key: str, hook: str, cuts: list, model: str = "") -> dict:
    """콘티 → {'bgm': 영어 프롬프트, 'sfx': [{'id','en','sec'}]}"""
    import anthropic
    from json_repair import repair_json
    brief = [{"id": c["id"], "dur": c.get("dur"), "climax": bool(c.get("climax")), "frame": c.get("frame_ko", ""),
              "action": c.get("action", ""), "sfx": c.get("sfx", ""), "screen_text": c.get("screen_text", ""),
              "line": (c.get("dialogue") or {}).get("text", "")} for c in cuts]
    cl = anthropic.Anthropic(api_key=api_key)
    r = cl.messages.create(model=model or "claude-sonnet-4-5", max_tokens=2000, system=PLAN_SYSTEM,
                           messages=[{"role": "user", "content": json.dumps({"hook": hook, "cuts": brief}, ensure_ascii=False)}])
    d = json.loads(repair_json("".join(b.text for b in r.content if getattr(b, "type", "") == "text")))
    ids = {c["id"] for c in cuts}
    out = []
    for x in d.get("sfx") or []:
        if isinstance(x, dict) and str(x.get("id")) in ids and str(x.get("en", "")).strip():
            out.append({"id": str(x["id"]), "en": str(x["en"]).strip(), "sec": max(0.5, min(4.0, float(x.get("sec") or 1.5)))})
    return {"bgm": str(d.get("bgm", "")).strip(), "sfx": out[:SFX_MAX]}
