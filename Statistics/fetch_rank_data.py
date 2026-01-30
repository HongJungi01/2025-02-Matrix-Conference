import requests
import json
import os

# --- 설정 구간 ---
TARGET_DATE = "2025-12" 
FORMAT_NAME = "gen9bssregj"
RATING = "1760" 

BASE_URL = f"https://www.smogon.com/stats/{TARGET_DATE}/chaos/"
FILE_NAME = f"{FORMAT_NAME}-{RATING}.json"
SAVE_FILE = "rank_battle_data.json"

def fetch_rank_data():
    full_url = f"{BASE_URL}{FILE_NAME}"
    print(f"📡 데이터 다운로드 시도: {full_url}")
    
    response = requests.get(full_url)
    
    if response.status_code != 200:
        print(f"⚠️ {RATING}점대 데이터가 없습니다. 전체 데이터(Rating 0)를 찾습니다...")
        fallback_file = f"{FORMAT_NAME}-0.json"
        full_url = f"{BASE_URL}{fallback_file}"
        response = requests.get(full_url)
        
        if response.status_code != 200:
            print(f"❌ 데이터를 찾을 수 없습니다. URL이나 날짜를 확인해주세요: {BASE_URL}")
            return

    print("✅ 데이터 다운로드 성공! 가공을 시작합니다...")
    raw_data = response.json()
    processed_data = {}

    if 'data' not in raw_data:
        print("❌ 데이터 구조가 예상과 다릅니다 ('data' 키 없음).")
        return

    # 테라타입 데이터가 실제로 있는지 확인하기 위한 디버그용 카운터
    tera_found_count = 0

    for pokemon, stats in raw_data['data'].items():
        if stats.get('usage', 0) < 0.01: 
            continue
        
        # 테라타입 키 찾기 (혹시 이름이 다를까봐 여러 후보군 탐색)
        tera_data = stats.get('TeraTypes') or stats.get('Tera Types') or stats.get('Terastal') or {}
        
        # 데이터가 있으면 카운트 증가
        if tera_data:
            tera_found_count += 1

        processed_data[pokemon] = {
            "Usage_Rate": round(stats.get('usage', 0) * 100, 2),
            "Moves": sorted(stats.get('Moves', {}).items(), key=lambda x: x[1], reverse=True)[:10],
            "Items": sorted(stats.get('Items', {}).items(), key=lambda x: x[1], reverse=True)[:5],
            "Abilities": sorted(stats.get('Abilities', {}).items(), key=lambda x: x[1], reverse=True)[:3],
            
            # [수정됨] 테라타입은 자르지 않고(slicing 없음) 전체 리스트를 다 저장
            "TeraTypes": sorted(tera_data.items(), key=lambda x: x[1], reverse=True),
            
            "Spreads": sorted(stats.get('Spreads', {}).items(), key=lambda x: x[1], reverse=True)[:3],
            "Teammates": sorted(stats.get('Teammates', {}).items(), key=lambda x: x[1], reverse=True)[:10]
        }

    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=2, ensure_ascii=False)
    
    print(f"🎉 완료! '{SAVE_FILE}'에 저장되었습니다.")

if __name__ == "__main__":
    fetch_rank_data()