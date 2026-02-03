import streamlit as st
import os
from dotenv import load_dotenv

# --- [모듈 임포트] ---
from Battle_Preparing.party_loader import load_party_from_file
from Battle_Preparing.user_party import my_party
from battle_state import current_battle  # Single Source of Truth
from entry import analyze_entry_strategy, parse_opponent_input, parse_recommended_selection
from battle import analyze_battle_turn

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Pokémon AI Consultant")

# 2. 스타일링
st.markdown("""
<style>
    .hp-bar { transition: width 0.5s; height: 20px; border-radius: 10px; }
    .stChatInput { bottom: 20px; }
    .block-container { padding-top: 2rem; }
    /* 사이드바 스타일링 */
    .status-text { font-size: 0.9rem; color: #555; }
    .rank-text { font-weight: bold; color: #E03E3E; }
    .stProgress > div > div > div > div { background-color: #4CAF50; }
</style>
""", unsafe_allow_html=True)

# 3. 초기화 (세션 상태 관리)
if "initialized" not in st.session_state:
    load_dotenv()
    
    # [Step 1] 파티 로드
    load_party_from_file("my_team.txt")
    
    # [Step 2] BattleState 초기화 (중요)
    current_battle.refresh_my_party()
    
    # [Step 3] 세션 변수
    st.session_state.messages = []
    st.session_state.entry_analysis = None
    st.session_state.opponent_list = []
    
    # [New] 토큰 관리 변수
    st.session_state.entry_tokens = {"parser": 0, "strategy": 0, "selection": 0}
    # 기존 battle_token_total 대신 상세 내역 저장을 위한 딕셔너리로 초기화
    if "battle_tokens" not in st.session_state:
        st.session_state.battle_tokens = {"parser": 0, "analysis": 0} 
    
    st.session_state.initialized = True

# ==============================================================================
# [사이드바] 배틀 상태 뷰어 (View Only Dashboard)
# ==============================================================================
with st.sidebar:
    st.header("📊 배틀 현황판")
    st.info("모든 상태 조작은 채팅으로 명령하세요.\n(예: '상대 딩루 교체', '내 피 50%')")
    
    if not os.getenv("GOOGLE_API_KEY"):
        st.error("API Key가 없습니다.")
        st.stop()

    st.divider()

    # --- 1. 나의 상태 (My Status) ---
    st.subheader("🟢 나의 필드")
    if current_battle.my_active:
        me = current_battle.my_active
        st.markdown(f"**{me.name}**")
        
        # HP Bar (읽기 전용)
        hp_val = int(me.current_hp_percent)
        st.progress(hp_val / 100)
        st.caption(f"HP: {hp_val}% | 상태: {me.status_condition or '정상'}")
        
        # 랭크 표시 (0이 아닌 것만)
        ranks = []
        for k, v in me.ranks.items():
            if v != 0:
                ranks.append(f"{k.upper()} {v:+d}")
        
        if ranks:
            st.markdown(f"<span class='rank-text'>{', '.join(ranks)}</span>", unsafe_allow_html=True)
            
        # 휘발성 상태
        volatiles = [k for k,v in me.volatile_status.items() if v]
        if volatiles:
            st.warning(f"⚠️ {', '.join(volatiles)}")
    else:
        st.markdown("*(대기 중)*")

    st.divider()

    # --- 2. 상대 상태 (Opponent Status) ---
    st.subheader("🔴 상대 필드")
    if current_battle.opp_active:
        opp = current_battle.opp_active
        st.markdown(f"**{opp.name}**")
        
        # HP Bar
        opp_hp_val = int(opp.current_hp_percent)
        st.progress(opp_hp_val / 100)
        st.caption(f"HP: {opp_hp_val}% | 상태: {opp.status_condition or '정상'}")
        
        # 랭크
        opp_ranks = []
        for k, v in opp.ranks.items():
            if v != 0:
                opp_ranks.append(f"{k.upper()} {v:+d}")
                
        if opp_ranks:
            st.markdown(f"<span class='rank-text'>{', '.join(opp_ranks)}</span>", unsafe_allow_html=True)

        # 정보 (확정 여부 표시)
        item_txt = f"{opp.info['item']} (확정)" if opp.confirmed['item'] else "❓ 미확인"
        st.markdown(f"🎒 도구: {item_txt}")
        
        # 휘발성 상태
        opp_volatiles = [k for k,v in opp.volatile_status.items() if v]
        if opp_volatiles:
            st.warning(f"⚠️ {', '.join(opp_volatiles)}")
        
    else:
        st.markdown("*(대기 중)*")

    st.divider()

    # --- 3. 필드 환경 (Environment) ---
    st.subheader("🌐 필드 환경")
    
    # 날씨/필드/룸
    w = current_battle.global_effects['weather']
    t = current_battle.global_effects['terrain']
    tr = current_battle.global_effects['trick_room']
    
    st.write(f"🌤️ 날씨: **{w if w else '없음'}**")
    st.write(f"🌱 필드: **{t if t else '없음'}**")
    if tr: st.error("🌀 트릭룸 활성화")
    
    # 순풍/벽 상태 표시
    st.caption("--- 진영 효과 ---")
    
    col_me, col_opp = st.columns(2)
    with col_me:
        st.markdown("**[나]**")
        effs = []
        if current_battle.side_effects['me']['tailwind']: effs.append("순풍")
        if current_battle.side_effects['me']['reflect']: effs.append("벽")
        if not effs: st.write("-")
        else: st.write(", ".join(effs))
        
    with col_opp:
        st.markdown("**[상대]**")
        o_effs = []
        if current_battle.side_effects['opp']['tailwind']: o_effs.append("순풍")
        if current_battle.side_effects['opp']['reflect']: o_effs.append("벽")
        if not o_effs: st.write("-")
        else: st.write(", ".join(o_effs))


# ==============================================================================
# [메인 화면] 채팅 인터페이스
# ==============================================================================
st.title("🤖 포켓몬 배틀 AI 컨설턴트")

tab1, tab2 = st.tabs(["📋 선출 분석 (Entry)", "⚔️ 실시간 배틀 (Battle)"])

# --- Tab 1: 선출 ---
with tab1:
    st.header("상대 엔트리 분석")
    st.info("상대 포켓몬 6마리를 입력하세요.")
    
    entry_input = st.text_input("입력 (예: 날치머 망나뇽 딩루 물거폰 우라오스 미라이돈 ...)")
    
    if st.button("분석 시작"):
        if entry_input:
            with st.spinner("Gemini 3.0이 시뮬레이션을 돌리고 있습니다..."):
                # 1. 파싱
                opp_list, t1 = parse_opponent_input(entry_input)
                
                if opp_list:
                    st.session_state.opponent_list = opp_list
                    
                    # 2. BattleState 초기화
                    current_battle.initialize_opponent(opp_list)
                    
                    # 3. 분석 실행
                    analysis, t2 = analyze_entry_strategy(opp_list)
                    st.session_state.entry_analysis = analysis
                    
                    # 4. 선출 추출
                    t3 = {"total_tokens": 0}
                    try:
                        rec_team, t3 = parse_recommended_selection(analysis)
                        if rec_team:
                            lead = rec_team[0]
                            if lead in my_party.team:
                                current_battle.set_active("me", lead)
                                current_battle.set_my_selection(rec_team)
                    except Exception as e:
                        print(f"선출 자동 반영 실패: {e}")

                    # [New] 토큰 정보 저장
                    st.session_state.entry_tokens = {
                        "parser": t1.get('total_tokens', 0),
                        "strategy": t2.get('total_tokens', 0),
                        "selection": t3.get('total_tokens', 0)
                    }

                    st.success("✅ 전략 수립 및 선출 반영 완료!")
                    st.rerun()
                else:
                    st.error("입력 해석 실패")
    
    if st.session_state.entry_analysis:
        st.markdown("---")
        st.markdown(st.session_state.entry_analysis)
        
        # 하단 토큰 리포트
        st.divider()
        et = st.session_state.entry_tokens
        total_entry = et['parser'] + et['strategy'] + et['selection']
        
        st.caption("📊 **Token Usage Report (Entry Phase)**")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("1. 이름 파싱", f"{et['parser']}")
        c2.metric("2. 전략 분석", f"{et['strategy']}")
        c3.metric("3. 선출 추출", f"{et['selection']}")
        c4.metric("💰 Total", f"{total_entry}", delta_color="off")

# --- Tab 2: 배틀 ---
with tab2:
    # 대화 기록 표시
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    st.markdown("---")
    
    # 입력창
    with st.container():
        c1, c2 = st.columns([5, 1])
        with c1:
            user_input = st.chat_input("상황을 입력하세요 (예: 상대 미라이돈 등장, 내 피 50%)")
        with c2:
            opp_first = st.checkbox("상대 선공?", key="chk_opp_first", help="체크 시 스피드/스카프 추론 작동")

        if user_input:
            # 1. 사용자 메시지
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            
            # 2. AI 응답 (상태 업데이트 + 계산 + 조언)
            with st.chat_message("assistant"):
                place = st.empty()
                with st.spinner("계산 및 전략 수립 중..."):
                    # [핵심] battle.py 호출 -> 상태 갱신 -> 조언 생성
                    response, parser_tokens, analyze_tokens = analyze_battle_turn(user_input, opp_first)
                    
                    # [Token Update] 채팅 턴마다 토큰 누적 (Index 2: Total Token 가정)
                    p_cnt = parser_tokens[2] if parser_tokens and len(parser_tokens) > 2 else 0
                    a_cnt = analyze_tokens[2] if analyze_tokens and len(analyze_tokens) > 2 else 0
                    
                    st.session_state.battle_tokens["parser"] += p_cnt
                    st.session_state.battle_tokens["analysis"] += a_cnt
                    
                    # [수정] 응답 메시지 끝에 이번 턴 토큰 정보 추가
                    token_info = f"\n\n--- \n*💎 Cost: {p_cnt + a_cnt} Tokens (Parser: {p_cnt}, Analysis: {a_cnt})*"
                    full_response = response + token_info
                    
                    place.markdown(full_response)
            
            # 저장할 때도 토큰 정보가 포함된 버전을 저장
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # 3. 화면 갱신 (변경된 상태를 사이드바에 반영)
            st.rerun()

    # [New] 하단 토큰 리포트 (배틀 누적)
    st.divider()
    bt = st.session_state.battle_tokens
    total_battle = bt['parser'] + bt['analysis']
    
    st.caption("📊 **Token Usage Report (Battle Phase - Cumulative)**")
    bc1, bc2, bc3 = st.columns(3)
    bc1.metric("1. 상황 파싱", f"{bt['parser']}")
    bc2.metric("2. 전략 분석", f"{bt['analysis']}")
    bc3.metric("💰 Total", f"{total_battle}", delta_color="off")