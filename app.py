import streamlit as st
import os
from dotenv import load_dotenv

from rag_system import load_rag_system
from battle_state import BattleState
from steps import step1_analyze, step2_battle

try:
    from my_party import PRESET_TEAM
except ImportError:
    PRESET_TEAM = ""

st.set_page_config(page_title="Poke-Advisor (Singles)", page_icon="🎮", layout="wide")
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("❌ API 키 오류")
    st.stop()

retriever, llm = load_rag_system(GOOGLE_API_KEY) # 여기선 vectorstore가 아니라 로드용 확인

# ★ 주의: rag_system.py가 vectorstore를 리턴하게 바꿨으므로 app.py도 맞춰야 함
# 만약 rag_system.py 코드가 vectorstore를 리턴한다면 아래처럼 받아야 함:
vectorstore, _ = load_rag_system(GOOGLE_API_KEY)
if not vectorstore:
    st.error("🚨 DB 오류")
    st.stop()

if "step" not in st.session_state:
    st.session_state.step = "ANALYZE_MATCHUP"
if "messages" not in st.session_state:
    st.session_state.messages = []

if "battle_state" not in st.session_state:
    bs = BattleState()
    if PRESET_TEAM:
        bs.my_party_full = PRESET_TEAM.strip()
        roster = []
        for chunk in bs.my_party_full.split("\n\n"):
            if not chunk.strip(): continue
            name = chunk.strip().split("\n")[0].split("@")[0].strip()
            if name: roster.append(name)
        bs.my_roster = roster
    st.session_state.battle_state = bs
    
    if not st.session_state.messages:
        st.session_state.messages.append({
            "role": "assistant", 
            "content": "✅ **싱글배틀 모드** 로드 완료. 상대 6마리를 입력하세요."
        })

# ==========================================
# 📊 사이드바
# ==========================================
with st.sidebar:
    st.title("📋 상태 (Singles 3v3)")
    st.markdown("---")
    
    bs = st.session_state.battle_state
    
    # 1. 필드 현황 (1 vs 1)
    if bs.my_active[0] != "?":
        st.subheader("🏟️ 현재 대면 (1v1)")
        c1, c2 = st.columns(2)
        with c1: 
            st.markdown("**🟢 나**")
            # 리스트의 첫 번째 요소만 표시
            st.success(f"{bs.my_active[0]}")
        with c2: 
            st.markdown("**🔴 상대**")
            st.error(f"{bs.opponent_active[0]}")
        st.divider()

    # 2. 내 선출 (3마리)
    with st.expander("🟢 내 선출 (3마리)", expanded=True):
        if bs.my_selection:
            for mon in bs.my_selection:
                hp = bs.my_hp.get(mon, "100%")
                active_mark = " (Active)" if mon in bs.my_active else ""
                st.write(f"- {mon} {active_mark} [HP: {hp}]")
        else:
            st.caption("대기 중...")

    # 3. 상대 엔트리
    st.subheader("🔴 상대 엔트리")
    if bs.opponent_roster:
        for i, mon in enumerate(bs.opponent_roster):
            hp = bs.opponent_hp.get(mon, "100%")
            status = bs.opponent_info.get(mon, "정보 없음")
            if mon in bs.opponent_confirmed:
                st.markdown(f"**{i+1}. {mon}** (HP: {hp})")
                st.caption(f"└ {status}")
            else:
                st.text(f"{i+1}. {mon}")

    st.markdown("---")
    if st.button("🔄 리셋"):
        st.session_state.clear()
        st.rerun()

# ==========================================
# 🖥️ 메인 UI
# ==========================================
st.title("Poke-Advisor (Singles) 🎮")
st.caption("Gen 9 Battle Stadium Singles (3v3) 솔루션")

steps_info = {
    "ANALYZE_MATCHUP": "1️⃣ 상대 분석 & 선출(3마리)",
    "BATTLE_PHASE": "2️⃣ 실전 배틀 조언"
}
st.info(f"현재 단계: **{steps_info.get(st.session_state.step)}**")

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

ph_text = {
    "ANALYZE_MATCHUP": "상대 6마리 입력...",
    "BATTLE_PHASE": "상황 입력 (예: 상대가 유턴 쓰고 망나뇽 나옴)"
}.get(st.session_state.step, "입력...")

if user_input := st.chat_input(ph_text):
    st.chat_message("user").write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    response = ""
    try:
        if st.session_state.step == "ANALYZE_MATCHUP":
            with st.spinner("🔍 싱글배틀 메타 분석 중..."):
                # vectorstore를 넘겨줘야 함
                response = step1_analyze.execute(user_input, vectorstore, GOOGLE_API_KEY)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()

        elif st.session_state.step == "BATTLE_PHASE":
             with st.spinner("🧠 수읽기 중..."):
                response = step2_battle.execute(user_input, vectorstore, GOOGLE_API_KEY)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")