import streamlit as st
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from rag_system import format_docs
from battle_state import BattleState

def execute(user_input, vectorstore, api_key):
    bs = st.session_state.battle_state

    # 1. LLM 초기화
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        google_api_key=api_key,
        temperature=0.0,
        max_output_tokens=500
    )
    
    # 2. 약어 변환
    norm_prompt = ChatPromptTemplate.from_template(
        "사용자 입력을 보고 '공식 포켓몬 영어이름' 6개로 변환해. 오직 이름 6개를 쉼표로 구분해 출력해.\n입력: {input}"
    )
    norm_chain = norm_prompt | llm | StrOutputParser()
    normalized_input = norm_chain.invoke({"input": user_input})
    
    opponent_list = [name.strip() for name in normalized_input.split(",")]
    bs.opponent_roster = opponent_list
    bs.opponent_status = {}

    # 3. RAG 검색 (k=6)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
    docs = retriever.invoke(normalized_input)
    
    # 4. 분석 프롬프트 (싱글배틀 3v3 맞춤형)
    analysis_prompt = ChatPromptTemplate.from_template(
        """
        너는 포켓몬 싱글배틀(3v3 Ranked Singles) 챔피언이야.
        [내 파티]와 [상대 파티]를 분석해서 **최적의 선출 3마리**를 정해.

        [내 파티]: {my_team}
        [상대 파티]: {opponent_team}
        [통계 데이터]: {context}
        
        [지시사항]:
        1. **싱글배틀 룰(3마리 선출)**을 엄수해.
        2. "selection"에는 내 파티의 영문 이름 3개를 순서대로 적어. (1번이 선발)
        3. 상대의 일관성(타점)을 끊거나, 스피드 싸움에서 유리한 선출을 추천해.

        **JSON 형식:**
        {{
            "selection": ["Lead_Pokemon", "Back_1", "Back_2"],
            "reasoning": "싱글배틀 관점에서의 분석 내용..."
        }}
        """
    )
    
    chain = analysis_prompt | llm | StrOutputParser()
    raw_response = chain.invoke({
        "my_team": bs.my_party_full,
        "opponent_team": ", ".join(opponent_list),
        "context": format_docs(docs)
    })
    
    # 5. 파싱
    try:
        json_str = raw_response
        if "```json" in raw_response:
            json_str = raw_response.split("```json")[1].split("```")[0].strip()
        elif "{" in raw_response:
            start = raw_response.find("{")
            end = raw_response.rfind("}") + 1
            json_str = raw_response[start:end]

        data = json.loads(json_str)
        selected_party = data.get("selection", [])
        
        # 3마리 보정
        if len(selected_party) < 3:
            remaining = [p for p in bs.my_roster if p not in selected_party]
            selected_party.extend(remaining[:3-len(selected_party)])
            
        bs.set_auto_selection(selected_party)
        
        reasoning = data.get("reasoning", "분석 실패")
        
        st.session_state.step = "BATTLE_PHASE"
        
        return (
            f"🔄 **상대 엔트리:** {normalized_input}\n\n"
            f"🤖 **AI 선출 (3마리):**\n"
            f"1️⃣ 선발: **{selected_party[0]}**\n"
            f"2️⃣ 후발: {selected_party[1]}, {selected_party[2]}\n\n"
            f"--- \n"
            f"📊 **전략 분석:**\n{reasoning}\n\n"
            f"--- \n"
            f"⚔️ **싱글배틀 시작!** 첫 턴 상황을 입력하세요."
        )

    except Exception as e:
        return f"❌ 오류: {e}\n원본: {raw_response}"