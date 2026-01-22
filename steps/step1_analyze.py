import streamlit as st
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag_system import format_docs
from battle_state import BattleState

def execute(user_input, retriever, llm):
    bs = st.session_state.battle_state

    # 1. [전처리] 약어 변환
    norm_prompt = ChatPromptTemplate.from_template(
        "사용자 입력을 보고 '공식 한국어 포켓몬 이름' 6개로 변환해. 오직 이름 6개를 쉼표로 구분해서 출력해.\n입력: {input}"
    )
    norm_chain = norm_prompt | llm | StrOutputParser()
    normalized_input = norm_chain.invoke({"input": user_input})
    
    # 상대 파티 저장
    opponent_list = [name.strip() for name in normalized_input.split(",")]
    bs.opponent_roster = opponent_list
    bs.opponent_status = {} # 초기화
    
    # 2. RAG 검색
    docs = retriever.invoke(normalized_input)
    
    # ★ 프롬프트 수정: 4마리 선출 강제 및 JSON 포맷 명확화
    analysis_prompt = ChatPromptTemplate.from_template(
        """
        너는 포켓몬 VGC(더블배틀) 세계 챔피언이야. 
        [내 파티]와 [상대 파티]를 분석해서 **반드시 4마리의 선출 멤버**를 정하고 이유를 설명해.

        [내 파티]: {my_team}
        [상대 파티]: {opponent_team}
        [상대 통계 데이터]: {context}
        
        [지시사항]:
        1. VGC 룰(4마리 선출)을 엄수해. 
        2. "selection" 리스트에는 [내 파티]에 있는 영문 이름 그대로 4개를 적어야 해. (한글 금지)
        3. 앞의 2마리는 선발(Lead), 뒤의 2마리는 후발(Back)이야.
        4. "reasoning"에는 상대의 핵심 위협이 무엇이고, 왜 이 4마리를 골랐는지 논리적으로 설명해.

        반드시 아래 **JSON 형식**으로만 출력해:
        {{
            "selection": ["Pokemon1", "Pokemon2", "Pokemon3", "Pokemon4"],
            "reasoning": "여기에 상세한 분석 내용을 작성..."
        }}
        """
    )
    
    chain = analysis_prompt | llm | StrOutputParser()
    
    # 실행
    raw_response = chain.invoke({
        "my_team": bs.my_party_full,
        "opponent_team": ", ".join(opponent_list),
        "context": format_docs(docs)
    })
    
    # 3. JSON 파싱
    try:
        json_str = raw_response
        if "```json" in raw_response:
            json_str = raw_response.split("```json")[1].split("```")[0].strip()
        elif "{" in raw_response:
            start = raw_response.find("{")
            end = raw_response.rfind("}") + 1
            json_str = raw_response[start:end]

        data = json.loads(json_str)
        
        # A. 자동 선출 적용
        selected_party = data.get("selection", [])
        
        # 안전장치: 혹시라도 4마리가 아니면 강제로 앞이나 뒤를 채움 (예외처리)
        if len(selected_party) < 4:
            # 내 로스터에서 안 뽑힌 애들 추가
            remaining = [p for p in bs.my_roster if p not in selected_party]
            selected_party.extend(remaining[:4-len(selected_party)])
            
        bs.set_auto_selection(selected_party)
        
        # B. 분석 멘트
        reasoning_text = data.get("reasoning", "분석 내용을 불러오지 못했습니다.")
        
        # 4. 다음 단계 이동
        st.session_state.step = "BATTLE_PHASE"
        
        # 최종 출력 메시지 구성
        return (
            f"🔄 **상대 파티 확인:** {normalized_input}\n\n"
            f"🤖 **AI 자동 선출 (4마리):**\n"
            f"- **선발:** {selected_party[0]}, {selected_party[1]}\n"
            f"- **후발:** {selected_party[2]}, {selected_party[3]}\n\n"
            f"--- \n"
            f"📊 **전략 분석:**\n{reasoning_text}\n\n"
            f"--- \n"
            f"⚔️ **배틀 시작!** 선출이 확정되었습니다. 첫 턴 상황을 입력하세요."
        )

    except Exception as e:
        return f"❌ 오류 발생 (JSON Parsing): {e}\n\n원본 응답:\n{raw_response}"