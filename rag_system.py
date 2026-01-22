import os
import streamlit as st
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

@st.cache_resource
def load_rag_system(api_key):
    """
    RAG 시스템(DB, LLM)을 로드하고 캐싱합니다.
    """
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001", 
        google_api_key=api_key
    )
    
    # DB 폴더 체크
    if not os.path.exists("./chroma_db"):
        return None, None
        
    vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    
    # 검색 범위(k) 설정
    retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        google_api_key=api_key,
        temperature=0.0
    )
    return retriever, llm

def format_docs(docs):
    """검색된 문서를 텍스트로 합치는 유틸리티 함수"""
    return "\n\n".join([d.page_content for d in docs])