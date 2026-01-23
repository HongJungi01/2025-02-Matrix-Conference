import os
import shutil
import requests
import re
from dotenv import load_dotenv

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document

# ==========================================
# ⚙️ 설정값: 싱글배틀(BSS) 최신 데이터로 변경
# ==========================================
# gen9bssregj = Gen 9 Battle Stadium Singles (3v3 랭크배틀)
TARGET_URL = "https://www.smogon.com/stats/2025-12/moveset/gen9bssregj-1760.txt"
DB_PATH = "./chroma_db"

def load_api_key():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("❌ .env 파일에서 GOOGLE_API_KEY를 찾을 수 없습니다.")
    return api_key

def fetch_smogon_data(url):
    print(f"📡 Smogon 싱글배틀 데이터 다운로드 중... ({url})")
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ 다운로드 실패: {e}")
        return []

    raw_text = response.text
    documents = []
    split_text = raw_text.split(" +----------------------------------------+ ")
    
    print(f"⚙️ 텍스트 데이터 정제 및 파싱 중...")
    
    for chunk in split_text:
        lines = chunk.strip().split('\n')
        if len(lines) < 5: continue 
        
        try:
            name_line = lines[1]
            if '|' not in name_line: continue
            
            pokemon_name = name_line.split('|')[1].strip()
            if pokemon_name == "Pokemon": continue 
            
            clean_content = chunk.replace("|", "").strip()
            clean_content = re.sub(r'\s+', ' ', clean_content)
            
            # 싱글배틀임을 명시
            final_text = (
                f"Pokemon: {pokemon_name}\n"
                f"Format: Gen9 Battle Stadium Singles (3v3)\n"
                f"Statistics:\n{clean_content}"
            )
            
            doc = Document(
                page_content=final_text,
                metadata={"name": pokemon_name, "source": "smogon_bss"}
            )
            documents.append(doc)
            
        except Exception:
            continue
            
    print(f"✅ 파싱 완료: 총 {len(documents)}마리의 싱글배틀 데이터 확보")
    return documents

def build_vector_db(documents, api_key):
    if os.path.exists(DB_PATH):
        print(f"🗑️ 기존 DB 폴더({DB_PATH}) 삭제 중...")
        shutil.rmtree(DB_PATH)
    
    print("🔌 임베딩 모델 초기화...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=api_key
    )
    
    print("💾 벡터 DB 저장 시작 (ChromaDB)...")
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=DB_PATH
    )
    print(f"🎉 DB 구축 성공! (싱글배틀 3v3 모드)")

if __name__ == "__main__":
    try:
        key = load_api_key()
        docs = fetch_smogon_data(TARGET_URL)
        if docs:
            build_vector_db(docs, key)
        else:
            print("❌ 데이터가 없어 DB를 생성하지 못했습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")