import json

def _is_admin_user() -> bool:
    try:
        return bool(st.session_state.get("authenticated") and st.session_state.get("user_role") == "admin")
    except Exception:
        return False

def _has_real_holdings(data) -> bool:
    if not isinstance(data, dict):
        return False
    for v in data.values():
        if isinstance(v, dict) and len(v) > 0:
            return True
    return False

def _get_secret_portfolio() -> dict:
    empty_pf = {"?? ?? (KRX)": {}, "?? ?? (??)": {}}
    if not _is_admin_user():
        return empty_pf
    raw = None
    try:
        if "PORTFOLIO_JSON" in st.secrets:
            raw = st.secrets["PORTFOLIO_JSON"]
    except Exception:
        pass
    if not raw:
        raw = os.getenv("PORTFOLIO_JSON", "")
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
            if _has_real_holdings(data):
                return data
        except Exception:
            pass
    return empty_pf

def load_portfolio() -> dict:
    empty_pf = {"?? ?? (KRX)": {}, "?? ?? (??)": {}}
    if not _is_admin_user():
        return empty_pf
    cached = st.session_state.get("admin_portfolio_cache")
    if _has_real_holdings(cached):
        return cached
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as _f:
                _local = json.load(_f)
                if _has_real_holdings(_local):
                    st.session_state["admin_portfolio_cache"] = _local
                    return _local
        except Exception:
            pass
    sec_pf = _get_secret_portfolio()
    if _has_real_holdings(sec_pf):
        st.session_state["admin_portfolio_cache"] = sec_pf
        return sec_pf
    return empty_pf

def save_portfolio(data: dict):
    try:
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def scan_buy_timing_signals(df: pd.DataFrame) -> list:
    """[종합 스코어 75점↑] + [PEG < 1.0] + [자체 적정가 괴리율 +25%↑] 3박자 매수 타점 스캔"""
    if df.empty:
        return []
    signals = []
    for _, r in df.iterrows():
        score = r.get("종합 스코어") or 0
        peg = r.get("PEG (배)")
        upside = r.get("괴리율 (상승여력%)") or 0
        roe = r.get("ROE (%)") or 0
        if score >= 75.0 and (peg is not None and pd.notnull(peg) and 0 < peg < 1.0) and upside >= 25.0:
            signals.append({
                "종목명": r["종목명"],
                "티커": r["티커"],
                "현재가": r["현재가"],
                "자체 퀀트 적정가": r["자체 퀀트 적정가"],
                "괴리율": upside,
                "PEG": peg,
                "ROE": roe,
                "종합 스코어": score,
            })
    signals.sort(key=lambda x: x["종합 스코어"], reverse=True)
    return signals

def render_portfolio_and_radar_tab(df: pd.DataFrame, selected_market: str, curr_mark: str, jump_callback):
    st.markdown("### 💼 내 포트폴리오 리밸런싱 & 🎯 매수 타점 레이더")
    is_krw = (selected_market == "국내 주식 (KRX)")
    fmt_p = lambda v: "-" if pd.isnull(v) else (f"{curr_mark}{v:,.0f}" if is_krw else f"{curr_mark}{v:,.2f}")

    # ---------------------------------------------------------
    # PART 1: 오늘의 3박자 매수 타점 포착 레이더 (2순위 기능)
    # ---------------------------------------------------------
    signals = scan_buy_timing_signals(df)
    with st.expander(f"🎯 오늘의 3박자 매수 타점 포착 레이더 ({len(signals)}종목 충족: 스코어 75점↑ · PEG<1.0 · 괴리율 +25%↑)", expanded=True):
        if signals:
            st.markdown("<div class='kpi-auto-grid'>", unsafe_allow_html=True)
            cols = st.columns(min(3, len(signals)))
            for idx, sig in enumerate(signals[:6]):
                with cols[idx % len(cols)]:
                    st.markdown(f"""
                    <div class='sweet-card' style='margin-bottom:8px;'>
                        <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <b style='font-size:1.05rem; color:#ffffff;'>🔥 {sig['종목명']} <span style='font-size:0.78rem; color:#94a3b8;'>({sig['티커']})</span></b>
                            <span style='background:#10b981; color:#052e16; padding:2px 8px; border-radius:999px; font-size:0.76rem; font-weight:800;'>{sig['종합 스코어']:.1f}점</span>
                        </div>
                        <div style='font-size:0.84rem; color:#e2e8f0; margin-top:6px;'>
                            현재가 <b>{fmt_p(sig['현재가'])}</b> ➔ 적정가 <b style='color:#38bdf8;'>{fmt_p(sig['자체 퀀트 적정가'])}</b> (<b style='color:#34d399;'>+{sig['괴리율']:.1f}%</b>)
                        </div>
                        <div style='font-size:0.78rem; color:#94a3b8; margin-top:4px;'>
                            PEG {sig['PEG']:.2f}배 · ROE {sig['ROE']:.1f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.button(
                        f"🤖 {sig['종목명']} AI 심의위원 검증하기",
                        key=f"radar_jump_{sig['티커']}",
                        use_container_width=True,
                        on_click=jump_callback,
                        args=("🤖 AI 4대 에이전트 투자심의위원회", sig["종목명"])
                    )
        else:
            st.info("현재 등록된 관심 종목 중 3박자(스코어 75점↑ + PEG<1.0 + 괴리율 +25%↑) 조건을 동시에 충족하는 종목이 없습니다.")

    st.markdown("---")

    # ---------------------------------------------------------
    # PART 2: 내 보유 포트폴리오 등록 & 실시간 손익/리밸런싱 (1순위 기능)
    # ---------------------------------------------------------
    if "portfolio_data" not in st.session_state:
        st.session_state.portfolio_data = load_portfolio()

    market_pf = st.session_state.portfolio_data.setdefault(selected_market, {})

    st.markdown("#### 📥 보유 종목 매수단가 · 수량 등록 / 수정")
    if not df.empty:
        c_in1, c_in2, c_in3, c_in4 = st.columns([2.2, 1.5, 1.3, 1.0])
        stock_names = df["종목명"].tolist()
        with c_in1:
            sel_name = st.selectbox("보유 종목 선택", stock_names, key="pf_sel_stock")
            sel_row = df[df["종목명"] == sel_name].iloc[0]
            sel_tick = str(sel_row["티커"])
            existing = market_pf.get(sel_tick, {})
        with c_in2:
            avg_price = st.number_input(
                f"평균 매수가 ({curr_mark})",
                min_value=0.0,
                value=float(existing.get("avg_price", sel_row.get("현재가") or 0.0)),
                step=100.0 if is_krw else 1.0,
                key=f"pf_price_{sel_tick}"
            )
        with c_in3:
            qty = st.number_input(
                "보유 수량 (주)",
                min_value=0,
                value=int(existing.get("qty", 10)),
                step=1,
                key=f"pf_qty_{sel_tick}"
            )
        with c_in4:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 저장/반영", type="primary", use_container_width=True, key="pf_save_btn"):
                if qty > 0 and avg_price > 0:
                    market_pf[sel_tick] = {"name": sel_name, "avg_price": float(avg_price), "qty": int(qty)}
                elif sel_tick in market_pf:
                    del market_pf[sel_tick]
                save_portfolio(st.session_state.portfolio_data)
                st.success(f"{sel_name} 포트폴리오 반영 완료!")
                st.rerun()

    if not market_pf:
        st.info("위에서 보유 중인 종목의 평균 매수가와 수량을 입력하고 **[💾 저장/반영]**을 누르면 실시간 평가손익과 AI 리밸런싱 가이드가 표시됩니다.")
        return

    # 보유 종목 계산 테이블 구성
    pf_rows = []
    tot_buy, tot_eval, tot_fair_eval = 0.0, 0.0, 0.0

    for tick, info in market_pf.items():
        match_df = df[df["티커"].astype(str) == str(tick)]
        if match_df.empty:
            continue
        r = match_df.iloc[0]
        cur_p = float(r.get("현재가") or info["avg_price"])
        fair_p = float(r.get("자체 퀀트 적정가") or cur_p)
        buy_p = float(info["avg_price"])
        q = int(info["qty"])

        buy_amt = buy_p * q
        eval_amt = cur_p * q
        fair_amt = fair_p * q
        pnl = eval_amt - buy_amt
        pnl_pct = ((cur_p - buy_p) / buy_p) * 100.0 if buy_p > 0 else 0.0
        rem_upside = ((fair_p - cur_p) / cur_p) * 100.0 if cur_p > 0 else 0.0

        tot_buy += buy_amt
        tot_eval += eval_amt
        tot_fair_eval += fair_amt

        pf_rows.append({
            "티커": tick,
            "종목명": r["종목명"],
            "보유수량": q,
            "평균매수가": buy_p,
            "현재가": cur_p,
            "퀀트적정가": fair_p,
            "매수금액": buy_amt,
            "평가금액": eval_amt,
            "평가손익": pnl,
            "수익률(%)": pnl_pct,
            "적정가잔여여력(%)": rem_upside,
            "종합스코어": r.get("종합 스코어") or 50.0,
        })

    if not pf_rows:
        st.warning("보유 종목이 현재 분석 유니버스에서 제외되어 있습니다. 사이드바에서 복원해 주세요.")
        return

    pf_df = pd.DataFrame(pf_rows)
    pf_df["비중(%)"] = (pf_df["평가금액"] / tot_eval * 100.0) if tot_eval > 0 else 0.0

    # 리밸런싱 & 대응 액션 자동 진단
    actions = []
    for _, pr in pf_df.iterrows():
        w_pct = pr["비중(%)"]
        pnl_p = pr["수익률(%)"]
        rem_u = pr["적정가잔여여력(%)"]
        sc = pr["종합스코어"]

        if w_pct >= 40.0:
            act = f"⚠️ 비중 과다 ({w_pct:.1f}%) · 리밸런싱 축소 검토"
        elif rem_u <= 5.0 and pnl_p > 10.0:
            act = f"💰 적정가 도달 임박 (여력 {rem_u:+.1f}%) · 분할 익절 권장"
        elif pnl_p <= -10.0 and sc >= 72.0 and rem_u >= 25.0:
            act = f"🛒 우량주 저점 구간 (스코어 {sc:.0f}점) · 분할 물타기 유효"
        elif rem_u >= 30.0 and sc >= 70.0:
            act = f"🚀 추가 상승여력 풍부 (+{rem_u:.1f}%) · 보유/비중확대"
        else:
            act = "✅ 적정 비중 유지 (Hold)"
        actions.append(act)
    pf_df["AI 리밸런싱 가이드"] = actions

    tot_pnl = tot_eval - tot_buy
    tot_pnl_pct = ((tot_eval - tot_buy) / tot_buy) * 100.0 if tot_buy > 0 else 0.0
    tot_target_upside = ((tot_fair_eval - tot_eval) / tot_eval) * 100.0 if tot_eval > 0 else 0.0
    pnl_color = "#34d399" if tot_pnl >= 0 else "#f43f5e"

    # 상단 계좌 요약 KPI 오토핏 카드
    st.markdown(f"""
    <div class='kpi-auto-grid' style='margin-top:14px;'>
        <div class='kpi-card'><div class='kpi-label'><span>총 매수원금</span><span>💳</span></div><div class='kpi-val'>{fmt_p(tot_buy)}</div><div class='kpi-sub'>{len(pf_df)}종목 분산 보유</div></div>
        <div class='kpi-card'><div class='kpi-label'><span>실시간 총 평가금액</span><span>💰</span></div><div class='kpi-val' style='color:#38bdf8;'>{fmt_p(tot_eval)}</div><div class='kpi-sub'>실시간 시세 반영</div></div>
        <div class='kpi-card'><div class='kpi-label'><span>총 평가손익 / 수익률</span><span>📈</span></div><div class='kpi-val' style='color:{pnl_color};'>{tot_pnl_pct:+.2f}%</div><div class='kpi-sub' style='color:{pnl_color};'>{('+' if tot_pnl>=0 else '')}{fmt_p(tot_pnl)}</div></div>
        <div class='kpi-card'><div class='kpi-label'><span>퀀트 적정가 도달 시 기대여력</span><span>🎯</span></div><div class='kpi-val' style='color:#a855f7;'>+{tot_target_upside:.1f}%</div><div class='kpi-sub'>목표 평가액 {fmt_p(tot_fair_eval)}</div></div>
    </div>
    """, unsafe_allow_html=True)

    c_tbl, c_pie = st.columns([2.3, 1.0])
    with c_tbl:
        st.markdown("##### 📋 보유 종목별 수익률 & AI 리밸런싱 진단표")
        show_df = pf_df[["종목명", "비중(%)", "보유수량", "평균매수가", "현재가", "퀀트적정가", "수익률(%)", "적정가잔여여력(%)", "AI 리밸런싱 가이드"]].copy()
        show_df["비중(%)"] = show_df["비중(%)"].apply(lambda x: f"{x:.1f}%")
        show_df["평균매수가"] = show_df["평균매수가"].apply(fmt_p)
        show_df["현재가"] = show_df["현재가"].apply(fmt_p)
        show_df["퀀트적정가"] = show_df["퀀트적정가"].apply(fmt_p)
        show_df["수익률(%)"] = show_df["수익률(%)"].apply(lambda x: f"{x:+.2f}%")
        show_df["적정가잔여여력(%)"] = show_df["적정가잔여여력(%)"].apply(lambda x: f"{x:+.1f}%")
        st.dataframe(show_df, use_container_width=True, hide_index=True)

        # 보유 종목 삭제 버튼
        del_target = st.selectbox("포트폴리오에서 제외할 종목 선택", ["선택 안 함"] + pf_df["종목명"].tolist(), key="pf_del_sel")
        if del_target != "선택 안 함":
            if st.button(f"🗑️ '{del_target}' 보유 목록에서 제거", key="pf_del_btn"):
                t_del = pf_df[pf_df["종목명"] == del_target].iloc[0]["티커"]
                if t_del in market_pf:
                    del market_pf[t_del]
                    save_portfolio(st.session_state.portfolio_data)
                    st.rerun()

    with c_pie:
        st.markdown("##### 🍩 포트폴리오 자산 비중")
        fig_pie = go.Figure(data=[go.Pie(
            labels=pf_df["종목명"],
            values=pf_df["평가금액"],
            hole=0.48,
            textinfo="label+percent",
            textfont=dict(size=11, color="#ffffff"),
            marker=dict(line=dict(color="#070b13", width=2))
        )])
        fig_pie.update_layout(
            template="plotly_dark",
            height=330,
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        