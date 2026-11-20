import hashlib
import os
import streamlit as st
import config
import kis_api

def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

USERS_DB = {
    os.getenv("AQ_ADMIN_ID", "admin"): {
        "password_hash": _hash_pw(os.getenv("AQ_ADMIN_PW", "1234")),
        "name": "관리자 (Master)",
        "role": "admin",
    },
    os.getenv("AQ_GUEST_ID", "guest"): {
        "password_hash": _hash_pw(os.getenv("AQ_GUEST_PW", "0000")),
        "name": "게스트 (Viewer)",
        "role": "guest",
    },
}

def check_login() -> bool:
    if st.session_state.get("authenticated", False):
        return True

    st.markdown("""
    <div style='max-width:440px; margin: 45px auto 16px auto; background:linear-gradient(135deg, rgba(30,41,59,0.96), rgba(15,23,42,0.98)); border:1px solid rgba(99,102,241,0.5); border-radius:18px; padding:28px 30px; box-shadow:0 20px 40px rgba(0,0,0,0.65); text-align:center;'>
        <span style='background:rgba(99,102,241,0.25); border:1px solid #6366f1; color:#c7d2fe; padding:4px 12px; border-radius:999px; font-size:0.76rem; font-weight:800;'>⚡ ALPHAQUANT TERMINAL</span>
        <h2 style='color:#ffffff; font-weight:900; margin:12px 0 6px 0; font-size:1.45rem;'>🔐 터미널 접근 인증</h2>
        <p style='color:#94a3b8; font-size:0.86rem; margin:0;'>퀀트 밸류에이션 & AI 에이전트 시스템 로그인</p>
    </div>
    """, unsafe_allow_html=True)

    _, col_mid, _ = st.columns([1, 1.4, 1])
    with col_mid:
        with st.form("login_form", clear_on_submit=False):
            user_id = st.text_input("아이디 (ID)", placeholder="admin 또는 guest")
            user_pw = st.text_input("비밀번호 (Password)", type="password", placeholder="비밀번호 입력")
            submitted = st.form_submit_button("🚀 터미널 접속하기", use_container_width=True, type="primary")

            if submitted:
                u_clean = user_id.strip()
                if u_clean in USERS_DB and USERS_DB[u_clean]["password_hash"] == _hash_pw(user_pw):
                    st.session_state.authenticated = True
                    st.session_state.user_id = u_clean
                    st.session_state.user_name = USERS_DB[u_clean]["name"]
                    st.session_state.user_role = USERS_DB[u_clean]["role"]
                    st.rerun()
                else:
                    st.error("❌ 아이디 또는 비밀번호가 일치하지 않습니다.")

    return False

def render_sidebar_auth_and_kis():
    role = st.session_state.get("user_role", "guest")
    u_name = st.session_state.get("user_name", "사용자")
    badge_color = "#10b981" if role == "admin" else "#38bdf8"

    st.sidebar.markdown(f"""
    <div style='background:#0f172a; border:1px solid #334155; border-radius:12px; padding:12px 14px; margin-bottom:10px;'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <span style='color:#f8fafc; font-weight:800; font-size:0.9rem;'>👤 {u_name}</span>
            <span style='border:1px solid {badge_color}; color:{badge_color}; padding:2px 8px; border-radius:999px; font-size:0.72rem; font-weight:800;'>{role.upper()}</span>
        </div>
        <div style='color:#94a3b8; font-size:0.75rem; margin-top:4px;'>
            {"전체 편집·포트폴리오·종목 관리 권한" if role == "admin" else "조회 전용 모드 (포트폴리오·삭제 잠금)"}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.sidebar.button("🚪 로그아웃", use_container_width=True, key="btn_logout"):
        for k in ["authenticated", "user_id", "user_name", "user_role", "kis_client_session"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    with st.sidebar.expander("🔑 한투(KIS) 실시간 API 설정 (선택)", expanded=False):
        st.caption("입력하지 않아도 네이버/Yahoo 실시간 데이터로 모든 기능이 정상 작동합니다.")
        default_key = getattr(config, "KIS_APP_KEY", "") or ""
        default_sec = getattr(config, "KIS_APP_SECRET", "") or ""
        default_virt = getattr(config, "KIS_IS_VIRTUAL", True)

        in_key = st.text_input("KIS App Key", value=st.session_state.get("user_kis_key", default_key), type="password", key="kis_key_in")
        in_sec = st.text_input("KIS App Secret", value=st.session_state.get("user_kis_sec", default_sec), type="password", key="kis_sec_in")
        in_virt = st.checkbox("모의투자 계좌 사용", value=st.session_state.get("user_kis_virt", default_virt), key="kis_virt_in")

        c_k1, c_k2 = st.columns(2)
        with c_k1:
            if st.button("연결 적용", use_container_width=True, key="btn_kis_apply"):
                st.session_state.user_kis_key = in_key.strip()
                st.session_state.user_kis_sec = in_sec.strip()
                st.session_state.user_kis_virt = in_virt
                if in_key.strip() and in_sec.strip():
                    try:
                        client = kis_api.KoreaInvestmentAPI(in_key.strip(), in_sec.strip(), in_virt)
                        if client.access_token:
                            st.session_state.kis_client_session = client
                            st.success("🟢 KIS API 연결 성공!")
                        else:
                            st.session_state.kis_client_session = None
                            st.warning("⚠️ 토큰 발급 실패 (네이버 모드로 전환)")
                    except Exception:
                        st.session_state.kis_client_session = None
                        st.warning("⚠️ 연결 오류 (네이버 모드로 전환)")
                else:
                    st.session_state.kis_client_session = None
                    st.info("⚡ 기본 실시간 모드로 전환됨")
        with c_k2:
            if st.button("키 초기화", use_container_width=True, key="btn_kis_clear"):
                st.session_state.user_kis_key = ""
                st.session_state.user_kis_sec = ""
                st.session_state.kis_client_session = None
                st.rerun()

    if "kis_client_session" not in st.session_state:
        k_init = getattr(config, "KIS_APP_KEY", "") or ""
        s_init = getattr(config, "KIS_APP_SECRET", "") or ""
        v_init = getattr(config, "KIS_IS_VIRTUAL", True)
        if k_init and s_init:
            try:
                c_obj = kis_api.KoreaInvestmentAPI(k_init, s_init, v_init)
                st.session_state.kis_client_session = c_obj if c_obj.access_token else None
            except Exception:
                st.session_state.kis_client_session = None
        else:
            st.session_state.kis_client_session = None

    return st.session_state.get("kis_client_session")
