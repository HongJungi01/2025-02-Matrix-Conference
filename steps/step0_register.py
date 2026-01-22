import streamlit as st

def extract_name_from_showdown(text):
    """
    Showdown 포맷의 첫 줄에서 포켓몬 이름을 추출
    예: "Roaring Moon @ Booster Energy" -> "Roaring Moon"
    """
    first_line = text.strip().split("\n")[0]
    # '@' 기준으로 자르거나, 없으면 전체 사용
    if "@" in first_line:
        name = first_line.split("@")[0].strip()
    else:
        name = first_line.strip()
    
    # 성별 표시 (M), (F) 제거 (선택사항)
    # 예: "Landorus-Therian (M)" -> "Landorus-Therian"
    # 필요하다면 아래 주석 해제
    # if "(" in name and ")" in name:
    #     name = name.split("(")[0].strip()
        
    return name

def execute(user_input):
    bs = st.session_state.battle_state
    
    # 1. 입력된 포켓몬 정보 임시 저장
    bs.temp_party_inputs.append(user_input)
    
    # 이름 추출 (UI 표시용)
    mon_name = extract_name_from_showdown(user_input)
    bs.my_roster.append(mon_name)
    
    current_count = len(bs.temp_party_inputs)
    
    # 2. 6마리가 아직 안 찼을 경우
    if current_count < 6:
        return (
            f"✅ **{mon_name}** 등록 완료! ({current_count}/6)\n"
            f"다음 포켓몬({current_count + 1}번째)의 정보를 입력해주세요."
        )
    
    # 3. 6마리가 모두 입력된 경우 (완료 처리)
    else:
        # 전체 텍스트 하나로 합치기
        bs.my_party_full = "\n\n".join(bs.temp_party_inputs)
        
        # 임시 저장소 비우기 (나중을 위해)
        bs.temp_party_inputs = []
        
        # 다음 단계로 이동
        st.session_state.step = "ANALYZE_MATCHUP"
        
        return (
            f"✅ **{mon_name}** 등록 완료! (6/6)\n"
            f"🎉 모든 파티 정보가 저장되었습니다.\n\n"
            f"이제 **상대방 포켓몬 6마리의 이름**을 입력해주세요."
        )