import sys
import os

# --- [경로 설정] ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# --- [모듈 임포트] ---
from Battle_Preparing.user_party import my_party
from Calculator.stat_estimator import estimate_stats, get_base_stats
from rag_retriever import get_pokemon_raw_data 

class BattlePokemon:
    """ 
    [개별 포켓몬 상태 객체]
    HP, 랭크, 상태이상, 정보 신뢰도(확정/예측) 관리
    """
    def __init__(self, name, is_mine=True):
        self.name = name
        self.is_mine = is_mine
        
        # 1. 기본 상태
        self.current_hp_percent = 100.0
        self.status_condition = None # 영구 상태이상
        self.is_fainted = False
        
        # 2. 랭크 (-6 ~ +6)
        self.ranks = {'atk': 0, 'def': 0, 'spa': 0, 'spd': 0, 'spe': 0}
        
        # 3. 휘발성 상태 (교체 시 해제)
        self.volatile_status = {
            "taunt": False, "trapped": False, "confusion": False, 
            "substitute": False, "encore": False, "leech_seed": False
        }

        # 4. 정보 및 신뢰도
        self.info = {
            "item": None, "ability": None, "tera_type": None, 
            "moves": [], "stats": {},
            "predictions": {"moves": [], "items": [], "teras": []}
        }
        
        self.confirmed = {
            "item": is_mine, "ability": is_mine, "tera_type": is_mine, "stats": is_mine
        }

        if is_mine: self._load_my_data()
        else: self._load_smogon_data()

    def _load_my_data(self):
        data = my_party.get_pokemon(self.name)
        if data: self.info.update(data)

    def _load_smogon_data(self):
        est = estimate_stats(self.name)
        if est: self.info['stats'] = est['stats']
        raw = get_pokemon_raw_data(self.name)
        if raw:
            self.info['predictions']['moves'] = raw['predicted_moves']
            self.info['predictions']['items'] = raw['predicted_items']
            self.info['predictions']['teras'] = raw['predicted_teras']

    # --- [상태 조작] ---
    def update_hp(self, amount):
        self.current_hp_percent = max(0, min(100, self.current_hp_percent + amount))
        if self.current_hp_percent == 0: self.is_fainted = True

    def set_rank(self, stat, change):
        if stat in self.ranks:
            self.ranks[stat] = max(-6, min(6, self.ranks[stat] + change))

    def update_volatile(self, key, is_active):
        if key in self.volatile_status: self.volatile_status[key] = is_active

    def reset_battle_status(self):
        """ 교체 시 초기화 (랭크, 휘발성 상태) """
        self.ranks = {k: 0 for k in self.ranks}
        for k in self.volatile_status: self.volatile_status[k] = False

    def reveal_info(self, category, value):
        self.info[category] = value
        self.confirmed[category] = True
        print(f"💡 [정보 갱신] {self.name} {category} -> {value}")

    def add_known_move(self, move_name):
        if move_name not in self.info['moves']:
            self.info['moves'].append(move_name)

    # --- [추론 로직] ---
    def infer_speed_nature(self, my_real_speed, opponent_moved_first, field_state):
        if self.is_mine: return None
        base_stats = get_base_stats(self.name)
        if not base_stats: return None
        
        base_spe = base_stats['spe']
        speed_neutral = int((2 * base_spe + 31 + 63) * 0.5 + 5)
        speed_positive = int(speed_neutral * 1.1)
        
        if field_state.get('tailwind_opp') or self.status_condition == 'Paralysis': return None

        if opponent_moved_first:
            if my_real_speed >= speed_positive:
                if not self.confirmed['item']:
                    self.reveal_info('item', 'Choice Scarf')
                    return f"❗ 상대가 최속 한계({speed_positive})보다 빠릅니다. **구애스카프** 확정."
            elif my_real_speed >= speed_neutral:
                return f"❗ 상대가 준속({speed_neutral})보다 빠릅니다. **최속 보정**입니다."
        else:
            if my_real_speed < speed_positive:
                return f"✅ 상대가 최속({speed_positive})보다 느립니다. 내구 보정 가능성."
        return None

    def get_summary_text(self):
        if self.is_mine: return ""
        moves = self.info['moves'] + self.info['predictions']['moves'][:5]
        moves = list(dict.fromkeys(moves))[:5]
        item = self.info['item'] if self.confirmed['item'] else f"예측({', '.join(self.info['predictions']['items'][:2])})"
        return f"[{self.name}] 도구:{item} | 기술:{', '.join(moves)}"


class BattleState:
    """ 
    [전체 배틀 필드 상태]
    """
    def __init__(self):
        self.turn_count = 1
        self.my_active = None
        self.opp_active = None
        
        self.opp_full_roster = []
        self.opp_revealed_party = {}
        
        self.my_party_status = {}
        # [NEW] 선출된 3마리 명단
        self.my_entry_selection = []
        
        self.global_effects = {"weather": None, "terrain": None, "trick_room": False}
        self.side_effects = {
            "me": {"tailwind": False, "reflect": False, "light_screen": False, "stealth_rock": False},
            "opp": {"tailwind": False, "reflect": False, "light_screen": False, "stealth_rock": False}
        }
        
        self.refresh_my_party()

    def refresh_my_party(self):
        if my_party.team:
            self.my_party_status = {name: BattlePokemon(name, True) for name in my_party.team.keys()}
            print(f"🔄 BattleState: 내 파티 {len(self.my_party_status)}마리 로드 완료")

    def initialize_opponent(self, roster_list):
        self.opp_full_roster = roster_list

    # [NEW] 선출 확정 메서드
    def set_my_selection(self, selection_list):
        """ app.py에서 선출 분석 후 호출됨 """
        self.my_entry_selection = selection_list
        print(f"✅ 내 선출 확정: {self.my_entry_selection}")
        # 첫 번째 포켓몬을 선봉으로 자동 설정
        if selection_list:
            self.set_active("me", selection_list[0])

    def set_active(self, side, pokemon_name):
        if side == "me":
            if not self.my_party_status: self.refresh_my_party()
            if pokemon_name in self.my_party_status:
                self.my_active = self.my_party_status[pokemon_name]
                self.my_active.reset_battle_status() # 교체 시 랭크 리셋
        else:
            if pokemon_name not in self.opp_revealed_party:
                self.opp_revealed_party[pokemon_name] = BattlePokemon(pokemon_name, is_mine=False)
            self.opp_active = self.opp_revealed_party[pokemon_name]
            self.opp_active.reset_battle_status() # 교체 시 랭크 리셋

    # --- [LLM 파싱 데이터 적용] ---
    def apply_llm_update(self, update_data):
        print(f"🔄 [State Update] 적용: {update_data}")
        
        if update_data.get("my_switch"): self.set_active("me", update_data["my_switch"])
        if update_data.get("opp_switch"): self.set_active("opp", update_data["opp_switch"])

        if update_data.get("my_hp_change_input"): 
            if self.my_active: self.my_active.update_hp(update_data["my_hp_change_input"])
        if update_data.get("opp_hp_change_input"):
            if self.opp_active: self.opp_active.update_hp(update_data["opp_hp_change_input"])

        if self.my_active and update_data.get("my_rank_change"):
            for stat, change in update_data["my_rank_change"].items():
                self.my_active.set_rank(stat, change)
                
        if self.opp_active and update_data.get("opp_rank_change"):
            for stat, change in update_data["opp_rank_change"].items():
                self.opp_active.set_rank(stat, change)

        # 상태이상 업데이트 (문자열 'Burn' 등이 들어온다고 가정)
        if update_data.get("my_status"): self.my_active.status_condition = update_data["my_status"]
        if update_data.get("opp_status"): self.opp_active.status_condition = update_data["opp_status"]

        if update_data.get("weather"): self.global_effects['weather'] = update_data["weather"]
        if update_data.get("terrain"): self.global_effects['terrain'] = update_data["terrain"]
        if update_data.get("trick_room") is not None: self.global_effects['trick_room'] = update_data["trick_room"]
        
        if update_data.get("tailwind_me") is not None: self.side_effects['me']['tailwind'] = update_data["tailwind_me"]
        if update_data.get("tailwind_opp") is not None: self.side_effects['opp']['tailwind'] = update_data["tailwind_opp"]
        if update_data.get("reflect_opp") is not None: self.side_effects['opp']['reflect'] = update_data["reflect_opp"]
        if update_data.get("light_screen_opp") is not None: self.side_effects['opp']['light_screen'] = update_data["light_screen_opp"]

        if self.opp_active:
            if update_data.get("opp_item"): self.opp_active.reveal_info("item", update_data["opp_item"])
            if update_data.get("opp_tera_type"): self.opp_active.reveal_info("tera_type", update_data["opp_tera_type"])
            if update_data.get("opp_move_used"): self.opp_active.add_known_move(update_data["opp_move_used"])

        if update_data.get("turn_end"):
            self.turn_count += 1

    def get_state_report(self):
        if not self.my_active or not self.opp_active: return "⚠️ 배틀 준비 중..."
        
        revealed = [p.name for p in self.opp_revealed_party.values() if not p.is_fainted]
        unknown = 3 - len(self.opp_revealed_party)
        
        opp = self.opp_active
        opp_item = f"{opp.info['item']} (확정)" if opp.confirmed['item'] else f"{opp.info['item'] or 'Unknown'} (예측)"
        
        vol_my = [k for k,v in self.my_active.volatile_status.items() if v]
        vol_opp = [k for k,v in opp.volatile_status.items() if v]

        # [핵심] 대기 포켓몬 리스트 생성 (선출된 3마리 기준)
        if self.my_entry_selection:
            # 선출된 멤버 중 현재 필드에 없는, 살아있는 애들만 필터링
            bench_candidates = [
                name for name in self.my_entry_selection
                if name != self.my_active.name 
                and name in self.my_party_status
                and not self.my_party_status[name].is_fainted
            ]
        else:
            # 선출 분석 안 했으면 전체 멤버 표시
            bench_candidates = [
                name for name in self.my_party_status.keys()
                if name != self.my_active.name 
                and not self.my_party_status[name].is_fainted
            ]

        return f"""
        [🏟️ Turn {self.turn_count}]
        🟢 **나 ({self.my_active.name})**: HP {self.my_active.current_hp_percent:.1f}% | 상태 {self.my_active.status_condition or '정상'} {vol_my}
           - 🏥 **대기 포켓몬**: {', '.join(bench_candidates) or '없음 (Last One)'}
           - 랭크: {self.my_active.ranks}
           
        🔴 **상대 ({opp.name})**: HP {opp.current_hp_percent:.1f}% | 상태 {opp.status_condition or '정상'} {vol_opp}
           - 랭크: {opp.ranks}
           - 파티 현황: 생존[{', '.join(revealed)}] / 미확인[{unknown}마리]
           - 정보: 도구[{opp_item}] / 기술[{', '.join(opp.info['moves'])}]
           
        🌐 **환경**: 날씨[{self.global_effects['weather']}] / 필드[{self.global_effects['terrain']}] / 룸[{self.global_effects['trick_room']}]
        🛡️ **벽/순풍**: 나[{'순풍' if self.side_effects['me']['tailwind'] else ''}] vs 상대[{'순풍' if self.side_effects['opp']['tailwind'] else ''}]
        """

current_battle = BattleState()