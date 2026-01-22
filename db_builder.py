import os
import shutil
import requests
import re
from dotenv import load_dotenv

# LangChain 관련
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document

# ==========================================
# ⚙️ 설정값
# ==========================================
# 타겟 URL: 2026년 1월 시점의 최신 데이터 (Gen9 VGC 2026 Reg F - 1760+)
TARGET_URL = "https://www.smogon.com/stats/2025-12/moveset/gen9vgc2026regf-1760.txt"
DB_PATH = "./chroma_db"

def load_api_key():
    """환경변수에서 API 키 로드"""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("❌ .env 파일에서 GOOGLE_API_KEY를 찾을 수 없습니다.")
    return api_key

def fetch_smogon_data(url):
    """Smogon에서 데이터 다운로드 및 파싱"""
    print(f"📡 Smogon 데이터 다운로드 중... ({url})")
    try:
        response = requests.get(url)
        response.raise_for_status() # 에러 체크
    except Exception as e:
        print(f"❌ 다운로드 실패: {e}")
        return []

    raw_text = response.text
    documents = []
    
    # Smogon 데이터는 " +----------------------------------------+ " 로 구분됨
    split_text = raw_text.split(" +----------------------------------------+ ")
    
    print(f"⚙️ 텍스트 데이터 정제 및 파싱 중...")
    
    for chunk in split_text:
        lines = chunk.strip().split('\n')
        if len(lines) < 5: continue 
        
        try:
            # 포켓몬 이름 추출
            name_line = lines[1]
            if '|' not in name_line: continue
            
            pokemon_name = name_line.split('|')[1].strip()
            if pokemon_name == "Pokemon": continue 
            
            # [전처리] 
            # 1. 불필요한 파이프(|) 제거
            # 2. 다중 공백을 단일 공백으로 치환
            clean_content = chunk.replace("|", "").strip()
            clean_content = re.sub(r'\s+', ' ', clean_content)
            
            # 최종 텍스트 포맷팅
            final_text = (
                f"Pokemon: {pokemon_name}\n"
                f"Format: Gen9 VGC 2026 Regulation F (High Ladder 1760+)\n"
                f"Statistics:\n{clean_content}"
            )
            
            # 문서 객체 생성
            doc = Document(
                page_content=final_text,
                metadata={"name": pokemon_name, "source": "smogon"}
            )
            documents.append(doc)
            
        except Exception:
            continue
            
    print(f"✅ 파싱 완료: 총 {len(documents)}마리의 포켓몬 데이터 확보")
    return documents

def build_vector_db(documents, api_key):
    """벡터 DB 구축 (기존 DB 삭제 후 재생성)"""
    
    # 1. 기존 DB 폴더가 있다면 삭제 (Clean Build)
    if os.path.exists(DB_PATH):
        print(f"🗑️ 기존 DB 폴더({DB_PATH}) 삭제 중...")
        shutil.rmtree(DB_PATH)
    
    # 2. 임베딩 모델 설정
    print("🔌 임베딩 모델(Google embedding-001) 초기화...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=api_key
    )
    
    # 3. DB 저장
    print("💾 벡터 DB 저장 시작 (ChromaDB)...")
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=DB_PATH
    )
    
    print(f"🎉 DB 구축 성공! 데이터가 '{DB_PATH}'에 저장되었습니다.")

# ==========================================
# 🚀 메인 실행부
# ==========================================
if __name__ == "__main__":
    try:
        # 1. 키 로드
        key = load_api_key()
        
        # 2. 데이터 가져오기
        docs = fetch_smogon_data(TARGET_URL)
        
        if docs:
            # 3. DB 만들기
            build_vector_db(docs, key)
        else:
            print("❌ 데이터가 없어 DB를 생성하지 못했습니다.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")