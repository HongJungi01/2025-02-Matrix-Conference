class BattleState:
    def __init__(self):
        # 1. 포켓몬 정보
        self.my_party_full = ""          # 6마리 전체 텍스트 (최종 저장용)
        self.my_roster = []              # 6마리 이름 리스트 (사이드바 표시용)
        self.temp_party_inputs = []      # [New] 입력 중인 포켓몬들을 임시 저장하는 리스트
        
        self.my_selection = []           # 선출한 4마리
        self.my_active = ["?", "?"]      # 내 선발
        
        # ... (나머지 상대 정보 변수들은 그대로 유지) ...
        self.opponent_roster = []
        self.opponent_confirmed = set()
        self.opponent_info = {}
        self.opponent_hp = {}
        self.my_hp = {}
        self.opponent_active = ["?", "?"]
        self.battle_log = []

    # ... (기존 메서드 유지) ...
    def set_auto_selection(self, selection_list):
        # ... (기존 코드 유지) ...
        self.my_selection = selection_list[:4]
        if len(self.my_selection) >= 2:
            self.my_active = self.my_selection[:2]
        for mon in self.my_selection:
            self.my_hp[mon] = "100%"

    def update_from_json(self, data):
        """LLM이 분석한 JSON 데이터를 받아 상태를 갱신하는 메서드"""
        if "my_active" in data:
            self.my_active = data["my_active"]
        if "opp_active" in data:
            self.opponent_active = data["opp_active"]
            # 필드에 나왔으면 확인된 것으로 처리
            for mon in data["opp_active"]:
                if mon != "?" and mon not in self.opponent_confirmed:
                    self.opponent_confirmed.add(mon)
        
        # 체력 업데이트
        if "my_hp" in data:
            self.my_hp.update(data["my_hp"])
        if "opp_hp" in data:
            self.opponent_hp.update(data["opp_hp"])
            
        # 상세 정보 업데이트 (도구, 기술 등)
        if "opp_info" in data:
            for mon_name, info in data["opp_info"].items():
                if mon_name not in self.opponent_info:
                    self.opponent_info[mon_name] = {}
                self.opponent_info[mon_name].update(info)

    def get_context_text(self):
        """LLM에게 던져줄 현재 상태 요약본 (프롬프트용)"""
        # 상대 엔트리 상태 (확정 / 미확정 구분)
        unknown_count = 4 - len(self.opponent_confirmed)
        unknown_str = f"(미확인 {unknown_count}마리)" if unknown_count > 0 else "(4마리 전원 확정)"
        
        return f"""
        [내 필드 (Active)]: {', '.join(self.my_active)}
        [상대 필드 (Active)]: {', '.join(self.opponent_active)}
        
        [내 체력 현황]: {self.my_hp}
        [상대 체력 현황]: {self.opponent_hp}
        
        [내 선출 4마리]: {', '.join(self.my_selection)}
        [상대 엔트리 정보]:
        - 전체 리스트: {', '.join(self.opponent_roster)}
        - 확인된 멤버: {', '.join(self.opponent_confirmed)} {unknown_str}
        
        [상대 상세 정보(도구/기술/특성)]:
        {self.opponent_info}
        """