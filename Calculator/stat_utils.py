# stat_utils.py
import math

# 성격 보정표 (상승 1.1, 하락 0.9, 나머지 1.0)
NATURE_MODS = {
    "Adamant": {"atk": 1.1, "spa": 0.9},  # 고집
    "Brave": {"atk": 1.1, "spe": 0.9},    # 용감
    "Lonely": {"atk": 1.1, "def": 0.9},   # 외로움
    "Naughty": {"atk": 1.1, "spd": 0.9},  # 개구쟁이
    "Bold": {"def": 1.1, "atk": 0.9},     # 대담
    "Relaxed": {"def": 1.1, "spe": 0.9},  # 무사태평
    "Impish": {"def": 1.1, "spa": 0.9},   # 장난꾸러기
    "Lax": {"def": 1.1, "spd": 0.9},      # 촐랑
    "Modest": {"spa": 1.1, "atk": 0.9},   # 조심
    "Quiet": {"spa": 1.1, "spe": 0.9},    # 냉정
    "Mild": {"spa": 1.1, "def": 0.9},     # 의젓
    "Rash": {"spa": 1.1, "spd": 0.9},     # 덜렁
    "Calm": {"spd": 1.1, "atk": 0.9},     # 차분
    "Gentle": {"spd": 1.1, "def": 0.9},   # 얌전
    "Sassy": {"spd": 1.1, "spe": 0.9},    # 건방
    "Careful": {"spd": 1.1, "spa": 0.9},  # 신중
    "Timid": {"spe": 1.1, "atk": 0.9},    # 겁쟁이
    "Hasty": {"spe": 1.1, "def": 0.9},    # 성급
    "Jolly": {"spe": 1.1, "spa": 0.9},    # 명랑
    "Naive": {"spe": 1.1, "spd": 0.9},    # 천진난만
}

def calculate_stat(base, iv, ev, nature_mod, is_hp=False, level=50):
    """
    포켓몬 실능 계산 공식 (레벨 50 기준)
    """
    # 1. 공통 부분: (종족값x2 + 개체값 + 노력치/4) * 레벨 / 100
    core = (2 * base + iv + (ev / 4)) * level / 100
    
    if is_hp:
        # HP 공식: core + 레벨 + 10
        # (단, 껍질몬 등 예외는 제외하고 일반적인 경우만)
        return math.floor(core + level + 10)
    else:
        # 나머지 공식: (core + 5) * 성격보정
        return math.floor((core + 5) * nature_mod)

def parse_smogon_spread(spread_str):
    """
    Smogon 문자열 파싱
    입력 예: "Timid:4/0/0/252/0/252"
    출력: 성격(str), 노력치 딕셔너리
    """
    try:
        nature, evs_str = spread_str.split(":")
        ev_list = list(map(int, evs_str.split("/")))
        # 순서: HP, Atk, Def, SpA, SpD, Spe
        evs = {
            "hp": ev_list[0],
            "atk": ev_list[1],
            "def": ev_list[2],
            "spa": ev_list[3],
            "spd": ev_list[4],
            "spe": ev_list[5]
        }
        return nature, evs
    except Exception as e:
        print(f"Spread 파싱 에러: {spread_str} -> {e}")
        return "Hardy", {"hp":0, "atk":0, "def":0, "spa":0, "spd":0, "spe":0}
    
def get_rank_multiplier(stage):
    """
    랭크 변화 단계(-6 ~ +6)를 실제 곱연산 수치로 변환
    """
    if stage == 0:
        return 1.0
    
    # 랭크업 (공, 방, 특공, 특방, 스피드)
    if stage > 0:
        return (2 + stage) / 2
    # 랭크다운
    else:
        return 2 / (2 + abs(stage))

def apply_rank(stat_value, stage):
    """
    실수치에 랭크 보정을 적용하여 최종 수치 반환
    """
    return int(stat_value * get_rank_multiplier(stage))