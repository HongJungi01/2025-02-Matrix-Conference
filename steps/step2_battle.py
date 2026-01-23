import streamlit as st
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from rag_system import format_docs

def execute(user_input, vectorstore, api_key):
    bs = st.session_state.battle_state
    
    # 1. 초고속 LLM (토큰 300제한)
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        google_api_key=api_key,
        temperature=0.0,
        max_output_tokens=500
    )

    # 2. 검색 (k=1, 현재 대면 중인 상대 정보만 보면 됨)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 1})
    
    # "현재 상대 필드에 있는 놈" 위주로 검색
    search_query = f"{user_input} {bs.opponent_active[0]}"
    context_docs = retriever.invoke(search_query)
    
    # 3. 싱글배틀 최적화 프롬프트
    template = """
    싱글배틀(1v1) 상황이야. [상태]와 [통계]를 보고 JSON(갱신)과 TEXT(지시)를 출력해.
    
    [상태]: {current_state}
    [통계]: {rag_context}
    [입력]: {user_input}

    **지시사항:**
    1. **교체 플레이**나 **랭크업 기점**을 중요하게 봐.
    2. 설명은 생략하고 **구체적인 행동**만 짧게 적어. (예: "망나뇽으로 교체해.", "지진 사용.")

    **출력 형식:**
    ```json
    {{
        "my_active": ["내_현재_포켓몬"],
        "opp_active": ["상대_현재_포켓몬"],
        "my_hp": {{"내_포켓몬": "80%"}},
        "opp_hp": {{"상대_포켓몬": "50%"}},
        "opp_info": {{"상대_포켓몬": {{"item": "기합의띠", "moves": ["카운터"]}} }}
    }}
    ```
    ===ADVICE_START===
    (핵심 행동 지침)
    """
    prompt = ChatPromptTemplate.from_template(template)
    
    chain = prompt | llm | StrOutputParser()
    
    raw_response = chain.invoke({
        "current_state": bs.get_context_text(),
        "rag_context": format_docs(context_docs),
        "user_input": user_input
    })
    
    # 파싱 로직
    advice_text = raw_response
    try:
        json_str = ""
        if "```json" in raw_response:
            parts = raw_response.split("```json")
            json_part = parts[1].split("```")[0]
            json_str = json_part.strip()
            
            if "===ADVICE_START===" in raw_response:
                advice_text = raw_response.split("===ADVICE_START===")[1].strip()
        
        if json_str:
            update_data = json.loads(json_str)
            bs.update_from_json(update_data)
            
    except Exception as e:
        print(f"Parsing Error: {e}")
    
    return advice_text