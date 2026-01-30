import os
import json
import ast
from dotenv import load_dotenv

# 모듈
from battle_state import current_battle
from Calculator.calculator import run_calculation
from Calculator.speed_checker import check_turn_order
from Calculator.move_loader import get_move_data
from Calculator.stat_estimator import estimate_stats
from entry import extract_clean_content

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

load_dotenv()
llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview", 
    temperature=0.1, 
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# -------------------------------------------------------------------------
# [Helper] 스펙 포장 함수 (시뮬레이션 & 업데이트 공용)
# -------------------------------------------------------------------------
def pack_specs():
    """ 현재 BattleState를 계산기 입력용 Spec으로 변환 """
    if not current_battle.my_active or not current_battle.opp_active:
        return None, None, None

    my_poke = current_battle.my_active
    opp_poke = current_battle.opp_active
    
    # 상대 스탯 (확정 아니면 추정치)
    opp_stats = opp_poke.info.get('stats')
    if not opp_stats:
        est = estimate_stats(opp_poke.name)
        opp_stats = est['stats'] if est else {'hp':100,'atk':100,'def':100,'spa':100,'spd':100,'spe':100}

    my_spec = {
        'stats': my_poke.info['stats'], 'ranks': my_poke.ranks, 
        'item': my_poke.info['item'], 'status': my_poke.status_condition,
        'ability': my_poke.info['ability'], 'types': [], 'is_terastal': False
    }
    
    opp_spec = {
        'stats': opp_stats, 'ranks': opp_poke.ranks,
        'item': opp_poke.info['item'], 'status': opp_poke.status_condition,
        'screens': current_battle.side_effects['opp'],
        'ability': opp_poke.info['ability']
    }
    
    field_spec = {
        'weather': current_battle.global_effects['weather'],
        'terrain': current_battle.global_effects['terrain'],
        'trick_room': current_battle.global_effects['trick_room'],
        'tailwind_me': current_battle.side_effects['me']['tailwind'],
        'tailwind_opp': current_battle.side_effects['opp']['tailwind']
    }
    
    return my_spec, opp_spec, field_spec

# -------------------------------------------------------------------------
# [Step 1] 파서 & 자동 계산 로직
# -------------------------------------------------------------------------
def parse_and_update_state(user_input):
    """
    사용자의 입력을 파싱하고, 수치가 비어있다면 계산기를 돌려 채워넣은 뒤 상태를 업데이트함.
    """
    print("🔄 [Logic] 사용자 입력 분석 및 자동 계산 시작...")
    
    my_name = current_battle.my_active.name if current_battle.my_active else "None"
    opp_name = current_battle.opp_active.name if current_battle.opp_active else "None"

    # 1. LLM에게 파싱 요청
    parser_template = """
    당신은 '포켓몬 배틀 로그 파서'입니다. 사용자의 말을 듣고 상태 변화를 JSON으로 추출하세요.
    
    [현재 상황] 나: {my_name} vs 상대: {opp_name}
    [사용자 입력] "{user_input}"

    [규칙]
    1. **교체(Switch)**: "상대가 미라이돈을 냈다" -> "opp_switch": "Miraidon"
    2. **기술 사용(Move)**: "상대가 용성군을 썼어" -> "opp_move_used": "Draco Meteor"
    3. **HP 변화**: 사용자가 수치를 말했으면 기입(음수=데미지), 말 안 했으면 null (계산기가 처리함).
    4. 모든 이름(포켓몬, 기술)은 **영어 공식 명칭**으로 변환하세요.

    [JSON 스키마]
    {{
        "opp_switch": str or null,
        "my_move_used": str or null,  (내가 사용한 기술명)
        "opp_move_used": str or null, (상대가 사용한 기술명)
        "my_hp_change_input": int or null, (사용자가 언급한 내 체력 변화량)
        "opp_hp_change_input": int or null, (사용자가 언급한 상대 체력 변화량)
        "my_rank_change": {{"stat": "val"}}, (예: {{"atk": 2}})
        "turn_end": bool (턴이 끝났는지 여부)
    }}
    """
    
    prompt = PromptTemplate.from_template(parser_template)
    chain = prompt | llm
    
    try:
        response = chain.invoke({"user_input": user_input, "my_name": my_name, "opp_name": opp_name})
        parsed_data = json.loads(extract_clean_content(response).replace("```json", "").replace("```", "").strip())
        print(f"🧩 파싱 결과: {parsed_data}")
        
    except Exception as e:
        print(f"❌ 파싱 실패: {e}")
        return False, "파싱 오류 발생"

    # 2. 상태 업데이트 적용 (Logic Layer)
    updates_log = []
    
    # (1) 교체 처리 (Switching)
    if parsed_data.get("opp_switch"):
        new_opp = parsed_data["opp_switch"]
        current_battle.set_active("opp", new_opp) # 상대 포켓몬 변경
        updates_log.append(f"상대 {new_opp} 등장")
        # 교체 시에는 보통 데미지 계산을 안 하므로 여기서 리턴해도 됨 (첫 턴 로직)
        if not parsed_data.get("my_move_used") and not parsed_data.get("opp_move_used"):
            return True, f"✅ 상태 업데이트: {', '.join(updates_log)}"

    # (2) 자동 데미지 계산 (Auto-Calc) - 사용자가 수치를 말 안 했을 때
    my_spec, opp_spec, field_spec = pack_specs()
    
    # Case A: 내가 공격했을 때
    my_move = parsed_data.get("my_move_used")
    if my_move and my_spec:
        # 사용자가 직접 데미지를 말했으면 그걸 우선시
        if parsed_data.get("opp_hp_change_input") is not None:
            dmg = parsed_data["opp_hp_change_input"]
            current_battle.opp_active.update_hp(dmg)
            updates_log.append(f"상대 HP {dmg}% (입력값)")
        else:
            # 말 안 했으면 계산기 가동
            move_info = get_move_data(my_move)
            if move_info['power'] > 0:
                res = run_calculation(my_spec, opp_spec, move_info, field_spec)
                # 범위(45~55)의 평균값 적용
                dmg_range = res['damage']['percent_range'].replace("%","").split('~')
                avg_dmg = -(float(dmg_range[0]) + float(dmg_range[1])) / 2
                current_battle.opp_active.update_hp(avg_dmg)
                updates_log.append(f"상대 HP {avg_dmg:.1f}% (자동계산: {my_move})")

    # Case B: 상대가 공격했을 때
    opp_move = parsed_data.get("opp_move_used")
    if opp_move and opp_spec:
        # 정보 갱신: 상대가 이 기술을 썼다는 건 기술배치 확정
        current_battle.opp_active.add_known_move(opp_move)
        
        if parsed_data.get("my_hp_change_input") is not None:
            dmg = parsed_data["my_hp_change_input"]
            current_battle.my_active.update_hp(dmg)
            updates_log.append(f"내 HP {dmg}% (입력값)")
        else:
            # 계산기 가동 (방어 시뮬레이션)
            move_info = get_move_data(opp_move)
            if move_info['power'] > 0:
                res = run_calculation(opp_spec, my_spec, move_info, field_spec) # 공수 교대
                dmg_range = res['damage']['percent_range'].replace("%","").split('~')
                avg_dmg = -(float(dmg_range[0]) + float(dmg_range[1])) / 2
                current_battle.my_active.update_hp(avg_dmg)
                updates_log.append(f"내 HP {avg_dmg:.1f}% (자동계산: {opp_move})")

    # (3) 랭크 변화 적용
    # (구현 생략: 필요시 parsed_data['my_rank_change'] 루프 돌려서 set_rank 호출)

    # (4) 턴 증가
    if parsed_data.get("turn_end"):
        current_battle.turn_count += 1
        updates_log.append("턴 종료")

    return True, f"✅ 상태 반영됨: {', '.join(updates_log)}"

# -------------------------------------------------------------------------
# [Step 2] 시뮬레이션 및 조언 (Advisor)
# -------------------------------------------------------------------------
def run_battle_simulation_report():
    """ 현재 상태 기준으로 승리 플랜 시뮬레이션 """
    my_spec, opp_spec, field_spec = pack_specs()
    if not my_spec: return "⚠️ 정보 부족", {}

    report = ""
    # 1. 스피드 판정
    speed_res = check_turn_order(my_spec, opp_spec, field_spec, {}, {})
    icon = "🚀선공" if speed_res['is_my_turn'] else "🐢후공"
    if speed_res['is_my_turn'] is None: icon = "⚖️동속"
    report += f"⚡ [스피드] {icon} (나:{speed_res['my_final_speed']} vs 상대:{speed_res['opp_final_speed']})\n"

    # 2. 공격 시뮬레이션
    report += f"⚔️ [공격] {current_battle.my_active.name} -> {current_battle.opp_active.name}\n"
    for move_name in current_battle.my_active.info['moves']:
        m_info = get_move_data(move_name)
        if m_info['power'] > 0:
            res = run_calculation(my_spec, opp_spec, m_info, field_spec)
            report += f" - {move_name}: {res['damage']['percent_range']} ({res['damage']['ko_result']})\n"

    # 3. 방어 시뮬레이션
    report += f"🛡️ [방어] {current_battle.opp_active.name} 공격 예상\n"
    # 상대 확인된 기술 + 예측 기술
    potential_moves = current_battle.opp_active.info['moves'] + current_battle.opp_active.info['predictions']['moves']
    unique_moves = list(dict.fromkeys(potential_moves))[:5]
    
    if unique_moves:
        for move_name in unique_moves:
            m_info = get_move_data(move_name)
            if m_info['power'] > 0:
                res = run_calculation(opp_spec, my_spec, m_info, field_spec)
                dmg_min = int(res['damage']['damage_range'].split('~')[0])
                # 위협적인 것만 표시
                if (dmg_min / my_spec['stats']['hp'] > 0.3) or "확정" in res['damage']['ko_result']:
                    report += f" - ⚠️ {move_name}: {res['damage']['percent_range']} ({res['damage']['ko_result']})\n"

    return report, {"my_real_speed": speed_res['my_final_speed']}

def analyze_battle_turn(user_input, opp_moved_first=False):
    """ [Main API] """
    
    # 1. 파싱 및 상태 업데이트 (자동 계산 포함)
    success, update_msg = parse_and_update_state(user_input)
    
    # 2. 업데이트된 상태로 시뮬레이션
    sim_report, meta = run_battle_simulation_report()
    
    # 3. 역산
    inference_msg = ""
    if current_battle.opp_active and not current_battle.opp_active.is_mine:
        inferred = current_battle.opp_active.infer_speed_nature(
            meta.get('my_real_speed', 0), opp_moved_first, current_battle.side_effects
        )
        if inferred: inference_msg = f"\n🕵️ **[정보 역산 성공]** {inferred}\n"

    # 4. 최종 조언 생성
    state_text = current_battle.get_state_report()
    opp_info_text = current_battle.opp_active.get_summary_text() if current_battle.opp_active else ""

    template = """
    당신은 포켓몬 배틀 AI 코치입니다.
    사용자의 입력에 따라 **상태가 이미 업데이트**되었습니다. 
    현재의 상태와 계산 결과를 바탕으로 **다음 행동**을 지시하세요.

    ---
    [🔄 업데이트 결과]
    {update_msg}
    
    {state_text}
    [상대 상세 정보]
    {opp_info_text}
    ---
    {sim_report}
    {inference_msg}
    ---
    [사용자 입력]
    "{user_input}"

    [답변 양식]
    - 💡 **추천 행동**: [기술명] or [교체]
    - 📊 **근거**: (변경된 HP 상황과 킬각 시뮬레이션을 인용하여 설명)
    """
    
    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm
    
    try:
        res = chain.invoke({
            "state_text": state_text,
            "opp_info_text": opp_info_text,
            "sim_report": sim_report,
            "inference_msg": inference_msg,
            "user_input": user_input,
            "update_msg": update_msg
        })
        return extract_clean_content(res)
    except Exception as e:
        return f"Error: {e}"