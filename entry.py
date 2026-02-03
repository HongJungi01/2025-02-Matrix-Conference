import os
import time
import json
import ast
from dotenv import load_dotenv

# --- [모듈 임포트] ---
from rag_retriever import get_opponent_party_report, SMOGON_DB, LEAD_STATS
from Battle_Preparing.user_party import my_party

# 계산기 모듈
from Calculator.calculator import run_calculation
from Calculator.speed_checker import check_turn_order
from Calculator.stat_estimator import estimate_stats 
from Calculator.move_loader import get_move_data # [NEW] API기반 기술 로더

# LangChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

# 1. 환경 설정
load_dotenv()
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("GOOGLE_API_KEY가 .env 파일에 설정되지 않았습니다.")

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview", 
    temperature=0.1, 
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# --------------------------------------------------------------------------
# [Helper 0] 토큰 정보 추출 함수
# --------------------------------------------------------------------------
def get_token_info(response):
    """LangChain 응답 객체에서 토큰 사용량을 추출합니다."""
    try:
        usage = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
        elif hasattr(response, 'response_metadata') and 'usage_metadata' in response.response_metadata:
            usage = response.response_metadata['usage_metadata']
            
        if usage:
            return {
                "input_tokens": usage.get('input_tokens', 0),
                "output_tokens": usage.get('output_tokens', 0),
                "total_tokens": usage.get('total_tokens', 0)
            }
    except Exception:
        pass
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

# --------------------------------------------------------------------------
# [Helper 1] 시뮬레이션 실행 함수 (수정됨)
# --------------------------------------------------------------------------
def run_simulation(my_party_data, opponent_list):
    """
    [핵심] 내 포켓몬 vs 상대 주요 선봉의 대면 시뮬레이션 실행
    """
    report = "=== ⚔️ 선봉 대면 시뮬레이션 (Simulation Report) ===\n"
    
    # 1. 상대 선봉 후보 선정 (Top 3)
    sorted_opps = sorted(opponent_list, key=lambda x: LEAD_STATS.get(x, 0), reverse=True)[:3]
    report += f"🎯 상대 유력 선봉 TOP 3: {', '.join(sorted_opps)}\n\n"

    for my_name, my_data in my_party_data.items():
        # 내 포켓몬 스펙 포장
        my_spec = {
            'stats': my_data['stats'],
            'ranks': {}, 
            'item': my_data['item'],
            'status': None,
            'ability': my_data.get('ability'),
            'types': [], 
            'is_terastal': False
        }
        
        # [수정] 내 기술 중 '가장 위력이 높은 기술' 하나 선정
        my_best_move = "Tackle"
        # 비교를 위해 초기값 위력 0 설정
        my_move_spec = {"name": "Tackle", "power": 0, "type": "Normal", "category": "Physical", "priority": 0}
        
        for m in my_data['moves']:
            # API 로더를 통해 정보 가져오기
            info = get_move_data(m)
            
            # 공격 기술이고, 현재 선택된 기술보다 위력이 높으면 교체
            # (break 없이 끝까지 돌려서 가장 센 기술을 찾음)
            if info['power'] > my_move_spec['power']:
                my_best_move = m
                my_move_spec = info
        
        report += f"[{my_name}의 분석]\n"

        for opp_name in sorted_opps:
            # 상대 스펙 추정
            opp_est = estimate_stats(opp_name)
            if not opp_est: continue
            
            opp_spec = {
                'stats': opp_est['stats'],
                'ranks': {},
                'item': None, 
                'status': None,
                'screens': {}
            }
            
            # A. 스피드 확인 (상대 기술 우선도는 0 가정)
            speed_res = check_turn_order(
                my_spec, opp_spec, 
                field_spec={}, 
                my_move_spec=my_move_spec,
                opp_move_spec={'priority':0}
            )
            
            speed_txt = "🚀선공" if speed_res['is_my_turn'] else "🐢후공"
            if speed_res['is_my_turn'] is None: speed_txt = "⚖️동속"
            
            # B. 데미지 확인
            dmg_res = run_calculation(my_spec, opp_spec, my_move_spec, field_spec={})
            ko_txt = dmg_res['damage']['ko_result']
            percent = dmg_res['damage']['percent_range']
            
            report += f"  vs {opp_name}: {speed_txt} | {my_best_move}: {percent} ({ko_txt})\n"
            
        report += "\n"
        
    return report

# --------------------------------------------------------------------------
# [Helper 2] 응답 추출 및 입력 파싱
# --------------------------------------------------------------------------
def extract_clean_content(response):
    try:
        content = ""
        if isinstance(response, dict):
            if 'text' in response: content = response['text']
            elif 'content' in response: content = response['content']
        elif hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and 'text' in item:
                    parts.append(item['text'])
                else:
                    parts.append(str(item))
            content = "".join(parts)
            
        # 딕셔너리 형태의 문자열 파싱 시도
        try:
            parsed = ast.literal_eval(str(content))
            if isinstance(parsed, dict) and 'text' in parsed:
                return parsed['text']
            if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                if 'text' in parsed[0]:
                    return parsed[0]['text']
        except (ValueError, SyntaxError):
            pass
            
        return str(content)
    except Exception as e:
        return f"Error: {e}"

def parse_opponent_input(user_input):
    """
    Returns: (parsed_list, token_usage_dict)
    """
    print(f"🔄 입력된 파티 정보를 표준화(English Mapping) 중입니다...")
    parser_template = """
    당신은 포켓몬 이름 번역기입니다. 
    사용자가 입력한 한국어 포켓몬 이름(약어/별명 포함)을 **Smogon/Showdown에서 사용하는 정확한 영어 공식 명칭**으로 변환하세요.
    입력: "{user_input}"
    출력 형식: Python List of Strings (예: ["Name1", "Name2"]) - Markdown 없이 리스트만 출력.
    매핑 예시: "날치머"->"Flutter Mane", "물라오스"->"Urshifu-Rapid-Strike", "망나뇽"->"Dragonite"
    """
    try:
        response = llm.invoke(parser_template.format(user_input=user_input))
        
        # 토큰 정보 추출
        token_info = get_token_info(response)
        print(f"💰 [Parser] Tokens: I:{token_info['input_tokens']} + O:{token_info['output_tokens']} = {token_info['total_tokens']}")

        content = extract_clean_content(response)
        clean_content = content.replace("```json", "").replace("```python", "").replace("```", "").strip()
        
        parsed_data = []
        try:
            parsed_data = json.loads(clean_content)
        except:
            parsed_data = ast.literal_eval(clean_content)
            
        return parsed_data, token_info
        
    except Exception as e:
        print(f"❌ 이름 변환 실패: {e}")
        return [], {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

def format_my_party_info():
    if not my_party.team: return "❌ 내 파티 정보 없음"
    text = "=== 🛡️ 내 파티 상세 스펙 (My Team Stats) ===\n"
    for name, data in my_party.team.items():
        stats = data['stats']
        stat_str = f"H{stats['hp']} A{stats['atk']} B{stats['def']} C{stats['spa']} D{stats['spd']} [S{stats['spe']}]"
        moves = ", ".join(data['moves'])
        text += f"[{name}] @ {data['item']} | {data['ability']} | {data['tera_type']} Tera | Stats: {stat_str} | Moves: {moves}\n"
    return text

# --------------------------------------------------------------------------
# [Main Function] 분석 실행
# --------------------------------------------------------------------------
def analyze_entry_strategy(opponent_input):
    """
    [Entry Phase] RAG + Calculator + SpeedChecker를 모두 결합한 최종 분석
    Returns: (analysis_text, token_usage_dict)
    """
    total_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    
    # 1. 입력 파싱 (입력이 문자열인 경우에만)
    if isinstance(opponent_input, str):
        opponent_list, parse_tokens = parse_opponent_input(opponent_input)
        # 토큰 누적
        for k in total_tokens: total_tokens[k] += parse_tokens[k]
    else:
        opponent_list = opponent_input

    # 실패 시 빈 문자열과 0 토큰 반환
    if not opponent_list: 
        return "❌ 상대 정보를 해석할 수 없습니다.", total_tokens

    print(f"🔍 [Entry Phase] '{len(opponent_list)}'마리 분석 및 대면 시뮬레이션 실행 중...")

    # 1. 기본 정보 준비
    my_team_context = format_my_party_info()
    opp_team_context = get_opponent_party_report(opponent_list)
    
    # 2. 대면 시뮬레이션 실행 (계산기 가동)
    try:
        simulation_report = run_simulation(my_party.team, opponent_list)
    except Exception as e:
        print(f"⚠️ 시뮬레이션 중 오류 발생 (건너뜀): {e}")
        simulation_report = "시뮬레이션 실패 (API 또는 데이터 오류)"

    # 3. 프롬프트 설계
    template = """
    당신은 '포켓몬 랭크배틀(3vs3 싱글)' 전문 AI 코치입니다.
    제공된 **정확한 시뮬레이션 데이터(Simulation Report)**와 통계를 바탕으로 승리 전략을 수립하세요.

    ---
    [1. 내 파티 정보]
    {my_team_context}
    
    [2. 상대 파티 정보 (Smogon 통계)]
    {opp_team_context}
    
    [3. ⚔️ 선봉 대면 시뮬레이션 결과 (Fact Check)]
    * 이 데이터는 실제 데미지 공식과 스피드 공식을 돌린 결과입니다. **절대적으로 신뢰하세요.**
    * '🚀선공'은 내가 먼저 때린다는 뜻이고, '확정 1타'는 내가 상대를 한 방에 잡는다는 뜻입니다.
    {simulation_report}
    ---

    [분석 로직]
    1. **선봉 결정 (Lead Check)**: [3. 시뮬레이션 결과]를 보세요. 상대 유력 선봉(TOP 3)을 상대로 '🚀선공'이면서 '확정 1타'를 내는 포켓몬이 있다면 최고의 선봉입니다.
    2. **스피드 싸움**: 시뮬레이션에서 '🐢후공'이 뜨는 대면은 위험합니다. 기합의띠나 내구 보정이 없다면 피하세요.
    3. **선출 구성**: 선봉을 이길 수 있는 포켓몬 1마리 + 일관성 있는 에이스 1마리 + 쿠션 1마리로 구성하세요.

    [결과 리포트 양식]
    1. **상대 예상 선출 (Top 3)**: [이름], [이름], [이름]
       - 이유: (선봉 확률 통계 및 내 파티와의 상성 고려)
    
    2. **나의 추천 선출**:
       - **선봉(Lead): [포켓몬 이름]**
         - 선정 이유: **(시뮬레이션 결과 인용 필수)** 예: "상대 딩루 상대로 선공이며, 인파이트로 확정 1타가 나옵니다."
       - **후속(Back): [포켓몬 이름], [포켓몬 이름]**
         - 역할: (에이스 / 쿠션 / 스위퍼)

    3. **승리 플랜 (Game Plan)**:
       - (초반 운영과 주의해야 할 상대의 테라스탈/도구 변수를 3줄 요약)
    """

    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm
    
    try:
        start_time = time.time()
        
        response = chain.invoke({
            "my_team_context": my_team_context,
            "opp_team_context": opp_team_context,
            "simulation_report": simulation_report
        })
        
        end_time = time.time()
        print(f"⏱️ 분석 완료! (소요 시간: {end_time - start_time:.2f}초)")

        # 토큰 정보 추출
        main_tokens = get_token_info(response)
        print(f"💰 [Strategy] Tokens: I:{main_tokens['input_tokens']} + O:{main_tokens['output_tokens']} = {main_tokens['total_tokens']}")
        
        # 토큰 누적
        for k in total_tokens: total_tokens[k] += main_tokens[k]

        return extract_clean_content(response), total_tokens

    except Exception as e:
        return f"❌ Gemini 3.0 분석 중 오류 발생: {str(e)}", total_tokens
    
def parse_recommended_selection(ai_response_text):
    """
    [New] AI의 분석 결과 텍스트에서 '나의 추천 선출' 3마리를 추출하여 리스트로 반환
    Returns: (selection_list, token_usage_dict)
    """
    print("🔄 AI 추천 선출을 파싱하여 상태에 반영 중...")
    
    parser_template = """
    당신은 '포켓몬 선출 리포트 파서'입니다.
    아래의 분석 리포트에서 AI가 추천한 **[나의 선출 포켓몬 3마리]**의 이름을 정확히 추출하세요.
    반드시 **영어 공식 명칭**으로 변환해야 합니다.

    [분석 리포트 내용]
    {report_text}

    [출력 형식 (JSON)]
    {{
        "lead": "PokemonName", (선봉)
        "back1": "PokemonName", (후속1)
        "back2": "PokemonName"  (후속2)
    }}
    """
    
    prompt = PromptTemplate.from_template(parser_template)
    chain = prompt | llm
    
    try:
        response = chain.invoke({"report_text": ai_response_text})
        
        # 토큰 정보 추출
        token_info = get_token_info(response)
        print(f"💰 [Selection] Tokens: I:{token_info['input_tokens']} + O:{token_info['output_tokens']} = {token_info['total_tokens']}")

        content = extract_clean_content(response)
        
        # JSON 파싱
        clean_json = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        
        # 리스트로 변환 (선봉, 후속1, 후속2)
        selection = [data.get("lead"), data.get("back1"), data.get("back2")]
        # None 제거
        selection = [p for p in selection if p]
        
        return selection, token_info
        
    except Exception as e:
        print(f"❌ 선출 파싱 실패: {e}")
        return [], {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    
# --------------------------------------------------------------------------
# [실행 예시]
if __name__ == "__main__":
    # [추가된 부분] 테스트를 위해 내 파티를 먼저 로드해야 합니다.
    from Battle_Preparing.party_loader import load_party_from_file
    
    print("📂 [Test Mode] 파티 데이터 로드 중...")
    load_party_from_file("my_team.txt")
    
    if not my_party.team:
        print("❌ 파티 로드 실패. my_team.txt를 확인하세요.")
        exit()

    # 예시 입력 (한국어 포켓몬 이름)
    user_input = "날치머, 물라오스, 망나뇽, 물거폰, 미라이돈, 날뛰는우레"
    
    print(f"\n🔍 테스트 입력: {user_input}")
    
    result_text, token_data = analyze_entry_strategy(user_input)
    print("\n" + result_text)
    print("\n📊 Total Token Usage in Main Analysis:", token_data)
    
    # 추가 파싱 테스트
    selection, sel_tokens = parse_recommended_selection(result_text)
    print(f"\nSelecton: {selection}, Tokens: {sel_tokens}")