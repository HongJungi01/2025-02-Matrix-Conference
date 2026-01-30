# Calculator/stat_estimator.py

import requests
import json
import os
import sys

# --- [모듈 임포트 경로 설정] ---
# 같은 폴더(Calculator)에 있는 stat_utils.py를 불러오기 위한 설정
try:
    # main.py에서 실행할 때 (패키지 형태)
    from Calculator.stat_utils import calculate_stat, parse_smogon_spread, NATURE_MODS
except ImportError:
    try:
        # 이 파일을 직접 실행하거나 같은 폴더 내에서 import 할 때
        from stat_utils import calculate_stat, parse_smogon_spread, NATURE_MODS
    except ImportError:
        # 경로가 완전히 꼬였을 경우를 대비해 현재 폴더를 sys.path에 추가
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)
        from stat_utils import calculate_stat, parse_smogon_spread, NATURE_MODS

# API 호출 횟수를 줄이기 위한 캐시
POKEAPI_CACHE = {}

def get_base_stats(pokemon_name):
    """
    PokeAPI를 통해 포켓몬의 종족값(Base Stats)을 가져옵니다.
    """
    # 이름 정규화 (Smogon: "Flutter Mane" -> API: "flutter-mane")
    api_name = pokemon_name.lower().replace(" ", "-").replace(".", "").replace(":", "")
    
    # 캐시 확인
    if api_name in POKEAPI_CACHE:
        return POKEAPI_CACHE[api_name]

    url = f"https://pokeapi.co/api/v2/pokemon/{api_name}"
    try:
        res = requests.get(url)
        if res.status_code != 200:
            print(f"⚠️ PokeAPI 검색 실패: {api_name} (Status: {res.status_code})")
            return None
            
        data = res.json()
        stats = {}
        for s in data['stats']:
            stats[s['stat']['name']] = s['base_stat']
        
        # API 키 이름을 우리 포맷으로 변경 (special-attack -> spa)
        formatted_stats = {
            "hp": stats['hp'],
            "atk": stats['attack'],
            "def": stats['defense'],
            "spa": stats['special-attack'],
            "spd": stats['special-defense'],
            "spe": stats['speed']
        }
        POKEAPI_CACHE[api_name] = formatted_stats
        return formatted_stats
    except Exception as e:
        print(f"API 에러: {e}")
        return None

def estimate_stats(pokemon_name, smogon_data_path=None):
    """
    Smogon 데이터의 1순위 샘플을 기반으로 포켓몬의 실능(Stats)을 추정합니다.
    """
    
    # --- [경로 자동 설정 로직] ---
    if smogon_data_path is None:
        # 1. 현재 파일(stat_estimator.py)이 있는 폴더 (.../Calculator)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 2. 부모 폴더(ProjectRoot)로 이동
        project_root = os.path.dirname(current_dir)
        
        # 3. Statistics 폴더 안의 json 파일 경로 완성
        # 결과: .../ProjectRoot/Statistics/rank_battle_data.json
        smogon_data_path = os.path.join(project_root, "Statistics", "rank_battle_data.json")
    # --------------------------------

    # 1. Smogon 데이터 로드
    try:
        with open(smogon_data_path, 'r', encoding='utf-8') as f:
            rank_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ [Error] 데이터 파일을 찾을 수 없습니다.\n경로 확인: {smogon_data_path}")
        return None
    
    if pokemon_name not in rank_data:
        # 데이터에 없으면 None 반환 (나중에 기본값 처리 등 필요)
        print(f"⚠️ Smogon 데이터에 없는 포켓몬: {pokemon_name}")
        return None

    # 2. 가장 많이 쓰이는 성격/노력치(Spread) 가져오기 (0번 인덱스 = 1순위)
    # 예: ["Modest:244/0/12/188/4/60", 0.35]
    if not rank_data[pokemon_name].get("Spreads"):
        print(f"⚠️ {pokemon_name}의 노력치(Spread) 데이터가 비어있습니다.")
        return None

    top_spread = rank_data[pokemon_name]["Spreads"][0][0]
    nature, evs = parse_smogon_spread(top_spread)
    
    # 3. 종족값(Base Stats) 가져오기
    base_stats = get_base_stats(pokemon_name)
    if not base_stats:
        return None

    # 4. 최종 실능 계산 (IV는 31로 가정 - 랭크배틀 표준)
    final_stats = {}
    iv = 31 
    
    # HP 계산
    final_stats["hp"] = calculate_stat(base_stats["hp"], iv, evs["hp"], 1.0, is_hp=True)
    
    # 나머지 스탯 계산 (공격, 방어, 특공, 특방, 스피드)
    for stat_name in ["atk", "def", "spa", "spd", "spe"]:
        # 성격 보정 값 찾기
        mod = NATURE_MODS.get(nature, {}).get(stat_name, 1.0)
        final_stats[stat_name] = calculate_stat(base_stats[stat_name], iv, evs[stat_name], mod, is_hp=False)
    
    return {
        "pokemon": pokemon_name,
        "nature": nature,
        "evs": evs,
        "stats": final_stats
    }

# --- 테스트 실행 코드 ---
if __name__ == "__main__":
    print("🧪 stat_estimator 테스트 시작...")
    
    # 테스트용 포켓몬 (망나뇽)
    test_pokemon = "Dragonite"
    
    result = estimate_stats(test_pokemon)
    
    if result:
        print(f"\n✅ {test_pokemon} 데이터 추정 성공!")
        print(f"성격: {result['nature']}")
        print(f"노력치: {result['evs']}")
        print(f"실능(Lv.50): {result['stats']}")
    else:
        print(f"\n❌ {test_pokemon} 데이터 추정 실패.")