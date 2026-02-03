import json
import os
import sys

# --- [경로 설정] ---
# 현재 파일 위치를 기준으로 경로를 잡습니다.
current_dir = os.path.dirname(os.path.abspath(__file__))

# Statistics 폴더 경로
STATISTICS_DIR = os.path.join(current_dir, "Statistics")

# 1. 랭크배틀 통계 (JSON) 경로
USAGE_DATA_PATH = os.path.join(STATISTICS_DIR, "rank_battle_data.json")

# 2. 선봉 통계 (TXT) 경로
LEAD_DATA_PATH = os.path.join(STATISTICS_DIR, "lead_stats.txt")


# --- [데이터 로딩 함수] ---
def load_usage_data():
    """ rank_battle_data.json 로드 """
    try:
        with open(USAGE_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ [RAG Error] 랭크배틀 데이터 파일을 찾을 수 없습니다: {USAGE_DATA_PATH}")
        return {}
    except json.JSONDecodeError:
        print("❌ [RAG Error] JSON 파일이 깨져있습니다.")
        return {}

def load_lead_data():
    """ lead_stats.txt 파싱하여 딕셔너리로 반환 """
    leads = {}
    if not os.path.exists(LEAD_DATA_PATH):
        return {}

    try:
        with open(LEAD_DATA_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        for line in lines:
            if "|" not in line or "Rank" in line or "Usage %" in line:
                continue
            
            parts = line.split("|")
            if len(parts) < 4: continue
            
            name = parts[2].strip()
            usage_str = parts[3].strip().replace("%", "")
            
            try:
                leads[name] = float(usage_str)
            except ValueError:
                continue
        return leads
    except Exception as e:
        print(f"⚠️ 선봉 데이터 파싱 중 오류: {e}")
        return {}

# --- [전역 데이터 로드] ---
SMOGON_DB = load_usage_data()
LEAD_STATS = load_lead_data()


# --- [기존 기능: 선출 분석용 텍스트 요약] ---
def get_pokemon_summary(pokemon_name):
    """
    특정 포켓몬의 정보를 LLM이 읽기 좋은 텍스트로 요약 반환
    (entry.py 및 battle.py 프롬프트용)
    """
    if pokemon_name not in SMOGON_DB:
        return f"⚠️ [{pokemon_name}]: Smogon 통계 데이터가 없습니다."

    data = SMOGON_DB[pokemon_name]
    
    # 선봉 확률 정보
    lead_prob = LEAD_STATS.get(pokemon_name, 0.0)
    lead_info = ""
    if lead_prob >= 10.0:
        lead_info = f"🔥선봉출전율: {lead_prob}% (매우 높음)"
    elif lead_prob >= 5.0:
        lead_info = f"⚠️선봉출전율: {lead_prob}% (높음)"
    elif lead_prob > 0:
        lead_info = f"선봉출전율: {lead_prob}%"
    else:
        lead_info = "선봉출전율: 정보 없음(낮음)"

    # 주요 정보 추출 (문자열로 변환)
    items = ", ".join([f"{i[0]}" for i in data.get('Items', [])[:3]])
    moves = ", ".join([f"{m[0]}" for m in data.get('Moves', [])[:7]])
    teras = ", ".join([f"{t[0]}" for t in data.get('TeraTypes', [])[:3]])
    if not teras: teras = "정보 없음"
    spread = data.get('Spreads', [])[0][0] if data.get('Spreads') else "정보 없음"
    usage_rate = data.get('Usage_Rate', 0)

    summary = f"""
    [{pokemon_name}] (전체사용률: {usage_rate}%) | {lead_info}
    - 도구: {items}
    - 테라: {teras}
    - 기술: {moves}
    - 노력치 분배: {spread}
    """
    return summary.strip()

def get_opponent_party_report(pokemon_list):
    """
    상대 엔트리 리스트(6마리)를 받아 전체 브리핑 리포트를 생성
    (entry.py 사용)
    """
    report = "=== 🕵️‍♂️ 상대 파티 분석 보고서 (Smogon Data & Lead Stats) ===\n"
    
    found_count = 0
    for poke in pokemon_list:
        summary = get_pokemon_summary(poke)
        report += summary + "\n"
        if "통계 데이터가 없습니다" not in summary:
            found_count += 1
            
    if found_count < len(pokemon_list):
        report += "\n⚠️ 일부 포켓몬의 데이터가 누락되었습니다. 이름(영어) 스펠링을 확인해주세요.\n"
        
    return report


# --- [NEW 기능: 배틀 상태 저장용 Raw Data 반환] ---
def get_pokemon_raw_data(pokemon_name):
    """
    [Battle Phase 용도]
    BattleState 객체에 저장하기 위해 가공되지 않은 리스트/딕셔너리 형태의 데이터를 반환합니다.
    (battle_state.py 사용)
    """
    if pokemon_name not in SMOGON_DB:
        return None

    data = SMOGON_DB[pokemon_name]
    
    return {
        # 기술 TOP 7 (이름만 리스트로) -> 방어 시뮬레이션용
        "predicted_moves": [m[0] for m in data.get('Moves', [])[:7]],
        
        # 도구 TOP 3 -> 아이템 추론용
        "predicted_items": [i[0] for i in data.get('Items', [])[:5]],
        
        # 특성 TOP 3
        "predicted_abilities": [a[0] for a in data.get('Abilities', [])[:3]],
        
        # 테라타입 TOP 3
        "predicted_teras": [t[0] for t in data.get('TeraTypes', [])[:3]],
        
        # 성격/노력치 샘플 -> 스탯 추정용
        "spread_sample": data.get('Spreads', [])[0][0] if data.get('Spreads') else None
    }

# --- [테스트 실행] ---
if __name__ == "__main__":
    # 테스트용
    test_poke = "Flutter Mane"
    print("--- Summary Report (For LLM) ---")
    print(get_pokemon_summary(test_poke))
    
    print("\n--- Raw Data (For BattleState) ---")
    raw = get_pokemon_raw_data(test_poke)
    print(raw)