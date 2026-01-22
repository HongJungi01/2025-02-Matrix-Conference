import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import os

# 1. 설정 (자율주행으로 치면 센서 초기화)

load_dotenv()

# API 키 확인
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# 2. 모델 준비 (Gemini 3.0 Flash - 빠르고 효율적)
llm = ChatGoogleGenerativeAI(
    model="gemini-flash-latest", # 혹은 3.0-flash (출시 상황에 맞춰 모델명 변경)
    google_api_key=GOOGLE_API_KEY,
    temperature=0.0 # RAG에서는 창의성(0.8)보다 사실성(0.0)이 중요
)

# 3. LangChain 체인 만들기 (ROS 노드 연결하듯이)
# 지금은 DB 없이 LLM만 있는 상태. 나중에 여기에 DB 검색 로직을 끼워 넣습니다.
prompt = ChatPromptTemplate.from_template(
    "너는 포켓몬 배틀 전문가야. 다음 질문에 대해 논리적으로 답해줘.\n질문: {question}"
)
chain = prompt | llm | StrOutputParser()

# 4. Streamlit UI (사용자 인터페이스)
st.title("Poke-Advisor 🎮")
st.caption("Gen 9 실전 배틀 전략 컨설턴트")

# 채팅 입력창
user_input = st.chat_input("질문을 입력하세요 (예: 날개치는머리 샘플 추천해줘)")

if user_input:
    # 화면에 내 질문 표시
    st.chat_message("user").write(user_input)
    
    # AI 답변 생성 (LangChain 구동)
    with st.spinner("데이터 분석 중..."):
        response = chain.invoke({"question": user_input})
        
    # 화면에 AI 답변 표시
    st.chat_message("assistant").write(response)