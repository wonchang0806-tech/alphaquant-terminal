import streamlit as st

def apply_custom_styles():
    st.markdown("""
    <style>
    .stAppToolbar, #MainMenu, header[data-testid='stHeader'] { display: none !important; }
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700&display=swap');
        html, body, [class*="css"], .stMarkdown { font-family: 'Pretendard', sans-serif; }
        
        /* 전체 배경 다크 고정 */
        [data-testid="stAppViewContainer"], .stApp {
            background-color: #070b13 !important;
            color: #f1f5f9 !important;
        }
        [data-testid="stHeader"] {
            background-color: rgba(7, 11, 19, 0.85) !important;
        }
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 3rem !important;
            max-width: 96% !important;
        }

        /* 메인 영역 모든 입력창/셀렉트박스 라벨 글씨 선명화 */
        [data-testid="stMain"] [data-testid="stWidgetLabel"] p,
        [data-testid="stMain"] [data-testid="stWidgetLabel"] span,
        [data-testid="stMain"] label {
            color: #cbd5e1 !important;
            font-weight: 700 !important;
        }

        /* 1. 상단 히어로 배너 */
        .hero-container {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
            border: 1px solid rgba(99, 102, 241, 0.45);
            border-radius: 16px;
            padding: clamp(14px, 2vw, 22px) clamp(16px, 2.5vw, 28px);
            margin-bottom: 14px;
            box-shadow: 0 15px 35px -10px rgba(0, 0, 0, 0.6);
        }
        .hero-badge {
            display: inline-flex; align-items: center; gap: 6px;
            background: rgba(99, 102, 241, 0.25); border: 1px solid #6366f1; color: #c7d2fe;
            padding: 4px 12px; border-radius: 9999px; font-size: 0.78rem; font-weight: 800;
        }
        .hero-title {
            font-size: clamp(1.2rem, 2.1vw, 1.85rem);
            font-weight: 900; color: #ffffff; margin: 8px 0 6px 0; line-height: 1.3;
        }
        .hero-subtitle {
            color: #cbd5e1; font-size: clamp(0.84rem, 1.1vw, 0.95rem); line-height: 1.5;
        }

        /* 2. 자동 맞춤(Auto-Fit) KPI 그리드 */
        .kpi-auto-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 14px;
            margin-bottom: 16px;
        }
        .kpi-card {
            background: rgba(22, 27, 34, 0.95);
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 14px;
            padding: 16px 18px;
            min-width: 0;
        }
        .kpi-label {
            font-size: 0.82rem; color: #94a3b8; font-weight: 700;
            display: flex; justify-content: space-between; align-items: center;
        }
        .kpi-val {
            font-size: clamp(1.3rem, 1.7vw, 1.8rem);
            font-weight: 800; color: #ffffff; margin: 6px 0 4px 0;
            font-family: 'JetBrains Mono', monospace;
        }
        .kpi-sub {
            font-size: 0.78rem; color: #38bdf8; font-weight: 600;
        }

        /* 3. 리포트 & 뉴스 & 근거 링크 카드 */
        .report-box {
            background: #111827 !important; border: 1px solid #374151 !important;
            border-radius: 12px; padding: 14px 18px; margin-bottom: 10px;
        }
        .report-box:hover { border-color: #6366f1 !important; background: #162032 !important; }
        .report-title-link { color: #f8fafc !important; font-size: 1.0rem; font-weight: 700; text-decoration: none; }
        .report-title-link:hover { color: #38bdf8 !important; }
        .broker-badge { background: rgba(99, 102, 241, 0.25); color: #a5b4fc; border: 1px solid #6366f1; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; }
        .news-title-link { color: #f1f5f9 !important; font-size: 0.94rem; font-weight: 600; text-decoration: none; }
        .news-title-link:hover { color: #34d399 !important; }

        .evidence-link {
            display: block;
            background: #0f172a;
            border: 1px solid rgba(56, 189, 248, 0.4);
            border-radius: 8px;
            padding: 9px 12px;
            margin-top: 6px;
            color: #7dd3fc !important;
            font-size: 0.82rem;
            font-weight: 600;
            text-decoration: none;
            line-height: 1.4;
        }
        .evidence-link:hover {
            border-color: #38bdf8;
            background: rgba(56, 189, 248, 0.18);
            color: #ffffff !important;
        }

        .sweet-card {
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.14) 0%, rgba(15, 23, 42, 0.95) 100%);
            border: 1px solid rgba(16, 185, 129, 0.45); border-radius: 12px; padding: 14px 18px; margin-bottom: 12px;
        }

        .chart-info-banner {
            background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 12px; padding: 14px 18px; margin-bottom: 14px;
            display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 14px;
        }
        .chart-info-item { display: flex; flex-direction: column; }
        .chart-info-item span:first-child { font-size: 0.75rem; color: #94a3b8; font-weight: 600; }
        .chart-info-item span:last-child { font-size: 1.05rem; color: #ffffff; font-weight: 800; font-family: 'JetBrains Mono', monospace; }

        /* 4. 메인 영역 라디오 버튼 고대비(흰색 글씨) */
        [data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] {
            display: flex !important;
            flex-wrap: wrap !important;
            gap: 8px !important;
        }
        [data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] > label {
            background-color: #161f33 !important;
            border: 1px solid #3b4963 !important;
            border-radius: 10px !important;
            padding: 8px 14px !important;
            margin: 0 !important;
            cursor: pointer !important;
        }
        [data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] > label:hover {
            border-color: #818cf8 !important;
            background-color: #1e293b !important;
        }
        [data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] > label * {
            color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 0.86rem !important;
        }
        [data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
            background-color: #4338ca !important;
            border-color: #a5b4fc !important;
            box-shadow: 0 0 12px rgba(99, 102, 241, 0.45) !important;
        }

        /* 5. [수정] 일반 버튼 + 다운로드 버튼(CSV 저장) 모두 다크 고대비 통일 */
        [data-testid="stMain"] [data-testid="stButton"] button,
        [data-testid="stMain"] [data-testid="stDownloadButton"] button {
            background-color: #1e293b !important;
            color: #ffffff !important;
            border: 1px solid #475569 !important;
            border-radius: 10px !important;
            padding: 8px 14px !important;
            min-height: 40px !important;
            white-space: nowrap !important;
        }
        [data-testid="stMain"] [data-testid="stButton"] button *,
        [data-testid="stMain"] [data-testid="stDownloadButton"] button * {
            color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 0.84rem !important;
        }
        [data-testid="stMain"] [data-testid="stButton"] button:hover,
        [data-testid="stMain"] [data-testid="stDownloadButton"] button:hover {
            background-color: #334155 !important;
            border-color: #38bdf8 !important;
        }
        [data-testid="stMain"] [data-testid="stButton"] button[kind="primary"] {
            background-color: #4f46e5 !important;
            border-color: #818cf8 !important;
        }

        /* 6. [수정] 접기/펼치기(Expander) 헤더 다크 고대비 테마 */
        [data-testid="stMain"] [data-testid="stExpander"] {
            background-color: #0f172a !important;
            border: 1px solid #334155 !important;
            border-radius: 12px !important;
        }
        [data-testid="stMain"] [data-testid="stExpander"] details summary {
            background-color: #162032 !important;
            color: #f8fafc !important;
            border-radius: 11px !important;
            padding: 10px 14px !important;
        }
        [data-testid="stMain"] [data-testid="stExpander"] details summary * {
            color: #f8fafc !important;
            font-weight: 800 !important;
        }
        [data-testid="stMain"] [data-testid="stExpander"] details summary svg {
            fill: #38bdf8 !important;
            color: #38bdf8 !important;
        }

        /* 7. 반쪽 창 / 좁은 화면(1200px 이하)에서 컬럼 자동 줄바꿈 */
        @media (max-width: 1200px) {
            [data-testid="stMain"] [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 12px !important;
            }
            [data-testid="stMain"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
            [data-testid="stMain"] [data-testid="stHorizontalBlock"] > [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)