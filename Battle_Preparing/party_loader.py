import os
import sys

# 경로 설정 (Calculator 폴더의 모듈을 쓰기 위함)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from Battle_Preparing.user_party import my_party
from Calculator.stat_utils import calculate_stat, NATURE_MODS
from Calculator.stat_estimator import get_base_stats # 종족값 가져오는 함수 재사용

def parse_evs_ivs(line):
    """ 'EVs: 252 HP / 4 Atk' 같은 문자열을 딕셔너리로 변환 """
    stats = {'hp': 0, 'atk': 0, 'def': 0, 'spa': 0, 'spd': 0, 'spe': 0}
    # "EVs: " 제거 및 " / "로 분리
    parts = line.split(':')[1].strip().split(' / ')
    
    mapping = {
        'HP': 'hp', 'Atk': 'atk', 'Def': 'def', 
        'SpA': 'spa', 'SpD': 'spd', 'Spe': 'spe'
    }
    
    for part in parts:
        part = part.strip()
        value, stat_name = part.split(' ')
        if stat_name in mapping:
            stats[mapping[stat_name]] = int(value)
            
    return stats

def load_party_from_file(file_path="my_team.txt"):
    print(f"📂 '{file_path}'에서 파티 정보를 불러옵니다...")
    
    if not os.path.exists(file_path):
        print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 포켓몬 사이는 빈 줄(\n\n)로 구분됨
    blocks = content.strip().split('\n\n')

    for block in blocks:
        lines = block.strip().split('\n')
        if not lines: continue

        # 1. 이름 및 도구 파싱 (첫 줄: "Roaring Moon @ Booster Energy")
        first_line = lines[0]
        if '@' in first_line:
            name_part, item_part = first_line.split('@')
            name = name_part.strip()
            item = item_part.strip()
        else:
            name = first_line.strip()
            item = None

        # (성별 표시 (M)/(F) 제거 로직 필요시 추가)
        if "(M)" in name: name = name.replace("(M)", "").strip()
        if "(F)" in name: name = name.replace("(F)", "").strip()

        # 2. 나머지 정보 파싱
        ability = None
        tera_type = None
        nature = "Hardy" # 기본 성격
        evs = {'hp': 0, 'atk': 0, 'def': 0, 'spa': 0, 'spd': 0, 'spe': 0}
        ivs = {'hp': 31, 'atk': 31, 'def': 31, 'spa': 31, 'spd': 31, 'spe': 31} # 기본 6V
        moves = []

        for line in lines[1:]:
            line = line.strip()
            if line.startswith("Ability:"):
                ability = line.split(":")[1].strip()
            elif line.startswith("Tera Type:"):
                tera_type = line.split(":")[1].strip()
            elif line.startswith("EVs:"):
                evs.update(parse_evs_ivs(line))
            elif line.startswith("IVs:"):
                # IVs는 기본 31에서 덮어쓰기
                parsed_ivs = parse_evs_ivs(line)
                ivs.update(parsed_ivs)
            elif "Nature" in line:
                nature = line.split(" ")[0].strip()
            elif line.startswith("- "):
                moves.append(line[2:].strip())

        # 3. 실제 스탯(실능) 계산 (PokeAPI 연동)
        print(f"Wait... {name}의 데이터를 조회 중...")
        base_stats = get_base_stats(name)
        
        if not base_stats:
            print(f"⚠️ {name}의 종족값을 찾을 수 없어 스킵합니다.")
            continue

        final_stats = {}
        for stat in ['hp', 'atk', 'def', 'spa', 'spd', 'spe']:
            # 성격 보정치 확인
            mod = NATURE_MODS.get(nature, {}).get(stat, 1.0)
            
            is_hp = (stat == 'hp')
            final_stats[stat] = calculate_stat(
                base_stats[stat], 
                ivs[stat], 
                evs[stat], 
                mod, 
                is_hp=is_hp
            )

        # 4. UserParty에 등록
        my_party.add_pokemon(
            name=name,
            stats=final_stats,
            item=item,
            ability=ability,
            moves=moves,
            tera_type=tera_type
        )

    print(f"✅ 총 {len(my_party.team)}마리의 포켓몬이 파티에 등록되었습니다!\n")

# 테스트 실행
if __name__ == "__main__":
    load_party_from_file("my_team.txt")
    print(my_party.team)