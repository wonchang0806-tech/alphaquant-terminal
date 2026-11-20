with open("data_loader.py", "r", encoding="utf-8") as f:
    text = f.read().replace("\r\n", "\n")

extra_code = """

# -------------------------------------------------------------
# 🌐 코스피 / 코스닥 전 시장 텐버거 & 턴어라운드 후보 발굴 유니버스
# -------------------------------------------------------------
KRX_WIDE_CANDIDATES = [
    # 반도체 장비/소재 (턴어라운드 및 AI 슈퍼사이클)
    {"name": "서진시스템", "ticker": "178320"},
    {"name": "한미반도체", "ticker": "042700"},
    {"name": "ISC", "ticker": "095340"},
    {"name": "유진테크", "ticker": "084370"},
    {"name": "주성엔지니어링", "ticker": "036930"},
    {"name": "원익IPS", "ticker": "240810"},
    {"name": "피에스케이", "ticker": "319660"},
    {"name": "하나마이크론", "ticker": "067310"},
    {"name": "파크시스템스", "ticker": "140860"},
    {"name": "동진쎄미켐", "ticker": "005290"},
    # 전력인프라 & 전선 & 원전 (글로벌 슈퍼사이클)
    {"name": "HD현대일렉트릭", "ticker": "267260"},
    {"name": "효성중공업", "ticker": "298040"},
    {"name": "LS ELECTRIC", "ticker": "010120"},
    {"name": "대한전선", "ticker": "001440"},
    {"name": "일진전기", "ticker": "103590"},
    {"name": "두산에너빌리티", "ticker": "034020"},
    # 방산 & 우주항공 (사상 최대 수주잔고)
    {"name": "한화에어로스페이스", "ticker": "012450"},
    {"name": "현대로템", "ticker": "064350"},
    {"name": "LIG넥스원", "ticker": "079550"},
    {"name": "한화시스템", "ticker": "272210"},
    {"name": "한국항공우주", "ticker": "047810"},
    # K-푸드 & 수출 소비재 퀀텀점프
    {"name": "삼양식품", "ticker": "003230"},
    {"name": "농심", "ticker": "004370"},
    {"name": "CJ제일제당", "ticker": "097950"},
    {"name": "실리콘투", "ticker": "257720"},
    {"name": "한국콜마", "ticker": "161890"},
    {"name": "코스맥스", "ticker": "192820"},
    # 로봇 & AI 하드웨어
    {"name": "레인보우로보틱스", "ticker": "277810"},
    {"name": "두산로보틱스", "ticker": "454910"},
    # 바이오 & 헬스케어 턴어라운드
    {"name": "알테오젠", "ticker": "196170"},
    {"name": "리가켐바이오", "ticker": "141080"},
    {"name": "에스티팜", "ticker": "237690"},
    {"name": "삼천당제약", "ticker": "000250"},
    {"name": "휴젤", "ticker": "145020"},
    # 딥밸류 청산가치 & 밸류업 금융/지주
    {"name": "한국타이어앤테크놀로지", "ticker": "161390"},
    {"name": "기업은행", "ticker": "024110"},
    {"name": "우리금융지주", "ticker": "316140"},
    {"name": "BNK금융지주", "ticker": "138930"},
    {"name": "영원무역", "ticker": "111770"},
    {"name": "F&F", "ticker": "383220"},
    {"name": "현대엘리베이터", "ticker": "017800"},
]

def scan_krx_wide_tenbaggers() -> pd.DataFrame:
    \"\"\"코스피/코스닥 전 시장 40대 핵심 가치/성장/턴어라운드 후보군 초고속 병렬 스캔\"\"\"
    return fetch_market_data_parallel("국내 주식 (KRX)", KRX_WIDE_CANDIDATES)
"""

if "def scan_krx_wide_tenbaggers" not in text:
    text = text + extra_code
    with open("data_loader.py", "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    print("SUCCESS")
else:
    print("ALREADY EXISTS")
