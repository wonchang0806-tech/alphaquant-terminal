import json
import os
from datetime import datetime
import FinanceDataReader as fdr
import pandas as pd
import streamlit as st
import yfinance as yf

import config
import agents
import wallstreet_analytics as ws
from auth import check_login, render_sidebar_auth_and_kis
from styles import apply_custom_styles
from chart_builder import create_sweet_spot_matrix, create_pro_candlestick_chart
from portfolio_manager import render_portfolio_and_radar_tab, scan_buy_timing_signals
from data_loader import (
    calculate_scores,
    fetch_market_data_parallel,
    fetch_intraday_chart,
    fetch_partner_news,
    fetch_quarterly_detailed_matrix,
    fetch_stock_news,
    fetch_stock_reports_and_consensus,
    find_krx_stock,
    scan_krx_wide_tenbaggers,
)

# 1. 페이지 기본 설정 및 오토핏 반응형 테마 적용
st.set_page_config(
    page_title="AlphaQuant Terminal | 독자 퀀트 밸류에이션 & AI 에이전트",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)
apply_custom_styles()

# 2. 로그인 인증 게이트 (미로그인 시 여기서 차단)
if not check_login():
    st.stop()

user_role = st.session_state.get("user_role", "guest")
is_admin = (user_role == "admin")

# 사이드바 인증 상태 + 선택형 한투(KIS) API 키 연동
kis_client_instance = render_sidebar_auth_and_kis()
st.sidebar.markdown("---")

# 3. 영구 저장소 (추가 종목 & 제외 종목 관리)
CUSTOM_STOCKS_FILE = "custom_stocks.json"
EXCLUDED_STOCKS_FILE = "excluded_stocks.json"

def load_json_data(file_path, default_val):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_val

def save_json_data(file_path, data):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

if "custom_stocks" not in st.session_state:
    st.session_state.custom_stocks = load_json_data(CUSTOM_STOCKS_FILE, {"국내 주식 (KRX)": [], "해외 주식 (미국)": []})
if "excluded_tickers" not in st.session_state:
    st.session_state.excluded_tickers = load_json_data(EXCLUDED_STOCKS_FILE, {"국내 주식 (KRX)": [], "해외 주식 (미국)": []})

# 4. 사이드바 제어판
preset_weights = {
    "⚖️ 피터 린치 GARP (추천 기본값)": (25, 40, 25, 10),
    "🛡️ 워런 버핏 퀄리티 밸류 (ROE 중심)": (35, 15, 40, 10),
    "🚀 고성장 모멘텀 (저PEG 주도주)": (10, 55, 25, 10),
    "💎 딥밸류 (절대 저PER 안전마진)": (60, 15, 15, 10),
    "🎛️ 사용자 직접 설정": None,
}

if "preset_select" not in st.session_state:
    st.session_state.preset_select = "⚖️ 피터 린치 GARP (추천 기본값)"
    st.session_state.slider_per, st.session_state.slider_peg, st.session_state.slider_roe, st.session_state.slider_eps = 25, 40, 25, 10

def on_preset_change():
    chosen = st.session_state.preset_select
    if chosen in preset_weights and preset_weights[chosen] is not None:
        st.session_state.slider_per, st.session_state.slider_peg, st.session_state.slider_roe, st.session_state.slider_eps = preset_weights[chosen]

st.sidebar.markdown("### ⚙️ 퀀트 컨트롤 센터")
selected_market = st.sidebar.radio("분석 시장 선택", ["국내 주식 (KRX)", "해외 주식 (미국)"], key="selected_market_radio")

if selected_market == "국내 주식 (KRX)":
    if kis_client_instance and getattr(kis_client_instance, "access_token", None):
        st.sidebar.success("🟢 한국투자증권(KIS) 실시간 API 가동 중")
    else:
        st.sidebar.info("⚡ 네이버 증권 실시간 모드 가동 중")

st.sidebar.markdown("---")
st.sidebar.subheader("🏆 랭킹 가중치 전략")
st.sidebar.selectbox("검증된 퀀트 프리셋", list(preset_weights.keys()), key="preset_select", on_change=on_preset_change)
w_per = st.sidebar.slider("저PER 가중치", 0, 100, key="slider_per")
w_peg = st.sidebar.slider("저PEG 가중치", 0, 100, key="slider_peg")
w_roe = st.sidebar.slider("고ROE 가중치", 0, 100, key="slider_roe")
w_eps = st.sidebar.slider("EPS 성장률 가중치", 0, 100, key="slider_eps")

st.sidebar.markdown("---")
st.sidebar.subheader("💎 독자 퀀트 미래주가 모델")
val_model = st.sidebar.selectbox(
    "적정 Target PER 산출 모델",
    [
        "🚀 피터 린치 성장가치 모델 (Target PER = EPS성장률)",
        "🏢 동일업종 평균 PER 모델 (업종 평균 회귀)",
        "🛡️ 보수적 가치투자 모델 (안전마진 PER 15배)",
        "🎯 타깃 PER 직접 지정 (사용자 설정)"
    ],
    key="val_model_select"
)
custom_target_per = st.sidebar.slider("적용할 목표 PER (배)", 5.0, 60.0, 20.0, 0.5, key="slider_custom_target_per") if "타깃 PER 직접 지정" in val_model else 20.0

excluded_now = st.session_state.excluded_tickers.get(selected_market, [])
all_market_candidates = config.DEFAULT_STOCKS[selected_market] + st.session_state.custom_stocks[selected_market]

# 종목 영구 추가/복원은 관리자(admin) 권한만 노출
if is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("➕ 종목 추가 (영구 저장)")
    if selected_market == "국내 주식 (KRX)":
        search_input = st.sidebar.text_input("종목명/코드 검색", placeholder="예: 서진시스템, 한화비전...", key="krx_search_box")
        matched_candidates = find_krx_stock(search_input) if search_input else []
        if matched_candidates:
            cand_labels = [f"{c['name']} ({c['ticker']}) - {c['market']}" for c in matched_candidates]
            selected_cand_idx = st.sidebar.selectbox("검색 결과 선택", range(len(cand_labels)), format_func=lambda i: cand_labels[i])
            target_cand = matched_candidates[selected_cand_idx]
            if st.sidebar.button(f"📌 '{target_cand['name']}' 추가", use_container_width=True, type="primary"):
                c_code = target_cand["ticker"]
                current_tickers = [x["ticker"] for x in config.DEFAULT_STOCKS[selected_market] + st.session_state.custom_stocks[selected_market]]
                if c_code not in current_tickers:
                    st.session_state.custom_stocks[selected_market].append({"name": target_cand["name"], "ticker": c_code})
                    save_json_data(CUSTOM_STOCKS_FILE, st.session_state.custom_stocks)
                    if c_code in st.session_state.excluded_tickers[selected_market]:
                        st.session_state.excluded_tickers[selected_market].remove(c_code)
                        save_json_data(EXCLUDED_STOCKS_FILE, st.session_state.excluded_tickers)
                    st.sidebar.success(f"{target_cand['name']} 등록 완료!")
                    st.rerun()
    else:
        us_name = st.sidebar.text_input("미국 종목명", placeholder="예: Coinbase", key="us_in_name")
        us_ticker = st.sidebar.text_input("미국 티커", placeholder="예: COIN", key="us_in_ticker")
        if st.sidebar.button("📌 미국 종목 영구 추가", use_container_width=True, type="primary"):
            if us_name and us_ticker:
                st.session_state.custom_stocks[selected_market].append({"name": us_name.strip(), "ticker": us_ticker.strip().upper()})
                save_json_data(CUSTOM_STOCKS_FILE, st.session_state.custom_stocks)
                st.rerun()

    if excluded_now:
        st.sidebar.markdown("---")
        st.sidebar.subheader(f"♻️ 제외된 종목 복원 ({len(excluded_now)}개)")
        for ex_code in excluded_now:
            matching = [x for x in all_market_candidates if x["ticker"] == ex_code]
            ex_name = matching[0]["name"] if matching else ex_code
            c_nm, c_rst = st.sidebar.columns([3, 1.2])
            with c_nm: st.caption(f"<s>{ex_name} ({ex_code})</s>", unsafe_allow_html=True)
            with c_rst:
                if st.button("복원", key=f"rst_{selected_market}_{ex_code}", use_container_width=True):
                    st.session_state.excluded_tickers[selected_market].remove(ex_code)
                    save_json_data(EXCLUDED_STOCKS_FILE, st.session_state.excluded_tickers)
                    st.rerun()

# 5. 초고속 데이터 병렬 동기화 & 독자 퀀트 적정가 계산
active_candidates = [item for item in all_market_candidates if item["ticker"] not in excluded_now]

@st.cache_data(ttl=120, show_spinner=False)
def load_fast_data(market, stock_list, _kis_client=None):
    return fetch_market_data_parallel(market, stock_list, _kis_client)

now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

with st.spinner("⚡ 실시간 시세 및 재무제표를 동기화 중입니다..."):
    raw_df = load_fast_data(selected_market, active_candidates, kis_client_instance)
    df_calc = calculate_scores(raw_df, w_per, w_peg, w_roe, w_eps)

    is_kis_active = bool(kis_client_instance and getattr(kis_client_instance, "access_token", None) and selected_market == "국내 주식 (KRX)")
    src_label = "🟢 KIS 실시간" if is_kis_active else ("⚡ 네이버실시간" if selected_market == "국내 주식 (KRX)" else "🌎 Yahoo실시간")

    target_pers, per_reasons, quant_fair_prices, price_diffs, upsides = [], [], [], [], []
    for _, r in df_calc.iterrows():
        p, f_eps, ttm_eps, mrq_eps = r.get("현재가"), r.get("미래 예상 EPS"), r.get("올해누적 EPS(TTM)"), r.get("최근분기 EPS(MRQ)")
        g, ind_pe = r.get("EPS 성장률(%)"), r.get("업종 PER")

        if "피터 린치" in val_model:
            if g is not None and pd.notnull(g) and g > 0:
                t_pe = 35.0 if g > 35.0 else (10.0 if g < 10.0 else round(g, 1))
                reason = f"고성장({g:+.0f}%) 상한캡 35배" if g > 35.0 else (f"저성장({g:+.0f}%) 하한선 10배" if g < 10.0 else f"PEG 1.0 (성장률 {g:+.1f}% 연동)")
            else:
                t_pe, reason = 12.0, "이익감소(역성장) 방어 12배"
        elif "동일업종" in val_model:
            t_pe = round(float(ind_pe), 1) if (ind_pe and pd.notnull(ind_pe) and ind_pe > 0) else 18.0
            reason = f"업종평균 PER({t_pe}배) 회귀" if (ind_pe and pd.notnull(ind_pe) and ind_pe > 0) else "시장평균 기본 18배"
        elif "보수적" in val_model:
            t_pe, reason = 15.0, "그레이엄 안전마진 15배"
        else:
            t_pe, reason = float(custom_target_per), f"사용자 지정 {float(custom_target_per)}배"

        target_pers.append(t_pe)
        per_reasons.append(reason)

        eval_eps = f_eps if (f_eps and pd.notnull(f_eps) and f_eps > 0) else (
            round(mrq_eps * 4.0 * 0.95, 2) if (mrq_eps and pd.notnull(mrq_eps) and mrq_eps > 0) else (
                ttm_eps if (ttm_eps and pd.notnull(ttm_eps) and ttm_eps > 0) else (round(p / t_pe, 2) if (p and t_pe > 0) else None)
            )
        )
        fair_p = round(t_pe * eval_eps, 0 if selected_market == "국내 주식 (KRX)" else 2) if (eval_eps and eval_eps > 0) else p
        quant_fair_prices.append(fair_p)

        diff = round(fair_p - p, 0 if selected_market == "국내 주식 (KRX)" else 2) if (p and pd.notnull(p) and p > 0 and fair_p) else 0.0
        up = round((diff / p) * 100.0, 1) if (p and pd.notnull(p) and p > 0 and fair_p) else 0.0
        price_diffs.append(diff)
        upsides.append(up)

    df_calc["적용 Target PER"], df_calc["Target PER 근거"], df_calc["자체 퀀트 적정가"] = target_pers, per_reasons, quant_fair_prices
    df_calc["괴리금액 (차이)"], df_calc["괴리율 (상승여력%)"] = price_diffs, upsides
    df = df_calc.reset_index(drop=True)

curr_mark = "₩" if selected_market == "국내 주식 (KRX)" else "$"
buy_signals = scan_buy_timing_signals(df)

# 6. 오토핏 반응형 상단 배너 & 4대 KPI 카드
col_h1, col_h2 = st.columns([4.5, 1])
with col_h1:
    sig_badge = f"<span style='background:rgba(16,185,129,0.22); border:1px solid #10b981; color:#34d399; padding:3px 10px; border-radius:999px; font-size:0.76rem; font-weight:800; margin-left:6px;'>🎯 매수 타점 포착 {len(buy_signals)}종목</span>" if buy_signals else ""
    st.markdown(f"""
    <div class='hero-container'>
        <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>
            <div><span class='hero-badge'>⚡ ALPHAQUANT ENGINE v7.5 PRO</span>{sig_badge}</div>
            <span style='color:#94a3b8; font-size:0.82rem; font-weight:600;'>실시간 동기화: <b style='color:#38bdf8;'>{now_str}</b></span>
        </div>
        <div class='hero-title'>🚀 퀀트 밸류에이션 · 독자 적정주가 · AI 에이전트 터미널</div>
        <div class='hero-subtitle'>기업 순수 실적·성장률·ROE, 연관 밸류체인 리스크 및 포트폴리오 밸런스를 입체 분석합니다.</div>
    </div>
    """, unsafe_allow_html=True)
with col_h2:
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 실시간 시세 재조회", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

avg_per = df["PER (배)"].dropna().mean() if not df["PER (배)"].dropna().empty else 0.0
avg_roe = df["ROE (%)"].dropna().mean() if not df["ROE (%)"].dropna().empty else 0.0
sweet_df = df[(df["PEG (배)"] > 0) & (df["PEG (배)"] < 1.0)]
top_stock = df.sort_values(by="종합 스코어", ascending=False).iloc[0] if not df.empty else None
top_name = top_stock['종목명'] if top_stock is not None else '-'
top_score = top_stock['종합 스코어'] if top_stock is not None else 0.0

st.markdown(f"""
<div class='kpi-auto-grid'>
    <div class='kpi-card'><div class='kpi-label'><span>분석 유니버스</span><span>🌐</span></div><div class='kpi-val'>{len(df):,} 종목</div><div class='kpi-sub'>✓ {src_label} 연동 중</div></div>
    <div class='kpi-card'><div class='kpi-label'><span>시장 평균 PER / ROE</span><span>📊</span></div><div class='kpi-val'>{avg_per:.1f}배 <span style='font-size:1.1rem;color:#38bdf8;'>({avg_roe:.1f}%)</span></div><div class='kpi-sub'>TTM 실적 및 자본 효율성</div></div>
    <div class='kpi-card'><div class='kpi-label'><span>Sweet Spot / 매수타점</span><span>🎯</span></div><div class='kpi-val' style='color:#34d399;'>{len(sweet_df):,} / {len(buy_signals):,}</div><div class='kpi-sub'>PEG&lt;1.0 / 3박자 타점 충족</div></div>
    <div class='kpi-card'><div class='kpi-label'><span>종합 1위 주도주</span><span>👑</span></div><div class='kpi-val' style='color:#a855f7;'>{top_score:.1f}점</div><div class='kpi-sub'>🔥 <b>{top_name}</b> (가중치 최우수)</div></div>
</div>
""", unsafe_allow_html=True)

# 7. 권한별 탭 구성 (admin은 개인 포트폴리오 포함, guest는 개인 자산 비공개)
tab_options = ["📋 종합 랭킹 & 괴리율 비교표"]
if is_admin:
    tab_options.append("💼 내 포트폴리오 & 매수 타점 레이더")
tab_options.extend([
    "🤖 AI 4대 에이전트 투자심의위원회",
    "🏛️ 월스트리트 IB 5대 프로 밸류에이션",
    "📊 분기별 실적 추이 (25년~26년)",
    "📰 증권사 리포트 & 실시간 뉴스",
    "🎯 4사분면 밸류에이션 매트릭스",
    "📈 트렌디 실시간 인터랙티브 차트 (Pro)"
])

if "nav_tab_radio" not in st.session_state or st.session_state.nav_tab_radio not in tab_options:
    st.session_state.nav_tab_radio = tab_options[0]

def jump_to_tab_with_stock(target_tab: str, stock_name: str):
    if target_tab in tab_options:
        st.session_state.nav_tab_radio = target_tab
        st.session_state.shared_selected_stock = stock_name

current_tab = st.radio("메뉴 탭 이동", tab_options, horizontal=True, label_visibility="collapsed", key="nav_tab_radio")

def smart_stock_selector(label_prefix: str, key_suffix: str):
    all_names = df["종목명"].tolist()
    default_idx = all_names.index(st.session_state.shared_selected_stock) if ("shared_selected_stock" in st.session_state and st.session_state.shared_selected_stock in all_names) else 0
    c_search, c_pick = st.columns([1.6, 2.4])
    with c_search:
        kw = st.text_input(f"🔍 {label_prefix} 검색", placeholder="종목명 입력...", key=f"kw_{key_suffix}")
    filtered = df[df["종목명"].str.upper().str.contains(kw.strip().upper(), na=False) | df["티커"].str.upper().str.contains(kw.strip().upper(), na=False)]["종목명"].tolist() if kw else all_names
    if not filtered: filtered = all_names
    idx_to_use = default_idx if (not kw and default_idx < len(filtered)) else 0
    with c_pick:
        chosen = st.selectbox(f"📌 {label_prefix} 선택 ({len(filtered)}개)", filtered, index=idx_to_use, key=f"sel_{key_suffix}")
    st.session_state.shared_selected_stock = chosen
    return chosen

# ---------------------------------------------------------
# TAB 1: 종합 랭킹 & CSV 저장 (삭제는 관리자 전용)
# ---------------------------------------------------------
if current_tab == "📋 종합 랭킹 & 괴리율 비교표":
    col_t1, col_t2, col_t3 = st.columns([1.8, 1.2, 1.0])
    with col_t1:
        search_query = st.text_input("🔍 표 내 종목 실시간 검색", placeholder="종목명 입력...", key="tbl_search")
    with col_t2:
        sort_key = st.selectbox("정렬 기준 선택", ["🏆 종합 스코어 순 (추천)", "🚀 괴리율 / 예상 상승여력 순 (자체 저평가)", "🎯 저PEG 순 (성장 대비 저평가)", "🔻 저PER 순 (절대 저평가)", "🔥 고ROE 순 (자본수익성)"])

    sort_map = {
        "🏆 종합 스코어 순 (추천)": ("종합 스코어", False),
        "🚀 괴리율 / 예상 상승여력 순 (자체 저평가)": ("괴리율 (상승여력%)", False),
        "🎯 저PEG 순 (성장 대비 저평가)": ("PEG (배)", True),
        "🔻 저PER 순 (절대 저평가)": ("PER (배)", True),
        "🔥 고ROE 순 (자본수익성)": ("ROE (%)", False),
    }
    scol, sasc = sort_map.get(sort_key, ("종합 스코어", False))
    display_df = df[df["종목명"].str.upper().str.contains(search_query.strip().upper(), na=False) | df["티커"].str.upper().str.contains(search_query.strip().upper(), na=False)] if search_query else df.copy()
    df_sorted = display_df.sort_values(by=scol, ascending=sasc).reset_index(drop=True)

    with col_t3:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        csv_bytes = df_sorted.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 퀀트 투자일지 CSV 저장",
            data=csv_bytes,
            file_name=f"AlphaQuant_Report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    clean_cols = [c for c in ["종목명", "티커", "업종명", "현재가", "자체 퀀트 적정가", "괴리금액 (차이)", "괴리율 (상승여력%)", "적용 Target PER", "Target PER 근거", "PER (배)", "PEG (배)", "ROE (%)", "종합 스코어"] if c in df_sorted.columns]
    view_df = df_sorted[clean_cols].copy()

    fmt_curr = lambda v: "-" if pd.isnull(v) else (f"{v:,.0f}원" if curr_mark == "₩" else f"${v:,.2f}")
    fmt_diff = lambda v: "-" if pd.isnull(v) else (f"{'+' if v > 0 else ''}{v:,.0f}원" if curr_mark == "₩" else f"{'+' if v > 0 else ''}${v:,.2f}")

    view_df["현재가"] = view_df["현재가"].apply(fmt_curr)
    view_df["자체 퀀트 적정가"] = view_df["자체 퀀트 적정가"].apply(fmt_curr)
    view_df["괴리금액 (차이)"] = view_df["괴리금액 (차이)"].apply(fmt_diff)
    view_df["괴리율 (상승여력%)"] = view_df["괴리율 (상승여력%)"].apply(lambda x: f"{x:+.1f}%" if pd.notnull(x) else "-")
    view_df["적용 Target PER"] = view_df["적용 Target PER"].apply(lambda x: f"{x:.1f}배" if pd.notnull(x) else "-")
    view_df["PER (배)"] = view_df["PER (배)"].apply(lambda x: f"{x:.2f}배" if pd.notnull(x) else "-")
    view_df["PEG (배)"] = view_df["PEG (배)"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-")
    view_df["ROE (%)"] = view_df["ROE (%)"].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "-")

    if is_admin:
        st.caption("💡 **표의 행 맨 앞 체크박스**를 선택하면 아래에 **'선택한 종목 삭제'** 버튼이 활성화됩니다.")
        event = st.dataframe(view_df, column_config={"종합 스코어": st.column_config.ProgressColumn("종합 스코어", min_value=0, max_value=100, format="%.1f점")}, use_container_width=True, height=520, on_select="rerun", selection_mode="multi-row")
        selected_rows = event.selection.rows if event and hasattr(event, "selection") else []
        if selected_rows:
            sel_ticks = [df_sorted.iloc[i]["티커"] for i in selected_rows]
            sel_names = [df_sorted.iloc[i]["종목명"] for i in selected_rows]
            c_a1, c_a2 = st.columns([3, 1])
            with c_a1: st.info(f"선택된 종목 ({len(sel_names)}개): **{', '.join(sel_names)}**")
            with c_a2:
                if st.button(f"🗑️ 선택한 {len(sel_names)}개 삭제", type="primary", use_container_width=True):
                    for tick in sel_ticks:
                        st.session_state.custom_stocks[selected_market] = [x for x in st.session_state.custom_stocks[selected_market] if x["ticker"] != tick]
                        if tick not in st.session_state.excluded_tickers[selected_market]: st.session_state.excluded_tickers[selected_market].append(tick)
                    save_json_data(CUSTOM_STOCKS_FILE, st.session_state.custom_stocks)
                    save_json_data(EXCLUDED_STOCKS_FILE, st.session_state.excluded_tickers)
                    st.rerun()
    else:
        st.dataframe(view_df, column_config={"종합 스코어": st.column_config.ProgressColumn("종합 스코어", min_value=0, max_value=100, format="%.1f점")}, use_container_width=True, height=520)

# ---------------------------------------------------------
# TAB 2: 내 포트폴리오 & 매수 타점 레이더 (Admin 전용)
# ---------------------------------------------------------
elif current_tab == "💼 내 포트폴리오 & 매수 타점 레이더":
    render_portfolio_and_radar_tab(df, selected_market, curr_mark, jump_to_tab_with_stock)

# ---------------------------------------------------------
# TAB 3: AI 4대 에이전트 투자심의위원회
# ---------------------------------------------------------
elif current_tab == "🤖 AI 4대 에이전트 투자심의위원회":
    st.markdown("### 🤖 AI 4대 에이전트 투자심의위원회 (Multi-Agent Committee)")
    if not df.empty:
        ag_target = smart_stock_selector("AI 심의 종목", "ag_tab")
        row_ag = df[df["종목명"] == ag_target].iloc[0]

        with st.spinner(f"🤖 {ag_target} 뉴스 텍스트 기반 연관 이슈 자동 추출 및 심의 중..."):
            n_ag = fetch_stock_news(selected_market, row_ag["티커"])
            vc_meta = agents.extract_dynamic_partners_from_news(row_ag, n_ag)
            p_news = fetch_partner_news(vc_meta["tickers"]) if vc_meta["tickers"] else []
            cns_ag = fetch_stock_reports_and_consensus(selected_market, row_ag["티커"], row_ag["현재가"])
            res_ag = agents.evaluate_stock_with_agents(row_ag, n_ag, cns_ag, partner_news=p_news)

        cio_ag = res_ag["cio"]
        cur_p, bear_p, base_p, bull_p = row_ag["현재가"] or 0, cio_ag["bear_target"], cio_ag["base_target"], cio_ag["bull_target"]
        fmt_p = lambda v: "-" if pd.isnull(v) else (f"{curr_mark}{v:,.0f}" if selected_market == "국내 주식 (KRX)" else f"{curr_mark}{v:,.2f}")
        pct_of = lambda t: (((t - cur_p) / cur_p) * 100.0) if (cur_p > 0 and t) else 0.0

        st.caption(f"🔗 **실시간 뉴스 자동 추출 연관 맥락:** {vc_meta['relation_desc']}")

        st.markdown(f"""
        <div style='background:linear-gradient(135deg, rgba(30,41,59,0.95), rgba(15,23,42,0.98)); border:2px solid {cio_ag["color"]}; border-radius:16px; padding:20px 24px; margin-bottom:16px;'>
            <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>
                <div>
                    <span style='background:rgba(255,255,255,0.08); color:#cbd5e1; padding:4px 10px; border-radius:999px; font-size:0.75rem; font-weight:700;'>⚖️ CIO 최종 판정 · {ag_target} ({row_ag["티커"]})</span>
                    <div style='font-size:1.55rem; font-weight:900; color:{cio_ag["color"]}; margin-top:6px;'>{cio_ag["verdict"]}</div>
                </div>
                <div style='text-align:right;'>
                    <div style='font-size:0.78rem; color:#94a3b8;'>심의 종합 점수</div>
                    <div style='font-size:2.0rem; font-weight:900; color:#ffffff;'>{cio_ag["score"]}점</div>
                </div>
            </div>
            <p style='color:#e2e8f0; font-size:0.9rem; margin:12px 0 14px 0; line-height:1.55;'>{cio_ag["summary"]}</p>
            <div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(165px, 1fr)); gap:10px;'>
                <div style='background:rgba(15,23,42,0.85); border:1px solid rgba(148,163,184,0.3); border-radius:12px; padding:12px; text-align:center;'>
                    <div style='font-size:0.78rem; color:#94a3b8; font-weight:700;'>📌 현재가</div>
                    <div style='font-size:1.35rem; font-weight:900; color:#ffffff; margin-top:4px;'>{fmt_p(cur_p)}</div>
                </div>
                <div style='background:rgba(244,63,94,0.08); border:1px solid rgba(244,63,94,0.35); border-radius:12px; padding:12px; text-align:center;'>
                    <div style='font-size:0.78rem; color:#fda4af; font-weight:700;'>🛡️ 하락 지지선</div>
                    <div style='font-size:1.35rem; font-weight:900; color:#f43f5e; margin-top:4px;'>{fmt_p(bear_p)}</div>
                    <div style='font-size:0.74rem; color:#fb7185;'>위험 {pct_of(bear_p):+.1f}%</div>
                </div>
                <div style='background:rgba(56,189,248,0.08); border:1px solid rgba(56,189,248,0.4); border-radius:12px; padding:12px; text-align:center;'>
                    <div style='font-size:0.78rem; color:#7dd3fc; font-weight:700;'>⚖️ CIO 적정 예상가</div>
                    <div style='font-size:1.35rem; font-weight:900; color:#38bdf8; margin-top:4px;'>{fmt_p(base_p)}</div>
                    <div style='font-size:0.74rem; color:#38bdf8;'>상승여력 {pct_of(base_p):+.1f}%</div>
                </div>
                <div style='background:rgba(52,211,153,0.08); border:1px solid rgba(52,211,153,0.4); border-radius:12px; padding:12px; text-align:center;'>
                    <div style='font-size:0.78rem; color:#6ee7b7; font-weight:700;'>🚀 강세 목표가</div>
                    <div style='font-size:1.35rem; font-weight:900; color:#34d399; margin-top:4px;'>{fmt_p(bull_p)}</div>
                    <div style='font-size:0.74rem; color:#34d399;'>최대기대 {pct_of(bull_p):+.1f}%</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        ac1, ac2, ac3 = st.columns(3)
        for col_obj, (ag_key, title, role_desc, data) in zip(
            [ac1, ac2, ac3],
            [
                ("eco", "🌍 AI 이코노미스트", "거시경제 · 산업 업종 멀티플 검증", res_ag["economist"]),
                ("ana", "📊 AI 애널리스트", "PER · PEG · 분기 실적 턴어라운드 검증", res_ag["analyst"]),
                ("jrn", "📰 AI 저널리스트", "개별 뉴스 · 연관 이슈 전이 리스크 검증", res_ag["journalist"])
            ]
        ):
            st_txt = data["stance"]
            b_col = "#10b981" if "찬성" in st_txt else ("#f59e0b" if "중립" in st_txt else "#f43f5e")
            pros_html = "".join([f"<div style='font-size:0.84rem; color:#cbd5e1; margin:5px 0;'>✅ {p}</div>" for p in data["pros"]]) or "<div style='color:#64748b; font-size:0.82rem;'>• 특이 긍정 요인 없음</div>"
            cons_html = "".join([f"<div style='font-size:0.84rem; color:#fca5a5; margin:5px 0;'>⚠️ {c}</div>" for c in data["cons"]]) or "<div style='color:#64748b; font-size:0.82rem;'>• 특이 반대 결격 사유 없음</div>"
            
            with col_obj:
                st.markdown(f"""
                <div class='kpi-card' style='border-top: 4px solid {b_col}; margin-bottom: 8px;'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <div>
                            <div style='font-size:1.02rem; font-weight:800; color:#ffffff;'>{title}</div>
                            <div style='font-size:0.75rem; color:#94a3b8;'>{role_desc}</div>
                        </div>
                        <span style='border:1px solid {b_col}; color:{b_col}; padding:3px 9px; border-radius:999px; font-size:0.78rem; font-weight:800;'>{st_txt} · {data["score"]}점</span>
                    </div>
                    <hr style='border-color:rgba(148,163,184,0.15); margin:10px 0;'>
                    <div style='font-size:0.8rem; font-weight:700; color:#34d399;'>👍 찬성 / 긍정 논거</div>
                    {pros_html}
                    <div style='font-size:0.8rem; font-weight:700; color:#f43f5e; margin-top:8px;'>👎 반대 / 리스크 경고</div>
                    {cons_html}
                </div>
                """, unsafe_allow_html=True)

                for l_idx, lnk in enumerate(data.get("links", [])):
                    if lnk["type"] == "url":
                        st.markdown(f"<a href='{lnk['url']}' target='_blank' class='evidence-link'>🔗 {lnk['label']}</a>", unsafe_allow_html=True)
                    elif lnk["type"] == "tab":
                        st.button(lnk["label"], key=f"jump_{ag_key}_{l_idx}", use_container_width=True, on_click=jump_to_tab_with_stock, args=(lnk["target"], ag_target))

# ---------------------------------------------------------
# TAB 4: 월스트리트 IB 5대 프로 밸류에이션
# ---------------------------------------------------------
elif current_tab == "🏛️ 월스트리트 IB 5대 프로 밸류에이션":
    st.markdown("### 🏛️ 월스트리트 IB 5대 프로 밸류에이션 (Wall Street Deep-Dive)")
    if not df.empty:
        ws_target = smart_stock_selector("월스트리트 정밀 분석 대상", "ws_tab")
        row_ws = df[df["종목명"] == ws_target].iloc[0]
        cur_p = row_ws.get("현재가") or 0
        eps_val = row_ws.get("올해누적 EPS(TTM)") or (cur_p / row_ws.get("PER (배)", 15) if row_ws.get("PER (배)") else 1.0)
        pbr_val, roe_val = row_ws.get("pbr") or 1.0, row_ws.get("ROE (%)") or 12.0
        fut_p = row_ws.get("자체 퀀트 적정가") or cur_p
        
        f_res = ws.evaluate_f_score_and_accruals(row_ws)
        scen_res = ws.calculate_scenario_valuation(cur_p, fut_p, fut_p * 0.82, fut_p * 1.20)
        exp_p, exp_up = scen_res.get("expected_price", cur_p), scen_res.get("expected_upside", 0.0)

        st.markdown(f"""
        <div class='kpi-auto-grid'>
            <div class='kpi-card' style='border-top: 4px solid {f_res["color"]};'><div class='kpi-label'><span>피오트로스키 F-Score</span><span>🎯</span></div><div class='kpi-val' style='color:{f_res["color"]};'>{f_res["score"]} / 9점</div><div class='kpi-sub'>{f_res["grade"]}</div></div>
            <div class='kpi-card' style='border-top: 4px solid #38bdf8;'><div class='kpi-label'><span>확률 가중 목표주가</span><span>⚖️</span></div><div class='kpi-val' style='color:#38bdf8;'>{curr_mark}{exp_p:,.0f}</div><div class='kpi-sub'>기대수익 {exp_up:+.1f}% (Bull25/Base50/Bear25)</div></div>
            <div class='kpi-card' style='border-top: 4px solid #818cf8;'><div class='kpi-label'><span>이익의 질 & 분식 검증</span><span>🛡️</span></div><div style='font-size:0.9rem; font-weight:700; color:#f8fafc; margin-top:6px;'>{f_res["message"]}</div></div>
        </div>
        """, unsafe_allow_html=True)

        ws_sub1, ws_sub2, ws_sub3 = st.tabs(["📊 1. 밸류에이션 밴드 & 풋볼 필드", "🏢 2. 피어그룹(Comps) & DCF 감응도", "🚀 3. 텐버거 발굴 레이더"])
        with ws_sub1:
            c_b1, c_b2 = st.columns([1.2, 1.0])
            with c_b1:
                h_df = fdr.DataReader(row_ws["티커"].zfill(6)) if selected_market == "국내 주식 (KRX)" else yf.Ticker(row_ws["티커"]).history(period="1y")
                band_fig = ws.create_valuation_band_chart(h_df, cur_p, eps_val, pbr_val, curr_mark)
                if band_fig: st.plotly_chart(band_fig, use_container_width=True)
            with c_b2:
                dcf_res = ws.calculate_dcf_sensitivity(cur_p, eps_val, roe_val)
                ff_fig = ws.create_football_field_chart(cur_p, (dcf_res["min_val"] or cur_p * 0.8, dcf_res["max_val"] or cur_p * 1.4), (eps_val * 10.0, eps_val * 25.0), (cur_p * 0.95, fut_p * 1.15), (scen_res.get("bear", {}).get("price", cur_p * 0.85), scen_res.get("bull", {}).get("price", cur_p * 1.25)), curr_mark)
                st.plotly_chart(ff_fig, use_container_width=True)
        with ws_sub2:
            c_d, c_c = st.columns(2)
            with c_d:
                st.markdown("##### 🏈 DCF 현금흐름할인 매트릭스")
                if not dcf_res["matrix"].empty: st.dataframe(dcf_res["matrix"].map(lambda x: f"{curr_mark}{x:,.0f}"), use_container_width=True)
            with c_c:
                st.markdown("##### 🏢 동종업계 피어그룹(Comps)")
                comps_data = ws.build_comps_table(row_ws["티커"], df)
                if not comps_data.empty: st.dataframe(comps_data[["종목명", "현재가", "PER (배)", "PEG (배)", "ROE (%)", "종합 스코어"]], use_container_width=True, hide_index=True)
        with ws_sub3:
            scan_mode = st.radio("스캔 대상", ["📌 내 관심 등록 종목군", "🌐 KRX 전 시장 전수조사 (42대 핵심주)"], horizontal=True, key="tb_scope")
            scan_ds = calculate_scores(scan_krx_wide_tenbaggers(), 25, 40, 25, 10) if ("KRX" in scan_mode and selected_market == "국내 주식 (KRX)") else df
            for cand in ws.scan_tenbagger_candidates(scan_ds)[:8]:
                sigs = " · ".join([f"{s[0]}: {s[1]}" for s in cand["signals"]])
                st.markdown(f"<div class='sweet-card'><b>{cand['종목명']} ({cand['티커']})</b> · 발굴 {cand['레이더 점수']:.0f}점<br><span style='font-size:0.82rem; color:#cbd5e1;'>{sigs}</span></div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# TAB 5: 분기별 실적 추이
# ---------------------------------------------------------
elif current_tab == "📊 분기별 실적 추이 (25년~26년)":
    q_target = smart_stock_selector("분기 실적 조회", "q_tab")
    if q_target:
        q_df = fetch_quarterly_detailed_matrix(selected_market, df[df["종목명"] == q_target].iloc[0]["티커"])
        if not q_df.empty: st.dataframe(q_df, use_container_width=True, height=380)

# ---------------------------------------------------------
# TAB 6: 증권사 리포트 & 실시간 뉴스
# ---------------------------------------------------------
elif current_tab == "📰 증권사 리포트 & 실시간 뉴스":
    rep_target = smart_stock_selector("리포트/뉴스 조회", "rep_tab")
    if rep_target:
        t_row = df[df["종목명"] == rep_target].iloc[0]
        rep_data = fetch_stock_reports_and_consensus(selected_market, t_row["티커"], t_row["현재가"])
        news_items = fetch_stock_news(selected_market, t_row["티커"])
        up_txt = f"{rep_data['upside_percent']:+.1f}%" if rep_data['upside_percent'] else "-"

        st.markdown(f"""
        <div class='kpi-auto-grid'>
            <div class='kpi-card'><div class='kpi-label'>증권사 평균 목표주가</div><div class='kpi-val' style='color:#38bdf8;'>{rep_data['target_price_str']}</div></div>
            <div class='kpi-card'><div class='kpi-label'>컨센서스 상승여력</div><div class='kpi-val' style='color:#34d399;'>{up_txt}</div></div>
            <div class='kpi-card'><div class='kpi-label'>증권사 투자의견</div><div class='kpi-val' style='color:#a855f7;'>{rep_data['recommendation']}</div></div>
        </div>
        """, unsafe_allow_html=True)

        cl, cr = st.columns(2)
        with cl:
            st.markdown(f"#### 📑 {rep_target} 증권사 분석 리포트")
            for r in rep_data["reports"]:
                st.markdown(f"<div class='report-box'><div style='display:flex;justify-content:space-between;margin-bottom:4px;'><span class='broker-badge'>{r['broker']}</span><span style='color:#9ca3af;font-size:0.78rem;'>{r['date']}</span></div><a href='{r['url']}' target='_blank' class='report-title-link'>🔗 {r['title']}</a></div>", unsafe_allow_html=True)
        with cr:
            st.markdown(f"#### ⚡ {rep_target} 실시간 핵심 뉴스")
            for n in news_items:
                st.markdown(f"<div class='report-box'><div style='display:flex;justify-content:space-between;margin-bottom:4px;'><span style='color:#38bdf8;font-size:0.8rem;font-weight:700;'>{n['media']}</span><span style='color:#9ca3af;font-size:0.76rem;'>{n['date']}</span></div><a href='{n['url']}' target='_blank' class='news-title-link'>{n['title']}</a></div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# TAB 7: 4사분면 밸류에이션 매트릭스
# ---------------------------------------------------------
elif current_tab == "🎯 4사분면 밸류에이션 매트릭스":
    st.markdown("##### 🎯 4사분면 밸류에이션 매트릭스 (좌측 하단 초록색 영역: SWEET SPOT)")
    fig_mat = create_sweet_spot_matrix(df)
    if fig_mat: st.plotly_chart(fig_mat, use_container_width=True)

# ---------------------------------------------------------
# TAB 8: 트렌디 실시간 인터랙티브 차트 (Pro)
# ---------------------------------------------------------
elif current_tab == "📈 트렌디 실시간 인터랙티브 차트 (Pro)":
    chart_target = smart_stock_selector("차트 분석 대상 종목", "pro_chart_tab")
    if chart_target:
        t_row = df[df["종목명"] == chart_target].iloc[0]
        t_tick, cur_p, fair_p, diff_pct = t_row["티커"], t_row["현재가"] or 0, t_row["자체 퀀트 적정가"] or 0, t_row["괴리율 (상승여력%)"] or 0.0
        up_color = "#34d399" if diff_pct > 0 else "#f43f5e"

        st.markdown(f"""
        <div class='chart-info-banner'>
            <div class='chart-info-item'><span>종목명 / 티커</span><span style='color:#f8fafc;'>{chart_target} ({t_tick})</span></div>
            <div class='chart-info-item'><span>실시간 현재가</span><span>{curr_mark}{cur_p:,.0f}</span></div>
            <div class='chart-info-item'><span>자체 퀀트 적정가</span><span style='color:#38bdf8;'>{curr_mark}{fair_p:,.0f}</span></div>
            <div class='chart-info-item'><span>자체 기대 상승여력</span><span style='color:{up_color};'>{diff_pct:+.1f}%</span></div>
        </div>
        """, unsafe_allow_html=True)

        c_m, c_s, c_b, c_a = st.columns([2, 1.3, 1.2, 2.2])
        with c_m: time_frame = st.radio("차트 주기", ["⚡ 당일 1분봉", "⚡ 5분봉", "일봉 (3개월)", "일봉 (1년)"], index=0, horizontal=True, key="pro_tf")
        with c_s: chart_style = st.radio("스타일", ["캔들스틱", "그라데이션"], index=0, horizontal=True, key="pro_style")
        with c_b: show_bb = st.checkbox("볼린저 밴드", value=True, key="pro_bb")
        with c_a: show_mas = st.multiselect("이동평균선", ["5선 (단기)", "20선 (생명선)", "60선 (추세선)"], default=["5선 (단기)", "20선 (생명선)"], key="pro_ma")

        is_intraday = "분봉" in time_frame
        if is_intraday:
            hist_df = fetch_intraday_chart(t_tick, selected_market, "1m" if "1분봉" in time_frame else "5m")
        else:
            n_days = 60 if "3개월" in time_frame else 250
            hist_df = fdr.DataReader(str(t_tick).zfill(6)).tail(n_days) if selected_market == "국내 주식 (KRX)" else yf.download(t_tick, period="1y", progress=False).tail(n_days)
            if isinstance(hist_df.columns, pd.MultiIndex): hist_df.columns = hist_df.columns.get_level_values(0)

        if not hist_df.empty and "Close" in hist_df.columns:
            fig_pro = create_pro_candlestick_chart(hist_df, chart_style, show_bb, show_mas, fair_p, curr_mark, is_intraday)
            st.plotly_chart(fig_pro, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True, "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"]})
        else:
            st.warning(f"⚠️ {chart_target}의 실시간 주가/분봉 데이터를 불러올 수 없습니다.")