import streamlit as st
import os
from dotenv import load_dotenv

# --- [모듈 임포트] ---
from Battle_Preparing.party_loader import load_party_from_file
from Battle_Preparing.user_party import my_party
from battle_state import current_battle  # Single Source of Truth
from entry import analyze_entry_strategy, parse_opponent_input
from battle import analyze_battle_turn

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Pokémon AI Consultant")

# 2. 스타일링
st.markdown("""
<style>
    .hp-bar { transition: width 0.5s; height: 20px; border-radius: 10px; }
    .stChatInput { bottom: 20px; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# 3. 초기화
if "initialized" not in st.session_state:
    load_dotenv()
    load_party_from_file("my_team.txt")
    current_battle.refresh_my_party()
    
    st.session_state.messages = []
    st.session_state.entry_analysis = None
    st.session_state.opponent_list = []
    st.session_state.initialized = True

# ==============================================================================
# [사이드바] 배틀 상태 대시보드
# ==============================================================================
with st.sidebar:
    st.header("🎛️ 배틀 상태 (Dashboard)")
    
    if not os.getenv("GOOGLE_API_KEY"):
        st.error("API Key가 없습니다.")
        st.stop()

    # ------------------------------------------------------------------
    # [핵심] 1. Backend(BattleState) -> Frontend(SessionState) 강제 동기화
    # AI가 내부 값을 바꿨을 때, 위젯이 이를 반영하도록 강제하는 코드입니다.
    # ------------------------------------------------------------------
    
    # 1. 포켓몬 이름 동기화
    if current_battle.my_active:
        st.session_state["sb_my"] = current_battle.my_active.name
    if current_battle.opp_active:
        st.session_state["sb_opp"] = current_battle.opp_active.name

    # 2. HP 동기화
    if current_battle.my_active:
        st.session_state["sl_my_hp"] = int(current_battle.my_active.current_hp_percent)
    if current_battle.opp_active:
        st.session_state["sl_opp_hp"] = int(current_battle.opp_active.current_hp_percent)

    # 3. 랭크 동기화
    if current_battle.my_active:
        st.session_state["ni_atk"] = current_battle.my_active.ranks['atk']
        st.session_state["ni_spe"] = current_battle.my_active.ranks['spe']

    # 4. 필드/날씨 동기화
    # (None 값 처리 주의)
    weather_val = current_battle.global_effects['weather'] if current_battle.global_effects['weather'] else "None"
    st.session_state["sb_weather"] = weather_val
    
    terrain_val = current_battle.global_effects['terrain'] if current_battle.global_effects['terrain'] else "None"
    st.session_state["sb_terrain"] = terrain_val
    
    st.session_state["cb_tr"] = current_battle.global_effects['trick_room']
    st.session_state["cb_tail"] = current_battle.side_effects['me']['tailwind']
    # 벽은 리플렉터를 대표값으로 사용
    st.session_state["cb_wall"] = current_battle.side_effects['opp']['reflect']

    # ------------------------------------------------------------------
    # [UI 렌더링] 위젯 표시 및 사용자 입력 처리 (Frontend -> Backend)
    # ------------------------------------------------------------------

    # [1] 필드 포켓몬
    st.subheader("1. 필드 포켓몬")
    if my_party.team:
        my_roster = list(my_party.team.keys())
        # key="sb_my"를 통해 위에서 동기화된 값을 초기값으로 사용
        my_active_name = st.selectbox("나", my_roster, key="sb_my")
        
        # 사용자가 바꿨을 때 반영
        if current_battle.my_active is None or current_battle.my_active.name != my_active_name:
            current_battle.set_active("me", my_active_name)
            st.rerun()

    opp_roster = st.session_state.opponent_list if st.session_state.opponent_list else ["Unknown"]
    opp_active_name = st.selectbox("상대", opp_roster, key="sb_opp")
    
    if opp_active_name != "Unknown":
        if current_battle.opp_active is None or current_battle.opp_active.name != opp_active_name:
            current_battle.set_active("opp", opp_active_name)
            st.rerun()

    st.divider()

    # [2] HP 관리
    st.subheader("2. 체력 (HP)")
    col1, col2 = st.columns(2)
    
    with col1:
        if current_battle.my_active:
            my_hp = st.slider("나 (%)", 0, 100, key="sl_my_hp")
            # 사용자가 슬라이더를 움직여서 값이 달라지면 업데이트
            if my_hp != int(current_battle.my_active.current_hp_percent):
                current_battle.my_active.current_hp_percent = my_hp
        else:
            st.info("준비 중")
            
    with col2:
        if current_battle.opp_active:
            opp_hp = st.slider("상대 (%)", 0, 100, key="sl_opp_hp")
            if opp_hp != int(current_battle.opp_active.current_hp_percent):
                current_battle.opp_active.current_hp_percent = opp_hp
        else:
            st.info("준비 중")

    st.divider()

    # [3] 필드 및 랭크
    st.subheader("3. 랭크 및 필드")
    
    r1, r2 = st.columns(2)
    with r1:
        new_atk = st.number_input("내 공격 랭크", -6, 6, key="ni_atk")
        if current_battle.my_active and new_atk != current_battle.my_active.ranks['atk']:
            current_battle.my_active.ranks['atk'] = new_atk
            
    with r2:
        new_spe = st.number_input("내 스피드 랭크", -6, 6, key="ni_spe")
        if current_battle.my_active and new_spe != current_battle.my_active.ranks['spe']:
            current_battle.my_active.ranks['spe'] = new_spe

    # 날씨
    w_opts = ["None", "Sun", "Rain", "Sand", "Snow"]
    new_w = st.selectbox("날씨", w_opts, key="sb_weather")
    val_w = None if new_w == "None" else new_w
    if val_w != current_battle.global_effects['weather']:
        current_battle.global_effects['weather'] = val_w

    # 필드
    t_opts = ["None", "Electric", "Grassy", "Psychic", "Misty"]
    new_t = st.selectbox("필드", t_opts, key="sb_terrain")
    val_t = None if new_t == "None" else new_t
    if val_t != current_battle.global_effects['terrain']:
        current_battle.global_effects['terrain'] = val_t

    # 체크박스
    is_tr = st.checkbox("트릭룸 (Trick Room)", key="cb_tr")
    if is_tr != current_battle.global_effects['trick_room']:
        current_battle.global_effects['trick_room'] = is_tr
        
    c1, c2 = st.columns(2)
    with c1:
        is_tail = st.checkbox("내 순풍", key="cb_tail")
        if is_tail != current_battle.side_effects['me']['tailwind']:
            current_battle.side_effects['me']['tailwind'] = is_tail
            
    with c2:
        is_wall = st.checkbox("상대 벽", key="cb_wall")
        # 단순화: 체크하면 리플렉터/빛의장막 둘 다 켜짐 (필요시 분리 가능)
        if is_wall != current_battle.side_effects['opp']['reflect']:
            current_battle.side_effects['opp']['reflect'] = is_wall
            current_battle.side_effects['opp']['light_screen'] = is_wall


# ==============================================================================
# [메인 화면]
# ==============================================================================
st.title("🤖 포켓몬 배틀 AI 컨설턴트")

tab1, tab2 = st.tabs(["📋 선출 분석 (Entry)", "⚔️ 실시간 배틀 (Battle)"])

# --- Tab 1: 선출 ---
with tab1:
    st.header("상대 엔트리 분석")
    st.info("상대 포켓몬 6마리를 입력하세요.")
    
    entry_input = st.text_input("입력 (예: 날치머, 망나뇽, 딩루 ...)")
    
    if st.button("분석 시작"):
        if entry_input:
            with st.spinner("Gemini 3.0이 시뮬레이션을 돌리고 있습니다..."):
                opp_list = parse_opponent_input(entry_input)
                
                if opp_list:
                    st.session_state.opponent_list = opp_list
                    current_battle.initialize_opponent(opp_list)
                    
                    analysis = analyze_entry_strategy(opp_list)
                    st.session_state.entry_analysis = analysis
                    
                    st.success(f"엔트리 등록 완료: {', '.join(opp_list)}")
                    st.rerun()
                else:
                    st.error("입력을 해석할 수 없습니다.")
        else:
            st.warning("포켓몬 이름을 입력해주세요.")
    
    if st.session_state.entry_analysis:
        st.markdown("---")
        st.markdown(st.session_state.entry_analysis)

# --- Tab 2: 배틀 ---
with tab2:
    st.header("실시간 턴 가이드")
    
    if not st.session_state.opponent_list:
        st.warning("👈 먼저 '선출 분석' 탭에서 상대 엔트리를 입력해주세요.")
    else:
        # 채팅창
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
        
        # 입력창
        st.markdown("---")
        with st.container():
            c_in, c_chk = st.columns([5, 1])
            with c_in:
                user_input = st.chat_input("상황 입력 (예: 상대가 지진을 써서 피가 반 남았어)")
            with c_chk:
                opp_first = st.checkbox("상대 선공?", key="chk_opp_first", help="상대가 먼저 행동했으면 체크")

            if user_input:
                st.session_state.messages.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.markdown(user_input)
                
                with st.chat_message("assistant"):
                    place = st.empty()
                    with st.spinner("전략 수립 중..."):
                        response = analyze_battle_turn(user_input, opp_first)
                        place.markdown(response)
                        
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # [중요] AI가 바꾼 상태를 UI에 반영하기 위해 리런
                st.rerun()