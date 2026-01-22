import streamlit as st
import os
from dotenv import load_dotenv

# 사용자 정의 모듈 임포트
from rag_system import load_rag_system
from battle_state import BattleState
from steps import step1_analyze, step2_battle
# step0은 my_party.py로 대체되었으므로 임포트 제외

# ★ 내 파티 정보 가져오기
try:
    from my_party import PRESET_TEAM
except ImportError:
    PRESET_TEAM = "" # 파일이 없을 경우 대비

# 1. 기본 설정
st.set_page_config(page_title="Poke-Advisor", page_icon="🎮", layout="wide")
load_dotenv()

# 2. API 키 확인 (os.getenv로만 로드)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    st.error("❌ API 키 오류: 프로젝트 폴더에 `.env` 파일이 없거나 GOOGLE_API_KEY가 설정되지 않았습니다.")
    st.stop()

# 3. RAG 시스템 로드 (엔진 시동)
retriever, llm = load_rag_system(GOOGLE_API_KEY)

if not llm:
    st.error("🚨 DB 오류: 'db_builder.py'를 먼저 실행해서 데이터를 구축하세요.")
    st.stop()

# 4. Session State 초기화
# 앱 시작 시 바로 Step 1(상대 분석)으로 설정
if "step" not in st.session_state:
    st.session_state.step = "ANALYZE_MATCHUP"

if "messages" not in st.session_state:
    st.session_state.messages = []

# 상태 공간 객체 초기화 및 파티 자동 등록
if "battle_state" not in st.session_state:
    bs = BattleState()
    
    # [자동 등록 로직]
    if PRESET_TEAM:
        # 1. 파티 전체 텍스트 저장
        bs.my_party_full = PRESET_TEAM.strip()
        
        # 2. 이름 파싱 (Showdown 형식에서 이름만 추출하여 사이드바용 리스트 생성)
        roster_names = []
        chunks = bs.my_party_full.split("\n\n")
        for chunk in chunks:
            if not chunk.strip(): continue
            # 첫 번째 줄이 "Name @ Item" 또는 "Name" 형식임
            first_line = chunk.strip().split("\n")[0]
            name = first_line.split("@")[0].strip()
            if name:
                roster_names.append(name)
        bs.my_roster = roster_names
    
    st.session_state.battle_state = bs
    
    # 초기 안내 메시지 추가
    if not st.session_state.messages:
        st.session_state.messages.append({
            "role": "assistant", 
            "content": (
                "✅ **내 파티가 자동으로 로드되었습니다.**\n\n"
                "이제 **상대방 포켓몬 6마리의 이름**을 입력해주세요.\n"
                "(예: 날치머, 망나뇽, 파오젠, 뽀록나, 우라오스, 타부자고)"
            )
        })

# ==========================================
# 📊 사이드바: 상태 시각화 (State Space)
# ==========================================
with st.sidebar:
    st.title("📋 상태 공간 (Status)")
    st.markdown("---")
    
    bs = st.session_state.battle_state
    
    # 1. 필드 현황 (Active)
    if bs.my_active[0] != "?":
        st.subheader("🏟️ 현재 필드 (Active)")
        c1, c2 = st.columns(2)
        with c1: 
            st.markdown("**🟢 나**")
            st.success(f"{bs.my_active[0]}\n\n{bs.my_active[1]}")
        with c2: 
            st.markdown("**🔴 상대**")
            st.error(f"{bs.opponent_active[0]}\n\n{bs.opponent_active[1]}")
        st.divider()

    # 2. 내 파티 (자동 로드됨)
    with st.expander("🟢 내 파티 & 선출", expanded=False):
        if bs.my_selection:
            st.caption("👇 선출된 4마리")
            for mon in bs.my_selection:
                hp = bs.my_hp.get(mon, "100%")
                st.write(f"- {mon} (HP: {hp})")
        else:
            st.caption(f"👇 전체 로스터 ({len(bs.my_roster)}마리)")
            for mon in bs.my_roster:
                st.text(f"- {mon}")

    # 3. 상대 파티
    st.subheader("🔴 상대 엔트리 분석")
    if bs.opponent_roster:
        for i, mon in enumerate(bs.opponent_roster):
            hp = bs.opponent_hp.get(mon, "100%")
            status_info = bs.opponent_info.get(mon, "정보 없음")
            
            if mon in bs.opponent_confirmed:
                # 확인된 녀석은 진하게 표시
                st.markdown(f"**{i+1}. {mon}** (HP: {hp})")
                st.caption(f"└ {status_info}")
            else:
                st.text(f"{i+1}. {mon}")
    else:
        st.caption("상대 엔트리 입력 대기 중")

    st.markdown("---")
    if st.button("🔄 리셋 (처음으로)", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ==========================================
# 🖥️ 메인 UI 구성
# ==========================================
st.title("Poke-Advisor 🎮")
st.caption("Gen 9 VGC 2026 Reg F 실시간 배틀 컨설턴트")

# 단계 표시
steps_info = {
    "ANALYZE_MATCHUP": "1️⃣ 상대 분석 & 자동 선출",
    "BATTLE_PHASE": "2️⃣ 실전 배틀 조언"
}
current_label = steps_info.get(st.session_state.step, "Unknown")
st.info(f"현재 단계: **{current_label}**")

# 대화 기록 표시
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# ==========================================
# 🎮 입력 처리 및 로직 분기
# ==========================================

placeholders = {
    "ANALYZE_MATCHUP": "상대 6마리 입력 (예: 날치머, 망나뇽, 파오젠...)",
    "BATTLE_PHASE": "상황 입력 (예: 상대가 테라스탈하고 섀도볼 썼어)"
}
ph_text = placeholders.get(st.session_state.step, "입력하세요...")

if user_input := st.chat_input(ph_text):
    # 1. 사용자 입력 즉시 표시 및 저장
    st.chat_message("user").write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    response = ""
    current_step = st.session_state.step
    
    try:
        # ---------------------------------------------------
        # Step 1: 상대 분석 & AI 자동 선출
        # ---------------------------------------------------
        if current_step == "ANALYZE_MATCHUP":
            with st.spinner("🔍 상대 분석 및 AI 자동 선출 진행 중..."):
                response = step1_analyze.execute(user_input, retriever, llm)
                
                # ★ 중요: 리런하기 전에 메시지 저장 필수!
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # 사이드바(선출 목록) 갱신을 위해 리런
                st.rerun() 

        # ---------------------------------------------------
        # Step 2: 실전 배틀 조언
        # ---------------------------------------------------
        elif current_step == "BATTLE_PHASE":
             with st.spinner("🧠 전황 분석 및 전략 수립 중..."):
                response = step2_battle.execute(user_input, retriever, llm)
                
                # ★ 중요: 리런하기 전에 메시지 저장 필수!
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # 사이드바(상대 상태) 갱신을 위해 리런
                st.rerun()

    except Exception as e:
        st.error(f"시스템 오류가 발생했습니다: {e}")