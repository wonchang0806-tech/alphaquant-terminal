import re
from collections import Counter
import pandas as pd

# 불용어(기사에서 자주 쓰이지만 기업/이슈가 아닌 일반 단어)
STOPWORDS = {
    "기자", "뉴스", "오늘", "내일", "전일", "대비", "상승", "하락", "마감", "장중", "특징주",
    "주가", "주식", "시장", "증시", "코스피", "코스닥", "투자", "매수", "매도", "목표가",
    "실적", "영업이익", "매출", "전망", "기록", "발표", "기준", "관련", "위해", "통해", "대한"
}

def extract_dynamic_partners_from_news(row: pd.Series, news_list: list) -> dict:
    """하드코딩 사전 없이 종목의 업종명과 실시간 뉴스에서 반복 등장하는 핵심 연관 키워드를 자동 추출"""
    stock_name = str(row.get("종목명", "")).strip()
    sector = str(row.get("업종명", "") or row.get("섹터", "")).strip()

    # 뉴스 제목과 본문에서 2글자 이상 명사/영문 대문자 토큰 빈도수 추출
    tokens = []
    for n in (news_list or []):
        text = f"{n.get('title', '')} {n.get('body', '')}"
        words = re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}", text)
        for w in words:
            w_clean = w.strip()
            if w_clean not in STOPWORDS and w_clean.lower() != stock_name.lower() and stock_name not in w_clean:
                tokens.append(w_clean)

    top_keywords = [word for word, cnt in Counter(tokens).most_common(6) if cnt >= 1]
    if sector:
        for s_tok in re.split(r"[/·,\s()]+", sector):
            if len(s_tok) >= 2 and s_tok not in top_keywords:
                top_keywords.insert(0, s_tok)

    # 글로벌 매크로 공통 지수(나스닥·필라델피아 반도체지수)만 연결 (개별 기업 하드코딩 제거)
    macro_tickers = ["^IXIC", "^SOX"] if any(k in sector for k in ["반도체", "IT", "전기", "전자", "소프트웨어"]) else ["^IXIC"]
    kw_preview = ", ".join(top_keywords[:4]) if top_keywords else "시장 전반"
    relation_desc = f"{sector or '전반'} 업종 · 뉴스 핵심 연관 키워드({kw_preview})"

    return {
        "tickers": macro_tickers,
        "keywords": top_keywords,
        "relation_desc": relation_desc
    }

def evaluate_stock_with_agents(
    row: pd.Series,
    news_list: list,
    consensus_data: dict,
    strictness: str = "중립 (표준 검증)",
    weights: tuple = (25, 45, 30),
    partner_news: list = None
) -> dict:
    price = row.get("현재가") or 0
    per = row.get("PER (배)")
    ind_per = row.get("업종 PER")
    peg = row.get("PEG (배)")
    roe = row.get("ROE (%)")
    eps_ttm = row.get("올해누적 EPS(TTM)")
    eps_mrq = row.get("최근분기 EPS(MRQ)")
    eps_growth = row.get("EPS 성장률(%)")
    fut_price = row.get("자체 퀀트 적정가") or row.get("미래 예상주가") or price

    # 1. AI 이코노미스트 (거시 매크로 · 지분 자산가치 · 신성장 인프라 종합 평가)
    eco_score, eco_pros, eco_cons = 65.0, [], []
    eco_links = [
        {"type": "tab", "label": "🎯 4사분면 밸류에이션 매트릭스 위치 보기", "target": "🎯 4사분면 밸류에이션 매트릭스"},
        {"type": "tab", "label": "🏛️ 동종업계 피어그룹(Comps) 멀티플 비교", "target": "🏛️ 월스트리트 IB 5대 프로 밸류에이션"}
    ]

    stock_name_ag = str(row.get("종목명", "")).strip()
    ticker_ag = str(row.get("티커", "")).strip().zfill(6)
    dvd_val = row.get("배당수익률(%)") or row.get("dividend_yield")

    # [핵심] 글로벌 AI 유니콘(엔트로픽 등) 지분투자 및 AIDC/신기술 인프라 가치 반영
    news_all_text = " ".join([f"{n.get('title','')} {n.get('body','')}" for n in (news_list or [])])
    has_ai_equity = (
        ticker_ag in ["017670", "035420", "035720", "489790"] or
        any(k in stock_name_ag for k in ["SK텔레콤", "NAVER", "카카오", "한화비전"]) or
        any(k in news_all_text for k in ["엔트로픽", "Anthropic", "람다", "지분투자", "AIDC", "데이터센터", "AI 반도체", "사피온"])
    )

    if has_ai_equity and "017670" in ticker_ag or "SK텔레콤" in stock_name_ag:
        eco_score += 18
        eco_pros.append("글로벌 AI 선두 유니콘(엔트로픽 등) 지분 투자 가치 및 AI 데이터센터(AIDC) 인프라 확장이 전통 통신주 한계를 넘어선 거시 리레이팅 촉매로 작용합니다.")
    elif has_ai_equity:
        eco_score += 10
        eco_pros.append("핵심 AI 기술 기업 지분 투자 및 미래 신성장 인프라 투자가 중장기 기업가치 리레이팅을 견인하고 있습니다.")

    # 고배당 캐시카우 매크로 방어력
    if dvd_val and pd.notnull(dvd_val) and dvd_val >= 4.5:
        eco_score += 8
        eco_pros.append(f"시중 금리를 상회하는 고배당(배당수익률 {dvd_val:.1f}%) 캐시카우가 금리 변동기 강력한 주가 하방 방어판 역할을 수행합니다.")

    if per and ind_per and pd.notnull(per) and pd.notnull(ind_per) and ind_per > 0:
        ratio = per / ind_per
        if ratio < 0.85:
            eco_score += 18
            eco_pros.append(f"동일업종 평균 PER({ind_per:.1f}배) 대비 저평가({per:.1f}배) 구간으로 리레이팅 여력이 큽니다.")
        elif ratio <= 1.15:
            eco_score += 5
            eco_pros.append(f"업종 평균 PER({ind_per:.1f}배) 부근의 합리적 멀티플({per:.1f}배)입니다.")
        else:
            eco_score -= 16
            eco_cons.append(f"업종 평균 PER({ind_per:.1f}배) 대비 할증({per:.1f}배) 거래 중으로 금리 변동 시 멀티플 축소 위험이 있습니다.")
    elif per and pd.notnull(per):
        if per < 12:
            eco_score += 14
            eco_pros.append(f"낮은 PER({per:.1f}배)로 변동성 장세에서 하방 경직성이 확보되어 있습니다.")
        elif per > 35:
            eco_score -= 15
            eco_cons.append(f"고멀티플({per:.1f}배) 구간으로 유동성 축소 시 변동성이 확대될 수 있습니다.")

    if roe is not None and pd.notnull(roe):
        if roe >= 15:
            eco_score += 8
            eco_pros.append(f"자본수익성(ROE {roe:.1f}%)이 시중 금리를 상회하여 자본비용 방어력이 뛰어납니다.")
        elif roe < 6 and not has_ai_equity:
            eco_score -= 10
            eco_cons.append(f"낮은 ROE({roe:.1f}%)로 초과수익 창출력이 부족합니다.")

    eco_score = max(15.0, min(98.0, eco_score))
    eco_stance = "찬성 (BULL)" if eco_score >= 68 else ("중립 (HOLD)" if eco_score >= 48 else "반대 (BEAR)")

    # 2. AI 애널리스트
    ana_score, ana_pros, ana_cons = 60.0, [], []
    ana_links = [
        {"type": "tab", "label": "📊 분기별 실적(EPS·영업이익) 추이 확인", "target": "📊 분기별 실적 추이 (25년~26년)"},
        {"type": "tab", "label": "📈 실시간 주가·적정가 밴드 차트 확인", "target": "📈 트렌디 실시간 인터랙티브 차트 (Pro)"}
    ]
    if peg is not None and pd.notnull(peg) and peg > 0:
        if peg < 0.8:
            ana_score += 22
            ana_pros.append(f"피터 린치 기준 초저평가 구간인 PEG {peg:.2f}배로 성장성 대비 주가가 현저히 저렴합니다.")
        elif peg <= 1.2:
            ana_score += 10
            ana_pros.append(f"PEG {peg:.2f}배로 이익 성장이 현재 밸류에이션을 정당화하고 있습니다.")
        else:
            ana_score -= 18
            ana_cons.append(f"PEG {peg:.2f}배로 이익 성장률 대비 과도한 프리미엄이 반영되어 있습니다.")

    if eps_mrq and eps_ttm and pd.notnull(eps_mrq) and pd.notnull(eps_ttm) and eps_ttm > 0:
        ann_mrq = eps_mrq * 4.0
        if ann_mrq > eps_ttm * 1.08:
            ana_score += 14
            ana_pros.append(f"최근분기 EPS 연환산치({ann_mrq:,.0f})가 누적 EPS({eps_ttm:,.0f})를 상회하며 턴어라운드 가속화 중입니다.")
        elif ann_mrq < eps_ttm * 0.85:
            ana_score -= 14
            ana_cons.append("최근분기 EPS 연환산치가 누적 평균 대비 둔화되어 단기 피크아웃 점검이 필요합니다.")

    if eps_growth is not None and pd.notnull(eps_growth):
        if eps_growth < 0:
            ana_score -= 15
            ana_cons.append(f"전년 대비 이익감소(역성장 {eps_growth:+.1f}%) 구간입니다.")
        elif eps_growth >= 20:
            ana_score += 8
            ana_pros.append(f"연간 EPS 성장률이 {eps_growth:+.1f}%로 강력한 이익 모멘텀을 보유하고 있습니다.")

    ana_score = max(15.0, min(98.0, ana_score))
    ana_stance = "찬성 (BULL)" if ana_score >= 68 else ("중립 (HOLD)" if ana_score >= 48 else "반대 (BEAR)")

    # 3. AI 저널리스트 (실시간 뉴스 + 매크로/연관 키워드 전이 리스크 판독)
    jrn_score, jrn_pros, jrn_cons = 60.0, [], []
    jrn_links = [
        {"type": "tab", "label": "📰 증권사 리포트 & 전체 뉴스 센터 이동", "target": "📰 증권사 리포트 & 실시간 뉴스"}
    ]
    pos_kw = ["수주", "최대", "급증", "호조", "상향", "돌파", "신고가", "흑자", "기대", "계약", "성장", "서프라이즈", "매수"]
    neg_kw = ["하락", "적자", "우려", "둔화", "하향", "소송", "감소", "부진", "리스크", "매도", "유상증자", "오버행", "쇼크"]
    shock_kw = ["스캔들", "사임", "불륜", "수출통제", "급락", "조사", "소송", "악재", "흔들", "scandal", "resign", "probe", "plunge", "ban"]

    vc_info = extract_dynamic_partners_from_news(row, news_list)
    seen_titles = set()
    all_articles = []
    for n in (list(news_list or []) + list(partner_news or [])):
        t = n.get("title", "").strip()
        if t and t not in seen_titles:
            seen_titles.add(t)
            all_articles.append(n)

    pos_cnt, neg_cnt = 0, 0
    spillover_articles = []
    evidence_articles = []

    for n in all_articles:
        t_raw = n.get("title", "")
        u_raw = n.get("url", "")
        m_raw = n.get("media", "뉴스")
        tb = (t_raw + " " + n.get("body", "")).lower()

        is_pos = any(kw in tb for kw in pos_kw)
        is_neg = any(kw in tb for kw in neg_kw)
        if is_pos: pos_cnt += 1
        if is_neg: neg_cnt += 1

        if vc_info["keywords"]:
            has_context = any(pk.lower() in tb for pk in vc_info["keywords"])
            has_shock = any(sk in tb for sk in shock_kw)
            if has_context and has_shock:
                spillover_articles.append(n)

        if (is_pos or is_neg) and u_raw and len(evidence_articles) < 3:
            evidence_articles.append({"type": "url", "label": f"[{m_raw}] {t_raw[:44]}...", "url": u_raw})

    if spillover_articles:
        deduct = min(24, len(spillover_articles) * 12)
        jrn_score -= deduct
        top_sp = spillover_articles[0]
        jrn_cons.append(
            f"[대외/연관 이슈 전이 리스크] {vc_info['relation_desc']} 관련 부정 이슈 포착: '{top_sp.get('title', '')[:40]}...'"
        )
        if top_sp.get("url"):
            jrn_links.insert(0, {"type": "url", "label": f"🚨 [전이악재 원문] {top_sp.get('title', '')[:42]}...", "url": top_sp["url"]})

    for ev in evidence_articles:
        if len(jrn_links) < 4:
            jrn_links.append(ev)

    if pos_cnt > neg_cnt + 1:
        jrn_score += min(16, (pos_cnt - neg_cnt) * 3)
        jrn_pros.append(f"최근 뉴스 긍정 키워드({pos_cnt}건)가 부정 요인({neg_cnt}건)을 압도합니다.")
    elif neg_cnt > pos_cnt:
        jrn_score -= min(16, (neg_cnt - pos_cnt) * 4)
        jrn_cons.append(f"최근 뉴스에서 우려/둔화 키워드({neg_cnt}건)가 포착되어 단기 차익실현 매물 주의가 필요합니다.")
    elif not spillover_articles:
        jrn_pros.append("뉴스 및 언론 보도 흐름은 중립적 수급 균형을 유지하고 있습니다.")

    cns_up = consensus_data.get("upside_percent")
    tp_str = consensus_data.get("target_price_str", "")
    if cns_up is not None and pd.notnull(cns_up):
        if cns_up >= 20.0:
            jrn_score += 8
            jrn_pros.append(f"증권사 평균 목표주가({tp_str}) 대비 +{cns_up:.1f}%의 상승여력이 존재합니다.")
        elif cns_up <= 0:
            jrn_score -= 15
            jrn_cons.append(f"현재 주가가 증권사 목표주가({tp_str})에 이미 도달({cns_up:+.1f}%)하여 호재 선반영 주의가 필요합니다.")

    jrn_score = max(15.0, min(98.0, jrn_score))
    jrn_stance = "찬성 (BULL)" if jrn_score >= 68 else ("중립 (HOLD)" if jrn_score >= 48 else "반대 (BEAR)")

    # 4. CIO 종합 판정
    w_eco, w_ana, w_jrn = weights
    tot_w = max(1, w_eco + w_ana + w_jrn)
    raw_cio = (eco_score * w_eco + ana_score * w_ana + jrn_score * w_jrn) / tot_w

    stances = [eco_stance, ana_stance, jrn_stance]
    bear_count = sum(1 for s in stances if "반대" in s)
    bull_count = sum(1 for s in stances if "찬성" in s)

    penalty = bear_count * (7.5 if "보수적" in strictness else (4.0 if "중립" in strictness else 1.5))
    if spillover_articles:
        penalty += 5.0

    cio_score = round(max(15.0, min(99.0, raw_cio - penalty)), 1)

    if cio_score >= 78 and bear_count == 0 and not spillover_articles:
        verdict, v_color = "🔥 강력 매수 (STRONG BUY)", "#10b981"
    elif cio_score >= 64:
        verdict, v_color = "📈 분할 매수 (BUY)", "#38bdf8"
    elif cio_score >= 48:
        verdict, v_color = "⚖️ 관망 및 보류 (HOLD)", "#f59e0b"
    else:
        verdict, v_color = "🚨 비중 축소 / 반대 (SELL WARNING)", "#f43f5e"

    base_tp = fut_price if (fut_price and fut_price > 0) else price
    adj_factor = 1.0 + ((cio_score - 60.0) / 240.0)
    if spillover_articles:
        adj_factor *= 0.90

    base_target = round(base_tp * adj_factor, 2)
    bull_target = round(base_target * 1.18, 2)

    pbr = row.get("pbr")
    downside_discount = 0.12
    if roe and pd.notnull(roe):
        if roe >= 20.0: downside_discount -= 0.04
        elif roe >= 12.0: downside_discount -= 0.02
        elif roe < 5.0: downside_discount += 0.05

    if per and pd.notnull(per) and per > 0:
        if per < 10.0: downside_discount -= 0.03
        elif per > 35.0: downside_discount += 0.06
        elif per > 25.0: downside_discount += 0.03

    if eps_growth and pd.notnull(eps_growth) and eps_growth < 0:
        downside_discount += 0.06
    elif peg and pd.notnull(peg) and peg < 0.8:
        downside_discount -= 0.02

    if spillover_articles:
        downside_discount += 0.04

    downside_discount = max(0.06, min(0.35, downside_discount))

    if pbr and pd.notnull(pbr) and pbr > 0:
        bps = price / pbr
        bear_calc = max(bps * 0.88, price * (1.0 - downside_discount)) if pbr < 1.0 else price * (1.0 - downside_discount)
    else:
        bear_calc = price * (1.0 - downside_discount)

    bear_target = round(min(bear_calc, base_target * 0.85), 2)

    if pbr and pd.notnull(pbr) and pbr < 1.1:
        bear_basis = f"PBR({pbr:.2f}배) 순자산 장부가치 바닥 및 하방 경직성 방어선"
    elif roe and pd.notnull(roe) and roe >= 15.0 and (per and per < 15.0):
        bear_basis = f"고ROE({roe:.1f}%) 퀄리티 및 저PER 절대가치 안전마진 지지선"
    elif per and pd.notnull(per) and per > 30.0:
        bear_basis = f"고멀티플(PER {per:.1f}배) 밸류에이션 수축 리스크 반영 지지선"
    elif eps_growth and pd.notnull(eps_growth) and eps_growth < 0:
        bear_basis = f"이익감소({eps_growth:+.1f}%) 시나리오 하방 압력 반영 지지선"
    else:
        bear_basis = "업종 평균 멀티플 및 중기 수급선 기반 복합 지지선"

    cio_summary = f"합동 심의 결과: 찬성 {bull_count}명 · 중립 {3 - bull_count - bear_count}명 · 반대 {bear_count}명. "
    if spillover_articles:
        cio_summary += f"본업 실적과 별개로 뉴스에서 포착된 대외 연관 이슈({vc_info['relation_desc']})의 충격이 감지되어 저널리스트의 반대(Bear) 의견을 반영, 목표주가를 10% 보수적으로 할인 조정했습니다."
    elif bear_count >= 2:
        cio_summary += "복수의 에이전트가 리스크를 경고하고 있어 보수적 관리가 우선입니다."
    elif bear_count == 1:
        cio_summary += "일부 에이전트가 반대 논거를 제시했으므로 조정 시 분할 매수 전략이 유효합니다."
    else:
        cio_summary += "거시 환경, 밸류에이션, 뉴스 센티먼트 모두 긍정적 정합성을 보여 주도주 편입에 적합합니다."

    return {
        "economist": {"score": round(eco_score, 1), "stance": eco_stance, "pros": eco_pros, "cons": eco_cons, "links": eco_links},
        "analyst": {"score": round(ana_score, 1), "stance": ana_stance, "pros": ana_pros, "cons": ana_cons, "links": ana_links},
        "journalist": {"score": round(jrn_score, 1), "stance": jrn_stance, "pros": jrn_pros, "cons": jrn_cons, "links": jrn_links},
        "cio": {
            "score": cio_score, "verdict": verdict, "color": v_color,
            "summary": cio_summary, "bull_count": bull_count, "bear_count": bear_count,
            "bear_target": bear_target, "base_target": base_target, "bull_target": bull_target,
            "bear_basis": bear_basis
        }
    }