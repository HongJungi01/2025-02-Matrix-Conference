import math
import os
import sys

# ---------------------------------------------------------
# [1] 데이터 및 유틸리티
# ---------------------------------------------------------

TYPE_CHART = {
    "Normal": {"Rock": 0.5, "Ghost": 0, "Steel": 0.5},
    "Fire": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0},
    "Water": {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
    "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0, "Flying": 2.0, "Dragon": 0.5},
    "Grass": {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5, "Steel": 0.5},
    "Ice": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0, "Dark": 2.0, "Steel": 2.0, "Fairy": 0.5},
    "Poison": {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0, "Fairy": 2.0},
    "Ground": {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0},
    "Flying": {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0, "Steel": 0.5},
    "Bug": {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0, "Steel": 0.5, "Fairy": 0.5},
    "Rock": {"Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0, "Steel": 0.5},
    "Ghost": {"Normal": 0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
    "Dragon": {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0},
    "Dark": {"Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5, "Fairy": 0.5},
    "Steel": {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0, "Rock": 2.0, "Steel": 0.5, "Fairy": 2.0},
    "Fairy": {"Fire": 0.5, "Fighting": 2.0, "Poison": 0.5, "Dragon": 2.0, "Dark": 2.0, "Steel": 0.5}
}

def get_type_effectiveness(move_type, defender_types):
    multiplier = 1.0
    for dtype in defender_types:
        if move_type in TYPE_CHART:
            multiplier *= TYPE_CHART[move_type].get(dtype, 1.0)
    return multiplier

def get_rank_multiplier(stage):
    if stage == 0: return 1.0
    if stage > 0: return (2 + stage) / 2
    return 2 / (2 + abs(stage))

def apply_rank(stat_value, stage):
    return int(stat_value * get_rank_multiplier(stage))

# ---------------------------------------------------------
# [2] 데미지 계산 로직 (Pure Function)
# ---------------------------------------------------------

def calculate_damage_math(att_spec, def_spec, move_spec, field_spec):

    level = 50
    
    # --- 정보 언패킹 ---
    move_power = move_spec['power']
    move_type = move_spec['type']
    move_cat = move_spec['category'] # Physical / Special
    is_crit = move_spec.get('is_crit', False) # [New] 급소 여부
    
    weather = field_spec.get('weather')
    terrain = field_spec.get('terrain')
    screens = def_spec.get('screens', {}) 
    
    # 1. 위력 보정 (날씨/필드)
    weather_mod = 1.0
    if weather == "Sun":
        if move_type == "Fire": weather_mod = 1.5
        elif move_type == "Water": weather_mod = 0.5
    elif weather == "Rain":
        if move_type == "Water": weather_mod = 1.5
        elif move_type == "Fire": weather_mod = 0.5
        
    terrain_mod = 1.0
    if terrain == "Electric" and move_type == "Electric": terrain_mod = 1.3
    elif terrain == "Grassy" and move_type == "Grass": terrain_mod = 1.3
    elif terrain == "Psychic" and move_type == "Psychic": terrain_mod = 1.3
    elif terrain == "Misty" and move_type == "Dragon": terrain_mod = 0.5

    base_power = math.floor(move_power * weather_mod * terrain_mod)
    
    # 2. 스탯 결정 및 랭크 반영 (급소 로직 적용)
    # 급소 시: 공격자의 '랭크 다운' 무시 / 방어자의 '랭크 업' 무시
    
    if move_cat == "Physical":
        raw_atk = att_spec['stats']['atk']
        raw_def = def_spec['stats']['def']
        atk_rank = att_spec['ranks'].get('atk', 0)
        def_rank = def_spec['ranks'].get('def', 0)
    else:
        raw_atk = att_spec['stats']['spa']
        raw_def = def_spec['stats']['spd']
        atk_rank = att_spec['ranks'].get('spa', 0)
        def_rank = def_spec['ranks'].get('spd', 0)

    # [New] 급소 보정: 유리한 랭크만 적용
    if is_crit:
        if atk_rank < 0: atk_rank = 0 # 공격자의 랭크 하락 무시
        if def_rank > 0: def_rank = 0 # 방어자의 랭크 상승 무시

    final_atk = apply_rank(raw_atk, atk_rank)
    final_def = apply_rank(raw_def, def_rank)

    # 3. 기초 데미지 계산
    base_damage = math.floor((math.floor((2 * level / 5 + 2) * base_power * final_atk / final_def) / 50) + 2)
    damage = base_damage

    # 4. 보정치 적용
    
    # (1) 화상 (물리 0.5배) - 객기 예외처리는 생략(호출자가 power를 2배로 주거나 해야 함)
    if att_spec.get('status') == "Burn" and move_cat == "Physical":
        damage = math.floor(damage * 0.5)
        
    # (2) 벽 (0.5배) - [New] 급소 시 무시
    if screens and not is_crit:
        if move_cat == "Physical" and screens.get('reflect'):
            damage = math.floor(damage * 0.5)
        elif move_cat == "Special" and screens.get('light_screen'):
            damage = math.floor(damage * 0.5)

    # (3) 도구 (간단 예시)
    item_mod = 1.0
    item = att_spec.get('item')
    if item == "Choice Band" and move_cat == "Physical": item_mod = 1.5
    elif item == "Choice Specs" and move_cat == "Special": item_mod = 1.5
    elif item == "Life Orb": item_mod = 1.3
    damage = math.floor(damage * item_mod)
    
    # (4) 급소 (1.5배)
    is_tera = att_spec.get('is_terastal', False)
    tera_type = att_spec.get('tera_type')
    original_types = att_spec.get('types', []) # 포켓몬의 원래 타입 리스트
    
    stab = 1.0
    
    if is_tera:
        # [Case 1] 사용하는 기술이 '테라 타입'과 같은 경우
        if move_type == tera_type:
            # 원래 타입에도 포함되어 있었다면 -> 2.0배 (적응력 효과)
            if move_type in original_types:
                stab = 2.0
            # 원래 타입은 아니었다면 -> 1.5배
            else:
                stab = 1.5
        
        # [Case 2] 기술이 테라 타입은 아니지만, '원래 타입'인 경우 (기존 자속 유지)
        # 예: 망나뇽(드래곤/비행)이 노말 테라를 하고 역린(드래곤)을 쓸 때 -> 1.5배 유지
        elif move_type in original_types:
            stab = 1.5
            
    else:
        # [Case 3] 테라스탈 안 함 (기본 자속)
        if move_type in original_types:
            stab = 1.5
            
    damage = math.floor(damage * stab)

    # (6) 상성
    type_eff = get_type_effectiveness(move_type, def_spec.get('types', []))
    damage = math.floor(damage * type_eff)

    # 5. 난수 범위 (0.85 ~ 1.00)
    min_damage = math.floor(damage * 0.85)
    max_damage = damage
    
    hp_stat = def_spec['stats']['hp']
    min_percent = round((min_damage / hp_stat) * 100, 1)
    max_percent = round((max_damage / hp_stat) * 100, 1)

    # 결과 문자열
    if min_damage >= hp_stat: ko_result = "확정 1타"
    elif max_damage >= hp_stat: ko_result = "난수 1타"
    elif min_damage * 2 >= hp_stat: ko_result = "확정 2타"
    else: ko_result = "난수 2타 이상"

    return {
        "damage_range": f"{min_damage}~{max_damage}",
        "percent_range": f"{min_percent}%~{max_percent}%",
        "ko_result": ko_result,
        "effectiveness": type_eff
    }

# ---------------------------------------------------------
# [3] 메인 실행 함수 (Interface)
# ---------------------------------------------------------

def run_calculation(attacker_spec, defender_spec, move_spec, field_spec):
    """
    [Interface Function]
    외부에서 스펙을 입력받아 데미지 계산 결과만 반환합니다.
    """
    
    # 데미지 계산
    dmg_res = calculate_damage_math(attacker_spec, defender_spec, move_spec, field_spec)
    
    # 결과 반환
    return {
        "move": move_spec['name'],
        "damage": dmg_res,
        "summary": f"{dmg_res['ko_result']} (상성 {dmg_res['effectiveness']}배)"
    }