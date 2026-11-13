"""BLUE JEANS · SHORTFORM DRAMA ENGINE  (숏폼드라마 엔진) v0.9

1인 운영 자동화 엔진. Shortform-Engine 대본 → 작품 정리 → 캐스팅 → 회당 컷 분할 → 스틸 → 영상 → 더빙 → 자막 → 편집 → 마스터.
v0.2 범위: 01 대본(작품 정리·정리본 내보내기) · 02 캐스팅 · 03 회당 컷 분할. 04 이후는 자리만.
화면 구성은 「3 MINUTES 제작 콘솔」(단계 띠 · 지금 할 일 · 상태 칸), 색은 블루진 엔진 공통 규칙.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st

from src import videogen, bible as bb
from src import cutter, dubbing, imagegen, profiles, qc, script_parser
from src.store import Store, secrets_dict

VERSION = "v1.0"
st.set_page_config(page_title="숏폼드라마 엔진", page_icon="🎬", layout="wide")

# ───────── 화면 색: 밝은 푸른 바탕, 포인트 #191970 · #FFCB05, Paperlogy, 그림자·그라데이션 없음 ─────────
st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/fonts-archive/Paperlogy/subsets/Paperlogy-dynamic-subset.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&display=swap">
<style>
:root{--navy:#191970;--y:#FFCB05;--bg:#F4F8FD;--card:#FFFFFF;--line:#D6E2EA;--ink:#1A1F3A;--muted:#5F6B85;
--blue:#3B6FD8;--ok-bg:#E8EEFA;--warn-bg:#FFF6CC;--fix:#C62828;--fix-bg:#FDECEC}
html,body,[class*="css"],.stApp,button,input,textarea{font-family:"Paperlogy",-apple-system,"Apple SD Gothic Neo",sans-serif!important}
.stApp{background:var(--bg)!important;color:var(--ink)}
[data-testid="stSidebar"]{background:var(--card)!important;border-right:1px solid var(--line)}
[data-testid="stHeader"]{background:transparent!important}
h1,h2,h3,h4{color:var(--navy)!important}
.stButton>button,.stDownloadButton>button{border:1px solid var(--line)!important;border-radius:8px!important;font-weight:700!important;box-shadow:none!important;background:var(--card)!important;color:var(--navy)!important}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--navy)!important}
.stButton>button[kind="primary"]{background:var(--y)!important;color:var(--navy)!important;border-color:var(--y)!important}
.stButton>button:disabled{opacity:.4!important}
[data-testid="stExpander"]{background:var(--card);border:1px solid var(--line)!important;border-radius:12px!important}
.stTabs [aria-selected="true"]{color:var(--navy)!important}
.stTabs [data-baseweb="tab-highlight"]{background:var(--y)!important}
.brand{background:var(--card);border:1px solid var(--line);border-bottom:4px solid var(--y);padding:16px 22px;border-radius:12px;margin-bottom:10px}
.brand .co{font-size:11px;font-weight:700;letter-spacing:.2em;color:var(--muted)}
.brand .ti{font-size:22px;font-weight:900;margin-top:2px;color:var(--navy)}
.brand .ver{font-family:"JetBrains Mono",monospace;font-size:11px;color:var(--navy);background:var(--y);padding:1px 6px;border-radius:4px;margin-left:8px;font-weight:700}
.brand .m{float:right;text-align:right;font-size:12px;color:var(--muted);line-height:1.6}.brand .m b{color:var(--navy)}
.pipe{display:flex;gap:4px;overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px;margin-bottom:10px}
.ps{flex:1 0 92px;padding:6px 8px;border-radius:9px;color:var(--navy)}
.ps .n{font-size:10px;color:var(--muted);letter-spacing:.1em;font-family:"JetBrains Mono",monospace}.ps .t{font-size:13px;font-weight:800;white-space:nowrap}
.ps .c{font-size:11px;color:var(--muted);white-space:nowrap}
.ps .b{height:3px;background:var(--line);border-radius:2px;margin-top:4px;overflow:hidden}.ps .b i{display:block;height:100%;background:var(--blue)}
.ps.on{background:var(--navy);color:#fff}.ps.on .n,.ps.on .c{color:rgba(255,255,255,.85)}.ps.on .b i{background:var(--y)}
.ps.lock{opacity:.4}
.brief{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--navy);border-radius:12px;padding:12px 16px;margin-bottom:12px}
.brief .now{font-size:16px;font-weight:800;color:var(--navy)}.brief .now em{font-style:normal;background:var(--y);color:var(--navy);padding:0 6px;border-radius:4px}
.brief .how{font-size:12.5px;color:var(--muted);margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(20,1fr);gap:4px}
.cell{font-size:11px;font-weight:700;text-align:center;padding:6px 0;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--muted);font-family:"JetBrains Mono",monospace}
.cell.done{background:var(--navy);color:#fff;border-color:var(--navy)}.cell.doing{background:var(--ok-bg);color:var(--navy);border-color:var(--blue)}
.cell.fix{background:var(--fix-bg);color:var(--fix);border-color:var(--fix)}
.tag{display:inline-block;font-size:11px;font-weight:800;padding:1px 8px;border-radius:99px;margin-right:4px}
.tag.ok{background:var(--ok-bg);color:var(--navy)}.tag.todo{background:var(--warn-bg);color:var(--navy)}.tag.fix{background:var(--fix-bg);color:var(--fix)}
.tag.mv{background:var(--navy);color:#fff}
.hook{font-weight:800;color:var(--fix)}.dlg b{color:var(--navy)}
.small{font-size:12px;color:var(--muted)}
.issue{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--y);border-radius:8px;padding:8px 12px;margin-bottom:6px;font-size:13px}
.issue b{color:var(--navy)}
.cut{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:6px}
.cut .h{font-size:13px;font-weight:800;color:var(--navy)}.cut .h .d{color:var(--blue);font-family:"JetBrains Mono",monospace;margin-left:6px}
.cut .a{font-size:13.5px;margin-top:3px}.cut .s{font-size:12px;color:var(--muted);margin-top:2px}
.rt{height:10px;border-radius:5px;background:var(--bg);border:1px solid var(--line);overflow:hidden;display:flex;margin:4px 0 10px}
.rt i{display:block;height:100%;border-right:1px solid #fff}
.ov{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:10px}
.ov .top{display:flex;gap:18px;align-items:flex-end;flex-wrap:wrap;margin-bottom:8px}
.ov .big{font-size:40px;font-weight:900;color:var(--navy);line-height:1;font-family:"JetBrains Mono",monospace}
.ov .big small{font-size:16px}
.ov .bar{flex:1 1 220px;min-width:200px}
.ov .bar .tr{height:12px;border-radius:6px;background:var(--bg);border:1px solid var(--line);overflow:hidden}
.ov .bar .tr i{display:block;height:100%;background:linear-gradient(90deg,var(--navy),#3B4BC8)}
.ov .bar .lb{font-size:11px;color:var(--muted);margin-bottom:3px}
.ov .kpi{min-width:92px}.ov .kpi .v{font-size:20px;font-weight:900;color:var(--navy);font-family:"JetBrains Mono",monospace}
.ov .kpi .k{font-size:11px;color:var(--muted)}
.ov .next{font-size:13px;color:var(--navy);margin:2px 0 8px}.ov .next em{font-style:normal;background:var(--y);padding:0 6px;border-radius:4px;font-weight:800}
.hm{display:grid;grid-template-columns:repeat(20,1fr);gap:3px}
.hm div{font-size:10px;font-weight:700;text-align:center;padding:4px 0;border-radius:4px;border:1px solid var(--line);color:var(--muted);font-family:"JetBrains Mono",monospace}
.hm div.g{border-left:3px solid var(--y)}
.hm div.fx{outline:2px solid var(--fix);outline-offset:-2px}
.lg{display:flex;gap:10px;flex-wrap:wrap;font-size:11px;color:var(--muted);margin-top:6px}
.lg span i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:4px;vertical-align:-1px;border:1px solid var(--line)}
</style>""", unsafe_allow_html=True)

KEYS = secrets_dict()
store = Store(KEYS)
SAMPLES = Path(__file__).parent / "samples"

STAGES = [
    ("script", "01", "대본", "원고 읽기 · 작품 정리"),
    ("cast", "02", "캐스팅", "인물 · 장소 기준 이미지"),
    ("cut", "03", "콘티", "컷 나누기 · 첫 장면 · 움직임"),
    ("still", "04", "콘티 그림", "컷별 첫 장면 스틸 · 자동 검수"),
    ("clip", "05", "영상", "움직임 · 완전 영상"),
    ("dub", "06", "더빙", "인물별 고정 목소리"),
    ("sub", "07", "자막·사운드", "한/영 자막 · 효과음"),
    ("edit", "08", "편집", "9:16 렌더링"),
    ("master", "09", "마스터", "확인 · 업로드"),
]
HOW = {
    "dub": "콘티의 대사를 인물별 고정 목소리로 만듭니다 (ElevenLabs). 만든 음성을 다시 글자로 받아 적어 대본과 비교하고, 다르게 읽힌 줄은 2회까지 다시 만듭니다. 음성이 컷보다 길면 편집에서 컷을 늘립니다.",
    "clip": "확정한 스틸을 첫 프레임으로 넣어 짧은 영상을 만듭니다 (Replicate · Kling). 테이크마다 첫·중간·마지막 장면을 Claude 가 검수하고, 불합격이면 고쳐서 2회까지 다시 만듭니다. 그래도 불합격이면 그 컷은 정지+카메라로 바꿉니다. 소리는 06·07 단계에서 얹습니다.",
    "still": "컷마다 장면 그림을 만듭니다. 인물 확정 그림과 장소 마스터를 기준 그림으로 넣고, 만든 직후 Claude 가 자동 검수합니다(지시문 대상·동작·몸에 거는 소품·같은 얼굴·글자·손). 불합격이면 이유를 지시문에 붙여 2회까지 다시 만들고, 그래도 불합격인 컷만 빨간 표시가 남습니다.",
    "script": "대본을 읽고 작품 정리를 합니다. 엔진은 인물 표기와 장소 세트만 통일하고, 설정 충돌은 '수정 제안'으로 남깁니다. 원고 수정은 감독님이 직접 하고, 고친 원고를 다시 올리면 됩니다.",
    "cast": "인물마다 프로필을 확정하고 얼굴 후보 중 1장을 고릅니다. 장소는 넓은 마스터 1장을 고릅니다. 직접 만든 이미지는 올리기로 넣습니다.",
    "cut": "대본을 콘티로 바꿉니다. 컷마다 '첫 장면'(스틸로 찍을 사진 한 장, 정지된 한 순간)과 '움직임'(영상에서 일어날 동작 하나)을 따로 쓰고, 감수 AI가 사진 한 장으로 찍히지 않는 컷을 고치거나 나눕니다. 한 화를 14~16컷, 50~70초로 잘게 나눕니다 (보통 컷 1.5~3초, 클라이맥스 한 컷만 4~6초 버티기). 말하는 얼굴은 정지 컷 2.5초 이하, 긴 대사는 듣는 사람 컷으로 이어 갑니다. 컷마다 크기·각도·움직임 종류·대사·화면 글자를 정하고 스틸·영상 지시문을 만듭니다. 빨간 표시는 고쳐야 할 컷입니다.",
}


def slug(name: str) -> str:
    s = re.sub(r"\s+", "_", name.strip())
    return re.sub(r"[^\w가-힣_-]", "", s) or uuid.uuid4().hex[:6]


KST = dt.timezone(dt.timedelta(hours=9))


def now() -> str:
    return dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")


EMBLEMS = Path(__file__).parent / "assets" / "emblems"


def emblem_list(work: dict) -> dict:
    """벽 엠블럼(회사 CI) 목록 {키: 이름}. 저장소 assets/emblems 의 파일 + 이 작품에 올린 것."""
    out = {}
    try:
        meta = json.loads((EMBLEMS / "emblems.json").read_text("utf-8"))
    except Exception:
        meta = {}
    for f, m in meta.items():
        if (EMBLEMS / f).exists():
            out["repo:" + f] = m.get("label", f)
    for name, k in (work.get("emblems") or {}).items():
        out[k] = name
    return out


def emblem_of(work: dict, loc_id: str, loc_name: str = "") -> str:
    """장소에 걸린 엠블럼 키. 고른 적이 없으면 장소 이름으로 자동 연결(예: '대성' → 대성그룹 CI). 없으면 ''."""
    info = work.get("loc", {}).get(loc_id, {})
    if "emblem" in info:
        return info["emblem"] or ""
    try:
        meta = json.loads((EMBLEMS / "emblems.json").read_text("utf-8"))
    except Exception:
        return ""
    for f, m in meta.items():
        if any(w in loc_name for w in m.get("match", [])) and (EMBLEMS / f).exists():
            return "repo:" + f
    return ""


@st.cache_data(show_spinner=False, ttl=600)
@st.cache_data(max_entries=400, show_spinner=False)
def img_bytes(key: str):
    if key.startswith("repo:"):
        return (EMBLEMS / key[5:]).read_bytes()
    return store.get_bytes(key)      # 그림 파일 이름은 매번 새로 만들어지므로 저장해 두고 다시 써도 안전


def save(work: dict):
    work["updated"] = now()
    store.save_work(work)


# ───────── 작품 상태 ─────────
def chars_ranked(work: dict) -> list[str]:
    b = work.get("bible")
    if not b:
        return []
    n = bb.stats(b, work["parsed"])["lines"]
    names = [c["name"] for c in b["characters"]]
    return sorted(names, key=lambda x: -n.get(x, 0))


def locs_ranked(work: dict) -> list[dict]:
    b = work.get("bible")
    if not b:
        return []
    n = bb.stats(b, work["parsed"])["loc"]
    return sorted(b["locations"], key=lambda l: -n.get(l["id"], 0))


def cast_locs(work: dict) -> list[dict]:
    """캐스팅할 장소: 장면 많은 순 상위 loc_n 곳 + 감독님이 따로 추가한 곳(loc_extra)."""
    allr = locs_ranked(work)
    top = allr[: work.get("loc_n", 8)]
    ids = {l["id"] for l in top}
    return top + [l for l in allr if l["id"] in work.get("loc_extra", []) and l["id"] not in ids]


def sheet_of(info: dict) -> dict:
    """캐스팅 시트 {front, side, full, back} → 저장 키. 정면이 바뀌어 예전 정면으로 만든 시트는 쓰지 않는다."""
    if not info.get("pick"):
        return {}
    out = {"front": info["pick"]}
    if info.get("views_of") == info["pick"]:
        out.update({k: v for k, v in (info.get("views") or {}).items() if v})
    return out


def look_info(work: dict, name: str, look: str | None):
    """인물의 분장·의상(룩) 정보. '기본'이거나 등록되지 않은 룩이면 None (확정 캐스팅 그림을 씀)."""
    if not look or look == "기본":
        return None
    return (work.get("cast", {}).get(name, {}).get("looks") or {}).get(look)


def look_text(work: dict, c: dict) -> dict:
    """컷에 배정된 룩 → {인물: (영어 설명, 룩 기준 그림이 있는가)}. 스틸 지시문에 들어간다."""
    out = {}
    for w, l in (c.get("looks") or {}).items():
        li = look_info(work, w, l)
        if li and li.get("prompt_en"):
            out[w] = (li["prompt_en"], bool(li.get("pick")))
    return out


def look_notes(work: dict) -> dict:
    """콘티에 넘기는 룩 목록 {인물: {룩 이름: 한 줄 설명}}."""
    return {n: {k: (v.get("note") or v.get("prompt_en", ""))[:120] for k, v in (info.get("looks") or {}).items()}
            for n, info in work.get("cast", {}).items() if info.get("pick")}


def view_notes(work: dict) -> dict:
    """콘티에 넘기는 장소 시점 목록 {장소 id: {시점 이름: 한 줄 설명}}."""
    return {lid: {k: (v.get("note") or v.get("prompt_en", ""))[:100] for k, v in (info.get("views") or {}).items()}
            for lid, info in work.get("loc", {}).items() if info.get("views")}


def prop_texts(work: dict) -> dict:
    """글자가 인쇄된 소품 {소품 이름: 글자}."""
    return {n: v["text"] for n, v in work.get("props", {}).items() if v.get("text")}


def set_loc(work: dict) -> dict:
    """장소에 놓인 소품 {소품 이름: 장소 id}."""
    return {n: v.get("loc", "") for n, v in work.get("props", {}).items() if v.get("kind") == "set" and v.get("loc")}


def register_prep(work: dict, bd: dict) -> int:
    """브레이크다운 결과를 작품에 등록한다 (이미 있는 것은 그대로). 등록한 개수를 돌려준다."""
    n = 0
    for x in bd.get("views", []):
        vs = work.setdefault("loc", {}).setdefault(x["loc"], {}).setdefault("views", {})
        if x["name"] not in vs:
            vs[x["name"]] = {"prompt_en": x["desc_en"], "note": x["note_ko"]}
            n += 1
    for x in bd.get("props", []):
        if x["name"] not in work.setdefault("props", {}):
            work["props"][x["name"]] = {"prompt_en": x["desc_en"], "note": x["note_ko"], "kind": x["kind"], "loc": x["loc"]}
            n += 1
    for x in bd.get("looks", []):
        if x["who"] in work.get("cast", {}):
            lk = work["cast"][x["who"]].setdefault("looks", {})
            if x["name"] not in lk:
                lk[x["name"]] = {"prompt_en": x["desc_en"], "note": x["note_ko"]}
                n += 1
    return n


def prep_items(work: dict, ep_key: str, loc_names: dict) -> list:
    """이 화의 준비물 점검표: 콘티가 쓰는 장소 시점·소품·분장의상 + 브레이크다운이 뽑은 것. 기준 그림이 있는지 표시."""
    cuts = work.get("cuts", {}).get(ep_key, {}).get("cuts", [])
    pre = work.get("prep", {}).get(ep_key, {})
    views = {(c["loc"], c["view"]) for c in cuts if c.get("view")} | {tuple(x) for x in pre.get("views", [])}
    props = {n for c in cuts for n in c.get("props", [])} | set(pre.get("props", []))
    looks = {(w, l) for c in cuts for w, l in (c.get("looks") or {}).items()} | {tuple(x) for x in pre.get("looks", [])}
    used_locs = {c["loc"] for c in cuts} | {v[0] for v in views}
    out = []
    for lid in sorted(used_locs):
        info = work.get("loc", {}).get(lid, {})
        out.append({"kind": "master", "label": f"장소 · {lid} {loc_names.get(lid, '')} (마스터)", "ready": bool(info.get("pick")), "info": info})
    for lid, name in sorted(views):
        info = work.get("loc", {}).get(lid, {}).get("views", {}).get(name)
        if info is not None:
            out.append({"kind": "view", "label": f"장소 시점 · {loc_names.get(lid, lid)} · {name}", "ready": bool(info.get("pick")), "info": info,
                        "ref": work.get("loc", {}).get(lid, {}).get("pick"), "path": f"loc/{slug(lid + '__' + name)}"})
    for n in sorted(props):
        info = work.get("props", {}).get(n)
        if info is not None:
            out.append({"kind": "prop", "label": f"소품 · {n}" + (" (장소에 놓임)" if info.get("kind") == "set" else ""),
                        "ready": bool(info.get("pick")), "info": info, "path": f"prop/{slug(n)}"})
    for w, l in sorted(looks):
        info = look_info(work, w, l)
        if info is not None:
            out.append({"kind": "look", "label": f"분장·의상 · {w} · {l}", "ready": bool(info.get("pick")), "info": info,
                        "ref": work.get("cast", {}).get(w, {}).get("pick"), "path": f"cast/{slug(w + '__' + l)}"})
    return out


def view_for(ch: str, c: dict) -> str:
    """컷의 인물 표기·각도·크기 → 어떤 시트를 기준 그림으로 쓸지."""
    part = ch.partition(":")[2]
    if part == "뒷모습" or c.get("angle") == "뒤에서":
        return "back"
    if part == "손":
        return "front"
    if c.get("angle") in ("3/4 측면", "측면"):
        return "side"
    if c.get("size") in ("WS", "MLS"):
        return "full"
    return "front"


def refresh_cut_status(work: dict | None):
    """콘티 점검 결과(완료/고칠 화)를 지금 규칙으로 다시 계산한다. 규칙이 바뀐 뒤에도 예전 판정이 남지 않게."""
    if not work or not work.get("cuts") or not work.get("bible"):
        return
    b = work["bible"]
    kc, kl = {c["name"] for c in b.get("characters", [])}, {l["id"] for l in b.get("locations", [])}
    eps = work.get("parsed", {}).get("episodes", [])
    for k, rec in work["cuts"].items():
        try:
            scenes = [s_["no"] for s_ in eps[int(k) - 1]["scenes"]]
            iss = cutter.check(cutter.fix_screens(cutter.clean_words(rec["cuts"])), kc, kl, scenes)
        except Exception:
            continue
        # 콘티가 있으면 그 단계는 끝난 것으로 본다. 점검에서 걸린 항목은 빨간 표시로만 남기고 다음 단계를 막지 않는다.
        e_ = work.setdefault("eps", {}).setdefault(k, {})
        e_["cut"], e_["cut_fix"] = "done", sum(1 for i in iss if i["level"] == "fix")


def refresh_clip_status(work: dict | None):
    """영상을 만든 뒤 스틸이 바뀐 컷이 있으면 그 화의 영상 단계를 '진행 중'으로 되돌린다 (사람이 찾아보지 않아도 되게)."""
    if not work:
        return
    for k, rec in (work.get("clips") or {}).items():
        srec = work.get("stills", {}).get(k, {})
        if any(c.get("key") and c.get("still") and c["still"] != srec.get(cid, {}).get("pick") for cid, c in rec.items()):
            if work.get("eps", {}).get(k, {}).get("clip") == "done":
                work["eps"][k]["clip"] = "doing"


def stage_counts(work: dict | None) -> dict:
    refresh_cut_status(work)
    refresh_clip_status(work)
    out = {k: (0, 0) for k, *_ in STAGES}
    if not work:
        return out
    n_ep = work["summary"]["episodes"]
    out["script"] = (1 if work.get("bible") else 0, 1)
    if work.get("bible"):
        chars = chars_ranked(work)[: work.get("main_n", 6)]
        locs = cast_locs(work)
        done = sum(1 for c in chars if work.get("cast", {}).get(c, {}).get("pick")) + \
            sum(1 for l in locs if work.get("loc", {}).get(l["id"], {}).get("pick"))
        out["cast"] = (done, len(chars) + len(locs))
    eps = work.get("eps", {})
    for k in ("cut", "still", "clip", "dub", "sub", "edit", "master"):
        out[k] = (sum(1 for e in eps.values() if e.get(k) == "done"), n_ep)
    return out


def cast_split(work: dict) -> str:
    """캐스팅 칸 수를 인물·장소로 나눠 보여 준다 (예: 인물 5/13 · 장소 8/8)."""
    chars = chars_ranked(work)[: work.get("main_n", 6)]
    locs = cast_locs(work)
    a = sum(1 for c in chars if work.get("cast", {}).get(c, {}).get("pick"))
    b = sum(1 for l in locs if work.get("loc", {}).get(l["id"], {}).get("pick"))
    return f"인물 {a}/{len(chars)} · 장소 {b}/{len(locs)}"


EP_STAGES = ["cut", "still", "clip", "dub", "sub", "edit", "master"]
EP_W = {"cut": 5, "still": 20, "clip": 30, "dub": 10, "sub": 10, "edit": 15, "master": 10}   # 한 화 안에서 작업량 비중(%)
BINGE = 7                                                                                      # 몰아보기 한 편 = 7화


def ep_level(s: dict) -> int:
    """한 화가 앞에서부터 몇 단계까지 끝났는지 (0~7)."""
    n = 0
    for k in EP_STAGES:
        if s.get(k) != "done":
            break
        n += 1
    return n


def shade(level: int) -> tuple[str, str]:
    if level == 0:
        return "#FFFFFF", "var(--muted)"
    if level == 7:
        return "#191970", "#FFCB05"
    a = 0.08 + 0.14 * level
    return f"rgba(25,25,112,{a:.2f})", ("#fff" if level >= 4 else "#191970")


def progress(work: dict) -> dict:
    """작품 전체 진행률. 준비(대본 3 + 캐스팅 7) 10%, 회차 제작 90%."""
    n_ep = work["summary"]["episodes"]
    cnt = stage_counts(work)
    eps = work.get("eps", {})
    a, b = cnt["cast"]
    setup = 3 * cnt["script"][0] + (7 * a / b if b else 0)
    ep_pts = sum(EP_W[k] for s in eps.values() for k in EP_STAGES if s.get(k) == "done")
    pct = setup + 90 * ep_pts / (100 * n_ep) if n_ep else setup
    levels = [ep_level(eps.get(str(i), {})) for i in range(1, n_ep + 1)]
    done = sum(1 for l in levels if l == 7)
    streak = next((i for i, l in enumerate(levels) if l < 7), n_ep)       # EP1부터 끊김 없이 완성된 화 수
    binge_total = -(-n_ep // BINGE)
    binge_ready = sum(1 for g in range(binge_total) if all(l == 7 for l in levels[g * BINGE:(g + 1) * BINGE]))
    left, nk, nep = [], "script", None
    if not work.get("bible"):
        nxt = "01 대본에서 작품 정리"
    elif b and a < b:
        nk = "cast"
        left = [c for c in chars_ranked(work)[: work.get("main_n", 6)] if not work.get("cast", {}).get(c, {}).get("pick")] + \
               [l["name"] for l in cast_locs(work) if not work.get("loc", {}).get(l["id"], {}).get("pick")]
        nxt = f"02 캐스팅 ({cast_split(work)} 확정)"
    elif streak < n_ep:
        nk, nep = EP_STAGES[levels[streak]], streak + 1
        nxt = f"EP {nep} · " + next(f"{n} {t}" for kk, n, t, d in STAGES if kk == nk)
    else:
        nk, nxt = "master", "전 화 완성"
    return {"pct": min(pct, 100), "levels": levels, "done": done, "streak": streak, "n": n_ep,
            "binge": (binge_ready, binge_total), "next": nxt, "next_stage": nk, "next_ep": nep, "left": left}


def heatmap(work: dict, levels: list[int], big: bool = False) -> str:
    eps = work.get("eps", {})
    hooks = {e["ep"]: e["hook"] for e in work["parsed"]["episodes"]}
    names = ["대기"] + [next(t for kk, n, t, d in STAGES if kk == k) + " 완료" for k in EP_STAGES]
    cells = ""
    for i, lv in enumerate(levels, start=1):
        bg, fg = shade(lv)
        e_s = eps.get(str(i), {})
        bad = e_s.get("cut_fix", 0) > 0 or e_s.get("still_qc", 0) > 0 or e_s.get("clip_qc", 0) > 0 or e_s.get("dub_qc", 0) > 0
        cls = ("g " if (i - 1) % BINGE == 0 else "") + ("fx" if bad else "")
        pad = "padding:7px 0;font-size:11px;" if big else ""
        cells += (f'<div class="{cls}" style="{pad}background:{bg};color:{fg}" '
                  f'title="EP {i} · {names[lv]} · {hooks.get(i, "")}">{i}</div>')
    lg = "".join(f'<span><i style="background:{shade(l)[0]}"></i>{names[l]}</span>' for l in range(8))
    return (f'<div class="hm">{cells}</div><div class="lg">{lg}'
            f'<span><i style="border-left:3px solid #FFCB05"></i>몰아보기 7화 묶음 시작</span>'
            f'<span><i style="outline:2px solid #C0392B;outline-offset:-2px"></i>고칠 컷 있음</span></div>')


def overview(work: dict):
    p = progress(work)
    bd, bt = p["binge"]
    kpi = lambda v, k: f'<div class="kpi"><div class="v">{v}</div><div class="k">{k}</div></div>'
    html = (f'<div class="ov"><div class="top">'
            f'<div><div class="big">{p["pct"]:.1f}<small>%</small></div><div class="small">작품 전체 진행률</div></div>'
            f'<div class="bar"><div class="lb">준비(대본·캐스팅) 10% + 회차 제작 90%</div>'
            f'<div class="tr"><i style="width:{p["pct"]:.1f}%"></i></div></div>'
            + kpi(f'{p["done"]}/{p["n"]}', "완성한 화")
            + kpi(f'{p["streak"]}일', f'업로드 비축 (EP1~{p["streak"]})')
            + kpi(f'{bd}/{bt}', "몰아보기 준비")
            + f'</div><div class="next">지금 할 일 <em>{p["next"]}</em></div>'
            + heatmap(work, p["levels"]) + '</div>')
    st.markdown(html, unsafe_allow_html=True)
    go_bar(p)


def stage_label(k: str) -> str:
    return next(f"{n} {t}" for kk, n, t, d in STAGES if kk == k)


def jump(k: str, ep: int | None = None):
    """다음 실행에서 단계(와 화)를 바꿔 띄운다. 위젯이 그려지기 전에 적용된다."""
    st.session_state["stage_jump"] = stage_label(k)
    if ep:
        st.session_state[{"cut": "cut_ep_next", "still": "still_ep_next", "clip": "clip_ep_next"}.get(k, "_ep")] = ep
    st.rerun()


def go_bar(p: dict, key: str = "go_next"):
    """지금 할 일 안내 + 그 자리로 가는 버튼. 다른 단계에 있으면 노란 버튼으로 데려간다."""
    here = st.session_state.get("stage_pick", stage_label("script"))
    target = stage_label(p["next_stage"])
    c1, c2 = st.columns([3, 1])
    with c1:
        if p["left"]:
            names = ", ".join(p["left"][:8]) + (f" 외 {len(p['left']) - 8}" if len(p["left"]) > 8 else "")
            st.caption(f"확정이 남은 칸: {names} · 인물 수·장소 수 막대를 줄이면 바로 다음 단계가 열립니다.")
    with c2:
        if here != target and st.button(f"지금 할 일로 → {target}", type="primary", key=key, width="stretch"):
            jump(p["next_stage"], p["next_ep"])


def locked(work, k) -> bool:
    if k == "script":
        return False
    if not work or not work.get("bible"):
        return True
    if k in ("cast", "cut"):
        return False
    a, b = stage_counts(work)["cast"]
    return not (b and a >= b)


def header(work):
    title = work["title"] if work else "새 작품"
    meta = f"저장소 <b>{store.kind}</b>"
    if work:
        meta += f"<br>송출 <b>{work.get('channel','')}</b> · 최종 저장 <b>{work.get('updated','')}</b>"
    st.markdown(f'<div class="brand"><span class="m">{meta}</span><div class="co">BLUE JEANS PICTURES · SHORTFORM DRAMA ENGINE'
                f'<span class="ver">{VERSION}</span></div><div class="ti">{title} 제작 대시보드</div></div>', unsafe_allow_html=True)


def pipe(work, cur):
    cnt = stage_counts(work)
    html = '<div class="pipe">'
    for k, n, t, d in STAGES:
        a, b = cnt[k]
        pct = int(100 * a / b) if b else 0
        cls = "ps" + (" on" if k == cur else "") + (" lock" if locked(work, k) and k != cur else "")
        html += f'<div class="{cls}"><div class="n">{n}</div><div class="t">{t}</div><div class="c">{a} / {b}</div><div class="b"><i style="width:{pct}%"></i></div></div>'
    st.markdown(html + "</div>", unsafe_allow_html=True)


def brief(stage, todo):
    k, n, t, d = next(s for s in STAGES if s[0] == stage)
    st.markdown(f'<div class="brief"><div class="now">{n} {t} <span class="small">{d}</span> · <em>{todo}</em></div>'
                f'<div class="how">{HOW.get(stage, "다음 버전에서 열립니다. 앞 단계가 끝나면 자동으로 이어집니다.")}</div></div>',
                unsafe_allow_html=True)


# ───────── 사이드바 ─────────
with st.sidebar:
    st.markdown("### 작품")
    works = store.works()
    labels = ["＋ 새 작품"] + [f"{w['title']}  ·  {w['id']}" for w in works]
    if "wid" not in st.session_state and works:      # 앱을 새로 열면 마지막으로 저장한 작품을 바로 연다
        st.session_state["wid"] = works[0]["id"]
    idx = 0
    for i, w in enumerate(works, start=1):
        if w["id"] == st.session_state.get("wid"):
            idx = i
    sel = st.selectbox("작품 선택", labels, index=idx, label_visibility="collapsed")
    st.session_state["wid"] = None if sel == "＋ 새 작품" else sel.rsplit("·", 1)[-1].strip()
    st.caption("저장은 자동입니다. 대본·작품 정리·캐스팅·컷은 만들거나 고르는 즉시 저장소에 저장되고, 앱을 다시 열면 마지막 작품이 열립니다.")
    st.markdown("### 연결 상태")
    for k, label in [("OPENAI_API_KEY", "그림 · gpt-image-2"), ("ANTHROPIC_API_KEY", "정리·컷 · Claude"),
                     ("ELEVENLABS_API_KEY", "더빙 · ElevenLabs"), ("REPLICATE_API_TOKEN", "영상 · Replicate")]:
        st.markdown(f'<span class="tag {"ok" if KEYS.get(k) else "todo"}">{"연결" if KEYS.get(k) else "없음"}</span>{label}',
                    unsafe_allow_html=True)
    st.markdown(f'<span class="tag {"ok" if store.r2 else "todo"}">{"연결" if store.r2 else "임시"}</span>저장 · {store.kind}',
                unsafe_allow_html=True)
    quality = st.selectbox("그림 품질", ["high", "medium", "low"],
                           index=0 if (KEYS.get("OPENAI_IMAGE_QUALITY") or "high") == "high" else 1,
                           help="캐스팅 후보는 얼굴이 기준이 되므로 high 권장 (세로 1장 약 $0.165, medium 약 $0.041).")
    AUTO_QC = st.toggle("자동 검수 (Claude)", value=bool(KEYS.get("ANTHROPIC_API_KEY")), disabled=not KEYS.get("ANTHROPIC_API_KEY"),
                        help="스틸·영상을 만든 직후 Claude 가 보고 판정합니다. 불합격이면 이유를 지시문에 붙여 2회까지 다시 만듭니다.")
    QC_RETRY = 2
    MODEL = KEYS.get("CLAUDE_MODEL", "")

work = store.load_work(st.session_state["wid"]) if st.session_state.get("wid") else None

# ───────── 새 작품 ─────────
if not work:
    header(None)
    pipe(None, "script")
    brief("script", "대본을 올려 주세요")
    c1, c2 = st.columns([2, 1])
    with c1:
        up = st.file_uploader("Shortform-Engine 대본 (docx · txt)", type=["docx", "txt"])
    with c2:
        channel = st.text_input("송출 채널", "HASIRA_yo!")
        subs = st.multiselect("자막 언어", ["한국어", "영어", "일본어"], default=["한국어", "영어"])
    if up:
        raw = up.getvalue()
        parsed = script_parser.parse(script_parser.read_text(raw, up.name))
        summ = script_parser.summarize(parsed)
        st.success(f"「{parsed['title']}」 {summ['episodes']}화 · 장면 {summ['scenes']}개 · 대사 인물 {len(summ['dialogue_lines'])}명 · 장면 머리 장소 {len(summ['places'])}가지")
        if summ["missing_hook"]:
            st.warning(f"훅 자막이 없는 화: {summ['missing_hook']}")
        if st.button("이 대본으로 작품 만들기", type="primary"):
            wid = dt.datetime.now(KST).strftime("%y%m%d") + "-" + uuid.uuid4().hex[:4]
            store.put_bytes(f"works/{wid}/script.{up.name.rsplit('.', 1)[-1].lower()}", raw)
            save({"id": wid, "title": parsed["title"] or up.name, "created": now(), "channel": channel, "subs": subs,
                  "parsed": parsed, "summary": summ, "bible": None, "main_n": 6, "loc_n": 8,
                  "cast": {}, "loc": {}, "eps": {}, "cuts": {}})
            st.session_state["wid"] = wid
            st.rerun()
    st.stop()

# ───────── 작품 화면 ─────────
header(work)
if "stage_jump" in st.session_state:          # '지금 할 일로' 버튼: 단계 선택을 위젯이 그려지기 전에 바꿈
    st.session_state["stage_pick"] = st.session_state.pop("stage_jump")
overview(work)
stage = st.radio("단계", [f"{n} {t}" for k, n, t, d in STAGES], horizontal=True, label_visibility="collapsed", key="stage_pick")
cur = next(k for k, n, t, d in STAGES if stage.startswith(n))
pipe(work, cur)
parsed, summ = work["parsed"], work["summary"]
B = work.get("bible")

if locked(work, cur):
    brief(cur, "01 대본에서 작품 정리를 먼저 해 주세요" if not B else "캐스팅 완료 후 열립니다")
    st.stop()

# ===== 01 대본 =====
if cur == "script":
    brief("script", "작품 정리 완료" if B else f"{summ['episodes']}화 읽기 완료 · 작품 정리 필요")
    t_bible, t_board, t_read, t_out = st.tabs(["작품 정리", "화별 진행판", "대본 보기", "정리본 내보내기"])

    with t_bible:
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("AI로 작품 정리 (Claude)", type="primary", disabled=not KEYS.get("ANTHROPIC_API_KEY")):
                with st.status("장면 전체를 읽고 인물·장소를 통일하는 중… (3~5분, 창을 닫지 마세요)") as s:
                    work["bible"] = bb.build(KEYS["ANTHROPIC_API_KEY"], parsed, MODEL)
                    save(work)
                    s.update(label="작품 정리 완료", state="complete")
                st.rerun()
        with c2:
            jf = st.file_uploader("정리 결과 불러오기 (JSON)", type=["json"], key="bible_up")
            if jf and st.button("불러온 정리 결과 적용"):
                work["bible"] = bb.validate(json.loads(jf.getvalue().decode("utf-8")), parsed)
                save(work)
                st.rerun()
        with c3:
            smp = SAMPLES / "danjjan_bible.json"
            if parsed.get("title") == "단짠단짠" and smp.exists():
                if st.button("「단짠단짠」 정리본 적용 (Claude 분석본)"):
                    work["bible"] = bb.validate(json.loads(smp.read_text("utf-8")), parsed)
                    save(work)
                    st.rerun()
        if B:
            if B.get("_missing_scenes") or B.get("_bad_loc"):
                st.markdown(f'<span class="tag fix">점검</span> 장소가 비어 있는 장면 {B.get("_missing_scenes")} · 없는 장소 id {B.get("_bad_loc")}',
                            unsafe_allow_html=True)
            stt = bb.stats(B, parsed)
            st.markdown(f"#### 수정 제안 {len(B['issues'])}건 <span class='small'>엔진은 대본 문장을 고치지 않습니다. 감독님이 원고를 고친 뒤 다시 올리면 됩니다.</span>", unsafe_allow_html=True)
            for w in B.get("_issue_warn") or bb.issue_warnings(B, parsed):
                st.markdown(f'<span class="tag todo">확인</span> <span class="small">{w}</span>', unsafe_allow_html=True)
            for i in B["issues"]:
                st.markdown(f"<div class='issue'><b>EP {i.get('eps','')} · {i.get('type','')}</b><br>{i.get('what','')}"
                            f"<br><span class='small'>제안: {i.get('suggest','')} · 엔진 처리: {i.get('applied','')}</span></div>", unsafe_allow_html=True)
            a, b2 = st.columns(2)
            with a:
                st.markdown(f"#### 인물 {len(B['characters'])}명")
                st.dataframe([{"이름": c["name"], "표기": ", ".join(c.get("aliases", [])), "대사": stt["lines"].get(c["name"], 0),
                               "역할": c.get("role", ""), "나이": c.get("age", "")} for c in sorted(B["characters"], key=lambda c: -stt["lines"].get(c["name"], 0))],
                             hide_index=True, width="stretch")
            with b2:
                st.markdown(f"#### 장소 세트 {len(B['locations'])}곳 <span class='small'>장면 머리 {len(summ['places'])}가지 → 세트 {len(B['locations'])}곳</span>", unsafe_allow_html=True)
                st.dataframe([{"id": l["id"], "세트": l["name"], "장면": stt["loc"].get(l["id"], 0), "공간": l.get("desc", "")}
                              for l in sorted(B["locations"], key=lambda l: -stt["loc"].get(l["id"], 0))], hide_index=True, width="stretch")
                with st.expander("세트 합치기 (같은 공간으로 쓰기)"):
                    st.caption("예: 세영의 아파트 거실을 세영의 원룸으로 합치면, 아파트로 적힌 장면도 모두 원룸 세트로 만듭니다. 대본 문장은 바뀌지 않습니다.")
                    lab = {l["id"]: f'{l["id"]} {l["name"]} · 장면 {stt["loc"].get(l["id"], 0)}' for l in B["locations"]}
                    ids = sorted(lab, key=lambda i: -stt["loc"].get(i, 0))
                    m1, m2 = st.columns(2)
                    src = m1.selectbox("없앨 세트", ids, index=None, placeholder="고르세요", format_func=lab.get, key="mg_src")
                    dst = m2.selectbox("합칠 곳", ids, index=None, placeholder="고르세요", format_func=lab.get, key="mg_dst")
                    if st.button(f"{src or '?'} → {dst or '?'} 합치기", disabled=not (src and dst) or src == dst):
                        for k, v in list(B["scene_loc"].items()):
                            if v == src:
                                B["scene_loc"][k] = dst
                        B["locations"] = [l for l in B["locations"] if l["id"] != src]
                        B.setdefault("merged", []).append({"from": src, "to": dst, "at": now()})
                        if src in work.get("loc", {}):
                            work["loc"].pop(src)
                        work["bible"] = B
                        save(work)
                        st.success(f"{src} 장면을 모두 {dst} 로 옮겼습니다.")
                        st.rerun()

    with t_board:
        p = progress(work)
        st.markdown(heatmap(work, p["levels"], big=True), unsafe_allow_html=True)
        st.caption("칸 색이 진할수록 많이 진행된 화입니다. 남색에 노란 숫자는 완성(마스터)된 화. 칸에 마우스를 올리면 단계와 훅 자막이 보입니다.")
        rows = []
        for k in EP_STAGES:
            a, b = stage_counts(work)[k]
            rows.append({"단계": next(f"{n} {t}" for kk, n, t, d in STAGES if kk == k), "끝난 화": a, "전체": b,
                         "진행률": f"{100 * a / b:.0f}%" if b else "0%", "한 화 안 비중": f"{EP_W[k]}%"})
        st.dataframe(rows, hide_index=True, width="stretch")

    with t_read:
        n = st.number_input("화", 1, len(parsed["episodes"]), 1, key="read_ep")
        e = parsed["episodes"][n - 1]
        st.markdown(f"**EP {e['ep']}** · {e['emotion']}  \n<span class='hook'>{e['hook']}</span>", unsafe_allow_html=True)
        for s in e["scenes"]:
            loc = bb.loc_of(B, e["ep"], s["no"])
            st.markdown(f"**S#{s['no']}. {s['slug']}**" + (f"  <span class='tag ok'>{loc['id']} {loc['name']}</span>" if loc else ""), unsafe_allow_html=True)
            for l in s["lines"]:
                if l["type"] == "dialogue":
                    note = f" ({l['note']})" if l["note"] else ""
                    st.markdown(f"<div class='dlg'><b>{bb.who(B, e['ep'], l['who'])}</b>{note} {l['text']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='small'>{l['text']}</div>", unsafe_allow_html=True)

    with t_out:
        if not B:
            st.info("작품 정리 후 내보낼 수 있습니다.")
        else:
            st.markdown("통일된 인물 표기·장소 세트·수정 제안이 들어간 **AI 숏폼 제작용 정리본**입니다. Shortform-Engine 의 '기존 글 → 숏폼 변환'에 넣어 다시 다듬을 수 있습니다.")
            txt = bb.export_text(B, parsed)
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("정리본 (txt)", txt.encode("utf-8"), f"{work['title']}_AI숏폼정리본.txt", "text/plain")
            with c2:
                st.download_button("작품 정리 데이터 (json)", json.dumps({k: v for k, v in B.items() if not k.startswith("_")}, ensure_ascii=False, indent=1).encode("utf-8"),
                                   f"{work['title']}_bible.json", "application/json")
            st.text_area("미리보기", txt[:4000], height=300)

# ===== 02 캐스팅 =====
elif cur == "cast":
    chars_all, locs_all = chars_ranked(work), locs_ranked(work)
    a, b = stage_counts(work)["cast"]
    brief("cast", f"확정 {cast_split(work)}" + (" · 캐스팅 완료" if b and a >= b else ""))
    picks = [(f"01_CAST_FINAL/{c}_ref_{vw}.jpg", k) for c, v in work.get("cast", {}).items() for vw, k in sheet_of(v).items()] + \
            [(f"02_MAKEUP_COSTUME/{c}_{ln}_{vw}.jpg", k) for c, v in work.get("cast", {}).items()
             for ln, li in (v.get("looks") or {}).items() for vw, k in sheet_of(li).items()] + \
            [(f"04_PROP/{n}.jpg", v["pick"]) for n, v in work.get("props", {}).items() if v.get("pick")] + \
            [(f"03_LOCATION_MASTER/{lid}_{next((l['name'] for l in B['locations'] if l['id'] == lid), '')}_view_{vn}.jpg", vi["pick"])
             for lid, v in work.get("loc", {}).items() for vn, vi in (v.get("views") or {}).items() if vi.get("pick")] + \
            [(f"05_EMBLEM/{n}.jpg", k) for n, k in (work.get("emblems") or {}).items()] + \
            [(f"03_LOCATION_MASTER/{lid}_{next((l['name'] for l in B['locations'] if l['id'] == lid), '')}_master.jpg", v["pick"])
             for lid, v in work.get("loc", {}).items() if v.get("pick")]
    if picks:
        def _zip():
            import io, re, zipfile
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for name, k in picks:
                    d = img_bytes(k)
                    if d:
                        z.writestr(re.sub(r'[\\:*?"<>|·]', "_", name).replace(" ", "_"), d)
            return buf.getvalue()
        st.download_button(f"확정 그림 {len(picks)}장 내려받기 (드라이브용 이름 정리, zip)", _zip, file_name=f"casting_{work['id']}.zip",
                           mime="application/zip", help="01_CAST_FINAL · 02_MAKEUP_COSTUME · 03_LOCATION_MASTER · 04_PROP · 05_EMBLEM 폴더로 나뉘고, 이름이 '인물_ref_front', '장소번호_장소_master' 로 정리됩니다. 압축을 풀어 드라이브 작업 폴더에 그대로 올리면 됩니다.")
    t_char, t_loc, t_prop = st.tabs(["인물", "장소 (마스터)", "소품"])
    stt = bb.stats(B, parsed)

    def gen_many(prompts, aspect, style="ref", refs=None):
        def one(p):
            try:
                if refs:
                    return imagegen.edit(KEYS["OPENAI_API_KEY"], p, refs, aspect, quality, style=style, model=KEYS.get("IMAGE_MODEL", ""))
                return imagegen.generate(KEYS["OPENAI_API_KEY"], p, aspect, quality, style=style)
            except Exception as ex:
                return ex
        with ThreadPoolExecutor(4) as ex:
            return list(ex.map(one, prompts))

    def asset_board(kind, key, label, info, aspect, n_cand):
        base = f"works/{work['id']}/{kind}/{slug(key)}"
        stored = info.get("prompt_en") or info.get("prompt") or info.get("image_prompt") or ""
        if not stored.strip() and (info.get("look_ko") or info.get("desc_ko")):
            st.markdown('<span class="tag todo">영어 지시문 없음</span> <span class="small">아래 버튼으로 이 칸만 다시 씁니다.</span>', unsafe_allow_html=True)
            if st.button("영어 지시문 쓰기 (Claude)", key=f"re_{kind}_{key}", disabled=not KEYS.get("ANTHROPIC_API_KEY")):
                with st.spinner("한국어 설명을 영어 지시문으로 옮기는 중…"):
                    stored = profiles.to_prompt(KEYS["ANTHROPIC_API_KEY"], kind, label, info, MODEL)
                if stored:
                    info["prompt_en"] = stored
                    save(work)
                    st.rerun()
        # 입력칸 이름에 저장된 지시문의 지문을 붙여, 저장값이 바뀌면 칸이 새로 그려지게 함 (빈 칸이 남는 문제 방지)
        import hashlib
        fp = hashlib.md5(stored.encode()).hexdigest()[:8]
        prompt = st.text_area("이미지 지시문 (영어, 확정형)", stored, key=f"p_{kind}_{key}_{fp}", height=110)
        bad = imagegen.banned_in(prompt)
        if bad:
            st.markdown(f'<span class="tag fix">금지어</span> {" · ".join(bad)}', unsafe_allow_html=True)
        if prompt != stored and prompt.strip():
            info["prompt_en"] = prompt
            save(work)
        c1, c2 = st.columns([1, 2])
        with c1:
            go = st.button(f"후보 {n_cand}장 만들기", key=f"g_{kind}_{key}", disabled=not (KEYS.get("OPENAI_API_KEY") and prompt and not bad))
        with c2:
            upf = st.file_uploader("직접 올리기", type=["png", "jpg", "jpeg", "webp"], key=f"u_{kind}_{key}", label_visibility="collapsed")
        if go:
            with st.status(f"{label} 후보 {n_cand}장 생성 중… (장당 30초~1분)") as s:
                g_prompt, g_refs, g_style = prompt, None, {"cast": "ref", "prop": "prop"}.get(kind, "location")
                if kind == "cast" and info.get("_face"):            # 분장·의상(룩): 확정 얼굴을 기준 그림으로 넣고 머리·분장·옷만 바꾼다
                    g_prompt, g_refs, g_style = imagegen.LOOK_SAME + prompt, [("face.jpg", img_bytes(info["_face"]))], "sheet"
                if kind == "loc" and info.get("_master"):           # 장소 시점: 마스터를 기준 그림으로 넣어 같은 방을 다른 쪽에서
                    g_prompt, g_refs = imagegen.LOC_VIEW + prompt, [("master.jpg", img_bytes(info["_master"]))]
                if kind == "loc" and info.get("_emblem"):          # 벽 엠블럼(회사 CI)을 기준 그림으로 넣어 마스터를 만든다
                    g_prompt = cutter.no_logo_words(prompt) + " " + cutter.EMBLEM_MASTER
                    g_refs = [("emblem.jpg", img_bytes(info["_emblem"]))]
                for r in gen_many([g_prompt] * n_cand, aspect, g_style, g_refs):
                    if isinstance(r, Exception):
                        st.error(str(r))
                        continue
                    k = f"{base}/cand_{uuid.uuid4().hex[:6]}.jpg"
                    store.put_bytes(k, r, "image/jpeg")
                    info.setdefault("cands", []).append(k)
                save(work)
                s.update(label=f"{label} 후보 생성 완료", state="complete")
        if upf is not None and not st.session_state.get(f"done_{upf.file_id}"):
            from io import BytesIO
            from PIL import Image
            im = Image.open(BytesIO(upf.getvalue())).convert("RGB")
            im.thumbnail((2048, 2048))
            buf = BytesIO()
            im.save(buf, "JPEG", quality=92)
            k = f"{base}/up_{uuid.uuid4().hex[:6]}.jpg"
            store.put_bytes(k, buf.getvalue(), "image/jpeg")
            info.setdefault("cands", []).append(k)
            st.session_state[f"done_{upf.file_id}"] = True
            save(work)
        cands = info.get("cands", [])
        if cands:
            cols = st.columns(4)
            for i, k in enumerate(reversed(cands[-8:])):
                with cols[i % 4]:
                    data = img_bytes(k)
                    if data:
                        st.image(data, width="stretch")
                    picked = info.get("pick") == k
                    if st.button("✓ 확정됨" if picked else "이걸로 확정", key=f"pk_{k}", type="primary" if picked else "secondary"):
                        info["pick"] = None if picked else k
                        save(work)
                        st.rerun()

    def sheet_board(c, info):
        """캐스팅 시트: 정면(확정) + 3/4 · 전신 · 뒷모습. 컷의 각도에 맞는 시트가 스틸의 기준 그림이 된다."""
        sh = sheet_of(info)
        stale = bool(info.get("views")) and info.get("views_of") != info["pick"]
        st.markdown(f"**캐스팅 시트** <span class='small'>정면을 바꾸면 시트를 다시 만들어야 합니다. 뒷모습 컷·측면 컷·전신 컷의 기준 그림으로 씁니다.</span>"
                    + (" <span class='tag fix'>정면이 바뀜 · 다시 만들기 필요</span>" if stale else ""), unsafe_allow_html=True)
        need = [v for v in imagegen.VIEWS if v not in sh]
        base = f"works/{work['id']}/cast/{slug(c)}"

        def make_views(views):
            front = img_bytes(info["pick"])
            desc = info.get("prompt_en", "")

            def one(v):
                try:
                    return imagegen.edit(KEYS["OPENAI_API_KEY"], imagegen.VIEWS[v][2] + " " + desc, [("front.jpg", front)],
                                         imagegen.VIEWS[v][1], quality, style="sheet", model=KEYS.get("IMAGE_MODEL", ""))
                except Exception as ex:
                    return ex
            with ThreadPoolExecutor(3) as ex:
                res = list(ex.map(one, views))
            if info.get("views_of") != info["pick"]:
                info["views"], info["views_of"] = {}, info["pick"]
            for v, r in zip(views, res):
                if isinstance(r, Exception):
                    st.error(f"{c} {imagegen.VIEWS[v][0]}: {r}")
                    continue
                k = f"{base}/sheet_{v}_{uuid.uuid4().hex[:6]}.jpg"
                store.put_bytes(k, r, "image/jpeg")
                info["views"][v] = k
            save(work)

        if need and st.button(f"시트 {len(need)}장 만들기 ({', '.join(imagegen.VIEWS[v][0] for v in need)})", key=f"sh_{c}",
                              type="primary", disabled=not KEYS.get("OPENAI_API_KEY")):
            with st.status(f"{c} 캐스팅 시트 {len(need)}장 생성 중… (1~2분)") as s:
                make_views(need)
                s.update(label="시트 생성 완료", state="complete")
            st.rerun()
        cols = st.columns(4)
        for i, (v, lab) in enumerate([("front", "정면 (확정)")] + [(k, imagegen.VIEWS[k][0]) for k in imagegen.VIEWS]):
            with cols[i]:
                st.caption(lab)
                if sh.get(v):
                    d = img_bytes(sh[v])
                    if d:
                        st.image(d, width="stretch")
                if v == "front":
                    continue
                if sh.get(v) and st.button("다시", key=f"shr_{c}_{v}", disabled=not KEYS.get("OPENAI_API_KEY")):
                    with st.spinner(f"{c} {lab} 다시 만드는 중…"):
                        make_views([v])
                    st.rerun()
                up = st.file_uploader("올리기", type=["png", "jpg", "jpeg", "webp"], key=f"shu_{c}_{v}", label_visibility="collapsed")
                if up is not None and not st.session_state.get(f"done_{up.file_id}"):
                    from io import BytesIO
                    from PIL import Image
                    im = Image.open(BytesIO(up.getvalue())).convert("RGB")
                    im.thumbnail((2048, 2048))
                    buf = BytesIO()
                    im.save(buf, "JPEG", quality=92)
                    k = f"{base}/sheet_{v}_up_{uuid.uuid4().hex[:6]}.jpg"
                    store.put_bytes(k, buf.getvalue(), "image/jpeg")
                    if info.get("views_of") != info["pick"]:
                        info["views"], info["views_of"] = {}, info["pick"]
                    info["views"][v] = k
                    st.session_state[f"done_{up.file_id}"] = True
                    save(work)
                    st.rerun()

    def looks_board(c, info):
        """분장·의상 (Make-up & Costume): 인물마다 머리·분장·옷 묶음(룩)을 여러 개 고정해 둔다.
        '기본'은 위에서 확정한 캐스팅 그림의 차림. 콘티가 장면마다 룩 하나를 고르고, 그 룩의 그림이 컷의 기준 그림이 된다."""
        looks = info.setdefault("looks", {})
        st.markdown(f"**분장·의상 (Make-up & Costume)** <span class='small'>기본 = 위 확정 그림의 차림 · 추가 룩 {len(looks)}개. "
                    "집·출근·환자복처럼 장면에 따라 바뀌는 차림을 등록합니다. 주연 3~4개, 조연 1~2개가 적당합니다.</span>", unsafe_allow_html=True)
        l1, l2, l3 = st.columns([1, 3, 1])
        with l1:
            ln = st.text_input("룩 이름", placeholder="집", key=f"lk_name_{c}")
        with l2:
            lm = st.text_input("머리·분장·의상 메모 (한국어)", placeholder="머리를 풀고 화장기 없는 얼굴, 아이보리 맨투맨, 회색 트레이닝 바지, 맨발", key=f"lk_note_{c}")
        with l3:
            st.write("")
            if st.button("룩 추가", key=f"lk_add_{c}", disabled=not (ln.strip() and ln.strip() != "기본" and KEYS.get("ANTHROPIC_API_KEY"))) \
                    and ln.strip() not in looks:
                with st.spinner("분장·의상 설명을 쓰는 중…"):
                    d = cutter.look_desc(KEYS["ANTHROPIC_API_KEY"], c, ln.strip(), lm.strip(), info.get("prompt_en", ""), MODEL)
                looks[ln.strip()] = {"prompt_en": d, "note": lm.strip()}
                save(work)
                st.rerun()
        for name in list(looks):
            li = looks[name]
            state = "그림 확정" if li.get("pick") else "그림 없음 · 글 설명으로만 들어감"
            st.markdown(f"<div class='cut'><div class='h'>{c} · {name} <span class='tag {'ok' if li.get('pick') else 'todo'}'>{state}</span></div>"
                        f"<div class='s'>{li.get('note', '')}</div></div>", unsafe_allow_html=True)
            if st.toggle("이 룩 열기", key=f"lk_open_{c}_{name}", value=not li.get("pick")):
                li["_face"] = info["pick"]
                asset_board("cast", f"{c}__{name}", f"{c} · {name}", li, "3:4", 2)
                li.pop("_face", None)
                if li.get("pick"):
                    sheet_board(f"{c}__{name}", li)
                if st.button("이 룩 삭제", key=f"lk_del_{c}_{name}"):
                    looks.pop(name)
                    save(work)
                    st.rerun()

    with t_char:
        main_n = st.slider("기준 이미지를 만들 인물 수 (대사 많은 순)", 1, max(1, len(chars_all)), min(work.get("main_n", 6), max(1, len(chars_all))))
        if main_n != work.get("main_n"):
            work["main_n"] = main_n
            save(work)
        chars = chars_all[:main_n]
        need = [c for c in chars if not work.get("cast", {}).get(c, {}).get("prompt_en")]
        if need and st.button(f"프로필 초안 만들기 ({len(need)}명, Claude)", disabled=not KEYS.get("ANTHROPIC_API_KEY")):
            with st.spinner("대본에서 나이·직업·처지를 읽는 중…"):
                d = profiles.draft(KEYS["ANTHROPIC_API_KEY"], parsed, need, {}, MODEL, B)
            alias = {a.replace(" ", ""): r["name"] for r in B["characters"] for a in [r["name"]] + r.get("aliases", [])}
            for c in d.get("characters", []):
                nm = alias.get(str(c.get("name", "")).replace(" ", ""), c.get("name"))   # '세영' → '한세영'
                if nm in chars:
                    c["name"] = nm
                    work.setdefault("cast", {}).setdefault(nm, {}).update(c)
                    st.session_state.pop(f"p_cast_{nm}", None)   # 비어 있던 입력칸 기억을 지워야 새 지시문이 보임
            save(work)
            st.rerun()
        roles = {c["name"]: c for c in B["characters"]}
        for c in chars:
            info = work.setdefault("cast", {}).setdefault(c, {})
            with st.expander(f"{'✓ ' if info.get('pick') else ''}{c} · 대사 {stt['lines'].get(c, 0)}줄 · {roles.get(c, {}).get('role', '')[:40]}", expanded=not info.get("pick")):
                if info.get("look_ko") or info.get("outfit_ko"):
                    st.markdown(f"<div class='small'>{info.get('age','')} · 외모: {info.get('look_ko','')}<br>의상: {info.get('outfit_ko','')}</div>", unsafe_allow_html=True)
                if info.get("look_ko") and st.button("외모 다시 잡기 (Claude)", key=f"rd_{c}", disabled=not KEYS.get("ANTHROPIC_API_KEY"),
                                                    help="주연급 외모 기준으로 이 인물의 외모·의상·영어 지시문을 새로 씁니다."):
                    with st.spinner(f"{c} 외모를 다시 잡는 중…"):
                        d = profiles.draft(KEYS["ANTHROPIC_API_KEY"], parsed, [c], {}, MODEL, B)
                    got = next((x for x in d.get("characters", []) if x.get("prompt_en")), None)
                    if got:
                        got["name"] = c
                        info.update(got)
                        save(work)
                        st.rerun()
                    st.error("다시 잡기에 실패했습니다. 한 번 더 눌러 주세요.")
                asset_board("cast", c, c, info, "3:4", 4)
                if info.get("pick"):
                    sheet_board(c, info)
                    looks_board(c, info)

    with t_loc:
        loc_n = st.slider("마스터를 만들 장소 수 (장면 많은 순)", 1, max(1, len(locs_all)), min(work.get("loc_n", 8), max(1, len(locs_all))))
        if loc_n != work.get("loc_n"):
            work["loc_n"] = loc_n
            save(work)
        rest = [l for l in locs_all[loc_n:]]
        if "loc_extra_ms" not in st.session_state:
            st.session_state["loc_extra_ms"] = [i for i in work.get("loc_extra", []) if i in {l["id"] for l in rest}]
        extra = st.multiselect("장소 따로 추가 (장면이 적어도 마스터가 필요한 곳)", [l["id"] for l in rest], key="loc_extra_ms",
                               format_func=lambda i: f'{i} {next(l["name"] for l in locs_all if l["id"] == i)} · 장면 {stt["loc"].get(i, 0)}개',
                               placeholder="예: 1화의 회사 소회의실")
        if extra != work.get("loc_extra", []):
            work["loc_extra"] = extra
            save(work)
        locs = cast_locs(work)
        need = [l for l in locs if not work.get("loc", {}).get(l["id"], {}).get("prompt_en")]
        if need and st.button(f"장소 지시문 초안 ({len(need)}곳, Claude)", disabled=not KEYS.get("ANTHROPIC_API_KEY")):
            with st.spinner("장면 머리에서 공간을 읽는 중…"):
                slugs = {f'{l["id"]} {l["name"]}': [f"EP{e['ep']} {s['slug']}" for e in parsed["episodes"] for s in e["scenes"]
                                     if B["scene_loc"].get(f"{e['ep']}-{s['no']}") == l["id"]][:5] for l in need}
                d = profiles.draft(KEYS["ANTHROPIC_API_KEY"], parsed, [], slugs, MODEL, B)
            got = [x for x in d.get("locations", []) if isinstance(x, dict) and x.get("prompt_en")]

            def match(x, i):
                """돌아온 이름 → 장소 id: id 가 들어 있으면 id, 이름이 겹치면 이름, 아니면 순서대로."""
                nm = str(x.get("name", "")) + " " + str(x.get("id", ""))
                for l in need:
                    if l["id"] in nm:
                        return l["id"]
                for l in need:
                    a, b = l["name"].replace(" ", ""), nm.replace(" ", "")
                    if a in b or (b.strip() and b.strip() in a):
                        return l["id"]
                return need[i]["id"] if i < len(need) and len(got) == len(need) else None
            for i, x in enumerate(got):
                lid = match(x, i)
                if lid:
                    work.setdefault("loc", {}).setdefault(lid, {}).update({k: v for k, v in x.items() if k != "name"})
            if not got:
                st.error("지시문을 받지 못했습니다. 한 번 더 누르거나 장소마다 '영어 지시문 쓰기'를 쓰세요.")
            save(work)
            st.rerun()
        with st.expander(f"벽 엠블럼 (회사 CI) 보관함 · {len(emblem_list(work))}개"):
            st.markdown("<div class='small'>글자 없는 도형 엠블럼 그림을 올려 두면 장소마다 골라 쓸 수 있습니다. 회사 이름 글자는 그림에 넣지 않고 편집 자막으로 넣습니다.</div>", unsafe_allow_html=True)
            ecols = st.columns(6)
            for i, (k, nm_) in enumerate(emblem_list(work).items()):
                with ecols[i % 6]:
                    st.image(img_bytes(k), caption=nm_, width="stretch")
            en = st.text_input("엠블럼 이름", placeholder="서경F&B CI", key="em_new_name")
            eu = st.file_uploader("엠블럼 그림 올리기", type=["png", "jpg", "jpeg", "webp"], key="em_new_file")
            if eu is not None and en.strip() and not st.session_state.get(f"done_{eu.file_id}"):
                from io import BytesIO
                from PIL import Image
                im = Image.open(BytesIO(eu.getvalue())).convert("RGBA")
                bg = Image.new("RGB", im.size, "white")
                bg.paste(im, mask=im.split()[3])
                bg.thumbnail((1024, 1024))
                buf = BytesIO()
                bg.save(buf, "JPEG", quality=92)
                k = f"works/{work['id']}/emblem/{slug(en.strip())}_{uuid.uuid4().hex[:6]}.jpg"
                store.put_bytes(k, buf.getvalue(), "image/jpeg")
                work.setdefault("emblems", {})[en.strip()] = k
                st.session_state[f"done_{eu.file_id}"] = True
                save(work)
                st.rerun()
        st.caption("장소마다 넓은 마스터 1장을 확정합니다. 같은 장소의 모든 컷은 이 마스터에서 만듭니다.")
        for l in locs:
            info = work.setdefault("loc", {}).setdefault(l["id"], {})
            info.setdefault("desc_ko", l.get("desc", ""))     # 영어 지시문이 비었을 때 이 설명으로 바로 쓸 수 있게
            with st.expander(f"{'✓ ' if info.get('pick') else ''}{l['id']} {l['name']} · 장면 {stt['loc'].get(l['id'], 0)}개", expanded=not info.get("pick")):
                st.markdown(f"<div class='small'>{l.get('desc','')}</div>", unsafe_allow_html=True)
                ems = emblem_list(work)
                cur = emblem_of(work, l["id"], l["name"])
                opts = [""] + list(ems)
                e1, e2 = st.columns([3, 1])
                with e1:
                    sel = st.selectbox("벽 엠블럼 (회사 CI)", opts, index=opts.index(cur) if cur in opts else 0, key=f"em_{l['id']}",
                                       format_func=lambda k: ems.get(k, "없음"),
                                       help="고르면 이 장소의 마스터를 만들 때와, 엠블럼이 보이는 컷을 만들 때 이 그림이 기준 그림으로 들어갑니다. 글자 없는 도형만 씁니다.")
                with e2:
                    if cur:
                        st.image(img_bytes(cur), width=90)
                if sel != cur:
                    info["emblem"] = sel
                    save(work)
                    st.rerun()
                info["_emblem"] = cur
                asset_board("loc", l["id"], l["name"], info, "16:9", 2)
                info.pop("_emblem", None)
                views = info.setdefault("views", {})
                st.markdown(f"**장소 시점** <span class='small'>카메라가 향하는 쪽마다 기준 그림 한 장 · {len(views)}개. 마스터를 기준으로 같은 방을 세로로 다시 그립니다. "
                            "컷은 이 그림을 배경으로 써서 컷마다 벽·로고·가구가 바뀌지 않습니다. 03 콘티의 '준비물 뽑기'가 자동으로 등록합니다.</span>", unsafe_allow_html=True)
                v1, v2, v3 = st.columns([1, 3, 1])
                with v1:
                    vn = st.text_input("시점 이름", placeholder="게이트 쪽", key=f"vw_name_{l['id']}")
                with v2:
                    vm = st.text_input("메모 (한국어)", placeholder="게이트가 줄지어 있고 뒤로 유리 출입문이 보인다", key=f"vw_note_{l['id']}")
                with v3:
                    st.write("")
                    if st.button("시점 추가", key=f"vw_add_{l['id']}", disabled=not (vn.strip() and KEYS.get("ANTHROPIC_API_KEY"))) and vn.strip() not in views:
                        with st.spinner("시점 설명을 쓰는 중…"):
                            d = cutter.view_desc(KEYS["ANTHROPIC_API_KEY"], l["name"], vn.strip(), vm.strip(), MODEL)
                        views[vn.strip()] = {"prompt_en": d, "note": vm.strip()}
                        save(work)
                        st.rerun()
                for vname in list(views):
                    vi = views[vname]
                    st.markdown(f"<div class='cut'><div class='h'>{l['name']} · {vname} <span class='tag {'ok' if vi.get('pick') else 'todo'}'>"
                                f"{'그림 확정' if vi.get('pick') else '그림 없음'}</span></div><div class='s'>{vi.get('note', '')}</div></div>", unsafe_allow_html=True)
                    if st.toggle("이 시점 열기", key=f"vw_open_{l['id']}_{vname}", value=False):
                        if not info.get("pick"):
                            st.info("마스터를 먼저 확정해야 시점 그림을 만들 수 있습니다. 직접 올리기는 가능합니다.")
                        vi["_master"] = info.get("pick")
                        asset_board("loc", f"{l['id']}__{vname}", f"{l['name']} · {vname}", vi, "9:16", 2)
                        vi.pop("_master", None)
                        if st.button("이 시점 삭제", key=f"vw_del_{l['id']}_{vname}"):
                            views.pop(vname)
                            save(work)
                            st.rerun()

    with t_prop:
        props = work.setdefault("props", {})
        st.markdown("<div class='small'>손에 드는 소품(가방, 휴대폰)과 장소에 놓인 소품(회의실 전화기, 책상 노트북)을 한 번 정해 두면 모든 컷에 같은 설명과 같은 기준 그림이 들어갑니다. "
                    "콘티를 만들 때 새 소품은 자동으로 등록됩니다. 이미 만든 콘티에는 첫 장면 문장에 소품 이름(예: 노트북 가방)이 나오는 컷에 자동으로 붙습니다.</div>",
                    unsafe_allow_html=True)
        a1, a2, a3 = st.columns([2, 3, 1])
        with a1:
            pn = st.text_input("소품 이름", placeholder="세영의 노트북 가방", key="prop_new_name")
        with a2:
            pm = st.text_input("메모 (한국어, 비워도 됨)", placeholder="검은 나일론, 손잡이 두 개, 한 손에 든다", key="prop_new_note")
        with a3:
            st.write("")
            if st.button("소품 추가", disabled=not (pn.strip() and KEYS.get("ANTHROPIC_API_KEY"))) and pn.strip() not in props:
                with st.spinner("소품 설명을 쓰는 중…"):
                    d = cutter.prop_desc(KEYS["ANTHROPIC_API_KEY"], pn.strip(), pm.strip(), MODEL)
                props[pn.strip()] = {"prompt_en": d, "note": pm.strip()}
                save(work)
                st.rerun()
        if not props:
            st.info("등록된 소품이 없습니다. 위에서 추가하거나 03 콘티를 만들면 자동으로 등록됩니다.")
        for name in list(props):
            info = props[name]
            with st.expander(f"{name} · {'기준 그림 확정' if info.get('pick') else '기준 그림 없음 (설명만 들어감)'}", expanded=not info.get("pick")):
                kinds = ["hand", "set"]
                k1, k2 = st.columns(2)
                with k1:
                    kd = st.selectbox("종류", kinds, index=kinds.index(info.get("kind", "hand")), key=f"pk_kind_{name}",
                                      format_func=lambda k: {"hand": "손에 드는 소품", "set": "장소에 놓인 소품"}[k])
                lid = info.get("loc", "")
                if kd == "set":
                    with k2:
                        lopts = [x["id"] for x in B["locations"]]
                        lid = st.selectbox("놓인 장소", lopts, index=lopts.index(lid) if lid in lopts else 0, key=f"pk_loc_{name}",
                                           format_func=lambda i: f"{i} {next((x['name'] for x in B['locations'] if x['id'] == i), '')}",
                                           help="이 장소의 컷(얼굴 클로즈업 제외)에 이 소품의 설명과 기준 그림이 자동으로 들어갑니다.")
                if kd != info.get("kind", "hand") or (kd == "set" and lid != info.get("loc", "")):
                    info["kind"], info["loc"] = kd, (lid if kd == "set" else "")
                    save(work)
                    st.rerun()
                ptxt = st.text_input("소품에 인쇄된 글자 (없으면 비워 둠)", info.get("text", ""), key=f"pk_text_{name}", placeholder="임시출입증",
                                     help="이 글자만 그림에 허용합니다. 글자가 있는 소품은 기준 그림을 직접 올리는 것이 정확합니다 (엔진이 만드는 소품 그림에는 글자를 넣지 않습니다).")
                if ptxt.strip() != info.get("text", ""):
                    info["text"] = ptxt.strip()
                    save(work)
                    st.rerun()
                asset_board("prop", name, name, info, "3:4", 2)
                if st.button("이 소품 삭제", key=f"pdel_{name}"):
                    props.pop(name)
                    save(work)
                    st.rerun()

# ===== 03 컷 =====
elif cur == "cut":
    allcuts = work.setdefault("cuts", {})
    n_ep = len(parsed["episodes"])
    done_n = sum(1 for k, v in work.get("eps", {}).items() if v.get("cut") == "done")
    fix_n = sum(1 for k, v in work.get("eps", {}).items() if v.get("cut_fix", 0) > 0)
    brief("cut", f"콘티 {done_n} / {n_ep}화" + (f" · 점검 표시 {fix_n}화" if fix_n else ""))
    known_c = {c["name"] for c in B["characters"]}
    known_l = {l["id"] for l in B["locations"]}
    castdesc = {c: (work.get("cast", {}).get(c, {}).get("prompt_en", "") or c).split(".")[0] for c in known_c}
    locdesc = {l["id"]: (l["name"], work.get("loc", {}).get(l["id"], {}).get("prompt_en", "") or l.get("desc", "")) for l in B["locations"]}
    propdesc = {n: v.get("prompt_en", "") for n, v in work.get("props", {}).items()}

    def run_breakdown(n: int, ep_: dict):
        """이 화 대본에서 준비물(장소 시점·소품·분장의상)을 뽑아 등록한다. 실패해도 콘티는 계속 만든다."""
        try:
            bd = cutter.breakdown(KEYS["ANTHROPIC_API_KEY"], ep_, B, propdesc, look_notes(work), view_notes(work), MODEL)
        except Exception as ex:
            st.warning(f"준비물 뽑기 실패 ({str(ex)[:100]}). 콘티는 그대로 만듭니다.")
            return
        register_prep(work, bd)
        pre = work.setdefault("prep", {}).setdefault(str(n), {"views": [], "props": [], "looks": []})
        pre["views"] += [[x["loc"], x["name"]] for x in bd["views"] if [x["loc"], x["name"]] not in pre["views"]]
        pre["props"] += [x["name"] for x in bd["props"] if x["name"] not in pre["props"]]
        pre["looks"] += [[x["who"], x["name"]] for x in bd["looks"] if [x["who"], x["name"]] not in pre["looks"]]
        for x in bd["props"]:
            propdesc.setdefault(x["name"], x["desc_en"])

    def make_prep(items: list):
        """기준 그림이 없는 준비물을 한 장씩 만들어 바로 확정한다 (마음에 안 들면 02 캐스팅에서 바꿈)."""
        def one(it):
            d = it["info"].get("prompt_en", "")
            try:
                if it["kind"] == "view":
                    return imagegen.edit(KEYS["OPENAI_API_KEY"], imagegen.LOC_VIEW + d, [("master.jpg", img_bytes(it["ref"]))],
                                         "9:16", quality, style="location", model=KEYS.get("IMAGE_MODEL", ""))
                if it["kind"] == "look":
                    return imagegen.edit(KEYS["OPENAI_API_KEY"], imagegen.LOOK_SAME + d, [("face.jpg", img_bytes(it["ref"]))],
                                         "3:4", quality, style="sheet", model=KEYS.get("IMAGE_MODEL", ""))
                return imagegen.generate(KEYS["OPENAI_API_KEY"], d, "3:4", quality, style="prop")
            except Exception as ex:
                return ex
        with ThreadPoolExecutor(4) as ex:
            res = list(ex.map(one, items))
        for it, r in zip(items, res):
            if isinstance(r, Exception):
                st.error(f"{it['label']}: {r}")
                continue
            k = f"works/{work['id']}/{it['path']}/cand_{uuid.uuid4().hex[:6]}.jpg"
            store.put_bytes(k, r, "image/jpeg")
            it["info"].setdefault("cands", []).append(k)
            it["info"]["pick"] = k
        save(work)

    def add_props(r: dict):
        """콘티가 새로 등록한 소품을 작품 소품 목록에 넣는다 (이미 있는 소품의 설명은 그대로)."""
        for n, d in (r.get("props") or {}).items():
            work.setdefault("props", {}).setdefault(n, {"prompt_en": d})
            propdesc.setdefault(n, d)
        for x in r.get("new_looks") or []:            # 콘티가 새로 등록한 분장·의상 (그림은 02 캐스팅에서 만든다)
            if x["who"] in work.get("cast", {}):
                work["cast"][x["who"]].setdefault("looks", {}).setdefault(x["name"], {"prompt_en": x["desc_en"], "note": x["note_ko"]})

    def store_cuts(ep_no: int, cuts: list, src: str, changes: list | None = None):
        """콘티 저장. 콘티가 바뀌면 컷 번호의 내용이 달라지므로 그 화의 스틸·영상은 보관함(stills_old·clips_old)으로 옮기고 처음부터."""
        k = str(ep_no)
        old = allcuts.get(k)
        if old and old.get("cuts") != cuts:
            for box in ("stills", "clips"):
                if work.get(box, {}).get(k):
                    work.setdefault(box + "_old", {}).setdefault(k, []).append({"at": now(), "data": work[box].pop(k)})
            e_s = work.setdefault("eps", {}).setdefault(k, {})
            for st_k in ("still", "clip", "still_qc", "clip_qc"):
                e_s.pop(st_k, None)
        allcuts[k] = {"cuts": cuts, "src": src, "at": now(), "changes": changes or []}
        iss = cutter.check(cuts, known_c, known_l, [s["no"] for s in parsed["episodes"][ep_no - 1]["scenes"]])
        e_ = work.setdefault("eps", {}).setdefault(str(ep_no), {})
        e_["cut"], e_["cut_fix"] = "done", sum(1 for i in iss if i["level"] == "fix")

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if "cut_ep_next" in st.session_state:
            st.session_state["cut_ep"] = st.session_state.pop("cut_ep_next")
        ep_no = st.number_input("화", 1, n_ep, 1, key="cut_ep")
    ep = parsed["episodes"][ep_no - 1]
    with c2:
        st.write("")
        if st.button("이 화 콘티 만들기" if str(ep_no) not in allcuts else "이 화 콘티 다시 만들기", type="primary", disabled=not KEYS.get("ANTHROPIC_API_KEY"),
                     help="다시 만들면 이 화의 기존 스틸·영상은 보관함으로 옮기고 새 콘티로 처음부터 만듭니다."):
            with st.spinner(f"EP {ep_no} 콘티 만드는 중… 준비물 뽑기 → 컷 나누기 → 감수 (2~3분)"):
                run_breakdown(ep_no, ep)
                r = cutter.split(KEYS["ANTHROPIC_API_KEY"], ep, B, MODEL, props=propdesc, looks=look_notes(work), views=view_notes(work))
            add_props(r)
            store_cuts(ep_no, r["cuts"], r["model"], r.get("changes"))
            save(work)
            st.rerun()
    with c3:
        st.write("")
        todo = [e["ep"] for e in parsed["episodes"] if str(e["ep"]) not in allcuts]
        # 한꺼번에 돌리지 않는다: 버튼 한 번 = 한 화. 감독님이 결과를 보고 다음 화로 넘어간다.
        if todo and st.button(f"다음 화 콘티 (EP {todo[0]})", disabled=not KEYS.get("ANTHROPIC_API_KEY")):
            n = todo[0]
            with st.spinner(f"EP {n} 콘티 만드는 중… 준비물 뽑기 → 컷 나누기 → 감수 (2~3분)"):
                run_breakdown(n, parsed["episodes"][n - 1])
                r = cutter.split(KEYS["ANTHROPIC_API_KEY"], parsed["episodes"][n - 1], B, MODEL, props=propdesc, looks=look_notes(work), views=view_notes(work))
            add_props(r)
            store_cuts(n, r["cuts"], r["model"], r.get("changes"))
            save(work)
            st.session_state["cut_ep_next"] = n      # 다음 실행에서 이 화를 화면에 띄움
            st.rerun()
    smp = SAMPLES / f"danjjan_ep{ep_no}_cuts.json"
    if parsed.get("title") == "단짠단짠" and smp.exists() and st.button(f"EP {ep_no} 샘플 분할 적용 (Claude 작성본)"):
        store_cuts(ep_no, cutter.normalize(json.loads(smp.read_text("utf-8"))["cuts"], ep, B), "sample")
        save(work)
        st.rerun()

    st.markdown(f"**EP {ep['ep']}** · {ep['emotion']} · <span class='hook'>{ep['hook']}</span>", unsafe_allow_html=True)
    items = prep_items(work, str(ep_no), {l["id"]: l["name"] for l in B["locations"]})
    lack = [it for it in items if not it["ready"]]
    can = [it for it in lack if it["kind"] == "prop" or (it["kind"] in ("view", "look") and it.get("ref"))]
    with st.expander(f"이 화 준비물 · {len(items)}개 · 기준 그림 없음 {len(lack)}개", expanded=bool(lack)):
        st.markdown("<div class='small'>이 화 대본에서 뽑은 장소 시점 · 소품 · 분장의상입니다. 콘티를 만들 때 자동으로 뽑아 등록합니다. "
                    "기준 그림이 있어야 컷마다 배경·소품·옷이 같게 나옵니다. 그림을 바꾸거나 직접 올리려면 02 캐스팅에서 합니다.</div>", unsafe_allow_html=True)
        for it in items:
            st.markdown(f"<span class='tag {'ok' if it['ready'] else 'fix'}'>{'그림 있음' if it['ready'] else '그림 없음'}</span> {it['label']} "
                        f"<span class='small'>{(it['info'].get('note') or '')[:80]}</span>", unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        with p1:
            if st.button("준비물만 다시 뽑기 (콘티는 그대로)", disabled=not KEYS.get("ANTHROPIC_API_KEY"), key="prep_only"):
                with st.spinner("대본에서 준비물을 뽑는 중…"):
                    run_breakdown(ep_no, ep)
                save(work)
                st.rerun()
        with p2:
            if st.button(f"없는 기준 그림 한 번에 만들기 ({len(can)}장)", type="primary", disabled=not (KEYS.get("OPENAI_API_KEY") and can), key="prep_make",
                         help="장소 시점은 마스터를, 분장·의상은 확정 얼굴을 기준 그림으로 넣어 한 장씩 만들고 바로 확정합니다. 마스터가 없는 장소는 02 캐스팅에서 먼저 만듭니다."):
                with st.status(f"기준 그림 {len(can)}장 생성 중… (4장씩 동시)") as stt_:
                    make_prep(can)
                    stt_.update(label="기준 그림 생성 완료", state="complete")
                st.rerun()
        if any(it["kind"] == "master" and not it["ready"] for it in items):
            st.markdown("<span class='tag fix'>마스터 없음</span> <span class='small'>마스터가 없는 장소는 02 캐스팅 · 장소 탭에서 먼저 확정해야 시점 그림을 만들 수 있습니다.</span>", unsafe_allow_html=True)
    rec = allcuts.get(str(ep_no))
    if not rec:
        st.info("아직 나누지 않은 화입니다.")
    else:
        cuts = rec["cuts"]
        total = sum(c["dur"] for c in cuts)
        color = {"still": "#D6E2EA", "move": "#7FA2E6", "video": "#191970"}
        bar = "".join(f'<i title="{c["id"]} {c["dur"]}초" style="width:{100 * c["dur"] / max(total, 1):.1f}%;background:{color[c["motion"]]}"></i>' for c in cuts)
        st.markdown(f"<span class='small'>러닝타임</span> <b style='color:var(--navy)'>{total:.1f}초</b> · 컷 {len(cuts)}개 · "
                    f"<span class='small'>연회색 정지 · 파랑 짧은 움직임 · 남색 완전 영상</span><div class='rt'>{bar}</div>", unsafe_allow_html=True)
        iss = cutter.check(cuts, known_c, known_l, [s["no"] for s in ep["scenes"]])
        main_iss = [i for i in iss if i["level"] != "info"]
        extras = sorted({i["msg"].split("'")[1] for i in iss if i["level"] == "info"})
        for i in main_iss:
            st.markdown(f"<span class='tag {i['level']}'>{'고침' if i['level'] == 'fix' else '확인'}</span> {i['id']} · {i['msg']}", unsafe_allow_html=True)
        if extras:
            st.markdown(f"<span class='tag ok'>단역</span> {', '.join(extras)} <span class='small'>(바이블 밖 인물, 기준 이미지 없이 생성)</span>", unsafe_allow_html=True)
        if not main_iss:
            st.markdown("<span class='tag ok'>점검 통과</span> 컷 수 · 길이 · 움직임 규칙 · 대사 길이 · 첫 장면 · 금지어 모두 통과", unsafe_allow_html=True)
        if rec.get("changes"):
            with st.expander(f"감수가 고친 곳 {len(rec['changes'])}건"):
                for x in rec["changes"]:
                    st.markdown(f"<div class='small'>· {x}</div>", unsafe_allow_html=True)
        for c in cuts:
            loc = locdesc.get(c["loc"], ("?", ""))[0]
            d = c["dialogue"]
            dl = f"<div class='s dlg'><b>{d['who']}</b>{'' if d.get('on_screen') else ' (화면 밖)'} {d['text']}</div>" if d else ""
            stx = f"<div class='s'>화면 글자: {c['screen_text']}</div>" if c["screen_text"] else ""
            clx = "<span class='tag fix'>클라이맥스</span>" if c["climax"] else ""
            st.markdown(f"<div class='cut'><div class='h'>{c['id']} · {c['size']} · {c['angle']} · {c['camera']}<span class='d'>{c['dur']}s</span> "
                        f"<span class='tag {'mv' if c['motion'] == 'video' else 'ok'}'>{cutter.MOTIONS[c['motion']]}</span>"
                        f"{clx}</div>"
                        f"<div class='a'>{c['action']}</div>"
                        f"<div class='s'><b>첫 장면</b> {c.get('frame_ko') or c['action']}</div>"
                        + (f"<div class='s'><b>분장·의상</b> {', '.join(f'{w} · {l}' for w, l in c['looks'].items())}</div>" if c.get("looks") else "") +
                        f"<div class='s'><b>움직임</b> {c.get('motion_ko') or ('카메라만 움직인다' if c['motion'] == 'still' else c.get('motion_en', ''))}</div>{dl}{stx}<div class='s'>{c['loc']} {loc}{' · 시점 ' + c['view'] if c.get('view') else ''} · 인물 {', '.join(c['chars']) or '없음'}"
                        f"{' · 효과음 ' + c['sfx'] if c['sfx'] else ''}</div></div>", unsafe_allow_html=True)
            with st.expander(f"{c['id']} 지시문 보기"):
                st.markdown("**스틸 지시문** (gpt-image-2, 기준 그림 함께)")
                st.code(cutter.still_prompt(c, castdesc, locdesc, None, propdesc, look_text(work, c), set(set_loc(work)), prop_texts(work)), language=None)
                st.markdown("**영상 지시문**")
                st.code(cutter.video_prompt(c, castdesc), language=None)
        with st.expander("컷 데이터 직접 고치기 (JSON)"):
            raw = st.text_area("cuts", json.dumps(cuts, ensure_ascii=False, indent=1), height=300, label_visibility="collapsed")
            if st.button("고친 내용 저장"):
                try:
                    store_cuts(ep_no, cutter.normalize(json.loads(raw), ep, B), "edited")
                    save(work)
                    st.rerun()
                except Exception as ex:
                    st.error(f"JSON 형식 오류: {ex}")

# ===== 04 스틸 =====
elif cur == "still":
    allcuts = work.get("cuts", {})
    stills = work.setdefault("stills", {})
    eps_state = work.setdefault("eps", {})
    ready = [e["ep"] for e in parsed["episodes"] if str(e["ep"]) in allcuts]
    done_n = sum(1 for v in eps_state.values() if v.get("still") == "done")
    brief("still", f"스틸 완료 {done_n} / {len(parsed['episodes'])}화")
    if not ready:
        st.info("03 콘티에서 먼저 콘티를 만든 화가 있어야 합니다.")
        st.stop()
    known_c = {c["name"] for c in B["characters"]}
    castdesc = {c: (work.get("cast", {}).get(c, {}).get("prompt_en", "") or c).split(".")[0] for c in known_c}
    locdesc = {l["id"]: (l["name"], work.get("loc", {}).get(l["id"], {}).get("prompt_en", "") or l.get("desc", "")) for l in B["locations"]}
    propdesc = {n: v.get("prompt_en", "") for n, v in work.get("props", {}).items()}

    def refs_for(c):
        """컷에 넣을 기준 그림: 화면에 나오는 인물(확정 그림) → 장소 마스터. 이름 순서가 지시문의 '기준 그림 n번'."""
        out = []
        for ch in c["chars"]:
            base = ch.split(":")[0]
            li = look_info(work, base, (c.get("looks") or {}).get(base))
            sh = sheet_of(li if li and li.get("pick") else work.get("cast", {}).get(base, {}))   # 룩 그림이 있으면 그 룩의 시트
            if not sh or base in [n for n, _ in out]:
                continue
            v = view_for(ch, c)
            out.append((base, sh.get(v) or sh["front"]))
            if sh.get(v) and v != "front":            # 측면·뒷모습·전신 시트를 쓸 때는 얼굴 기준으로 정면도 함께
                out.append((f"{base}@정면", sh["front"]))
        k = work.get("loc", {}).get(c["loc"], {}).get("pick")
        vk = work.get("loc", {}).get(c["loc"], {}).get("views", {}).get(c.get("view") or "", {}).get("pick")
        if vk:                                        # 시점 그림이 이 컷의 배경, 마스터는 전경 참고
            out.append((c["loc"], vk))
            if k:
                out.append((c["loc"] + "@전경", k))
        elif k:
            out.append((c["loc"], k))
        em = emblem_of(work, c["loc"], locdesc.get(c["loc"], ("", ""))[0])
        if em and cutter.shows_emblem(c):             # 벽 엠블럼이 보이는 컷
            out.append(("엠블럼", em))
        for n in c.get("props", []):                  # 소품 기준 그림
            pk = work.get("props", {}).get(n, {}).get("pick")
            if pk:
                out.append(("소품:" + n, pk))
        return out

    def still_state(n):
        cuts = cutter.fix_screens(cutter.fill_props(allcuts[str(n)]["cuts"], propdesc, set_loc(work)))
        rec = stills.setdefault(str(n), {})
        picked = sum(1 for c in cuts if rec.get(c["id"], {}).get("pick"))
        return cuts, rec, picked

    todo = [n for n in ready if eps_state.get(str(n), {}).get("still") != "done"]
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if "still_ep_next" in st.session_state:
            st.session_state["still_ep"] = st.session_state.pop("still_ep_next")
        default = todo[0] if todo else ready[0]
        ep_no = st.selectbox("화", ready, index=ready.index(st.session_state.get("still_ep", default)) if st.session_state.get("still_ep", default) in ready else 0,
                             format_func=lambda n: f"EP {n}" + (" ✓" if eps_state.get(str(n), {}).get("still") == "done" else ""), key="still_ep")
    with c2:
        n_c = st.selectbox("컷당 후보", [1, 2], index=0, help="2장이면 고르는 재미는 있지만 비용이 두 배입니다.")
    cuts, rec, picked = still_state(ep_no)
    missing = [c for c in cuts if not rec.get(c["id"], {}).get("cands")]

    def gen_chain(c, prompt, refs):
        """컷 하나: 만들기 → 자동 검수 → 불합격이면 이유를 지시문에 붙여 다시 (최대 QC_RETRY 회).
        스레드 안에서 돌고, 저장은 하지 않는다. → [{'img','prompt','qc'} …] 시도 기록."""
        ref_data = [(n, img_bytes(k)) for n, k in refs]
        tries, p = [], prompt
        for attempt in range(1 + (QC_RETRY if AUTO_QC else 0)):
            try:
                img = imagegen.edit(KEYS["OPENAI_API_KEY"], p, [(f"{n}.jpg", d) for n, d in ref_data],
                                    "9:16", quality, style="cut", model=KEYS.get("IMAGE_MODEL", ""))
            except Exception as ex:
                tries.append({"err": str(ex), "prompt": p})
                if attempt == 0 and any(x in str(ex) for x in ("429", "500", "502", "503", "imeout")):
                    continue                          # 일시적인 오류는 한 번 더
                break
            res = None
            if AUTO_QC:
                try:
                    res = qc.judge_still(KEYS["ANTHROPIC_API_KEY"], img, ref_data, c, p, MODEL)
                except Exception as ex:              # 검수 자체가 실패하면 그림은 살리고 표시만 남김
                    res = {"pass": True, "items": {}, "fails": [], "note": f"검수 오류: {str(ex)[:120]}"}
            tries.append({"img": img, "prompt": p, "qc": res})
            if res is None or res["pass"]:
                break
            p = qc.fix_prompt(p, res)
        return tries

    def make(targets):
        """targets = [(컷, 지시문, 기준그림)] → 동시에 4개씩 생성·검수.
        컷 하나가 끝날 때마다 바로 저장한다 (창이 닫혀도 이미 만든 그림은 남음).
        컷마다 이번에 만든 그림 중 합격한 첫 그림(없으면 불합격 항목이 가장 적은 그림)을 확정한다."""
        from concurrent.futures import as_completed
        jobs = [t for t in targets for _ in range(n_c)]
        best = {}
        with ThreadPoolExecutor(4) as ex:
            futs = {ex.submit(gen_chain, *t): t for t in jobs}
            for f in as_completed(futs):
                c, prompt, refs = futs[f]
                try:
                    tries = f.result()
                except Exception as e:
                    st.error(f"{c['id']}: {e}")
                    continue
                cell = rec.setdefault(c["id"], {})
                for t in tries:
                    if "err" in t:
                        st.error(f"{c['id']}: {t['err']}")
                        continue
                    k = f"works/{work['id']}/still/ep{ep_no:03d}/{c['id']}_{uuid.uuid4().hex[:6]}.jpg"
                    store.put_bytes(k, t["img"], "image/jpeg")
                    cell.setdefault("cands", []).append(k)
                    cell.setdefault("qc_by", {})[k] = t["qc"]
                    cell.setdefault("prompt_by", {})[k] = t["prompt"]
                    sc = qc.score(t["qc"]) if t["qc"] else 0
                    if c["id"] not in best or sc < best[c["id"]][0]:
                        best[c["id"]] = (sc, k)
                if c["id"] in best:
                    set_pick(cell, best[c["id"]][1])
                finish()                             # 컷마다 저장

    def set_pick(cell, k):
        cell["pick"] = k
        cell["qc"] = cell.get("qc_by", {}).get(k)
        cell["prompt"] = cell.get("prompt_by", {}).get(k) or cell.get("prompt")
        cell.pop("qc_ok", None)

    def qc_bad(cell) -> bool:
        q = cell.get("qc")
        return bool(q) and not q.get("pass") and not cell.get("qc_ok")

    def finish():
        cs, rc, pk = still_state(ep_no)
        e_s = eps_state.setdefault(str(ep_no), {})
        e_s["still"] = "done" if pk == len(cs) else "doing"
        e_s["still_qc"] = sum(1 for c in cs if qc_bad(rc.get(c["id"], {})))
        save(work)

    with c3:
        st.write("")
        label = f"EP {ep_no} 스틸 만들기 ({len(missing)}컷)" if missing else f"EP {ep_no} 스틸 완료 · {picked}/{len(cuts)}컷 확정"
        if st.button(label, type="primary", disabled=not (KEYS.get("OPENAI_API_KEY") and missing)):
            with st.status(f"EP {ep_no} 스틸 {len(missing) * n_c}장 생성{' · 자동 검수' if AUTO_QC else ''} 중… (4컷씩 동시, 2~6분)") as s:
                make([(c, cutter.still_prompt(c, castdesc, locdesc, [n for n, _ in refs_for(c)], propdesc, look_text(work, c), set(set_loc(work)), prop_texts(work)), refs_for(c)) for c in missing])
                finish()
                s.update(label="생성 완료", state="complete")
            st.rerun()
    lack_ = [it["label"] for it in prep_items(work, str(ep_no), {l["id"]: l["name"] for l in B["locations"]}) if not it["ready"]]
    if lack_:
        st.markdown(f"<span class='tag fix'>준비물 그림 없음 {len(lack_)}개</span> <span class='small'>{' · '.join(lack_[:6])}"
                    " — 이대로 만들면 글 설명으로만 들어가 컷마다 달라질 수 있습니다. 03 콘티의 '이 화 준비물'에서 한 번에 만들 수 있습니다.</span>", unsafe_allow_html=True)
    st.caption("버튼 한 번에 한 화만 만듭니다. 만든 직후 자동 검수를 거쳐 합격한 그림이 확정됩니다. 빨간 표시가 남은 컷만 보면 됩니다.")

    have = [c for c in cuts if rec.get(c["id"], {}).get("pick")]
    bad_cuts = [c for c in cuts if qc_bad(rec.get(c["id"], {}))]
    unchecked = [c for c in have if not rec[c["id"]].get("qc")]
    q1, q2, q3 = st.columns([1, 1, 2])
    with q1:
        if st.button(f"검수만 하기 ({len(have)}컷 · 그림 비용 없음)", disabled=not (KEYS.get("ANTHROPIC_API_KEY") and have),
                     help="이미 확정된 그림을 다시 만들지 않고 검수만 합니다. 예전에 만든 화를 점검할 때 씁니다."):
            with st.status(f"EP {ep_no} {len(have)}컷 검수 중… (4컷씩 동시)") as s:
                def judge(c):
                    cell = rec[c["id"]]
                    try:
                        return qc.judge_still(KEYS["ANTHROPIC_API_KEY"], img_bytes(cell["pick"]),
                                              [(n, img_bytes(k)) for n, k in refs_for(c)], c,
                                              cell.get("prompt") or cutter.still_prompt(c, castdesc, locdesc, [n for n, _ in refs_for(c)], propdesc, look_text(work, c), set(set_loc(work)), prop_texts(work)), MODEL)
                    except Exception as ex:
                        return {"pass": True, "items": {}, "fails": [], "note": f"검수 오류: {str(ex)[:120]}"}
                with ThreadPoolExecutor(4) as ex:
                    res = list(ex.map(judge, have))
                for c, r in zip(have, res):
                    cell = rec[c["id"]]
                    cell["qc"] = r
                    cell.setdefault("qc_by", {})[cell["pick"]] = r
                    cell.pop("qc_ok", None)
                finish()
                s.update(label=f"검수 완료 · 불합격 {sum(1 for r in res if not r['pass'])}컷", state="complete")
            st.rerun()
    with q2:
        if st.button(f"불합격 컷 고치기 ({len(bad_cuts)}컷)", disabled=not (KEYS.get("OPENAI_API_KEY") and bad_cuts),
                     type="primary" if bad_cuts else "secondary"):
            with st.status(f"불합격 {len(bad_cuts)}컷을 고쳐 다시 만드는 중… (컷당 최대 {1 + QC_RETRY}회)") as s:
                make([(c, qc.fix_prompt(rec[c["id"]].get("prompt") or cutter.still_prompt(c, castdesc, locdesc, [n for n, _ in refs_for(c)], propdesc, look_text(work, c), set(set_loc(work)), prop_texts(work)),
                                        rec[c["id"]]["qc"]), refs_for(c)) for c in bad_cuts])
                finish()
                s.update(label="다시 만들기 완료", state="complete")
            st.rerun()
    with q3:
        if have:
            ok_n = sum(1 for c in have if (rec[c["id"]].get("qc") or {}).get("pass") or rec[c["id"]].get("qc_ok"))
            st.markdown(f"<div class='small' style='margin-top:8px'>검수 합격 <b>{ok_n}</b> · 불합격 <b style='color:var(--fix)'>{len(bad_cuts)}</b>"
                        f" · 검수 전 <b>{len(unchecked)}</b></div>", unsafe_allow_html=True)

    made = [c for c in cuts if rec.get(c["id"], {}).get("cands")]
    if made:
        r1, r2 = st.columns([1, 3])
        with r1:
            if st.button(f"이 화 스틸 전체 다시 만들기 ({len(cuts)}컷)", key="still_redo",
                         help="콘티는 그대로 두고 이 화의 스틸을 모두 새로 만듭니다. 지금 스틸과 영상은 보관함으로 옮깁니다."):
                st.session_state["still_redo_ask"] = ep_no
        if st.session_state.get("still_redo_ask") == ep_no:
            with r2:
                st.markdown(f"<span class='tag fix'>확인</span> <span class='small'>EP {ep_no} 스틸 {len(made)}컷과 이 화의 영상을 보관함으로 옮기고 "
                            f"{len(cuts)}컷을 새로 만듭니다 (high 기준 약 ${len(cuts) * 0.165:.1f}, 다시 만들기 제외). "
                            "배경·소품이 흔들려서 다시 하는 경우에는 03 콘티에서 '콘티 다시 만들기'를 먼저 하는 것이 맞습니다 (장소 시점이 콘티에서 정해짐).</span>",
                            unsafe_allow_html=True)
                y, n_ = st.columns(2)
                with y:
                    go_redo = st.button("네, 전체 다시 만들기", type="primary", key="still_redo_yes", disabled=not KEYS.get("OPENAI_API_KEY"))
                with n_:
                    if st.button("취소", key="still_redo_no"):
                        st.session_state.pop("still_redo_ask", None)
                        st.rerun()
            if go_redo:
                st.session_state.pop("still_redo_ask", None)
                k = str(ep_no)
                for box in ("stills", "clips"):
                    if work.get(box, {}).get(k):
                        work.setdefault(box + "_old", {}).setdefault(k, []).append({"at": now(), "data": work[box].pop(k)})
                for st_k in ("still", "clip", "still_qc", "clip_qc"):
                    eps_state.setdefault(k, {}).pop(st_k, None)
                for c in cuts:
                    st.session_state.pop(f"sp_{c['id']}", None)
                save(work)
                cuts, rec, picked = still_state(ep_no)
                with st.status(f"EP {ep_no} 스틸 {len(cuts) * n_c}장 새로 생성{' · 자동 검수' if AUTO_QC else ''} 중… (4컷씩 동시)") as s_:
                    make([(c, cutter.still_prompt(c, castdesc, locdesc, [n for n, _ in refs_for(c)], propdesc, look_text(work, c), set(set_loc(work)), prop_texts(work)), refs_for(c)) for c in cuts])
                    finish()
                    s_.update(label="생성 완료", state="complete")
                st.rerun()
    old_p = [c for c in cuts if rec.get(c["id"], {}).get("prompt")]
    if old_p and st.button(f"이 화 지시문 전체 새로 쓰기 ({len(old_p)}컷 · 비용 없음)",
                           help="엔진 규칙·소품·기준 그림이 바뀐 뒤에 누릅니다. 그림은 그대로 두고 지시문만 지금 규칙으로 다시 조립합니다. 그다음 다시 만들 컷만 '이 컷 다시'를 누르세요."):
        for c in old_p:
            rec[c["id"]].pop("prompt", None)
            st.session_state.pop(f"sp_{c['id']}", None)
        save(work)
        st.rerun()
    st.markdown(f"**EP {ep_no}** · {parsed['episodes'][ep_no - 1]['emotion']} · <span class='hook'>{parsed['episodes'][ep_no - 1]['hook']}</span>", unsafe_allow_html=True)
    cols = st.columns(4)
    for i, c in enumerate(cuts):
        cell = rec.get(c["id"], {})
        refs = refs_for(c)
        with cols[i % 4]:
            q = cell.get("qc")
            if not q:
                qtag = ""
            elif cell.get("qc_ok"):
                qtag = "<span class='tag ok'>통과 처리</span>"
            elif q.get("pass"):
                qtag = "<span class='tag ok'>검수 합격</span>" + (f"<div class='s'>{q['note']}</div>" if q.get("note") else "")
            else:
                qtag = f"<span class='tag fix'>불합격</span><div class='s' style='color:var(--fix)'>{qc.label(q)}</div>"
            st.markdown(f"<div class='cut'><div class='h'>{c['id']} · {c['size']}<span class='d'>{c['dur']}s</span> "
                        f"<span class='tag {'mv' if c['motion'] == 'video' else 'ok'}'>{cutter.MOTIONS[c['motion']]}</span></div>"
                        f"<div class='s'><b>첫 장면</b> {c.get('frame_ko') or c['action']}</div>"
                        + (f"<div class='s'><b>분장·의상</b> {', '.join(f'{w} · {l}' for w, l in c['looks'].items())}</div>" if c.get("looks") else "") +
                        f"<div class='s'>기준 그림: {', '.join(n for n, _ in refs) or '없음 (지시문만)'}</div>{qtag}</div>", unsafe_allow_html=True)
            if cell.get("pick"):
                data = img_bytes(cell["pick"])
                if data:
                    st.image(data, width="stretch")
            if qc_bad(cell) and st.button("이대로 통과", key=f"sok_{c['id']}", help="검수 판정이 틀렸을 때 사람이 통과시킵니다."):
                cell["qc_ok"] = True
                finish()
                st.rerun()
            others = [k for k in cell.get("cands", []) if k != cell.get("pick")]
            if others:
                oc = st.columns(min(3, len(others)))
                for j, k in enumerate(others[-3:]):
                    with oc[j]:
                        d = img_bytes(k)
                        if d:
                            st.image(d, width="stretch")
                        qk = cell.get("qc_by", {}).get(k)
                        if qk:
                            st.caption("합격" if qk.get("pass") else "불합격")
                        if st.button("이걸로", key=f"spk_{k}"):
                            set_pick(cell, k)
                            finish()
                            st.rerun()
            with st.expander("지시문 · 다시 만들기"):
                base_p = cell.get("prompt") or cutter.still_prompt(c, castdesc, locdesc, [n for n, _ in refs], propdesc, look_text(work, c), set(set_loc(work)), prop_texts(work))
                if cell.get("prompt") and st.button("지시문 새로 쓰기 (지금 규칙·소품·기준 그림으로)", key=f"snew_{c['id']}",
                                                    help="예전 규칙으로 만든 지시문을 버리고 새로 조립합니다. 그다음 '이 컷 다시'를 누르세요."):
                    cell.pop("prompt", None)
                    st.session_state.pop(f"sp_{c['id']}", None)
                    save(work)
                    st.rerun()
                p2 = st.text_area("지시문", base_p, key=f"sp_{c['id']}", height=160, label_visibility="collapsed")
                bad = imagegen.banned_in(p2)
                if bad:
                    st.markdown(f'<span class="tag fix">금지어</span> {" · ".join(bad)}', unsafe_allow_html=True)
                if st.button("이 컷 다시", key=f"sre_{c['id']}", disabled=not (KEYS.get("OPENAI_API_KEY") and not bad)):
                    with st.spinner(f"{c['id']} 다시 만드는 중…"):
                        make([(c, p2, refs)])
                        finish()
                    st.rerun()
    if picked == len(cuts) and todo and ep_no in todo:
        finish()
    nxt = [n for n in todo if n != ep_no]
    if eps_state.get(str(ep_no), {}).get("still") == "done" and nxt and st.button(f"다음 화로 (EP {nxt[0]})"):
        st.session_state["still_ep_next"] = nxt[0]
        st.rerun()

# ===== 05 영상 =====
elif cur == "clip":
    allcuts = work.get("cuts", {})
    stills = work.get("stills", {})
    clips = work.setdefault("clips", {})
    eps_state = work.setdefault("eps", {})
    ready = [e["ep"] for e in parsed["episodes"] if eps_state.get(str(e["ep"]), {}).get("still") == "done"]
    done_n = sum(1 for v in eps_state.values() if v.get("clip") == "done")
    brief("clip", f"영상 완료 {done_n} / {len(parsed['episodes'])}화")
    if not ready:
        st.info("04 콘티 그림에서 모든 컷 그림이 확정된 화가 있어야 합니다.")
        st.stop()
    TOKEN = KEYS.get("REPLICATE_API_TOKEN", "")
    VMODEL = KEYS.get("REPLICATE_VIDEO_MODEL", "") or videogen.DEFAULT_MODEL
    if not TOKEN:
        st.warning("Streamlit 시크릿에 REPLICATE_API_TOKEN 을 넣으면 영상 생성 버튼이 열립니다.")
    known_c = {c["name"] for c in B["characters"]}
    castdesc = {c: (work.get("cast", {}).get(c, {}).get("prompt_en", "") or c).split(".")[0] for c in known_c}

    todo = [n for n in ready if eps_state.get(str(n), {}).get("clip") != "done"]
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if "clip_ep_next" in st.session_state:
            st.session_state["clip_ep"] = st.session_state.pop("clip_ep_next")
        dflt = st.session_state.get("clip_ep", todo[0] if todo else ready[0])
        ep_no = st.selectbox("화", ready, index=ready.index(dflt) if dflt in ready else 0, key="clip_ep",
                             format_func=lambda n: f"EP {n}" + (" ✓" if eps_state.get(str(n), {}).get("clip") == "done" else ""))
    with c2:
        mode = st.selectbox("화질", ["pro", "standard"], format_func=lambda m: {"standard": "720p (시험용)", "pro": "1080p (기본 · 4K 업스케일 대비)"}[m],
                            help="720p로 시험한 테이크를 1080p로 다시 만들면 다른 움직임이 나옵니다. 본편은 처음부터 1080p로 만듭니다.")
    cuts = cutter.fix_screens(allcuts[str(ep_no)]["cuts"])   # 화면 글자 컷은 정지 컷 (영상을 만들지 않음)
    rec = clips.setdefault(str(ep_no), {})
    srec = stills.get(str(ep_no), {})
    moving = [c for c in cuts if c["motion"] in ("move", "video")]
    def stale(c) -> bool:
        """영상을 만든 뒤에 스틸이 바뀐 컷: 영상이 예전 스틸에서 시작하므로 다시 만들어야 한다."""
        cell = rec.get(c["id"], {})
        return bool(cell.get("key") and cell.get("still") and cell["still"] != srec.get(c["id"], {}).get("pick"))

    missing = [c for c in moving if not rec.get(c["id"], {}).get("key") or stale(c)]
    running = {cid: r["get"] for cid, r in rec.items() if r.get("get") and r.get("status") not in videogen.DONE}

    cutmap = {c["id"]: c for c in cuts}

    def clip_bad(cell) -> bool:
        return bool(cell.get("fallback")) and not cell.get("qc_ok")

    def finish():
        ok = all(rec.get(c["id"], {}).get("key") and not stale(c) for c in moving)
        e_s = eps_state.setdefault(str(ep_no), {})
        e_s["clip"] = "done" if ok else "doing"
        e_s["clip_qc"] = sum(1 for c in moving if clip_bad(rec.get(c["id"], {})))
        save(work)

    def judge_take(cid, data):
        c = cutmap[cid]
        still = img_bytes(srec.get(cid, {}).get("pick", "")) if srec.get(cid, {}).get("pick") else None
        if not (AUTO_QC and still):
            return None
        try:
            return qc.judge_clip(KEYS["ANTHROPIC_API_KEY"], data, still, c, rec[cid].get("prompt", ""), MODEL)
        except Exception as ex:
            return {"pass": True, "items": {}, "fails": [], "note": f"검수 오류: {str(ex)[:120]}"}

    def collect(jobs, box):
        """진행 중인 예측을 끝까지 기다렸다가 영상을 저장소에 넣고 자동 검수한다.
        불합격이면 이유를 지시문에 붙여 다시 만들고(컷당 QC_RETRY 회), 그래도 불합격이면 불합격 항목이 가장 적은 테이크를 남기고
        그 컷을 '정지+카메라로 전환' 표시한다 (편집에서 스틸을 씀). 창을 닫아도 '결과 불러오기'로 이어 받을 수 있다."""
        while jobs:
            def tick(res):
                n = sum(1 for r in res.values() if r.get("status") in videogen.DONE)
                box.update(label=f"영상 {n}/{len(jobs)}개 완료 (컷마다 1~5분)")
            res = videogen.wait_all(TOKEN, jobs, on_tick=tick)
            retry = []
            for cid, r in res.items():
                cell = rec.setdefault(cid, {})
                cell["status"] = r.get("status")
                if r.get("status") == "succeeded" and r.get("output"):
                    try:
                        data = videogen.download(r["output"])
                    except Exception as ex:          # 받기 실패: 예측 번호는 남아 있으니 '결과 불러오기'로 다시
                        cell["status"] = "processing"
                        st.error(f"{cid}: 영상 받기 실패 ({ex}). 잠시 뒤 '결과 불러오기'를 누르세요.")
                        continue
                    k = f"works/{work['id']}/clip/ep{ep_no:03d}/{cid}_{uuid.uuid4().hex[:6]}.mp4"
                    store.put_bytes(k, data, "video/mp4")
                    cell.setdefault("takes", []).append(k)
                    cell["key"] = k
                    box.update(label=f"{cid} 영상 검수 중…")
                    q = judge_take(cid, data)
                    cell["qc"] = q
                    cell.setdefault("qc_by", {})[k] = q
                    cell.pop("qc_ok", None)
                    if not q or q["pass"]:
                        cell.pop("fallback", None)
                    elif cell.get("tries", 0) < QC_RETRY:
                        retry.append((cutmap[cid], qc.fix_prompt(cell.get("prompt", ""), q)))
                    else:                            # 다시 만들어도 불합격: 가장 나은 테이크 + 정지 컷 전환 표시
                        bk = min(cell["takes"], key=lambda t: qc.score(cell.get("qc_by", {}).get(t)))
                        cell["key"], cell["qc"] = bk, cell["qc_by"].get(bk)
                        cell["fallback"] = not (cell["qc"] or {}).get("pass", True)
                elif r.get("status") in ("failed", "canceled"):
                    cell["error"] = str(r.get("error"))[:300]
                    if r.get("status") == "failed" and cell.get("tries", 0) < 1:   # 서버 쪽 실패는 같은 지시문으로 한 번 더
                        retry.append((cutmap[cid], cell.get("prompt", "")))
            finish()
            if not retry:
                break
            box.update(label=f"불합격 {len(retry)}컷 고쳐서 다시 만드는 중…")
            jobs = launch(retry, again=True)

    def launch(targets, again: bool = False):
        """again=True 는 자동 검수 불합격으로 다시 만드는 경우 (시도 횟수를 이어서 셈)."""
        jobs = {}
        for c, prompt in targets:
            still = srec.get(c["id"], {}).get("pick")
            data = img_bytes(still) if still else None
            if not data:
                st.error(f"{c['id']}: 확정 스틸이 없습니다")
                continue
            try:
                p = videogen.start(TOKEN, prompt, data, videogen.clip_seconds(c["dur"]), VMODEL, mode)
            except Exception as ex:
                st.error(f"{c['id']}: {ex}")
                continue
            old = rec.get(c["id"], {})
            keep = ("takes", "qc_by", "key") if old.get("still") in (None, still) else ("takes", "qc_by")   # 스틸이 바뀌었으면 예전 영상은 확정에서 뺌
            rec[c["id"]] = {**{k: v for k, v in old.items() if k in keep}, "still": still,
                            "tries": old.get("tries", 0) + 1 if again else 0,
                            "pred": p["id"], "get": p["get"], "status": p["status"], "prompt": prompt, "mode": mode, "model": VMODEL}
            jobs[c["id"]] = p["get"]
        save(work)                      # 예측 번호를 먼저 저장 (창을 닫아도 이어 받기)
        return jobs

    with c3:
        st.write("")
        if running:
            if st.button(f"진행 중인 영상 결과 불러오기 ({len(running)}컷)", type="primary", disabled=not TOKEN):
                with st.status("Replicate 결과 확인 중…") as box:
                    collect(running, box)
                    box.update(label="확인 완료", state="complete")
                st.rerun()
        else:
            label = f"EP {ep_no} 영상 만들기 ({len(missing)}컷)" if missing else f"EP {ep_no} 영상 완료 · {len(moving)}컷"
            if st.button(label, type="primary", disabled=not (TOKEN and missing)):
                with st.status(f"EP {ep_no} 영상 {len(missing)}개 생성 시작…") as box:
                    jobs = launch([(c, cutter.video_prompt(c, castdesc)) for c in missing])
                    if jobs:
                        collect(jobs, box)
                    box.update(label="생성 끝", state="complete")
                st.rerun()
    st.caption(f"모델 {VMODEL} · 확정 스틸을 첫 프레임으로 씁니다. '짧은 움직임'과 '완전 영상' 컷만 3초부터 만들고 편집에서 컷 길이만큼 자릅니다. "
               "'정지+카메라' 컷은 편집 단계에서 스틸에 카메라 움직임을 넣습니다. 버튼 한 번에 한 화만 진행합니다.")

    cols = st.columns(4)
    for i, c in enumerate(cuts):
        cell = rec.get(c["id"], {})
        with cols[i % 4]:
            st.markdown(f"<div class='cut'><div class='h'>{c['id']} · {c['size']}<span class='d'>{c['dur']}s</span> "
                        f"<span class='tag {'mv' if c['motion'] == 'video' else 'ok'}'>{cutter.MOTIONS[c['motion']]}</span></div>"
                        f"<div class='s'><b>움직임</b> {c.get('motion_ko') or c.get('motion_en') or c['action']}</div></div>", unsafe_allow_html=True)
            if c["motion"] == "still":
                d = img_bytes(srec.get(c["id"], {}).get("pick", "")) if srec.get(c["id"], {}).get("pick") else None
                if d:
                    st.image(d, width="stretch")
                st.caption("편집에서 카메라 움직임만 넣습니다")
                continue
            if stale(c):
                st.markdown("<span class='tag fix'>스틸이 바뀜</span> <span class='small'>이 영상은 예전 스틸에서 시작합니다. 위의 '영상 만들기'를 누르면 이 컷만 다시 만듭니다.</span>",
                            unsafe_allow_html=True)
            q = cell.get("qc")
            if cell.get("fallback") and not cell.get("qc_ok"):
                st.markdown(f"<span class='tag fix'>정지+카메라로 전환</span><div class='small' style='color:var(--fix)'>{qc.label(q)}</div>",
                            unsafe_allow_html=True)
            elif cell.get("qc_ok"):
                st.markdown("<span class='tag ok'>통과 처리</span>", unsafe_allow_html=True)
            elif q:
                st.markdown(f"<span class='tag {'ok' if q.get('pass') else 'fix'}'>{'검수 합격' if q.get('pass') else '불합격'}</span>"
                            f"<span class='small'>{q.get('note', '') if q.get('pass') else qc.label(q)}</span>", unsafe_allow_html=True)
            if cell.get("key"):
                v = img_bytes(cell["key"])
                if v:
                    st.video(v)
                if clip_bad(cell) and st.button("영상 그대로 쓰기", key=f"vok_{c['id']}", help="검수 판정이 틀렸을 때 사람이 통과시킵니다."):
                    cell["qc_ok"] = True
                    finish()
                    st.rerun()
            elif cell.get("status") and cell["status"] not in videogen.DONE:
                st.markdown('<span class="tag todo">생성 중</span>', unsafe_allow_html=True)
            elif cell.get("error"):
                st.markdown(f'<span class="tag fix">실패</span> <span class="small">{cell["error"]}</span>', unsafe_allow_html=True)
            takes = [k for k in cell.get("takes", []) if k != cell.get("key")]
            for k in takes[-2:]:
                if st.button("이전 테이크로", key=f"vtk_{k}"):
                    cell["key"] = k
                    cell["qc"] = cell.get("qc_by", {}).get(k)
                    cell["fallback"] = bool(cell["qc"]) and not cell["qc"].get("pass")
                    finish()
                    st.rerun()
            with st.expander("지시문 · 다시 만들기"):
                p2 = st.text_area("지시문", cell.get("prompt") or cutter.video_prompt(c, castdesc), key=f"vp_{c['id']}",
                                  height=150, label_visibility="collapsed")
                if st.button("이 컷 다시", key=f"vre_{c['id']}", disabled=not TOKEN or bool(running)):
                    with st.status(f"{c['id']} 다시 만드는 중… (1~5분)") as box:
                        jobs = launch([(c, p2)])
                        if jobs:
                            collect(jobs, box)
                    st.rerun()
    nxt = [n for n in todo if n != ep_no]
    if eps_state.get(str(ep_no), {}).get("clip") == "done" and nxt and st.button(f"다음 화로 (EP {nxt[0]})"):
        st.session_state["clip_ep_next"] = nxt[0]
        st.rerun()

# ===== 06 더빙 =====
elif cur == "dub":
    allcuts = work.get("cuts", {})
    dubs = work.setdefault("dubs", {})
    vmap = work.setdefault("voices", {})
    eps_state = work.setdefault("eps", {})
    EKEY = KEYS.get("ELEVENLABS_API_KEY", "")
    n_ep = len(parsed["episodes"])
    brief("dub", f"더빙 완료 {sum(1 for v in eps_state.values() if v.get('dub') == 'done')} / {n_ep}화")
    ready = [e["ep"] for e in parsed["episodes"] if str(e["ep"]) in allcuts]
    if not EKEY:
        st.info("Streamlit Secrets 에 ELEVENLABS_API_KEY 를 넣으면 더빙을 만들 수 있습니다.")
    if not ready:
        st.info("03 콘티를 만든 화가 있어야 합니다.")
        st.stop()

    @st.cache_data(show_spinner=False, ttl=900)
    def voice_list(_key: str, tag: str):
        return dubbing.voices(_key)

    d1, d2, d3 = st.columns([1, 1, 2])
    with d1:
        todo_d = [n for n in ready if eps_state.get(str(n), {}).get("dub") != "done"]
        if "dub_ep_next" in st.session_state:
            st.session_state["dub_ep"] = st.session_state.pop("dub_ep_next")
        ep_no = st.selectbox("화", ready, index=ready.index(todo_d[0]) if todo_d else 0, key="dub_ep",
                             format_func=lambda n: f"EP {n}" + (" ✓" if eps_state.get(str(n), {}).get("dub") == "done" else ""))
    with d2:
        speed = st.slider("말 빠르기", 0.8, 1.2, float(work.get("dub_speed", 1.0)), 0.05,
                          help="1.0 이 기본입니다. 숏폼은 1.0~1.1 이 자연스럽습니다. 바꾸면 그다음에 만드는 대사부터 적용됩니다.")
        if speed != work.get("dub_speed", 1.0):
            work["dub_speed"] = speed
            save(work)
    cuts = allcuts[str(ep_no)]["cuts"]
    rec = dubs.setdefault(str(ep_no), {})
    lines = [(i, c) for i, c in enumerate(cuts) if c.get("dialogue") and c["dialogue"].get("text", "").strip()]
    whos = []
    for _, c in lines:
        if c["dialogue"]["who"] not in whos:
            whos.append(c["dialogue"]["who"])
    speakers = whos + [n for n in chars_ranked(work)[: work.get("main_n", 6)] if n not in whos]

    def stale_d(c) -> bool:
        """대사나 배정한 목소리가 바뀐 줄: 다시 만들어야 한다."""
        cell = rec.get(c["id"], {})
        v = vmap.get(c["dialogue"]["who"], {}).get("id")
        return bool(cell.get("key")) and (cell.get("text") != c["dialogue"]["text"] or cell.get("voice") != v)

    def dub_bad(cell) -> bool:
        return bool(cell.get("key")) and not cell.get("pass", True) and not cell.get("ok")

    def finish_d():
        ok = all(rec.get(c["id"], {}).get("key") and not stale_d(c) for _, c in lines)
        e_s = eps_state.setdefault(str(ep_no), {})
        e_s["dub"] = "done" if ok else "doing"
        e_s["dub_qc"] = sum(1 for _, c in lines if dub_bad(rec.get(c["id"], {})))
        save(work)

    # ── 목소리 배정 (작품당 한 번) ──
    no_voice = [w for w in whos if not vmap.get(w, {}).get("id")]
    with st.expander(f"목소리 배정 · {sum(1 for w in speakers if vmap.get(w, {}).get('id'))} / {len(speakers)}명"
                     + (f" · 이 화에 필요한 {len(no_voice)}명 미배정" if no_voice else ""), expanded=bool(no_voice)):
        st.markdown("<div class='small'>인물마다 목소리 하나를 고르면 100화 내내 그 목소리로 만듭니다. 목록은 ElevenLabs 계정에서 쓸 수 있는 목소리입니다. "
                    "한국어 목소리가 적으면 ElevenLabs 의 Voice Library 에서 한국어 목소리를 'Add' 한 뒤 '목록 새로 받기'를 누르세요.</div>", unsafe_allow_html=True)
        vs = []
        if EKEY:
            try:
                vs = voice_list(EKEY, st.session_state.get("voice_tag", "0"))
            except Exception as ex:
                st.error(f"목소리 목록을 받지 못했습니다: {ex}")
        f1, f2, f3, f4 = st.columns([1, 1, 2, 1])
        with f1:
            fg = st.selectbox("성별", ["전체", "여", "남"], key="vf_gender")
        with f2:
            fk = st.checkbox("한국어 목소리만", value=False, key="vf_ko")
        with f3:
            fq = st.text_input("이름·설명으로 찾기", key="vf_q")
        with f4:
            st.write("")
            if st.button("목록 새로 받기", key="vf_reload"):
                st.session_state["voice_tag"] = uuid.uuid4().hex[:6]
                st.rerun()
        gmap = {"여": "female", "남": "male"}
        shown = [v for v in vs if (fg == "전체" or v["gender"] == gmap[fg]) and (not fk or v["ko"])
                 and (not fq.strip() or fq.strip().lower() in (v["name"] + " " + v["desc"]).lower())]
        st.caption(f"목소리 {len(shown)}개 (전체 {len(vs)}개)")
        byid = {v["id"]: v for v in vs}
        for w in speakers:
            cur_id = vmap.get(w, {}).get("id", "")
            opts = [""] + [v["id"] for v in shown] + ([cur_id] if cur_id and cur_id not in [v["id"] for v in shown] else [])
            a1, a2, a3 = st.columns([2, 2, 1])
            with a1:
                sel = st.selectbox(w + (" · 이 화에 나옴" if w in whos else ""), opts, index=opts.index(cur_id) if cur_id in opts else 0, key=f"vsel_{w}",
                                   format_func=lambda i: dubbing.voice_label(byid[i]) if i in byid else (vmap.get(w, {}).get("name", "") if i else "고르지 않음"))
            with a2:
                pv = byid.get(sel, {}).get("preview")
                if pv:
                    st.audio(pv)
                samp = st.session_state.get(f"vsamp_{w}_{sel}")
                if samp:
                    st.audio(samp, format="audio/mpeg")
            with a3:
                st.write("")
                first = next((c["dialogue"]["text"] for _, c in lines if c["dialogue"]["who"] == w), "")
                if sel and first and st.button("대사로 들어 보기", key=f"vtry_{w}", disabled=not EKEY, help=f"이 화의 첫 대사를 이 목소리로 만들어 들려줍니다: {first[:30]}"):
                    try:
                        st.session_state[f"vsamp_{w}_{sel}"] = dubbing.speak(EKEY, sel, first, model=KEYS.get("ELEVEN_MODEL", ""), speed=speed)
                    except Exception as ex:
                        st.error(str(ex))
                    st.rerun()
            if sel != cur_id:
                if sel:
                    vmap[w] = {"id": sel, "name": byid.get(sel, {}).get("name", "")}
                else:
                    vmap.pop(w, None)
                finish_d()
                st.rerun()

    missing_d = [(i, c) for i, c in lines if (not rec.get(c["id"], {}).get("key") or stale_d(c)) and vmap.get(c["dialogue"]["who"], {}).get("id")]

    def make_dub(targets):
        """targets = [(i, 컷)] → 3줄씩 동시에 만들고 받아 적기로 검수. 한 줄이 끝날 때마다 저장."""
        from concurrent.futures import as_completed

        def one(i, c):
            prev, nxt = dubbing.context(cuts, i)
            return dubbing.make_line(EKEY, vmap[c["dialogue"]["who"]]["id"], c["dialogue"]["text"], prev, nxt,
                                     KEYS.get("ELEVEN_MODEL", ""), speed, check=True)
        with ThreadPoolExecutor(3) as ex:
            futs = {ex.submit(one, i, c): c for i, c in targets}
            for f in as_completed(futs):
                c = futs[f]
                try:
                    r = f.result()
                except Exception as e:
                    st.error(f"{c['id']}: {e}")
                    continue
                k = f"works/{work['id']}/dub/ep{ep_no:03d}/{c['id']}_{uuid.uuid4().hex[:6]}.mp3"
                store.put_bytes(k, r["mp3"], "audio/mpeg")
                old = rec.get(c["id"], {})
                rec[c["id"]] = {"key": k, "takes": (old.get("takes") or []) + [k], "sec": r["sec"], "heard": r["heard"], "score": r["score"],
                                "pass": r["pass"], "note": r["note"], "tries": r["tries"], "text": c["dialogue"]["text"],
                                "voice": vmap[c["dialogue"]["who"]]["id"], "who": c["dialogue"]["who"]}
                finish_d()

    with d3:
        st.write("")
        lab = f"EP {ep_no} 더빙 만들기 ({len(missing_d)}줄)" if missing_d else (f"EP {ep_no} 더빙 완료 · {len(lines)}줄" if lines else f"EP {ep_no} 대사 없음")
        if st.button(lab, type="primary", disabled=not (EKEY and missing_d)):
            with st.status(f"EP {ep_no} 대사 {len(missing_d)}줄 생성 · 받아 적기 검수 중… (3줄씩 동시)") as s_:
                make_dub(missing_d)
                finish_d()
                s_.update(label="더빙 완료", state="complete")
            st.rerun()
    if not lines and eps_state.get(str(ep_no), {}).get("dub") != "done":
        finish_d()
    if no_voice:
        st.markdown(f"<span class='tag fix'>목소리 미배정</span> <span class='small'>{' · '.join(no_voice)} — 위 '목소리 배정'에서 고르면 그 인물의 대사를 만듭니다.</span>", unsafe_allow_html=True)
    total = sum(max(c["dur"], rec.get(c["id"], {}).get("sec", 0) + 0.2 if c.get("dialogue") else 0) for c in cuts)
    st.caption(f"버튼 한 번에 한 화만 만듭니다. 만든 음성을 다시 글자로 받아 적어 대본과 비교하고, 다르게 읽힌 줄은 2회까지 다시 만듭니다. "
               f"빨간 표시가 남은 줄만 들어 보면 됩니다. · 더빙을 반영한 이 화 길이 약 {total:.0f}초")

    for i, c in lines:
        cell = rec.get(c["id"], {})
        d = c["dialogue"]
        vname = vmap.get(d["who"], {}).get("name", "미배정")
        if not cell.get("key"):
            tag = "<span class='tag todo'>대기</span>"
        elif stale_d(c):
            tag = "<span class='tag fix'>대사·목소리가 바뀜</span>"
        elif cell.get("ok"):
            tag = "<span class='tag ok'>통과 처리</span>"
        elif cell.get("pass", True):
            tag = "<span class='tag ok'>검수 합격</span>" + (f" <span class='small'>{cell['note']}</span>" if cell.get("note") else "")
        else:
            tag = f"<span class='tag fix'>다르게 읽힘</span> <span class='small' style='color:var(--fix)'>들린 말: {cell.get('heard', '')}</span>"
        over = cell.get("sec", 0) + 0.2 - c["dur"]
        longer = f" <span class='tag todo'>컷보다 {over:.1f}초 김 · 편집에서 컷을 늘림</span>" if cell.get("key") and over > 0.05 else ""
        l1, l2, l3 = st.columns([3, 2, 1])
        with l1:
            st.markdown(f"<div class='cut'><div class='h'>{c['id']} · {d['who']} <span class='d'>{vname}</span>"
                        f"<span class='d'>{cell.get('sec', 0):.1f}s / 컷 {c['dur']}s</span></div>"
                        f"<div class='a'>{d['text']}</div>{tag}{longer}</div>", unsafe_allow_html=True)
        with l2:
            if cell.get("key"):
                a = img_bytes(cell["key"])
                if a:
                    st.audio(a, format="audio/mpeg")
        with l3:
            if vmap.get(d["who"], {}).get("id") and st.button("이 줄 다시", key=f"dre_{c['id']}", disabled=not EKEY):
                with st.spinner(f"{c['id']} 다시 만드는 중…"):
                    make_dub([(i, c)])
                    finish_d()
                st.rerun()
            if dub_bad(cell) and st.button("이대로 통과", key=f"dok_{c['id']}", help="받아 적기가 틀렸을 때 사람이 통과시킵니다."):
                cell["ok"] = True
                finish_d()
                st.rerun()
    nxt_d = [n for n in ready if n != ep_no and eps_state.get(str(n), {}).get("dub") != "done"]
    if eps_state.get(str(ep_no), {}).get("dub") == "done" and nxt_d and st.button(f"다음 화로 (EP {nxt_d[0]})"):
        st.session_state["dub_ep_next"] = nxt_d[0]
        st.rerun()

# ===== 07 이후 =====
else:
    brief(cur, "다음 버전")
    st.info("지금 버전은 대본 · 캐스팅 · 콘티 · 콘티 그림 · 영상 · 더빙까지입니다. 다음: 07 자막·사운드 → 08 편집 → 09 마스터.")

# ───────── 화면 맨 아래: 다음 할 일 안내 ─────────
st.divider()
_p = progress(work)
st.markdown(f"<div class='small'>다음 할 일 · <b>{_p['next']}</b></div>", unsafe_allow_html=True)
go_bar(_p, key="go_next_bottom")
