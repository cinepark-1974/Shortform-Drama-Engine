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

from src import bible as bb
from src import cutter, imagegen, profiles, script_parser
from src.store import Store, secrets_dict

VERSION = "v0.2"
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
def img_bytes(key: str):
    return store.get_bytes(key)


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
    idx = 0
    for i, w in enumerate(works, start=1):
        if w["id"] == st.session_state.get("wid"):
            idx = i
    sel = st.selectbox("작품 선택", labels, index=idx, label_visibility="collapsed")
    st.session_state["wid"] = None if sel == "＋ 새 작품" else sel.rsplit("·", 1)[-1].strip()
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
            for i in B["issues"]:
                st.markdown(f"<div class='issue'><b>EP {i.get('eps','')} · {i.get('type','')}</b><br>{i.get('what','')}"
                            f"<br><span class='small'>제안: {i.get('suggest','')} · 엔진 처리: {i.get('applied','')}</span></div>", unsafe_allow_html=True)
            a, b2 = st.columns(2)
            with a:
                st.markdown(f"#### 인물 {len(B['characters'])}명")
                st.dataframe([{"이름": c["name"], "표기": ", ".join(c.get("aliases", [])), "대사": stt["lines"].get(c["name"], 0),
                               "역할": c.get("role", ""), "나이": c.get("age", "")} for c in sorted(B["characters"], key=lambda c: -stt["lines"].get(c["name"], 0))],
                             hide_index=True, use_container_width=True)
            with b2:
                st.markdown(f"#### 장소 세트 {len(B['locations'])}곳 <span class='small'>장면 머리 {len(summ['places'])}가지 → 세트 {len(B['locations'])}곳</span>", unsafe_allow_html=True)
                st.dataframe([{"id": l["id"], "세트": l["name"], "장면": stt["loc"].get(l["id"], 0), "공간": l.get("desc", "")}
                              for l in sorted(B["locations"], key=lambda l: -stt["loc"].get(l["id"], 0))], hide_index=True, use_container_width=True)

    with t_board:
        eps = work.get("eps", {})
        cells = ""
        for e in parsed["episodes"]:
            s = eps.get(str(e["ep"]), {})
            cls = "done" if s.get("master") == "done" else ("fix" if s.get("cut") == "fix" else ("doing" if s else ""))
            cells += f'<div class="cell {cls}" title="{e["hook"]}">{e["ep"]}</div>'
        st.markdown(f'<div class="grid">{cells}</div>', unsafe_allow_html=True)
        st.caption("남색: 업로드 완료 · 하늘색: 제작 중 · 빨강: 고칠 컷 있음 · 흰색: 대기. 칸에 마우스를 올리면 훅 자막이 보입니다.")

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
    brief("cast", f"확정 {a} / {b}" + (" · 캐스팅 완료" if b and a >= b else ""))
    t_char, t_loc = st.tabs(["인물", "장소 (마스터)"])
    stt = bb.stats(B, parsed)

    def gen_many(prompts, aspect):
        def one(p):
            try:
                return imagegen.generate(KEYS["OPENAI_API_KEY"], p, aspect, quality)
            except Exception as ex:
                return ex
        with ThreadPoolExecutor(4) as ex:
            return list(ex.map(one, prompts))

    def asset_board(kind, key, label, info, aspect, n_cand):
        base = f"works/{work['id']}/{kind}/{slug(key)}"
        prompt = st.text_area("이미지 지시문 (영어, 확정형)", info.get("prompt_en", ""), key=f"p_{kind}_{key}", height=110)
        bad = imagegen.banned_in(prompt)
        if bad:
            st.markdown(f'<span class="tag fix">금지어</span> {" · ".join(bad)}', unsafe_allow_html=True)
        if prompt != info.get("prompt_en", ""):
            info["prompt_en"] = prompt
            save(work)
        c1, c2 = st.columns([1, 2])
        with c1:
            go = st.button(f"후보 {n_cand}장 만들기", key=f"g_{kind}_{key}", disabled=not (KEYS.get("OPENAI_API_KEY") and prompt and not bad))
        with c2:
            upf = st.file_uploader("직접 올리기", type=["png", "jpg", "jpeg", "webp"], key=f"u_{kind}_{key}", label_visibility="collapsed")
        if go:
            with st.status(f"{label} 후보 {n_cand}장 생성 중… (장당 30초~1분)") as s:
                for r in gen_many([prompt] * n_cand, aspect):
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
                        st.image(data, use_container_width=True)
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
            for c in d.get("characters", []):
                if c.get("name") in chars:
                    work.setdefault("cast", {}).setdefault(c["name"], {}).update(c)
            save(work)
            st.rerun()
        roles = {c["name"]: c for c in B["characters"]}
        for c in chars:
            info = work.setdefault("cast", {}).setdefault(c, {})
            with st.expander(f"{'✓ ' if info.get('pick') else ''}{c} · 대사 {stt['lines'].get(c, 0)}줄 · {roles.get(c, {}).get('role', '')[:40]}", expanded=not info.get("pick")):
                if info.get("look_ko") or info.get("outfit_ko"):
                    st.markdown(f"<div class='small'>{info.get('age','')} · 외모: {info.get('look_ko','')}<br>의상: {info.get('outfit_ko','')}</div>", unsafe_allow_html=True)
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
                slugs = {l["name"]: [f"EP{e['ep']} {s['slug']}" for e in parsed["episodes"] for s in e["scenes"]
                                     if B["scene_loc"].get(f"{e['ep']}-{s['no']}") == l["id"]][:5] for l in need}
                d = profiles.draft(KEYS["ANTHROPIC_API_KEY"], parsed, [], slugs, MODEL, B)
            byname = {l["name"]: l["id"] for l in need}
            for l in d.get("locations", []):
                if l.get("name") in byname:
                    work.setdefault("loc", {}).setdefault(byname[l["name"]], {}).update(l)
            save(work)
            st.rerun()
        st.caption("장소마다 넓은 마스터 1장을 확정합니다. 같은 장소의 모든 컷은 이 마스터에서 만듭니다.")
        for l in locs:
            info = work.setdefault("loc", {}).setdefault(l["id"], {})
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
        iss = cutter.check(cuts, known_c, known_l)
        work.setdefault("eps", {}).setdefault(str(ep_no), {})["cut"] = "fix" if any(i["level"] == "fix" for i in iss) else "done"

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
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
        if st.button(f"남은 {len(todo)}화 전부 자동 분할", disabled=not (KEYS.get("ANTHROPIC_API_KEY") and todo)):
            bar = st.progress(0.0, text="시작")
            for i, n in enumerate(todo, start=1):
                try:
                    r = cutter.split(KEYS["ANTHROPIC_API_KEY"], parsed["episodes"][n - 1], B, MODEL)
                    store_cuts(n, r["cuts"], r["model"])
                    save(work)                          # 화마다 저장 → 중간에 끊겨도 이어서
                except Exception as ex:
                    st.error(f"EP {n}: {ex}")
                bar.progress(i / len(todo), text=f"EP {n} 완료 ({i}/{len(todo)})")
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
        iss = cutter.check(cuts, known_c, known_l)
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

# ===== 04 이후 =====
else:
    brief(cur, "다음 버전")
    st.info("v0.2 는 대본 · 작품 정리 · 캐스팅 · 회당 컷 분할까지입니다. 다음 버전: 04 스틸 → 05 영상 → 06 더빙 → 07 자막·사운드 → 08 편집 → 09 마스터.")
