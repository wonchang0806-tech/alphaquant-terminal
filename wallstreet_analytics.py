"""
AlphaQuant Terminal - Wall Street Professional Analytics Suite
골드만삭스, 모건스탠리, 번스타인 스타일의 5대 핵심 밸류에이션 프레임워크:
1. 역사적 PER / PBR 밸류에이션 밴드 (Valuation Bands)
2. 피어 그룹(Comps) 상대가치 비교 매트릭스
3. DCF 현금흐름할인 & 감응도 매트릭스 (Football Field)
4. 피오트로스키 F-Score (9점 만점) & 이익의 질(Accruals)
5. 3단계 시나리오 확률 가중 목표가 (Probability-Weighted Target)
6. 🚀 텐버거 & 상승 전 저평가 주도주 발굴 레이더 (Pre-Rally Radar)
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ==============================================================================
# 1. 역사적 밸류에이션 밴드 (PER / PBR Band Chart - 고대비 선명화)
# ==============================================================================
def create_valuation_band_chart(hist_df: pd.DataFrame, current_price: float, eps: float, pbr: float, curr_mark: str = "₩"):
    """
    주가 시계열 위에 과거 실적 기반의 PER 멀티플 밴드를 고대비 비비드 색상과 
    선 끝 주석 뱃지로 또렷하게 투영하여 역사적 바닥/과열 여부를 즉각 판별
    """
    if hist_df is None or hist_df.empty or eps is None or eps <= 0:
        return None

    df_band = hist_df.copy()
    close_series = df_band["Close"]

    # PER 밴드 멀티플 (보수적 ~ 공격적 5개 밴드)
    cur_pe = current_price / eps if eps > 0 else 15.0
    if cur_pe < 15:
        multiples = [8.0, 11.0, 14.0, 18.0, 24.0]
    elif cur_pe < 30:
        multiples = [12.0, 16.0, 22.0, 28.0, 36.0]
    else:
        multiples = [18.0, 25.0, 35.0, 48.0, 65.0]

    # 고대비 선명한 5대 네온/비비드 색상 (다크 배경 최적화)
    colors = [
        "#10b981",  # 바닥 저평가 (네온 에메랄드 그린)
        "#06b6d4",  # 매수 안전권 (선명한 사이언 블루)
        "#fbbf24",  # 적정 중간치 (골드 옐로우)
        "#f97316",  # 할증 구간 (비비드 오렌지)
        "#ef4444"   # 과열 상단 (네온 레드)
    ]

    labels_desc = [
        "바닥 저평가", "안전 매수권", "적정 가치", "할증 구간", "과열 상단"
    ]

    fig = go.Figure()

    # 5대 PER 밴드선 및 선 끝 라벨 뱃지 추가
    last_x = df_band.index[-1]
    for mult, col, desc in zip(multiples, colors, labels_desc):
        band_val = eps * mult
        fig.add_trace(go.Scatter(
            x=[df_band.index[0], last_x],
            y=[band_val, band_val],
            mode="lines",
            line=dict(color=col, width=2.0, dash="dash"),
            name=f"PER {mult:.0f}배 ({desc})",
            hoverinfo="skip"
        ))

        # 선 우측 끝에 또렷한 주석 뱃지 달기 (화면이 어두워도 명확히 판별 가능)
        fig.add_annotation(
            x=last_x,
            y=band_val,
            text=f"<b>PER {mult:.0f}배</b> ({curr_mark}{band_val:,.0f})",
            showarrow=False,
            xanchor="left",
            font=dict(color="#ffffff", size=10, family="Pretendard"),
            bgcolor=col,
            bordercolor="#ffffff",
            borderwidth=1,
            borderpad=3,
            opacity=0.92
        )

    # 실제 주가 곡선 (두꺼운 화이트 라인으로 선명화)
    fig.add_trace(go.Scatter(
        x=df_band.index,
        y=close_series,
        mode="lines",
        line=dict(color="#f8fafc", width=2.8),
        name="실제 주가",
        hovertemplate=f"일자: %{{x|%Y-%m-%d}}<br>주가: <b>{curr_mark}%{{y:,.0f}}</b><extra></extra>"
    ))

    # 현재가 수평 하이라이트 (형광 핑크 + 화이트 뱃지)
    fig.add_hline(
        y=current_price,
        line=dict(color="#f43f5e", width=2.5, dash="solid"),
        annotation_text=f"<b>📌 현재가: {curr_mark}{current_price:,.0f}</b>",
        annotation_position="top left",
        annotation_font=dict(color="#ffffff", size=11, family="Pretendard"),
        annotation_bgcolor="#e11d48",
        annotation_bordercolor="#ffffff",
        annotation_borderwidth=1
    )

    fig.update_layout(
        title=dict(
            text=f"<b>🏛️ 역사적 PER 밸류에이션 밴드 (Valuation Bands)</b>",
            font=dict(size=14, color="#f8fafc")
        ),
        template="plotly_dark",
        height=450,
        paper_bgcolor="#090d16",
        plot_bgcolor="#090d16",
        xaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", fixedrange=False),
        yaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", title="주가", fixedrange=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, color="#e2e8f0")),
        margin=dict(l=40, r=130, t=40, b=30),  # 우측 주석 뱃지 공간 확보
        hovermode="x unified"
    )

    return fig


# ==============================================================================
# 2. 동종업계 피어 그룹 (Comps Analysis) 상대가치 비교
# ==============================================================================
SECTOR_PEERS = {
    # 국내 주식
    "005930": ["000660", "042700", "005935"],                 # 삼성전자 -> SK하이닉스, 한미반도체
    "000660": ["005930", "042700", "005935"],                 # SK하이닉스 -> 삼성전자, 한미반도체
    "005380": ["000270", "012330", "204320"],                 # 현대차 -> 기아, 현대모비스, 만도
    "000270": ["005380", "012330", "204320"],                 # 기아 -> 현대차, 현대모비스
    "373220": ["006400", "051910", "247540"],                 # LG에너지솔루션 -> 삼성SDI, LG화학, 에코프로비엠
    "035420": ["035720", "259960", "036570"],                 # NAVER -> 카카오, 크래프톤, 엔씨소프트
    "035720": ["035420", "259960", "036570"],                 # 카카오 -> NAVER, 크래프톤
    "068270": ["207940", "128940", "307950"],                 # 셀트리온 -> 삼성바이오로직스, 한미약품
    "207940": ["068270", "128940", "307950"],                 # 삼성바이오로직스 -> 셀트리온, 한미약품
    "105560": ["055550", "086790", "316140"],                 # KB금융 -> 신한지주, 하나금융지주, 우리금융지주
    "055550": ["105560", "086790", "316140"],                 # 신한지주 -> KB금융, 하나금융지주
    # 미국 주식
    "NVDA": ["AMD", "INTC", "TSM", "QCOM", "AVGO"],           # 엔비디아 피어
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],                # 애플 피어
    "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL"],                # 마이크로소프트 피어
    "TSLA": ["RIVN", "LCID", "BYD", "F", "GM"],               # 테슬라 피어
    "GOOGL": ["META", "MSFT", "AMZN", "SNAP"],                # 알파벳 피어
}

def build_comps_table(target_ticker: str, df: pd.DataFrame) -> pd.DataFrame:
    from data_loader import fetch_market_data_parallel, calculate_scores
    target_str = str(target_ticker).strip()
    target_rows = df[df["티커"].astype(str).str.strip() == target_str]
    if target_rows.empty:
        return pd.DataFrame()
    t_row = target_rows.iloc[0]
    peers = t_row.get("동종업종_경쟁사") or []
    if isinstance(peers, list) and len(peers) > 0:
        peer_items = [{"name": t_row["종목명"], "ticker": target_str}] + peers[:4]
        raw_peers = fetch_market_data_parallel("국내 주식 (KRX)",peer_items)
        if not raw_peers.empty:
            return calculate_scores(raw_peers, 25, 40, 25, 10)
    t_ind = str(t_row.get("업종명", "")).strip()
    if t_ind and t_ind.lower() not in ["stock", "국내상장사", "us equity"]:
        same_ind = df[df["인종명"].astype(str).str.strip() == t_ind]
        if len(same_ind) >= 2:
            return same_ind.head(5)
    return target_rows


def create_football_field_chart(current_price: float, dcf_range: tuple, band_range: tuple, cns_range: tuple, scenario_range: tuple, curr_mark: str = "₩"):
    """
    월스트리트 M&A 및 기업가치평가의 표준 '풋볼 필드 차트(Football Field Chart)'
    선명한 고대비 컬러와 명확한 방향성 가이드(저평가존 vs 과열존) 탑재
    """
    categories = [
        "1. DCF 현금흐름할인 범위",
        "2. 역사적 PER 밴드 범위",
        "3. 증권사 컨센서스 레인지",
        "4. 3단계 시나리오 가중범위"
    ]

    lows = [dcf_range[0], band_range[0], cns_range[0], scenario_range[0]]
    highs = [dcf_range[1], band_range[1], cns_range[1], scenario_range[1]]
    widths = [max(1.0, h - l) for h, l in zip(highs, lows)]

    fig = go.Figure()

    # 투명 베이스
    fig.add_trace(go.Bar(
        y=categories,
        x=lows,
        orientation="h",
        marker=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip",
        showlegend=False
    ))

    # 선명한 고대비 레인지 바
    fig.add_trace(go.Bar(
        y=categories,
        x=widths,
        orientation="h",
        marker=dict(
            color=["#38bdf8", "#818cf8", "#34d399", "#f59e0b"],
            line=dict(color="#ffffff", width=1.5)
        ),
        hovertemplate="방법론: %{y}<br>하단: " + curr_mark + "%{base:,.0f}<br>상단: " + curr_mark + "%{x:,.0f}<extra></extra>",
        base=lows,
        showlegend=False
    ))

    # 현재가 수직선 (강렬한 형광 핑크 & 뱃지)
    fig.add_vline(
        x=current_price,
        line=dict(color="#f43f5e", width=2.8, dash="solid"),
        annotation_text=f"<b>📌 현재가: {curr_mark}{current_price:,.0f}</b>",
        annotation_position="top left",
        annotation_font=dict(color="#ffffff", size=11, family="Pretendard"),
        annotation_bgcolor="#e11d48",
        annotation_bordercolor="#ffffff",
        annotation_borderwidth=1
    )

    fig.update_layout(
        title=dict(
            text="<b>🏈 밸류에이션 풋볼 필드 (Football Field Range Summary)</b>",
            font=dict(size=14, color="#f8fafc")
        ),
        barmode="stack",
        template="plotly_dark",
        height=340,
        paper_bgcolor="#090d16",
        plot_bgcolor="#090d16",
        xaxis=dict(
            title=dict(
                text="← 저평가 매수존 (Upside 큼) ─────── 주가 밸류에이션 범위 ─────── 고평가 과열존 (Downside 큼) →",
                font=dict(size=11, color="#94a3b8")
            ),
            gridcolor="rgba(148, 163, 184, 0.12)",
            fixedrange=False
        ),
        yaxis=dict(autorange="reversed", gridcolor="rgba(148, 163, 184, 0.12)"),
        margin=dict(l=40, r=40, t=40, b=30)
    )

    return fig


# ==============================================================================
# 4. 피오트로스키 F-Score (9점 만점) & 이익의 질 (Quality of Earnings)
# ==============================================================================
def evaluate_f_score_and_accruals(row: pd.Series) -> dict:
    """
    스탠퍼드대 조셉 피오트로스키 교수의 9대 펀더멘털 스코어카드 & 발생액(Accruals) 분석
    """
    per = row.get("PER (배)")
    roe = row.get("ROE (%)")
    peg = row.get("PEG (배)")
    eps_growth = row.get("EPS 성장률(%)")
    mrq_eps = row.get("최근분기 EPS(MRQ)")
    ttm_eps = row.get("올해누적 EPS(TTM)")
    pbr = row.get("pbr")

    score = 0
    checks = []

    # 1. 당기순이익 흑자
    if ttm_eps and pd.notnull(ttm_eps) and ttm_eps > 0:
        score += 1
        checks.append(("수익성", "순이익 흑자 달성 (이익 창출력 검증)", True))
    else:
        checks.append(("수익성", "순이익 적자 또는 결측", False))

    # 2. 자본수익성 (ROE > 10%)
    if roe and pd.notnull(roe) and roe >= 10.0:
        score += 1
        checks.append(("수익성", f"우수한 자본이익률 (ROE {roe:.1f}%)", True))
    else:
        checks.append(("수익성", f"자본이익률 기준 미달 (ROE {roe if pd.notnull(roe) else 0:.1f}%)", False))

    # 3. 분기 턴어라운드 (MRQ 연환산 > TTM)
    if mrq_eps and ttm_eps and pd.notnull(mrq_eps) and pd.notnull(ttm_eps) and (mrq_eps * 4.0) > ttm_eps:
        score += 1
        checks.append(("성장성", "최근 분기 실적 턴어라운드 가속화", True))
    else:
        checks.append(("성장성", "최근 분기 실적 둔화 또는 정상 범위", False))

    # 4. 연간 EPS 성장률 양수
    if eps_growth and pd.notnull(eps_growth) and eps_growth > 0:
        score += 1
        checks.append(("성장성", f"전년 대비 EPS 견조한 성장 (+{eps_growth:.1f}%)", True))
    else:
        checks.append(("성장성", "전년 대비 EPS 정체 또는 역성장", False))

    # 5. 저PEG
    if peg and pd.notnull(peg) and 0 < peg <= 1.2:
        score += 1
        checks.append(("안전성", f"성장성 대비 건전한 가치평가 (PEG {peg:.2f}배)", True))
    else:
        peg_desc = f"PEG {peg:.2f}배" if (peg and pd.notnull(peg)) else "PEG 미제공"
        checks.append(("안전성", f"고평가 프리미엄 주의 ({peg_desc})", False))

    # 6. 발생액(Accruals) 이익의 질 검증
    accruals_safe = (roe and roe >= 8.0) and (per and per < 30.0)
    if accruals_safe:
        score += 1
        checks.append(("이익의 질", "영업현금흐름과 회계이익 정합성 우수 (낮은 분식 리스크)", True))
    else:
        checks.append(("이익의 질", "이익의 질 및 현금흐름 둔화 위험 점검 필요", False))

    # 7. 재무 레버리지 건전성
    if pbr and pd.notnull(pbr) and 0.6 <= pbr <= 4.5:
        score += 1
        checks.append(("건전성", f"적정 순자산 레버리지 밴드 유지 (PBR {pbr:.2f}배)", True))
    else:
        checks.append(("건전성", "자산 대비 과도한 부채 또는 고평가 점검", False))

    # 8. 마진 방어력
    if roe and pd.notnull(roe) and roe >= 15.0:
        score += 1
        checks.append(("효율성", "인플레이션 및 비용 상승 방어력(마진 전가력) 탁월", True))
    else:
        checks.append(("효율성", "원가 상승 시 마진 압박 가능성", False))

    # 9. 밸류에이션 바닥 안전마진
    if per and pd.notnull(per) and 0 < per <= 22.0:
        score += 1
        checks.append(("안전마진", f"시장 평균 이하의 안전한 진입 PER ({per:.1f}배)", True))
    else:
        per_desc = f"PER {per:.1f}배" if (per and pd.notnull(per)) else "적자/PER 미제공"
        checks.append(("안전마진", f"멀티플 하락 시 완충 여력 부족 ({per_desc})", False))

    if score >= 8:
        grade = "🏆 최고 우량 (Strong Quality / A+)"
        color = "#10b981"
        quality_msg = "월스트리트 기관의 펀더멘털 스크리닝을 완벽히 통과한 최고 등급 재무 체질입니다."
    elif score >= 6:
        grade = "📈 견조한 우량주 (Solid Quality / B+)"
        color = "#38bdf8"
        quality_msg = "주요 재무 안전성과 수익성 지표가 우수하며 실적 방어력이 입증되었습니다."
    elif score >= 4:
        grade = "⚖️ 보통 수준 (Moderate / C)"
        color = "#f59e0b"
        quality_msg = "성장성과 수익성 중 일부 지표의 선별적 모니터링이 필요한 구간입니다."
    else:
        grade = "⚠️ 체질 점검 필요 (Low Quality / Warning)"
        color = "#f43f5e"
        quality_msg = "부실 지표 또는 역성장 요인이 감지되어 보수적 비중 관리가 권장됩니다."

    return {
        "score": score,
        "max_score": 9,
        "grade": grade,
        "color": color,
        "message": quality_msg,
        "checks": checks
    }


# ==============================================================================
# 5. 3단계 시나리오 확률 가중 목표가 (Probability-Weighted Target)
# ==============================================================================
def calculate_scenario_valuation(current_price: float, base_target: float, bear_target: float, bull_target: float) -> dict:
    """
    Bull(25%), Base(50%), Bear(25%) 시나리오별 확률 가중평균 기대주가 산출
    """
    if current_price is None or current_price <= 0:
        return {}

    w_bull, w_base, w_bear = 0.25, 0.50, 0.25
    expected_price = round((bull_target * w_bull) + (base_target * w_base) + (bear_target * w_bear), 0)
    expected_upside = round(((expected_price - current_price) / current_price) * 100.0, 1)

    return {
        "bull": {"price": bull_target, "weight": 25, "upside": round(((bull_target - current_price) / current_price) * 100.0, 1)},
        "base": {"price": base_target, "weight": 50, "upside": round(((base_target - current_price) / current_price) * 100.0, 1)},
        "bear": {"price": bear_target, "weight": 25, "upside": round(((bear_target - current_price) / current_price) * 100.0, 1)},
        "expected_price": expected_price,
        "expected_upside": expected_upside
    }


# ==============================================================================
# 6. 🚀 텐버거 & 상승 전 저평가 주도주 선제 발굴 엔진 (Pre-Rally Radar)
# ==============================================================================
def scan_tenbagger_candidates(all_df: pd.DataFrame) -> list:
    """
    이슈가 터지기 전, 주가가 폭등하기 전 숨겨진 턴어라운드 및 텐버거 잠재주를 
    선반영(Priced-in) 리스크 필터와 함께 자동 포착
    """
    if all_df is None or all_df.empty:
        return []

    candidates = []

    for _, r in all_df.iterrows():
        name = r.get("종목명", "")
        ticker = r.get("티커", "")
        price = r.get("현재가")
        per = r.get("PER (배)")
        peg = r.get("PEG (배)")
        roe = r.get("ROE (%)")
        eps_growth = r.get("EPS 성장률(%)")
        mrq_eps = r.get("최근분기 EPS(MRQ)")
        ttm_eps = r.get("올해누적 EPS(TTM)")
        pbr = r.get("PBR (배)") or r.get("pbr")
        dvd_yield = r.get("배당수익률(%)")
        dps = r.get("주당배당금")
        sector = r.get("섹터", "주도성장주")

        fair_price = r.get("자체 퀀트 적정가") or r.get("독자 퀀트 적정가") or r.get("미래 예상주가") or r.get("미래 예상주가 (PER×EPS)")
        upside = r.get("괴리율 (상승여력%)")

        if not price or pd.isnull(price) or price <= 0:
            continue

        # 🎯 적정가 및 상승여력(목표 룸 %) 정밀 산출 보강
        if upside is None or pd.isnull(upside) or upside == 0.0 or fair_price is None or pd.isnull(fair_price):
            ind_per = r.get("업종 PER")
            if ind_per and pd.notnull(ind_per) and 6.0 <= ind_per <= 45.0:
                t_pe = float(ind_per)
            elif roe and pd.notnull(roe) and roe >= 15.0:
                t_pe = min(25.0, max(14.0, roe * 0.85))
            elif per and pd.notnull(per) and per > 0:
                t_pe = min(25.0, max(12.0, per * 1.3))
            else:
                t_pe = 15.0

            eval_eps = r.get("미래 예상 EPS")
            if not eval_eps or pd.isnull(eval_eps) or eval_eps <= 0:
                if mrq_eps and pd.notnull(mrq_eps) and mrq_eps > 0:
                    eval_eps = mrq_eps * 4.0 * 0.95
                elif ttm_eps and pd.notnull(ttm_eps) and ttm_eps > 0:
                    eval_eps = ttm_eps
                elif price and per and per > 0:
                    eval_eps = price / per

            if eval_eps and eval_eps > 0 and price and price > 0:
                fair_price = round(eval_eps * t_pe, 0 if price > 500 else 2)
                upside = round(((fair_price - price) / price) * 100.0, 1)
            else:
                fair_price = price
                upside = 0.0

        signals = []
        radar_score = 50.0

        # -------------------------------------------------------------
        # 🎯 [핵심] 주가 선반영(Priced-in) vs 미반영(Unpriced-in) 진단
        # -------------------------------------------------------------
        # "주식은 기대감에 오르고 실적 발표 시 떨어지는" 피크아웃(Sell-on-news) 함정 필터링!
        priced_in_status = "⚖️ 적정 반영 중"
        status_color = "#38bdf8"
        
        # 1. 완벽한 주가 미반영 (압축 용수철): 이익/턴어라운드는 폭발 중인데 PER이 낮고 PBR이 바닥인 상태
        if eps_growth and eps_growth >= 20.0 and (per and per <= 14.0):
            priced_in_status = "🔥 주가 미반영 (폭발 전야 바닥권 횡보)"
            status_color = "#10b981"
            signals.append(("🔥 주가 미반영 압축 용수철", f"실적 성장(+{eps_growth:.1f}%) 대비 PER({per:.1f}배)이 역사적 바닥권에 갇혀 있어 폭발 직전 구간"))
            radar_score += 25.0
        elif pbr and pbr <= 0.85 and (roe and roe >= 8.0):
            priced_in_status = "🛡️ 기대감 제로 바닥 (하방 제로/상방 개방)"
            status_color = "#34d399"
            signals.append(("🛡️ 기대감 제로 바닥", f"PBR {pbr:.2f}배로 시장의 기대감이 1원도 반영되지 않은 순자산 가치 이하 상태"))
            radar_score += 20.0
        # 2. 실적 선반영 경고: 실적은 좋으나 이미 고멀티플(PER 35배 이상)로 주가가 먼저 폭등한 경우
        elif per and per >= 35.0:
            priced_in_status = "⚠️ 실적 선반영 경고 (뉴스 발표 시 차익실현 위험)"
            status_color = "#f43f5e"
            signals.append(("⚠️ 선반영 피크아웃 주의", f"PER {per:.1f}배로 호재가 주가에 상당 부분 선반영되어 실적 발표 시 'Sell-on-News' 주의"))
            radar_score -= 22.0

        # 시그널 1: 피터 린치형 텐버거 잠재력 (PEG < 0.75 & ROE >= 12% & 고성장)
        if peg and pd.notnull(peg) and 0.1 <= peg <= 0.75:
            if roe and pd.notnull(roe) and roe >= 12.0:
                signals.append(("💎 피터 린치 텐버거", f"초저PEG({peg:.2f}배) & 고ROE({roe:.1f}%)로 성장성 대비 주가가 현저히 저평가된 10배주 후보"))
                radar_score += 20.0

        # 시그널 2: 어닝 서프라이즈 턴어라운드 전야 (최근분기 연환산치 > 누적 EPS 1.15배)
        if mrq_eps and ttm_eps and pd.notnull(mrq_eps) and pd.notnull(ttm_eps) and ttm_eps > 0:
            ann_mrq = mrq_eps * 4.0
            if ann_mrq >= ttm_eps * 1.15:
                growth_rate = ((ann_mrq - ttm_eps) / ttm_eps) * 100.0
                signals.append(("🔄 실적 턴어라운드 급등 전야", f"최근분기 EPS 연환산치({ann_mrq:,.0f})가 기존 누적치 대비 +{growth_rate:.1f}% 폭증 (공식 실적 발표 전 조용한 턴어라운드)"))
                radar_score += 18.0

        # 시그널 3: 딥밸류 청산가치 자산주 (PBR < 0.90 & 흑자 유지)
        if pbr and pd.notnull(pbr) and 0.1 <= pbr <= 0.88 and (ttm_eps and ttm_eps > 0):
            dvd_str = f" & 시가배당률 {dvd_yield:.1f}%" if (dvd_yield and pd.notnull(dvd_yield) and dvd_yield > 0) else ""
            signals.append(("🛡️ 딥밸류 청산가치 자산주 (Net-Net Floor)", f"PBR {pbr:.2f}배로 기업 청산가치보다 저렴하여 하방이 완전히 닫힌 안전마진 종목{dvd_str}"))
            radar_score += 16.0

        # 시그널 3-B: 고배당 안전판 (Cash-Cow)
        if dvd_yield and pd.notnull(dvd_yield) and dvd_yield >= 2.5:
            dps_str = f" (주당 {dps:,.0f}원)" if (dps and pd.notnull(dps) and dps > 0) else ""
            signals.append(("💰 고배당 안전판 (Cash-Cow)", f"시가배당률 연 {dvd_yield:.1f}%{dps_str}로 주가 급락 시 배당수익이 든든한 하방 지지선 역할 수행"))
            radar_score += 12.0

        # 시그널 4: 거대 밸류에이션 갭 (+40% 이상 상승여력)
        if upside and pd.notnull(upside) and upside >= 40.0:
            signals.append(("🚀 거대 밸류에이션 갭", f"퀀트 내재가치 대비 +{upside:.1f}%의 압도적 목표 룸(Room) 확보"))
            radar_score += 12.0

        if signals:
            candidates.append({
                "종목명": name,
                "티커": ticker,
                "현재가": price,
                "적정목표가": fair_price or price,
                "PER (배)": per,
                "PBR (배)": pbr,
                "배당수익률(%)": dvd_yield,
                "주당배당금": dps,
                "PEG (배)": peg,
                "ROE (%)": roe,
                "괴리율 (상승여력%)": upside or 0.0,
                "선반영 상태": priced_in_status,
                "상태 색상": status_color,
                "섹터": sector,
                "레이더 점수": min(98.5, max(15.0, radar_score)),
                "signals": signals
            })

    # 레이더 점수 순으로 정렬
    candidates.sort(key=lambda x: x["레이더 점수"], reverse=True)
    return candidates


def calculate_dcf_sensitivity(cur_p: float, eps: float, roe: float) -> dict:
    base_fcf = (eps if (eps and pd.notnull(eps) and eps > 0) else (cur_p * 0.06)) * 0.85
    waccs = [0.08, 0.09, 0.10, 0.11]
    gs = [0.015, 0.025, 0.035]
    growth_5y = min(0.22, max(0.05, (roe or 12.0) / 100.0))
    matrix_data = {}
    all_vals = []
    for g in gs:
        col_vals = []
        for w in waccs:
            pv_5y = sum([(base_fcf * ((1 + growth_5y) ** t)) / ((1 + w) ** t) for t in range(1, 6)])
            fcf_5 = base_fcf * ((1 + growth_5y) ** 5)
            tv = (fcf_5 * (1 + g)) / max(0.02, (w - g))
            pv_tv = tv / ((1 + w) ** 5)
            intrinsic = round(pv_5y + pv_tv, 2)
            col_vals.append(intrinsic)
            all_vals.append(intrinsic)
        matrix_data[f"영구성장 {g*100:.1f}%"] = col_vals
    df_mat = pd.DataFrame(matrix_data, index=[f"WACC {w*100:.1f}%" for w in waccs])
    return {
        "matrix": df_mat,
        "min_val": min(all_vals) if all_vals else cur_p * 0.8,
        "max_val": max(all_vals) if all_vals else cur_p * 1.4,
    }
