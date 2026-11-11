"""BLUE JEANS · SHORTFORM DRAMA ENGINE  (숏폼드라마 엔진) v0.2

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
from src import cutter, imagegen, profiles, script_parser
from src.store import Store, secrets_dict

VERSION = "v0.4"
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
    ("cut", "03", "컷", "회당 컷 분할 · 지시문"),
    ("still", "04", "스틸", "컷별 장면 이미지"),
    ("clip", "05", "영상", "움직임 · 완전 영상"),
    ("dub", "06", "더빙", "인물별 고정 목소리"),
    ("sub", "07", "자막·사운드", "한/영 자막 · 효과음"),
    ("edit", "08", "편집", "9:16 렌더링"),
    ("master", "09", "마스터", "확인 · 업로드"),
]
HOW = {
    "clip": "확정한 스틸을 첫 프레임으로 넣어 짧은 영상을 만듭니다 (Replicate · Kling). 소리는 만들지 않고 06·07 단계에서 대사와 효과음을 얹습니다.",
    "still": "컷마다 장면 그림을 만듭니다. 화면에 나오는 인물의 확정 그림과 장소 마스터를 기준 그림으로 함께 넣어 얼굴·의상·공간을 이어 갑니다. 글자는 그림에 넣지 않고 편집에서 얹습니다.",
    "script": "대본을 읽고 작품 정리를 합니다. 엔진은 인물 표기와 장소 세트만 통일하고, 설정 충돌은 '수정 제안'으로 남깁니다. 원고 수정은 감독님이 직접 하고, 고친 원고를 다시 올리면 됩니다.",
    "cast": "인물마다 프로필을 확정하고 얼굴 후보 중 1장을 고릅니다. 장소는 넓은 마스터 1장을 고릅니다. 직접 만든 이미지는 올리기로 넣습니다.",
    "cut": "한 화를 6~8컷, 50~70초로 나눕니다. 컷마다 크기·각도·움직임 종류·대사·화면 글자를 정하고 스틸·영상 지시문을 만듭니다. 빨간 표시는 고쳐야 할 컷입니다.",
}


def slug(name: str) -> str:
    s = re.sub(r"\s+", "_", name.strip())
    return re.sub(r"[^\w가-힣_-]", "", s) or uuid.uuid4().hex[:6]


KST = dt.timezone(dt.timedelta(hours=9))


def now() -> str:
    return dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")


@st.cache_data(show_spinner=False, ttl=600)
@st.cache_data(max_entries=400, show_spinner=False)
def img_bytes(key: str):
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


def stage_counts(work: dict | None) -> dict:
    out = {k: (0, 0) for k, *_ in STAGES}
    if not work:
        return out
    n_ep = work["summary"]["episodes"]
    out["script"] = (1 if work.get("bible") else 0, 1)
    if work.get("bible"):
        chars = chars_ranked(work)[: work.get("main_n", 6)]
        locs = locs_ranked(work)[: work.get("loc_n", 8)]
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
    locs = locs_ranked(work)[: work.get("loc_n", 8)]
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
               [l["name"] for l in locs_ranked(work)[: work.get("loc_n", 8)] if not work.get("loc", {}).get(l["id"], {}).get("pick")]
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
        cls = ("g " if (i - 1) % BINGE == 0 else "") + ("fx" if eps.get(str(i), {}).get("cut") == "fix" else "")
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
    picks = [(f"CAST_FINAL/{c}_ref_front.jpg", v["pick"]) for c, v in work.get("cast", {}).items() if v.get("pick")] + \
            [(f"LOCATION_MASTER/{lid}_{next((l['name'] for l in B['locations'] if l['id'] == lid), '')}_master.jpg", v["pick"])
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
                           mime="application/zip", help="CAST_FINAL·LOCATION_MASTER 폴더로 나뉘고, 이름이 '인물_ref_front', '장소번호_장소_master' 로 정리됩니다. 압축을 풀어 드라이브 작업 폴더에 그대로 올리면 됩니다.")
    t_char, t_loc = st.tabs(["인물", "장소 (마스터)"])
    stt = bb.stats(B, parsed)

    def gen_many(prompts, aspect, style="ref"):
        def one(p):
            try:
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
                for r in gen_many([prompt] * n_cand, aspect, "ref" if kind == "cast" else "location"):
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

    with t_loc:
        loc_n = st.slider("마스터를 만들 장소 수 (장면 많은 순)", 1, max(1, len(locs_all)), min(work.get("loc_n", 8), max(1, len(locs_all))))
        if loc_n != work.get("loc_n"):
            work["loc_n"] = loc_n
            save(work)
        locs = locs_all[:loc_n]
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
        st.caption("장소마다 넓은 마스터 1장을 확정합니다. 같은 장소의 모든 컷은 이 마스터에서 만듭니다.")
        for l in locs:
            info = work.setdefault("loc", {}).setdefault(l["id"], {})
            info.setdefault("desc_ko", l.get("desc", ""))     # 영어 지시문이 비었을 때 이 설명으로 바로 쓸 수 있게
            with st.expander(f"{'✓ ' if info.get('pick') else ''}{l['id']} {l['name']} · 장면 {stt['loc'].get(l['id'], 0)}개", expanded=not info.get("pick")):
                st.markdown(f"<div class='small'>{l.get('desc','')}</div>", unsafe_allow_html=True)
                asset_board("loc", l["id"], l["name"], info, "16:9", 2)

# ===== 03 컷 =====
elif cur == "cut":
    allcuts = work.setdefault("cuts", {})
    n_ep = len(parsed["episodes"])
    done_n = sum(1 for k, v in work.get("eps", {}).items() if v.get("cut") == "done")
    fix_n = sum(1 for k, v in work.get("eps", {}).items() if v.get("cut") == "fix")
    brief("cut", f"분할 {done_n + fix_n} / {n_ep}화" + (f" · 고칠 화 {fix_n}" if fix_n else ""))
    known_c = {c["name"] for c in B["characters"]}
    known_l = {l["id"] for l in B["locations"]}
    castdesc = {c: (work.get("cast", {}).get(c, {}).get("prompt_en", "") or c).split(".")[0] for c in known_c}
    locdesc = {l["id"]: (l["name"], work.get("loc", {}).get(l["id"], {}).get("prompt_en", "") or l.get("desc", "")) for l in B["locations"]}

    def store_cuts(ep_no: int, cuts: list, src: str):
        allcuts[str(ep_no)] = {"cuts": cuts, "src": src, "at": now()}
        iss = cutter.check(cuts, known_c, known_l, [s["no"] for s in parsed["episodes"][ep_no - 1]["scenes"]])
        work.setdefault("eps", {}).setdefault(str(ep_no), {})["cut"] = "fix" if any(i["level"] == "fix" for i in iss) else "done"

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if "cut_ep_next" in st.session_state:
            st.session_state["cut_ep"] = st.session_state.pop("cut_ep_next")
        ep_no = st.number_input("화", 1, n_ep, 1, key="cut_ep")
    ep = parsed["episodes"][ep_no - 1]
    with c2:
        st.write("")
        if st.button("이 화 컷 나누기" if str(ep_no) not in allcuts else "이 화 다시 나누기", type="primary", disabled=not KEYS.get("ANTHROPIC_API_KEY")):
            with st.spinner(f"EP {ep_no} 컷 나누는 중… (20~40초)"):
                r = cutter.split(KEYS["ANTHROPIC_API_KEY"], ep, B, MODEL)
            store_cuts(ep_no, r["cuts"], r["model"])
            save(work)
            st.rerun()
    with c3:
        st.write("")
        todo = [e["ep"] for e in parsed["episodes"] if str(e["ep"]) not in allcuts]
        # 한꺼번에 돌리지 않는다: 버튼 한 번 = 한 화. 감독님이 결과를 보고 다음 화로 넘어간다.
        if todo and st.button(f"다음 화 나누기 (EP {todo[0]})", disabled=not KEYS.get("ANTHROPIC_API_KEY")):
            n = todo[0]
            with st.spinner(f"EP {n} 컷 나누는 중… (20~40초)"):
                r = cutter.split(KEYS["ANTHROPIC_API_KEY"], parsed["episodes"][n - 1], B, MODEL)
            store_cuts(n, r["cuts"], r["model"])
            save(work)
            st.session_state["cut_ep_next"] = n      # 다음 실행에서 이 화를 화면에 띄움
            st.rerun()
    smp = SAMPLES / f"danjjan_ep{ep_no}_cuts.json"
    if parsed.get("title") == "단짠단짠" and smp.exists() and st.button(f"EP {ep_no} 샘플 분할 적용 (Claude 작성본)"):
        store_cuts(ep_no, cutter.normalize(json.loads(smp.read_text("utf-8"))["cuts"], ep, B), "sample")
        save(work)
        st.rerun()

    st.markdown(f"**EP {ep['ep']}** · {ep['emotion']} · <span class='hook'>{ep['hook']}</span>", unsafe_allow_html=True)
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
            st.markdown("<span class='tag ok'>점검 통과</span> 컷 수 · 길이 · 움직임 규칙 · 대사 길이 · 금지어 모두 통과", unsafe_allow_html=True)
        for c in cuts:
            loc = locdesc.get(c["loc"], ("?", ""))[0]
            d = c["dialogue"]
            dl = f"<div class='s dlg'><b>{d['who']}</b>{'' if d.get('on_screen') else ' (화면 밖)'} {d['text']}</div>" if d else ""
            stx = f"<div class='s'>화면 글자: {c['screen_text']}</div>" if c["screen_text"] else ""
            clx = "<span class='tag fix'>클라이맥스</span>" if c["climax"] else ""
            st.markdown(f"<div class='cut'><div class='h'>{c['id']} · {c['size']} · {c['angle']} · {c['camera']}<span class='d'>{c['dur']}s</span> "
                        f"<span class='tag {'mv' if c['motion'] == 'video' else 'ok'}'>{cutter.MOTIONS[c['motion']]}</span>"
                        f"{clx}</div>"
                        f"<div class='a'>{c['action']}</div>{dl}{stx}<div class='s'>{c['loc']} {loc} · 인물 {', '.join(c['chars']) or '없음'}"
                        f"{' · 효과음 ' + c['sfx'] if c['sfx'] else ''}</div></div>", unsafe_allow_html=True)
            with st.expander(f"{c['id']} 지시문 보기"):
                st.markdown("**스틸 지시문** (gpt-image-2, 기준 그림 함께)")
                st.code(cutter.still_prompt(c, castdesc, locdesc), language=None)
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
        st.info("03 컷에서 먼저 컷을 나눈 화가 있어야 합니다.")
        st.stop()
    known_c = {c["name"] for c in B["characters"]}
    castdesc = {c: (work.get("cast", {}).get(c, {}).get("prompt_en", "") or c).split(".")[0] for c in known_c}
    locdesc = {l["id"]: (l["name"], work.get("loc", {}).get(l["id"], {}).get("prompt_en", "") or l.get("desc", "")) for l in B["locations"]}

    def refs_for(c):
        """컷에 넣을 기준 그림: 화면에 나오는 인물(확정 그림) → 장소 마스터. 이름 순서가 지시문의 '기준 그림 n번'."""
        out = []
        for ch in c["chars"]:
            base = ch.split(":")[0]
            k = work.get("cast", {}).get(base, {}).get("pick")
            if k and base not in [n for n, _ in out]:
                out.append((base, k))
        k = work.get("loc", {}).get(c["loc"], {}).get("pick")
        if k:
            out.append((c["loc"], k))
        return out

    def still_state(n):
        cuts = allcuts[str(n)]["cuts"]
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

    def make(targets):
        """targets = [(컷, 지시문, 기준그림)] → 동시에 4장씩 생성, 저장은 이 함수 안(메인 흐름)에서."""
        def one(t):
            c, prompt, refs = t
            try:
                return imagegen.edit(KEYS["OPENAI_API_KEY"], prompt, [(f"{n}.jpg", img_bytes(k)) for n, k in refs],
                                     "9:16", quality, style="cut", model=KEYS.get("IMAGE_MODEL", ""))
            except Exception as ex:
                return ex
        jobs = [t for t in targets for _ in range(n_c)]
        with ThreadPoolExecutor(4) as ex:
            results = list(ex.map(one, jobs))
        for (c, prompt, refs), r in zip(jobs, results):
            if isinstance(r, Exception):
                st.error(f"{c['id']}: {r}")
                continue
            k = f"works/{work['id']}/still/ep{ep_no:03d}/{c['id']}_{uuid.uuid4().hex[:6]}.jpg"
            store.put_bytes(k, r, "image/jpeg")
            cell = rec.setdefault(c["id"], {})
            cell.setdefault("cands", []).append(k)
            cell.setdefault("pick", k)                 # 첫 그림을 일단 확정 → 마음에 안 들면 다시 만들기
            cell["prompt"] = prompt

    def finish():
        cs, rc, pk = still_state(ep_no)
        eps_state.setdefault(str(ep_no), {})["still"] = "done" if pk == len(cs) else "doing"
        save(work)

    with c3:
        st.write("")
        label = f"EP {ep_no} 스틸 만들기 ({len(missing)}컷)" if missing else f"EP {ep_no} 스틸 완료 · {picked}/{len(cuts)}컷 확정"
        if st.button(label, type="primary", disabled=not (KEYS.get("OPENAI_API_KEY") and missing)):
            with st.status(f"EP {ep_no} 스틸 {len(missing) * n_c}장 생성 중… (4장씩 동시, 1~3분)") as s:
                make([(c, cutter.still_prompt(c, castdesc, locdesc, [n for n, _ in refs_for(c)]), refs_for(c)) for c in missing])
                finish()
                s.update(label="생성 완료", state="complete")
            st.rerun()
    st.caption("버튼 한 번에 한 화만 만듭니다. 컷마다 첫 그림이 자동으로 확정되고, 마음에 안 드는 컷만 '이 컷 다시'로 바꾸면 됩니다.")

    st.markdown(f"**EP {ep_no}** · {parsed['episodes'][ep_no - 1]['emotion']} · <span class='hook'>{parsed['episodes'][ep_no - 1]['hook']}</span>", unsafe_allow_html=True)
    cols = st.columns(4)
    for i, c in enumerate(cuts):
        cell = rec.get(c["id"], {})
        refs = refs_for(c)
        with cols[i % 4]:
            st.markdown(f"<div class='cut'><div class='h'>{c['id']} · {c['size']}<span class='d'>{c['dur']}s</span> "
                        f"<span class='tag {'mv' if c['motion'] == 'video' else 'ok'}'>{cutter.MOTIONS[c['motion']]}</span></div>"
                        f"<div class='s'>{c['action']}</div>"
                        f"<div class='s'>기준 그림: {', '.join(n for n, _ in refs) or '없음 (지시문만)'}</div></div>", unsafe_allow_html=True)
            if cell.get("pick"):
                data = img_bytes(cell["pick"])
                if data:
                    st.image(data, width="stretch")
            others = [k for k in cell.get("cands", []) if k != cell.get("pick")]
            if others:
                oc = st.columns(min(3, len(others)))
                for j, k in enumerate(others[-3:]):
                    with oc[j]:
                        d = img_bytes(k)
                        if d:
                            st.image(d, width="stretch")
                        if st.button("이걸로", key=f"spk_{k}"):
                            cell["pick"] = k
                            finish()
                            st.rerun()
            with st.expander("지시문 · 다시 만들기"):
                base_p = cell.get("prompt") or cutter.still_prompt(c, castdesc, locdesc, [n for n, _ in refs])
                p2 = st.text_area("지시문", base_p, key=f"sp_{c['id']}", height=160, label_visibility="collapsed")
                bad = imagegen.banned_in(p2)
                if bad:
                    st.markdown(f'<span class="tag fix">금지어</span> {" · ".join(bad)}', unsafe_allow_html=True)
                if st.button("이 컷 다시", key=f"sre_{c['id']}", disabled=not (KEYS.get("OPENAI_API_KEY") and not bad)):
                    with st.spinner(f"{c['id']} 다시 만드는 중…"):
                        make([(c, p2, refs)])
                        rec[c["id"]]["pick"] = rec[c["id"]]["cands"][-1]
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
        st.info("04 스틸에서 모든 컷 그림이 확정된 화가 있어야 합니다.")
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
        mode = st.selectbox("화질", ["standard", "pro"], format_func=lambda m: {"standard": "720p (기본)", "pro": "1080p (비용 높음)"}[m])
    cuts = allcuts[str(ep_no)]["cuts"]
    rec = clips.setdefault(str(ep_no), {})
    srec = stills.get(str(ep_no), {})
    moving = [c for c in cuts if c["motion"] in ("move", "video")]
    missing = [c for c in moving if not rec.get(c["id"], {}).get("key")]
    running = {cid: r["get"] for cid, r in rec.items() if r.get("get") and not r.get("key") and r.get("status") not in videogen.DONE}

    def finish():
        ok = all(rec.get(c["id"], {}).get("key") for c in moving)
        eps_state.setdefault(str(ep_no), {})["clip"] = "done" if ok else "doing"
        save(work)

    def collect(jobs, box):
        """진행 중인 예측을 끝까지 기다렸다가 영상을 저장소에 넣는다. 창을 닫아도 '결과 불러오기'로 이어 받을 수 있다."""
        def tick(res):
            n = sum(1 for r in res.values() if r.get("status") in videogen.DONE)
            box.update(label=f"영상 {n}/{len(jobs)}개 완료 (컷마다 1~5분)")
        res = videogen.wait_all(TOKEN, jobs, on_tick=tick)
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
            elif r.get("status") in ("failed", "canceled"):
                cell["error"] = str(r.get("error"))[:300]
        finish()

    def launch(targets):
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
            rec[c["id"]] = {**{k: v for k, v in rec.get(c["id"], {}).items() if k == "takes"},
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
    st.caption(f"모델 {VMODEL} · 확정 스틸을 첫 프레임으로 씁니다. '짧은 움직임'과 '완전 영상' 컷만 만들고, "
               "'정지+카메라' 컷은 편집 단계에서 스틸에 카메라 움직임을 넣습니다. 버튼 한 번에 한 화만 진행합니다.")

    cols = st.columns(4)
    for i, c in enumerate(cuts):
        cell = rec.get(c["id"], {})
        with cols[i % 4]:
            st.markdown(f"<div class='cut'><div class='h'>{c['id']} · {c['size']}<span class='d'>{c['dur']}s</span> "
                        f"<span class='tag {'mv' if c['motion'] == 'video' else 'ok'}'>{cutter.MOTIONS[c['motion']]}</span></div>"
                        f"<div class='s'>{c['action']}</div></div>", unsafe_allow_html=True)
            if c["motion"] == "still":
                d = img_bytes(srec.get(c["id"], {}).get("pick", "")) if srec.get(c["id"], {}).get("pick") else None
                if d:
                    st.image(d, width="stretch")
                st.caption("편집에서 카메라 움직임만 넣습니다")
                continue
            if cell.get("key"):
                v = img_bytes(cell["key"])
                if v:
                    st.video(v)
            elif cell.get("status") and cell["status"] not in videogen.DONE:
                st.markdown('<span class="tag todo">생성 중</span>', unsafe_allow_html=True)
            elif cell.get("error"):
                st.markdown(f'<span class="tag fix">실패</span> <span class="small">{cell["error"]}</span>', unsafe_allow_html=True)
            takes = [k for k in cell.get("takes", []) if k != cell.get("key")]
            for k in takes[-2:]:
                if st.button("이전 테이크로", key=f"vtk_{k}"):
                    cell["key"] = k
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

# ===== 06 이후 =====
else:
    brief(cur, "다음 버전")
    st.info("지금 버전은 대본 · 작품 정리 · 캐스팅 · 컷 분할 · 스틸 · 영상까지입니다. 다음: 06 더빙 → 07 자막·사운드 → 08 편집 → 09 마스터.")

# ───────── 화면 맨 아래: 다음 할 일 안내 ─────────
st.divider()
_p = progress(work)
st.markdown(f"<div class='small'>다음 할 일 · <b>{_p['next']}</b></div>", unsafe_allow_html=True)
go_bar(_p, key="go_next_bottom")
