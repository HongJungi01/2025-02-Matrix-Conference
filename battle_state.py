class BattleState:
    def __init__(self):
        self.my_party_full = ""
        self.my_roster = []
        self.my_selection = []    # 3마리
        
        # 싱글배틀은 필드에 1마리만 나옴
        self.my_active = ["?"]       
        self.opponent_active = ["?"] 
        
        self.opponent_roster = []
        self.opponent_confirmed = set()
        self.opponent_info = {}
        self.opponent_hp = {}
        self.my_hp = {}
        self.battle_log = []

    def set_auto_selection(self, selection_list):
        """AI가 추천한 3마리를 선출로 확정"""
        # 싱글배틀: 3마리 선출
        self.my_selection = selection_list[:3]
        
        # 첫 번째 포켓몬이 선발(Active)
        if len(self.my_selection) >= 1:
            self.my_active = [self.my_selection[0]]
        
        for mon in self.my_selection:
            self.my_hp[mon] = "100%"

    def update_from_json(self, data):
        # 싱글배틀용 업데이트 로직 (리스트 길이 1)
        if "my_active" in data:
            self.my_active = data["my_active"] # ["망나뇽"]
        if "opp_active" in data:
            self.opponent_active = data["opp_active"] # ["파오젠"]
            for mon in data["opp_active"]:
                if mon != "?" and mon not in self.opponent_confirmed:
                    self.opponent_confirmed.add(mon)
        
        if "my_hp" in data: self.my_hp.update(data["my_hp"])
        if "opp_hp" in data: self.opponent_hp.update(data["opp_hp"])
        if "opp_info" in data:
            for mon, info in data["opp_info"].items():
                if mon not in self.opponent_info: self.opponent_info[mon] = {}
                self.opponent_info[mon].update(info)

    def get_context_text(self):
        # 3마리 선출 중 미확인 계산
        unknown_count = 3 - len(self.opponent_confirmed)
        unknown_str = f"(미확인 {unknown_count}마리)" if unknown_count > 0 else "(3마리 전원 확정)"
        
        return f"""
        [내 필드 (Active)]: {self.my_active[0]}
        [상대 필드 (Active)]: {self.opponent_active[0]}
        
        [내 체력]: {self.my_hp}
        [상대 체력]: {self.opponent_hp}
        
        [내 선출 3마리]: {', '.join(self.my_selection)}
        [상대 엔트리]:
        - 전체: {', '.join(self.opponent_roster)}
        - 확인된 멤버: {', '.join(self.opponent_confirmed)} {unknown_str}
        
        [상대 상세 정보]: {self.opponent_info}
        """