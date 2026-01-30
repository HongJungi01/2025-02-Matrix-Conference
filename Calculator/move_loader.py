import requests
import json
import os

# 1. 캐시 파일 경로 설정
# (현재 파일 위치 기준으로 moves_cache.json 파일을 찾거나 생성)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "moves_cache.json")

# 2. 메모리 캐시 로드
_MEMORY_CACHE = {}

def load_cache_from_disk():
    """ 파일에서 캐시 로드 """
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache_to_disk():
    """ 메모리 캐시를 파일에 저장 """
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_MEMORY_CACHE, f, indent=2)
    except Exception as e:
        print(f"⚠️ 캐시 저장 실패: {e}")

# 초기 실행 시 캐시 로드
_MEMORY_CACHE = load_cache_from_disk()

# 3. 핵심 함수: 기술 정보 가져오기
def get_move_data(move_name):
    """
    기술 이름(영어)을 받아서 위력, 타입, 분류, 우선도 등을 반환합니다.
    """
    # API 요청을 위해 이름 소문자 변환 및 공백 처리 (Make It Rain -> make-it-rain)
    api_name = move_name.lower().replace(" ", "-")
    
    # 캐시에 있으면 반환
    if move_name in _MEMORY_CACHE:
        return _MEMORY_CACHE[move_name]

    # API 호출
    url = f"https://pokeapi.co/api/v2/move/{api_name}"
    
    try:
        # 타임아웃을 짧게 주어 너무 오래 걸리면 건너뛰도록 함
        response = requests.get(url, timeout=2)
        
        if response.status_code != 200:
            # 기술을 못 찾은 경우 기본값 반환 (에러 방지)
            default_data = {
                "name": move_name, 
                "type": "Normal", 
                "category": "Physical", 
                "power": 0, 
                "priority": 0
            }
            _MEMORY_CACHE[move_name] = default_data
            return default_data

        data = response.json()
        
        # 데이터 가공
        move_info = {
            "name": move_name,
            "type": data['type']['name'].capitalize(), # type
            "category": data['damage_class']['name'].capitalize(), # category
            "power": data['power'] if data['power'] else 0, # power
            "priority": data['priority'], # priority
            "accuracy": data['accuracy']
        }
        
        # 캐시 업데이트 및 저장
        _MEMORY_CACHE[move_name] = move_info
        save_cache_to_disk()
        
        return move_info

    except Exception as e:
        print(f"⚠️ 기술 데이터 조회 실패 ({move_name}): {e}")
        # 실패 시에도 프로그램이 죽지 않도록 기본값 반환
        return {
            "name": move_name, 
            "type": "Normal", 
            "category": "Physical", 
            "power": 0, 
            "priority": 0
        }

# 테스트용 코드 (이 파일을 직접 실행했을 때만 동작)
if __name__ == "__main__":
    print("Testing get_move_data...")
    print(get_move_data("Extreme Speed")) # 신속
    print(get_move_data("Moonblast"))     # 문포스