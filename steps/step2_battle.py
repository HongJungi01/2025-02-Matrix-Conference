import streamlit as st
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag_system import format_docs

def execute(user_input, retriever, llm):
    bs = st.session_state.battle_state
    
    # 1. RAG 검색 (사용자 입력 + 현재 필드에 있는 포켓몬 정보 검색)
    # 현재 필드에 있는 포켓몬들의 이름도 같이 검색 쿼리에 넣어줍니다.
    search_query = f"{user_input} {' '.join(bs.opponent_active)}"
    context_docs = retriever.invoke(search_query)
    
    # 2. 프롬프트 정의 (JSON 출력 강제)
    # 전략과 상태 업데이트를 동시에 요구합니다.
    template = """
    너는 포켓몬 더블 배틀 AI야. [현재 상태]와 [사용자 입력]을 보고 두 가지를 출력해야 해.

    1. **STATE_UPDATE (JSON)**: 사용자의 입력에 따라 변화된 전황을 JSON 형식으로 추출해.
       - 필드에 나와있는 포켓몬(active), 체력 변화(hp), 밝혀진 도구/기술(info) 등을 갱신해.
       - 모르는 정보는 기존 값을 유지하거나 "?"로 둬.
    2. **ADVICE (Text)**: 갱신된 상태와 통계 데이터를 바탕으로 최선의 전략을 조언해.

    [현재 상태 공간]:
    {current_state}

    [Smogon 통계 데이터]:
    {rag_context}

    [사용자 입력 (이번 턴 상황)]: 
    {user_input}

    ---
    **반드시 아래 형식을 지켜서 출력해:**
    
    ```json
    {{
        "my_active": ["포켓몬A", "포켓몬B"],
        "opp_active": ["포켓몬C", "포켓몬D"],
        "my_hp": {{"포켓몬A": "80%", "포켓몬B": "100%"}},
        "opp_hp": {{"포켓몬C": "50%", "포켓몬D": "100%"}},
        "opp_info": {{
            "포켓몬C": {{"item": "자뭉열매", "moves": ["하품"]}}
        }}
    }}
    ```
    ===ADVICE_START===
    (여기에 전략 조언 작성)
    """
    prompt = ChatPromptTemplate.from_template(template)
    
    # 3. 체인 실행
    chain = prompt | llm | StrOutputParser()
    
    raw_response = chain.invoke({
        "current_state": bs.get_context_text(),
        "rag_context": format_docs(context_docs),
        "user_input": user_input
    })
    
    # 4. 파싱 (JSON 부분과 조언 부분 분리)
    try:
        # JSON 부분 추출 (```json ... ``` 사이 혹은 맨 앞부분)
        json_str = ""
        advice_text = raw_response
        
        if "```json" in raw_response:
            parts = raw_response.split("```json")
            json_part = parts[1].split("```")[0]
            json_str = json_part.strip()
            
            # 조언 부분은 ===ADVICE_START=== 뒤에 있는 것
            if "===ADVICE_START===" in raw_response:
                advice_text = raw_response.split("===ADVICE_START===")[1].strip()
        
        # 상태 업데이트 적용
        if json_str:
            update_data = json.loads(json_str)
            bs.update_from_json(update_data)
            
    except Exception as e:
        print(f"JSON Parsing Error: {e}")
        # 파싱 실패해도 조언은 보여줌
    
    return advice_text