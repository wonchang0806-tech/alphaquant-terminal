import json
import os
from datetime import datetime, timedelta
import requests

class KoreaInvestmentAPI:
    def __init__(self, app_key: str, app_secret: str, is_virtual: bool = False):
        self.app_key = app_key
        self.app_secret = app_secret
        self.is_virtual = is_virtual
        self.base_url = (
            "https://openapivts.koreainvestment.com:29443"
            if is_virtual
            else "https://openapi.koreainvestment.com:9443"
        )
        self.token_file = "kis_token.json"
        self.access_token = self._get_valid_token()

    def _get_valid_token(self) -> str:
        now = datetime.now()
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                exp = datetime.strptime(data.get("expires_at", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
                if exp - now > timedelta(minutes=10):
                    return data.get("access_token")
            except Exception:
                pass
        return self._issue_new_token()

    def _issue_new_token(self) -> str:
        if not self.app_key or not self.app_secret:
            return ""
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        res = requests.post(url, headers=headers, json=body, timeout=10)
        if res.status_code != 200:
            return ""
        res_data = res.json()
        token = res_data.get("access_token", "")
        expires_in = int(res_data.get("expires_in", 86400))
        expires_at = datetime.now() + timedelta(seconds=expires_in)

        try:
            with open(self.token_file, "w", encoding="utf-8") as f:
                json.dump({"access_token": token, "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S")}, f)
        except Exception:
            pass
        return token

    def get_stock_price(self, ticker: str) -> dict:
        if not self.access_token:
            return {"error": "토큰 없음"}
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100",
        }
        params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": ticker}
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code != 200:
            return {"error": f"HTTP {res.status_code}"}
        result = res.json()
        if result.get("rt_cd") != "0":
            return {"error": result.get("msg1", "조회 실패")}
        output = result.get("output", {})

        def parse(val):
            try:
                return float(str(val).replace(",", ""))
            except Exception:
                return None

        price = parse(output.get("stck_prpr"))
        per = parse(output.get("per"))
        eps = parse(output.get("eps"))
        return {
            "current_price": price,
            "per": per,
            "eps": eps,
            "per_x_eps": round(per * eps, 2) if (per and eps) else None,
        }