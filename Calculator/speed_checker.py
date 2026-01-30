import math

def get_rank_multiplier(stage):
    if stage == 0: return 1.0
    if stage > 0: return (2 + stage) / 2
    return 2 / (2 + abs(stage))

def calculate_dynamic_speed(stats, ranks, item, status, ability, field_state):
    """
    [스피드 실수치 계산]
    특성(쓱쓱, 곡예 등)과 날씨/필드 상호작용 반영
    * 고대활성/쿼크차지는 외부에서 스탯이나 랭크를 수정해서 입력한다고 가정하고 여기서는 제외함.
    """
    # 1. 기본 실수치
    speed = stats.get('spe', 0)
    
    # 2. 랭크업
    rank_stage = ranks.get('spe', 0)
    speed = int(speed * get_rank_multiplier(rank_stage))
    
    # 3. 아이템 (구애스카프, 철구 등)
    if item == "Choice Scarf":
        speed = int(speed * 1.5)
    elif item == "Iron Ball":
        speed = int(speed * 0.5)

    # 4. 특성 & 날씨 상호작용 (Speed Abilities)
    weather = field_state.get('weather')
    terrain = field_state.get('terrain')

    if ability == "Swift Swim" and weather == "Rain":       # 쓱쓱 (비)
        speed *= 2
    elif ability == "Chlorophyll" and weather == "Sun":     # 엽록소 (쾌청)
        speed *= 2
    elif ability == "Sand Rush" and weather == "Sand":      # 모래헤치기 (모래바람)
        speed *= 2
    elif ability == "Slush Rush" and weather == "Snow":     # 눈치우기 (설경)
        speed *= 2
    elif ability == "Surge Surfer" and terrain == "Electric": # 서핑테일 (일렉트릭필드)
        speed *= 2
    elif ability == "Unburden" and field_state.get('item_lost'): # 곡예 (도구 소모)
        speed *= 2
    
    # [삭제됨] 고대활성(Protosynthesis) / 쿼크차지(Quark Drive)
    # 외부에서 처리: 스피드가 오르는 경우라면 rank에 +1을 더해주거나, 
    # 기본 stats['spe']에 1.5배를 해서 넘겨주는 것을 권장.

    # 5. 상태이상 (마비)
    if status == "Paralysis":
        if ability == "Quick Feet": # 속보
            speed = int(speed * 1.5)
        else:
            speed = int(speed * 0.5)

    # 6. 순풍
    if field_state.get('tailwind', False):
        speed *= 2
        
    return int(speed)

def calculate_priority_bonus(priority, move_cat, move_type, ability, hp_percent):
    """
    [우선도 보정]
    """
    final_prio = priority
    
    # 짓궂은마음 (Prankster)
    if ability == "Prankster" and move_cat == "Status":
        final_prio += 1
        
    # 질풍날개 (Gale Wings)
    if ability == "Gale Wings" and move_type == "Flying" and hp_percent >= 100:
        final_prio += 1
        
    return final_prio

def check_turn_order(my_spec, opp_spec, field_spec, my_move_spec, opp_move_spec=None):
    """
    [최종 턴 순서 판정]
    """
    # 1. 스피드 계산
    my_field = {
        'weather': field_spec.get('weather'),
        'terrain': field_spec.get('terrain'),
        'tailwind': field_spec.get('tailwind_me'),
        'item_lost': field_spec.get('my_item_lost', False)
    }
    opp_field = {
        'weather': field_spec.get('weather'),
        'terrain': field_spec.get('terrain'),
        'tailwind': field_spec.get('tailwind_opp'),
        'item_lost': field_spec.get('opp_item_lost', False)
    }

    my_speed = calculate_dynamic_speed(
        my_spec['stats'], my_spec.get('ranks', {}), 
        my_spec.get('item'), my_spec.get('status'), 
        my_spec.get('ability'), my_field
    )
    
    opp_speed = calculate_dynamic_speed(
        opp_spec['stats'], opp_spec.get('ranks', {}), 
        opp_spec.get('item'), opp_spec.get('status'), 
        opp_spec.get('ability'), opp_field
    )

    # 2. 우선도 계산
    my_prio = calculate_priority_bonus(
        my_spec.get('priority', 0), 
        my_move_spec.get('category', 'Physical'), 
        my_move_spec.get('type', 'Normal'),
        my_spec.get('ability'),
        100 
    )
    
    opp_prio = 0
    if opp_move_spec:
        opp_prio = calculate_priority_bonus(
            opp_move_spec.get('priority', 0),
            opp_move_spec.get('category'),
            opp_move_spec.get('type'),
            opp_spec.get('ability'),
            100
        )

    # 3. 판정
    is_my_turn = False
    reason = ""
    
    if my_prio > opp_prio:
        is_my_turn = True
        reason = f"우선도 승리 (+{my_prio} vs {opp_prio})"
    elif my_prio < opp_prio:
        is_my_turn = False
        reason = f"우선도 패배 ({my_prio} < {opp_prio})"
    else:
        # 동속 or 스피드 싸움
        is_trick_room = field_spec.get('trick_room', False)
        
        if my_speed == opp_speed:
            is_my_turn = None # Tie
            reason = "스피드 동속 (50%)"
        else:
            if is_trick_room:
                is_my_turn = (my_speed < opp_speed)
                reason = "트릭룸 (느린 쪽 선공)" if is_my_turn else "트릭룸 (상대가 더 느림)"
            else:
                is_my_turn = (my_speed > opp_speed)
                reason = "스피드 우위" if is_my_turn else "스피드 열세"

    return {
        "is_my_turn": is_my_turn,
        "reason": reason,
        "my_final_speed": my_speed,
        "opp_final_speed": opp_speed,
        "details": f"나(S{my_speed}/P{my_prio}) vs 상대(S{opp_speed}/P{opp_prio})"
    }