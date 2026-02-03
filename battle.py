import os
import json
import ast
from dotenv import load_dotenv

# --- [모듈 임포트] ---
from battle_state import current_battle
from Calculator.calculator import run_calculation
from Calculator.speed_checker import check_turn_order
from Calculator.move_loader import get_move_data
from Calculator.stat_estimator import estimate_stats
from entry import extract_clean_content

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

# 1. 환경 설정
load_dotenv()
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview", 
    temperature=0.1, # 배틀 분석은 정확성이 중요하므로 낮게 설정
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
    사용자의 자연어 입력을 분석하여 BattleState를 갱신합니다.
    """
    print("🔄 [Logic] 사용자 입력 분석 및 자동 계산 시작...")
    
    my_name = current_battle.my_active.name if current_battle.my_active else "None"
    opp_name = current_battle.opp_active.name if current_battle.opp_active else "None"
    
    # 교체 후보 리스트 (파싱 정확도 향상용)
    my_roster = list(current_battle.my_party_status.keys())
    opp_roster = current_battle.opp_full_roster

    # [핵심 수정] 프롬프트 대폭 강화 (모든 변수 캡처)
    parser_template = """
    당신은 '포켓몬 배틀 로그 파서(Parser)'입니다. 
    사용자의 입력을 보고 상태 변경 사항을 정확한 JSON으로 추출하세요.

    [현재 필드]
    - 나: {my_name} (대기: {my_roster})
    - 상대: {opp_name} (엔트리: {opp_roster})

    [사용자 입력]
    "{user_input}"

    [추출 규칙]
    1. **교체**: 
       - "상대 미라이돈 등장" -> "opp_switch": "Miraidon"
       - "내가 랜드로스로 교체" -> "my_switch": "Landorus-Therian" (반드시 영어 공식 명칭 사용)
    2. **기술**: "상대 용성군 사용" -> "opp_move_used": "Draco Meteor"
    3. **HP 변화**: 사용자가 수치를 말했으면 기입(음수=데미지), 말 안 했으면 null.
    4. **상태이상**: "화상 입음" -> "Burn", "마비" -> "Paralysis", "잠듦" -> "Sleep".
    5. **랭크**: "칼춤췄어(+2공)" -> {{"atk": 2}}, "위협(-1공)" -> {{"atk": -1}}.
    6. **필드/날씨**: "비 내림" -> weather: "Rain", "벽 설치" -> opp_reflect: true.

    [JSON 스키마]
    {{
        "my_switch": str or null,
        "opp_switch": str or null,
        "my_move_used": str or null,
        "opp_move_used": str or null,
        "my_hp_change_input": int or null,
        "opp_hp_change_input": int or null,
        
        "my_status_change": str or null,
        "opp_status_change": str or null,
        
        "my_rank_change": {{"atk": int, "def": int, "spa": int, "spd": int, "spe": int}},
        "opp_rank_change": {{"atk": int, "def": int, "spa": int, "spd": int, "spe": int}},
        
        "weather": str or null,
        "terrain": str or null,
        "trick_room": bool or null,
        
        "my_tailwind": bool or null,
        "opp_reflect": bool or null,
        "opp_light_screen": bool or null,
        "turn_end": bool
    }}
    """
    
    prompt = PromptTemplate.from_template(parser_template)
    chain = prompt | llm
    
    try:
        response = chain.invoke({
            "user_input": user_input, 
            "my_name": my_name, 
            "opp_name": opp_name,
            "my_roster": ", ".join(my_roster),
            "opp_roster": ", ".join(opp_roster)
        })

        usage = response.usage_metadata
        token_result = [
            usage.get('input_tokens', 0),
            usage.get('output_tokens', 0),
            usage.get('total_tokens', 0)
        ]

        print(token_result)
        
        json_text = extract_clean_content(response)
        json_text = json_text.replace("```json", "").replace("```", "").strip()
        parsed_data = json.loads(json_text)
        print(f"🧩 파싱 결과: {parsed_data}")
        
    except Exception as e:
        print(f"❌ 파싱 실패: {e}")
        return False, "파싱 오류 발생"

    # 2. 상태 업데이트 적용 (Logic Layer)
    updates_log = []
    
    # (1) 교체 처리
    if parsed_data.get("my_switch"):
        new_my = parsed_data["my_switch"]
        current_battle.set_active("me", new_my)
        updates_log.append(f"나 교체 -> {new_my}")
        
    if parsed_data.get("opp_switch"):
        new_opp = parsed_data["opp_switch"]
        current_battle.set_active("opp", new_opp)
        updates_log.append(f"상대 교체 -> {new_opp}")

    # (2) 자동 데미지 계산 (Auto-Calc)
    # 교체가 없을 때만 수행
    if not parsed_data.get("my_switch") and not parsed_data.get("opp_switch"):
        my_spec, opp_spec, field_spec = pack_specs()
        
        # Case A: 내가 공격
        my_move = parsed_data.get("my_move_used")
        if my_move and my_spec:
            if parsed_data.get("opp_hp_change_input") is not None:
                dmg = parsed_data["opp_hp_change_input"]
                current_battle.opp_active.update_hp(dmg)
                updates_log.append(f"상대 HP {dmg}% (입력)")
            else:
                move_info = get_move_data(my_move)
                if move_info['power'] > 0:
                    res = run_calculation(my_spec, opp_spec, move_info, field_spec)
                    dmg_range = res['damage']['percent_range'].replace("%","").split('~')
                    avg_dmg = -(float(dmg_range[0]) + float(dmg_range[1])) / 2
                    current_battle.opp_active.update_hp(avg_dmg)
                    updates_log.append(f"상대 HP {avg_dmg:.1f}% (계산)")

        # Case B: 상대가 공격
        opp_move = parsed_data.get("opp_move_used")
        if opp_move and opp_spec:
            current_battle.opp_active.add_known_move(opp_move)
            
            if parsed_data.get("my_hp_change_input") is not None:
                dmg = parsed_data["my_hp_change_input"]
                current_battle.my_active.update_hp(dmg)
                updates_log.append(f"내 HP {dmg}% (입력)")
            else:
                move_info = get_move_data(opp_move)
                if move_info['power'] > 0:
                    res = run_calculation(opp_spec, my_spec, move_info, field_spec)
                    dmg_range = res['damage']['percent_range'].replace("%","").split('~')
                    avg_dmg = -(float(dmg_range[0]) + float(dmg_range[1])) / 2
                    current_battle.my_active.update_hp(avg_dmg)
                    updates_log.append(f"내 HP {avg_dmg:.1f}% (계산)")

    # (3) 턴 증가
    if parsed_data.get("turn_end"):
        current_battle.turn_count += 1
        updates_log.append("턴 종료")

    # [최종 반영] 랭크/상태이상/필드 등 나머지 변수 일괄 적용
    current_battle.apply_llm_update(parsed_data)

    return True, f"✅ 상태 반영됨: {', '.join(updates_log)}", token_result

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
    # 확인된 기술 + 예측 기술
    potential_moves = current_battle.opp_active.info['moves'] + current_battle.opp_active.info['predictions']['moves']
    unique_moves = list(dict.fromkeys(potential_moves))[:5]
    
    if unique_moves:
        for move_name in unique_moves:
            m_info = get_move_data(move_name)
            if m_info['power'] > 0:
                res = run_calculation(opp_spec, my_spec, m_info, field_spec)
                dmg_min = int(res['damage']['damage_range'].split('~')[0])
                if (dmg_min / my_spec['stats']['hp'] > 0.3) or "확정" in res['damage']['ko_result']:
                    report += f" - ⚠️ {move_name}: {res['damage']['percent_range']} ({res['damage']['ko_result']})\n"

    return report, {"my_real_speed": speed_res['my_final_speed']}

# -------------------------------------------------------------------------
# [Main API] 통합 분석 함수
# -------------------------------------------------------------------------
def analyze_battle_turn(user_input, opp_moved_first=False):
    """
    1. 파싱 및 상태 업데이트 (자동 계산 포함)
    2. 시뮬레이션 재실행
    3. AI 조언 생성
    """
    
    # 1. 상태 업데이트 (LLM Parser)
    success, update_msg, parser_tokens = parse_and_update_state(user_input)
    
    # 2. 시뮬레이션 (업데이트된 상태 기준)
    sim_report, meta = run_battle_simulation_report()
    
    # 3. 역산 로직
    inference_msg = ""
    if current_battle.opp_active and not current_battle.opp_active.is_mine:
        inferred = current_battle.opp_active.infer_speed_nature(
            meta.get('my_real_speed', 0), opp_moved_first, current_battle.side_effects
        )
        if inferred: inference_msg = f"\n🕵️ **[정보 역산 성공]** {inferred}\n"

    # 4. 최종 프롬프트 (Advisor)
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

    [지시사항]
    1. **상태 변화 인지**: HP 감소, 랭크 변화, 상태이상 등을 확인하고 전략을 수정하세요.
    2. **공격 체크**: 공격 시뮬레이션에서 1타가 나면 공격을 우선시하세요.
    3. **방어 체크**: 방어 시뮬레이션에서 내가 위험하고 후공이라면, 교체나 방어를 고려하세요.

    [답변 양식]
    - 💡 **추천 행동**: [기술명] or [교체]
    - 📊 **근거**: (변경된 상태와 계산 결과를 인용하여 설명)
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

        usage = res.usage_metadata

        analyze_tokens = [
            usage.get('input_tokens', 0),
            usage.get('output_tokens', 0),
            usage.get('total_tokens', 0)
        ]

        print(analyze_tokens)

        return extract_clean_content(res), parser_tokens, analyze_tokens
    except Exception as e:
        return f"Error: {e}"