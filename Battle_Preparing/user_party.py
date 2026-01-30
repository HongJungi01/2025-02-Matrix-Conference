# user_party.py

class UserParty:
    def __init__(self):
        self.team = {} # 내 포켓몬들이 저장될 딕셔너리

    def add_pokemon(self, name, stats, item=None, ability=None, moves=None, tera_type=None):
        """
        사용자가 입력한 상세 정보를 저장합니다.
        stats: {'hp': 131, 'atk': 76, 'def': 75, 'spa': 187, 'spd': 155, 'spe': 205} (실수치)
        """
        self.team[name] = {
            "stats": stats,
            "item": item,
            "ability": ability,
            "moves": moves or [],
            "tera_type": tera_type,
            "is_user": True # 내 포켓몬임을 표시
        }
        print(f"✅ 내 파티 등록 완료: {name} (HP: {stats.get('hp')}) (ATK: {stats.get('atk')}) (DEF: {stats.get('def')}) (SPA: {stats.get('spa')}) (SPD: {stats.get('spd')}) (SPE: {stats.get('spe')})")

    def get_pokemon(self, name):
        return self.team.get(name)

# 전역 인스턴스 생성 (어디서든 불러다 쓸 수 있게)
my_party = UserParty()