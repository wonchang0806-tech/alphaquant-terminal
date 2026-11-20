import os
from dotenv import load_dotenv

load_dotenv()

KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_IS_VIRTUAL = os.getenv("KIS_IS_VIRTUAL", "False").lower() == "true"

DEFAULT_STOCKS = {
    "국내 주식 (KRX)": [
        {"name": "삼성전자", "ticker": "005930"},
        {"name": "SK하이닉스", "ticker": "000660"},
        {"name": "현대차", "ticker": "005380"},
        {"name": "기아", "ticker": "000270"},
        {"name": "한화비전", "ticker": "489790"},
        {"name": "삼성바이오로직스", "ticker": "207940"},
        {"name": "LG에너지솔루션", "ticker": "373220"},
        {"name": "현대모비스", "ticker": "012330"},
        {"name": "NAVER", "ticker": "035420"},
        {"name": "카카오", "ticker": "035720"},
        {"name": "셀트리온", "ticker": "068270"},
        {"name": "알테오젠", "ticker": "196170"},
        {"name": "신성델타테크", "ticker": "065350"},
        {"name": "한미반도체", "ticker": "042700"},
        {"name": "포스코홀딩스", "ticker": "005490"},
        {"name": "KB금융", "ticker": "105560"},
    ],
    "해외 주식 (미국)": [
        {"name": "NVIDIA", "ticker": "NVDA"},
        {"name": "Apple", "ticker": "AAPL"},
        {"name": "Microsoft", "ticker": "MSFT"},
        {"name": "Alphabet (Google)", "ticker": "GOOGL"},
        {"name": "Amazon", "ticker": "AMZN"},
        {"name": "Meta", "ticker": "META"},
        {"name": "TSMC", "ticker": "TSM"},
        {"name": "Broadcom", "ticker": "AVGO"},
        {"name": "Tesla", "ticker": "TSLA"},
        {"name": "Eli Lilly", "ticker": "LLY"},
        {"name": "Palantir", "ticker": "PLTR"},
        {"name": "AMD", "ticker": "AMD"},
    ],
}
