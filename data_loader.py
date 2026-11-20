import json

def _restore_cloud_stock_lists():
    try:
        import streamlit as _st
        for fn, key in [("custom_stocks.json", "CUSTOM_STOCKS_JSON"), ("excluded_stocks.json", "EXCLUDED_STOCKS_JSON")]:
            if not os.path.exists(fn) and key in _st.secrets:
                raw = _st.secrets[key]
                data = json.loads(raw) if isinstance(raw, str) else raw
                with open(fn, "w", encoding="utf-8") as wf:
                    json.dump(data, wf, ensure_ascii=False, indent=2)
    except Exception:
        pass

_restore_cloud_stock_lists()

import html
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import FinanceDataReader as fdr
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yfinance as yf

def get_session():
    session = requests.Session()
    retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=25, pool_maxsize=25)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    return session

GLOBAL_SESSION = get_session()
_KRX_LISTING_CACHE = None

# KRX 주요 대표 종목 섹터 사전 (초고속 즉시 매핑 & 오프라인 대비)
KRX_SECTOR_MAP = {
    "005930": "반도체·전자", "000660": "반도체·메모리", "005380": "자동차·모빌리티",
    "000270": "자동차·모빌리티", "012330": "자동차부품", "035900": "엔터·콘텐츠",
    "017670": "통신·AI인프라", "035420": "인터넷·클라우드", "035720": "인터넷·플랫폼",
    "068270": "바이오·시밀러", "207940": "바이오·CDMO", "196170": "바이오·신약",
    "005490": "철강·2차전지소재", "105560": "금융·지주", "373220": "2차전지·배터리",
    "042700": "반도체장비", "065350": "전자부품·신소재", "489790": "보안·AI비전",
    "009830": "태양광·케미칼", "000880": "방산·화학", "012450": "방산·항공우주",
    "042660": "조선·해양", "272210": "방산·ICT", "088350": "보험·금융",
    "082740": "조선엔진", "003530": "증권·금융", "451800": "부동산리츠"
}

def get_krx_sector(ticker: str) -> str:
    """KRX 종목의 정확한 표준 산업 업종(WICS)을 실시간 조회 및 매핑"""
    clean = str(ticker).strip().zfill(6)
    if clean in KRX_SECTOR_MAP:
        return KRX_SECTOR_MAP[clean]
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.daum.net"
        }
        r = requests.get(f"https://finance.daum.net/api/quotes/A{clean}", headers=headers, timeout=2.5)
        if r.status_code == 200:
            d = r.json()
            sec = d.get("wicsSectorName") or d.get("sectorName")
            if sec and sec.lower() not in ["stock", "국내상장사"]:
                return sec
    except Exception:
        pass
    return "제조·서비스"

def get_krx_listing():
    global _KRX_LISTING_CACHE
    if _KRX_LISTING_CACHE is None or _KRX_LISTING_CACHE.empty:
        try:
            df = fdr.StockListing("KRX")
            _KRX_LISTING_CACHE = df[["Code", "Name", "Market"]]
        except Exception:
            _KRX_LISTING_CACHE = pd.DataFrame()
    return _KRX_LISTING_CACHE

def find_krx_stock(query: str):
    if not query: return []
    df = get_krx_listing()
    if df.empty: return []
    q = query.strip()
    match = df[df["Name"].str.contains(q, case=False, na=False) | df["Code"].str.contains(q, na=False)]
    res = []
    for _, r in match.head(10).iterrows():
        res.append({"name": r["Name"], "ticker": r["Code"], "market": r["Market"]})
    return res

def _safe_float(val):
    if val is None: return None
    try:
        clean_str = str(val).replace(",", "").replace("%", "").replace("배", "").replace("원", "").replace("억원", "").strip()
        if not clean_str or clean_str in ["-", "N/A", "nan", "None"]: return None
        res = float(clean_str)
        return None if math.isnan(res) or math.isinf(res) else res
    except Exception:
        return None

def fetch_naver_financials(ticker: str) -> dict:
    clean_ticker = ticker.strip().zfill(6)
    res_data = {
        "price": None, "per_ttm": None, "eps_last_yr": None, "eps_ttm": None, "eps_mrq": None,
        "eps_forward": None, "industry_per": None, "industry_name": "", "peers": [],
        "roe": None, "pbr": None, "eps_growth": None, "dividend_yield": None, "dps": None
    }
    session = GLOBAL_SESSION
    
    # 1. 기본 시세 및 업종명 추출
    try:
        r_basic = session.get(f"https://m.stock.naver.com/api/stock/{clean_ticker}/basic", timeout=3.5)
        if r_basic.status_code == 200:
            b_json = r_basic.json()
            now_p = _safe_float(b_json.get("nowPrice"))
            close_p = _safe_float(b_json.get("closePrice"))
            res_data["price"] = now_p if now_p is not None else close_p
            ind_b = b_json.get("industryName") or b_json.get("sectorName") or ""
            if ind_b and ind_b.lower() != "stock":
                res_data["industry_name"] = ind_b
    except Exception:
        pass

    # 2. 통합 지표 및 실제 동일업종 비교군(compareList) 추출
    try:
        r_int = session.get(f"https://m.stock.naver.com/api/stock/{clean_ticker}/integration", timeout=3.5)
        if r_int.status_code == 200:
            i_json = r_int.json()
            info_map = {item.get("code"): item.get("value") for item in i_json.get("totalInfos", [])}
            res_data["per_ttm"] = _safe_float(info_map.get("per"))
            res_data["eps_ttm"] = _safe_float(info_map.get("eps"))
            res_data["pbr"] = _safe_float(info_map.get("pbr"))
            res_data["industry_per"] = _safe_float(info_map.get("industryPer") or info_map.get("sameIndustryPer"))
            res_data["dividend_yield"] = _safe_float(info_map.get("dvdYld") or info_map.get("dividendYield"))
            res_data["dps"] = _safe_float(info_map.get("dvd") or info_map.get("dps"))
            if res_data["price"] is None:
                res_data["price"] = _safe_float(info_map.get("lastClosePrice"))

            # 실제 동일업종 비교 종목 및 업종명 추출
            comp_info = i_json.get("industryCompareInfo") or {}
            if not res_data["industry_name"]:
                ind_c = comp_info.get("industryName") or info_map.get("industryName") or ""
                if ind_c and ind_c.lower() != "stock":
                    res_data["industry_name"] = ind_c

            raw_peers = comp_info.get("compareList") or i_json.get("compareList") or []
            peers_clean = []
            for p_item in raw_peers:
                p_code = str(p_item.get("itemCode") or p_item.get("code") or "").strip()
                p_name = str(p_item.get("itemName") or p_item.get("name") or "").strip()
                if p_code and p_name and p_code != clean_ticker:
                    peers_clean.append({"name": p_name, "ticker": p_code})
            res_data["peers"] = peers_clean[:5]
    except Exception:
        pass

    # 3. 연간 재무제표
    try:
        r_ann = session.get(f"https://m.stock.naver.com/api/stock/{clean_ticker}/finance/annual", timeout=3.5)
        if r_ann.status_code == 200:
            a_json = r_ann.json()
            fin = a_json.get("financeInfo", {})
            tr_list = fin.get("trTitleList", [])
            valid_keys = [t.get("key") for t in tr_list if t.get("key")]
            cns_keys = [t.get("key") for t in tr_list if t.get("isConsensus") == "Y" and t.get("key")]
            for row in fin.get("rowList", []):
                t = str(row.get("title", "")).strip()
                cols = row.get("columns", {})
                if t == "ROE":
                    for k in reversed(valid_keys):
                        v = _safe_float(cols.get(k, {}).get("value"))
                        if v is not None:
                            res_data["roe"] = v
                            break
                elif t == "EPS":
                    for ck in cns_keys:
                        cv = _safe_float(cols.get(ck, {}).get("value"))
                        if cv is not None:
                            res_data["eps_forward"] = cv
                            break
                    eps_series = [_safe_float(cols.get(k, {}).get("value")) for k in valid_keys if k not in cns_keys]
                    eps_series = [v for v in eps_series if v is not None]
                    if len(eps_series) >= 2:
                        res_data["eps_last_yr"] = eps_series[-2]
                        if res_data["eps_ttm"] is None: res_data["eps_ttm"] = eps_series[-1]
                    elif len(eps_series) == 1:
                        if res_data["eps_last_yr"] is None: res_data["eps_last_yr"] = eps_series[0]
                        if res_data["eps_ttm"] is None: res_data["eps_ttm"] = eps_series[0]
                elif "주당배당금" in t or "배당금" in t:
                    for k in reversed(valid_keys):
                        v = _safe_float(cols.get(k, {}).get("value"))
                        if v is not None:
                            res_data["dps"] = v
                            break
                elif "시가배당률" in t or "배당수익률" in t:
                    for k in reversed(valid_keys):
                        v = _safe_float(cols.get(k, {}).get("value"))
                        if v is not None:
                            res_data["dividend_yield"] = v
                            break
    except Exception:
        pass

    # 4. 분기 재무제표
    try:
        r_q = session.get(f"https://m.stock.naver.com/api/stock/{clean_ticker}/finance/quarter", timeout=3.5)
        if r_q.status_code == 200:
            q_json = r_q.json()
            fin_q = q_json.get("financeInfo", {})
            tr_q = fin_q.get("trTitleList", [])
            q_keys = [t.get("key") for t in tr_q if t.get("key")]
            for row in fin_q.get("rowList", []):
                if str(row.get("title", "")).strip() == "EPS":
                    cols = row.get("columns", {})
                    for k in reversed(q_keys):
                        v = _safe_float(cols.get(k, {}).get("value"))
                        if v is not None:
                            res_data["eps_mrq"] = v
                            break
    except Exception:
        pass

    if res_data["eps_last_yr"] and res_data["eps_last_yr"] > 0 and res_data["eps_ttm"]:
        res_data["eps_growth"] = round(((res_data["eps_ttm"] - res_data["eps_last_yr"]) / abs(res_data["eps_last_yr"])) * 100, 1)

    if res_data.get("dividend_yield") is None and res_data.get("dps") and res_data.get("price") and res_data["price"] > 0:
        res_data["dividend_yield"] = round((res_data["dps"] / res_data["price"]) * 100.0, 2)

    if res_data["price"] is None:
        try:
            df_fdr = fdr.DataReader(clean_ticker)
            if not df_fdr.empty: res_data["price"] = float(df_fdr["Close"].iloc[-1])
        except Exception:
            pass
    return res_data

def fetch_single_stock(market_type: str, item: dict, kis_client=None) -> dict:
    name = item["name"]
    ticker = str(item["ticker"]).strip()
    price, per, peg, roe = None, None, None, None
    eps_last_yr, eps_ttm, eps_mrq, eps_growth = None, None, None, None
    eps_forward, industry_per, industry_name = None, None, ""
    pbr, dividend_yield, dps, peers = None, None, None, []

    if kis_client and kis_client.access_token and market_type == "국내 주식 (KRX)":
        try:
            kis_res = kis_client.get_stock_price(ticker.zfill(6))
            if kis_res and not kis_res.get("error"):
                price = kis_res.get("current_price")
                per = kis_res.get("per")
                eps_ttm = kis_res.get("eps")
        except Exception:
            pass

    if market_type == "국내 주식 (KRX)":
        clean_ticker = ticker.zfill(6)
        nv = fetch_naver_financials(clean_ticker)
        if price is None: price = nv["price"]
        if per is None: per = nv["per_ttm"]
        if eps_ttm is None: eps_ttm = nv["eps_ttm"]
        eps_last_yr = nv["eps_last_yr"]
        eps_mrq = nv["eps_mrq"]
        roe = nv["roe"]
        eps_growth = nv["eps_growth"]
        eps_forward = nv.get("eps_forward")
        industry_per = nv.get("industry_per")
        industry_name = item.get("sector") or nv.get("industry_name")
        if not industry_name or industry_name in ["국내상장사", "stock", "Stock"]:
            industry_name = get_krx_sector(clean_ticker)
        peers = nv.get("peers", [])
        pbr = nv.get("pbr")
        dividend_yield = nv.get("dividend_yield")
        dps = nv.get("dps")
    else:
        try:
            t_obj = yf.Ticker(ticker)
            info = t_obj.info or {}
            price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose"))
            per = _safe_float(info.get("trailingPE") or info.get("forwardPE"))
            eps_ttm = _safe_float(info.get("trailingEps") or info.get("forwardEps"))
            eps_last_yr = _safe_float(info.get("trailingEps"))
            eps_mrq = _safe_float(info.get("epsCurrentYear")) or (round(eps_ttm / 4.0, 2) if eps_ttm else None)
            eps_forward = _safe_float(info.get("forwardEps"))
            industry_per = _safe_float(info.get("forwardPE"))
            industry_name = info.get("industry") or info.get("sector") or "US Equity"
            roe_raw = _safe_float(info.get("returnOnEquity"))
            if roe_raw is not None: roe = round(roe_raw * 100, 2) if roe_raw < 5 else round(roe_raw, 2)
            eg_raw = _safe_float(info.get("earningsGrowth"))
            if eg_raw is not None: eps_growth = round(eg_raw * 100, 1) if eg_raw < 10 else round(eg_raw, 1)
            peg = _safe_float(info.get("pegRatio"))
            pbr = _safe_float(info.get("priceToBook"))
            dvd_raw = _safe_float(info.get("dividendYield"))
            if dvd_raw is not None: dividend_yield = round(dvd_raw * 100.0, 2) if dvd_raw < 0.5 else round(dvd_raw, 2)
            dps = _safe_float(info.get("dividendRate"))
        except Exception:
            pass

    if price and per and (eps_ttm is None or eps_ttm <= 0): eps_ttm = round(price / per, 2)
    elif price and eps_ttm and eps_ttm > 0 and (per is None or per <= 0): per = round(price / eps_ttm, 2)

    if eps_last_yr is None and eps_ttm is not None: eps_last_yr = round(eps_ttm * 0.90, 2)
    if eps_mrq is None and eps_ttm is not None: eps_mrq = round(eps_ttm * 0.26, 2)
    if eps_growth is None and eps_last_yr and eps_last_yr > 0 and eps_ttm:
        eps_growth = round(((eps_ttm - eps_last_yr) / abs(eps_last_yr)) * 100, 1)
    if (peg is None or peg <= 0) and per and per > 0:
        peg = round(per / (eps_growth if (eps_growth and eps_growth > 5) else 15.0), 2)

    if eps_forward is None or eps_forward <= 0:
        eps_forward = round(eps_ttm * (1.0 + max(-25.0, min(eps_growth if eps_growth else 12.0, 50.0)) / 100.0), 2) if eps_ttm else eps_ttm

    return {
        "종목명": name, "티커": ticker,
        "현재가": round(float(price), 2) if price is not None else None,
        "미래 예상 EPS": round(float(eps_forward), 2) if eps_forward is not None else None,
        "PER (배)": round(float(per), 2) if per is not None else None,
        "작년 EPS": round(float(eps_last_yr), 2) if eps_last_yr is not None else None,
        "올해누적 EPS(TTM)": round(float(eps_ttm), 2) if eps_ttm is not None else None,
        "최근분기 EPS(MRQ)": round(float(eps_mrq), 2) if eps_mrq is not None else None,
        "EPS 성장률(%)": eps_growth, "PEG (배)": round(float(peg), 2) if peg is not None else None,
        "ROE (%)": round(float(roe), 2) if roe is not None else None,
        "PBR (배)": round(float(pbr), 2) if pbr is not None else None,
        "pbr": round(float(pbr), 2) if pbr is not None else None,
        "배당수익률(%)": round(float(dividend_yield), 2) if dividend_yield is not None else None,
        "주당배당금": round(float(dps), 2) if dps is not None else None,
        "업종 PER": round(float(industry_per), 2) if industry_per is not None else None,
        "업종명": industry_name,
        "동종업종_경쟁사": peers,
        "섹터": item.get("sector", industry_name or "주도성장주"),
    }

def fetch_market_data_parallel(market_type: str, stock_items: list, kis_client=None) -> pd.DataFrame:
    results = []
    max_workers = min(16, max(len(stock_items), 1))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(fetch_single_stock, market_type, item, kis_client): item for item in stock_items}
        for future in as_completed(future_map):
            try:
                data = future.result()
                if data: results.append(data)
            except Exception:
                pass
    order_map = {str(item["ticker"]).strip(): idx for idx, item in enumerate(stock_items)}
    results.sort(key=lambda x: order_map.get(str(x.get("티커", "")).strip(), 999))
    return pd.DataFrame(results)

def calculate_scores(df: pd.DataFrame, w_per: float, w_peg: float, w_roe: float, w_eps: float) -> pd.DataFrame:
    if df.empty:
        df["종합 스코어"] = 50.0
        return df
    out_df = df.copy()
    
    def score_per(val):
        if pd.isnull(val) or val <= 0: return 15.0
        if 4.0 <= val <= 13.0: return 95.0 - (val - 4.0) * 0.5
        elif 13.0 < val <= 22.0: return 90.0 - (val - 13.0) * 1.8
        elif 22.0 < val <= 35.0: return 73.0 - (val - 22.0) * 1.5
        elif 35.0 < val <= 60.0: return 53.0 - (val - 35.0) * 0.8
        else: return max(15.0, 33.0 - (val - 60.0) * 0.2)

    def score_peg(val):
        if pd.isnull(val) or val <= 0: return 25.0
        if val <= 0.4: return 98.0
        elif 0.4 < val <= 0.8: return 95.0 - (val - 0.4) * 12.5
        elif 0.8 < val <= 1.2: return 90.0 - (val - 0.8) * 25.0
        elif 1.2 < val <= 2.0: return 80.0 - (val - 1.2) * 25.0
        elif 2.0 < val <= 3.5: return 60.0 - (val - 2.0) * 15.0
        else: return max(15.0, 37.0 - (val - 3.5) * 5.0)

    def score_roe(val):
        if pd.isnull(val): return 45.0
        if val >= 25.0: return min(100.0, 95.0 + (val - 25.0) * 0.1)
        elif 15.0 <= val < 25.0: return 82.0 + (val - 15.0) * 1.3
        elif 10.0 <= val < 15.0: return 68.0 + (val - 10.0) * 2.8
        elif 5.0 <= val < 10.0: return 48.0 + (val - 5.0) * 4.0
        elif 0.0 <= val < 5.0: return 30.0 + val * 3.6
        else: return max(10.0, 30.0 + val * 0.5)

    def score_eps(val):
        if pd.isnull(val): return 50.0
        c_val = min(val, 60.0)
        if c_val >= 25.0: return 90.0 + (c_val - 25.0) * 0.28
        elif 12.0 <= c_val < 25.0: return 75.0 + (c_val - 12.0) * 1.15
        elif 0.0 <= c_val < 12.0: return 55.0 + c_val * 1.66
        elif -20.0 <= c_val < 0.0: return 35.0 + (c_val + 20.0) * 1.0
        else: return max(15.0, 35.0 + (c_val + 20.0) * 0.4)

    per_scores = out_df["PER (배)"].apply(score_per)
    peg_scores = out_df["PEG (배)"].apply(score_peg)
    roe_scores = out_df["ROE (%)"].apply(score_roe)
    eps_scores = out_df["EPS 성장률(%)"].apply(score_eps)

    tot_w = float(w_per + w_peg + w_roe + w_eps)
    base_scores = ((per_scores * w_per + peg_scores * w_peg + roe_scores * w_roe + eps_scores * w_eps) / tot_w) if tot_w > 0 else pd.Series(50.0, index=out_df.index)

    bonus = []
    for _, r in out_df.iterrows():
        mrq = r.get("최근분기 EPS(MRQ)")
        ttm = r.get("올해누적 EPS(TTM)")
        if pd.notnull(mrq) and pd.notnull(ttm) and ttm > 0 and (mrq * 4.0) > (ttm * 1.05): bonus.append(3.0)
        else: bonus.append(0.0)

    out_df["종합 스코어"] = (base_scores + pd.Series(bonus, index=out_df.index)).clip(lower=15.0, upper=98.5).round(1)
    return out_df

def fetch_intraday_chart(ticker: str, market_type: str, interval: str = "1m") -> pd.DataFrame:
    clean_ticker = str(ticker).strip()
    session = GLOBAL_SESSION
    if market_type == "국내 주식 (KRX)":
        c_tick = clean_ticker.zfill(6)
        try:
            url = f"https://m.stock.naver.com/front-api/v1/chart/domestic/price?code={c_tick}&timeframe=minute&count=120"
            r = session.get(url, timeout=3.5)
            if r.status_code == 200:
                j = r.json()
                items = j.get("result", {}).get("priceInfos", [])
                if items:
                    rows = []
                    for it in items:
                        dt = datetime.strptime(str(it["localDateTime"]), "%Y%m%d%H%M%S")
                        rows.append({
                            "Date": dt,
                            "Open": float(it["openPrice"]),
                            "High": float(it["highPrice"]),
                            "Low": float(it["lowPrice"]),
                            "Close": float(it["currentPrice"]),
                            "Volume": float(it["accumulatedTradingVolume"])
                        })
                    return pd.DataFrame(rows).set_index("Date").sort_index()
        except Exception:
            pass
        try:
            yf_tick = f"{c_tick}.KS"
            df_yf = yf.download(yf_tick, period="1d", interval="1m", progress=False)
            if not df_yf.empty:
                if isinstance(df_yf.columns, pd.MultiIndex): df_yf.columns = df_yf.columns.get_level_values(0)
                return df_yf
        except Exception:
            pass
    else:
        try:
            df_yf = yf.download(clean_ticker, period="1d", interval=interval, progress=False)
            if not df_yf.empty:
                if isinstance(df_yf.columns, pd.MultiIndex): df_yf.columns = df_yf.columns.get_level_values(0)
                return df_yf
        except Exception:
            pass
    return pd.DataFrame()

def fetch_quarterly_detailed_matrix(market_type: str, ticker: str) -> pd.DataFrame:
    clean_ticker = str(ticker).strip()
    session = GLOBAL_SESSION
    if market_type == "국내 주식 (KRX)":
        c_tick = clean_ticker.zfill(6)
        try:
            r_q = session.get(f"https://m.stock.naver.com/api/stock/{c_tick}/finance/quarter", timeout=4)
            q_fin = r_q.json().get("financeInfo", {}) if r_q.status_code == 200 else {}
            tr_q = q_fin.get("trTitleList", [])
            r_a = session.get(f"https://m.stock.naver.com/api/stock/{c_tick}/finance/annual", timeout=4)
            a_fin = r_a.json().get("financeInfo", {}) if r_a.status_code == 200 else {}
            tr_a = a_fin.get("trTitleList", [])
            target_metrics = ["매출액", "영업이익", "당기순이익", "영업이익률", "순이익률", "ROE", "EPS", "PER", "PBR"]
            q_cols = {}
            for row in q_fin.get("rowList", []):
                t = str(row.get("title", "")).strip()
                for target in target_metrics:
                    if target in t:
                        cols = row.get("columns", {})
                        val_map = {}
                        for item in tr_q:
                            label = item.get("title", "")
                            hdr = f"{label} (E)" if item.get("isConsensus") == "Y" else label
                            val_map[hdr] = cols.get(item.get("key"), {}).get("value", "-")
                        q_cols[target] = val_map
                        break
            a_cols = {}
            for row in a_fin.get("rowList", []):
                t = str(row.get("title", "")).strip()
                for target in target_metrics:
                    if target in t:
                        cols = row.get("columns", {})
                        val_map = {}
                        for item in tr_a:
                            label = item.get("title", "")
                            hdr = f"{label} 연간(E)" if item.get("isConsensus") == "Y" else f"{label} 연간"
                            val_map[hdr] = cols.get(item.get("key"), {}).get("value", "-")
                        a_cols[target] = val_map
                        break
            combined_rows = []
            for m in target_metrics:
                row_dict = {"주요 재무 지표": m}
                if m in a_cols:
                    for k, v in a_cols[m].items():
                        if any(yr in k for yr in ["2024", "2025", "2026"]): row_dict[k] = v
                if m in q_cols:
                    for k, v in q_cols[m].items(): row_dict[k] = v
                combined_rows.append(row_dict)
            return pd.DataFrame(combined_rows)
        except Exception:
            return pd.DataFrame()
    else:
        try:
            t_obj = yf.Ticker(clean_ticker)
            q_fin = t_obj.quarterly_income_stmt
            if q_fin is not None and not q_fin.empty:
                dates = [d.strftime("%Y-%m") for d in q_fin.columns[:5]]
                rows = []
                metric_keys = {"Total Revenue": "매출액 (백만$)", "Operating Income": "영업이익 (백만$)", "Net Income": "당기순이익 (백만$)", "Diluted EPS": "EPS ($)"}
                for yf_key, name in metric_keys.items():
                    if yf_key in q_fin.index:
                        row_dict = {"주요 재무 지표": name}
                        for col_d, d_label in zip(q_fin.columns[:5], dates):
                            val = q_fin.loc[yf_key, col_d]
                            if pd.notnull(val):
                                row_dict[d_label] = f"{val:,.2f}" if "EPS" in name else f"{val / 1e6:,.1f}"
                            else: row_dict[d_label] = "-"
                        rows.append(row_dict)
                return pd.DataFrame(rows)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

def fetch_stock_news(market_type: str, ticker: str) -> list:
    session = GLOBAL_SESSION
    clean_ticker = str(ticker).strip()
    news_list = []
    if market_type == "국내 주식 (KRX)":
        c_tick = clean_ticker.zfill(6)
        try:
            r = session.get(f"https://m.stock.naver.com/api/news/stock/{c_tick}?pageSize=8&page=1", timeout=3.5)
            if r.status_code == 200:
                for group in r.json():
                    for it in group.get("items", []):
                        dt_raw = str(it.get("datetime", ""))
                        dt_str = f"{dt_raw[:4]}-{dt_raw[4:6]}-{dt_raw[6:8]} {dt_raw[8:10]}:{dt_raw[10:12]}" if len(dt_raw) >= 12 else dt_raw
                        body_txt = html.unescape(it.get("body", "") or "")[:120]
                        news_list.append({"title": html.unescape(it.get("titleFull") or it.get("title", "")), "media": it.get("officeName", "증권뉴스"), "date": dt_str, "url": it.get("mobileNewsUrl", ""), "body": body_txt + "..." if body_txt else ""})
                        if len(news_list) >= 6: break
                    if len(news_list) >= 6: break
        except Exception:
            pass
    else:
        try:
            t_obj = yf.Ticker(clean_ticker)
            if hasattr(t_obj, "news") and t_obj.news:
                for item in t_obj.news[:6]:
                    news_list.append({"title": item.get("title", ""), "media": item.get("publisher", "Yahoo Finance"), "date": datetime.fromtimestamp(item.get("providerPublishTime", 0)).strftime("%Y-%m-%d %H:%M"), "url": item.get("link", ""), "body": item.get("summary", "")[:120] + "..." if item.get("summary") else ""})
        except Exception:
            pass
    return news_list

def fetch_partner_news(partner_tickers: list) -> list:
    seen_titles = set()
    partner_news = []
    for pt in partner_tickers:
        items = fetch_stock_news("해외 주식 (미국)", pt)
        for it in items[:4]:
            t = it.get("title", "").strip()
            if t and t not in seen_titles:
                seen_titles.add(t)
                it["source_ticker"] = pt
                partner_news.append(it)
    return partner_news

def fetch_stock_reports_and_consensus(market_type: str, ticker: str, current_price: float = None) -> dict:
    session = GLOBAL_SESSION
    clean_ticker = str(ticker).strip()
    result = {"target_price": None, "target_price_str": "컨센서스 없음", "recommendation": "N/A", "upside_percent": None, "reports": []}
    if market_type == "국내 주식 (KRX)":
        c_tick = clean_ticker.zfill(6)
        try:
            r_int = session.get(f"https://m.stock.naver.com/api/stock/{c_tick}/integration", timeout=3.5)
            if r_int.status_code == 200:
                data = r_int.json()
                cns = data.get("consensusInfo", {})
                tp_raw = _safe_float(cns.get("priceTargetMean"))
                if tp_raw:
                    result["target_price"] = tp_raw
                    result["target_price_str"] = f"{tp_raw:,.0f}원"
                    if current_price and current_price > 0:
                        result["upside_percent"] = round(((tp_raw - current_price) / current_price) * 100.0, 1)
                rec_val = cns.get("recommMean")
                if rec_val:
                    r_flt = _safe_float(rec_val)
                    if r_flt:
                        if r_flt >= 4.0: result["recommendation"] = f"강력 매수 ({r_flt:.1f}/5.0)"
                        elif r_flt >= 3.5: result["recommendation"] = f"매수 ({r_flt:.1f}/5.0)"
                        elif r_flt >= 2.5: result["recommendation"] = f"중립 ({r_flt:.1f}/5.0)"
                        else: result["recommendation"] = f"비중축소 ({r_flt:.1f}/5.0)"
                for rep in data.get("researches", [])[:6]:
                    wdt = str(rep.get("wdt", ""))
                    date_str = f"{wdt[:4]}-{wdt[4:6]}-{wdt[6:8]}" if len(wdt) == 8 else wdt
                    nid = rep.get("id")
                    result["reports"].append({"title": html.unescape(rep.get("tit", "")), "broker": rep.get("bnm", "증권사"), "date": date_str, "url": f"https://finance.naver.com/research/company_read.naver?nid={nid}" if nid else ""})
        except Exception:
            pass
    else:
        try:
            t_obj = yf.Ticker(clean_ticker)
            info = t_obj.info or {}
            tp_raw = _safe_float(info.get("targetMeanPrice"))
            if tp_raw:
                result["target_price"] = tp_raw
                result["target_price_str"] = f"${tp_raw:,.2f}"
                if current_price and current_price > 0:
                    result["upside_percent"] = round(((tp_raw - current_price) / current_price) * 100.0, 1)
            rec_key = str(info.get("recommendationKey", "")).lower()
            rec_map = {"strong_buy": "강력 매수 (Strong Buy)", "buy": "매수 (Buy)", "hold": "중립 (Hold)", "underperform": "비중축소 (Underperform)", "sell": "매도 (Sell)"}
            result["recommendation"] = rec_map.get(rec_key, rec_key.capitalize())
        except Exception:
            pass
    return result

KRX_WIDE_CANDIDATES = [
    {"name": "서진시스템", "ticker": "178320", "sector": "반도체/소부장"},
    {"name": "한미반도체", "ticker": "042700", "sector": "반도체/소부장"},
    {"name": "ISC", "ticker": "095340", "sector": "반도체/소부장"},
    {"name": "유진테크", "ticker": "084370", "sector": "반도체/소부장"},
    {"name": "주성엔지니어링", "ticker": "036930", "sector": "반도체/소부장"},
    {"name": "원익IPS", "ticker": "240810", "sector": "반도체/소부장"},
    {"name": "피에스케이", "ticker": "319660", "sector": "반도체/소부장"},
    {"name": "하나마이크론", "ticker": "067310", "sector": "반도체/소부장"},
    {"name": "파크시스템스", "ticker": "140860", "sector": "반도체/소부장"},
    {"name": "동진쎄미켐", "ticker": "005290", "sector": "반도체/소부장"},
    {"name": "HD현대일렉트릭", "ticker": "267260", "sector": "전력인프라/원전"},
    {"name": "효성중공업", "ticker": "298040", "sector": "전력인프라/원전"},
    {"name": "LS ELECTRIC", "ticker": "010120", "sector": "전력인프라/원전"},
    {"name": "대한전선", "ticker": "001440", "sector": "전력인프라/원전"},
    {"name": "일진전기", "ticker": "103590", "sector": "전력인프라/원전"},
    {"name": "두산에너빌리티", "ticker": "034020", "sector": "전력인프라/원전"},
    {"name": "한화에어로스페이스", "ticker": "012450", "sector": "방산/우주항공"},
    {"name": "현대로템", "ticker": "064350", "sector": "방산/우주항공"},
    {"name": "LIG넥스원", "ticker": "079550", "sector": "방산/우주항공"},
    {"name": "한화시스템", "ticker": "272210", "sector": "방산/우주항공"},
    {"name": "한국항공우주", "ticker": "047810", "sector": "방산/우주항공"},
    {"name": "삼양식품", "ticker": "003230", "sector": "K-푸드/소비재"},
    {"name": "농심", "ticker": "004370", "sector": "K-푸드/소비재"},
    {"name": "CJ제일제당", "ticker": "097950", "sector": "K-푸드/소비재"},
    {"name": "실리콘투", "ticker": "257720", "sector": "K-푸드/소비재"},
    {"name": "한국콜마", "ticker": "161890", "sector": "K-푸드/소비재"},
    {"name": "코스맥스", "ticker": "192820", "sector": "K-푸드/소비재"},
    {"name": "레인보우로보틱스", "ticker": "277810", "sector": "로봇/AI"},
    {"name": "두산로보틱스", "ticker": "454910", "sector": "로봇/AI"},
    {"name": "알테오젠", "ticker": "196170", "sector": "바이오/헬스케어"},
    {"name": "리가켐바이오", "ticker": "141080", "sector": "바이오/헬스케어"},
    {"name": "에스티팜", "ticker": "237690", "sector": "바이오/헬스케어"},
    {"name": "삼천당제약", "ticker": "000250", "sector": "바이오/헬스케어"},
    {"name": "휴젤", "ticker": "145020", "sector": "바이오/헬스케어"},
    {"name": "한국타이어앤테크놀로지", "ticker": "161390", "sector": "딥밸류/금융·지주"},
    {"name": "기업은행", "ticker": "024110", "sector": "딥밸류/금융·지주"},
    {"name": "우리금융지주", "ticker": "316140", "sector": "딥밸류/금융·지주"},
    {"name": "BNK금융지주", "ticker": "138930", "sector": "딥밸류/금융·지주"},
    {"name": "영원무역", "ticker": "111770", "sector": "딥밸류/금융·지주"},
    {"name": "F&F", "ticker": "383220", "sector": "딥밸류/금융·지주"},
    {"name": "현대엘리베이터", "ticker": "017800", "sector": "딥밸류/금융·지주"},
]

def scan_krx_wide_tenbaggers() -> pd.DataFrame:
    return fetch_market_data_parallel("국내 주식 (KRX)", KRX_WIDE_CANDIDATES)