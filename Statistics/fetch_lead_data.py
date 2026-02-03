import requests
import os

# 설정
TARGET_DATE = "2025-12" 
FORMAT_NAME = "gen9bssregj"
RATING = "1760" 

# Leads 데이터는 JSON이 아니라 텍스트 테이블 형태입니다.
URL = f"https://www.smogon.com/stats/{TARGET_DATE}/leads/{FORMAT_NAME}-{RATING}.txt"
SAVE_PATH = os.path.join("Statistics", "lead_stats.txt")

def fetch_lead_stats():
    print(f"📡 선봉 데이터 다운로드: {URL}")
    response = requests.get(URL)

    # 파일로 저장
    if not os.path.exists("Statistics"):
        os.makedirs("Statistics")
        
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"✅ 선봉 데이터 저장 완료: {SAVE_PATH}")

def parse_lead_stats():
    """ 텍스트 파일을 읽어서 딕셔너리로 변환 {포켓몬명: 선봉사용률(%)} """
    leads = {}
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # Smogon 텍스트 테이블 파싱
        #  | Rank | Pokemon            | Usage % | ...
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
    except FileNotFoundError:
        return {}

if __name__ == "__main__":
    fetch_lead_stats()