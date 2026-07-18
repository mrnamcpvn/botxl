import pytest

@pytest.fixture
def basic_player():
    return {
        "id": "test1", "name": "Test1", "class_id": "banxabong",
        "hp": 120, "hp_max": 120, "attack_min": 12, "attack_max": 17,
        "defense": 8, "wins": 0, "losses": 0,
        "damage_dealt": 0, "damage_taken": 0,
        "coins": 0, "xp": 0, "level": 1, "stat_points": 0, "elo": 1000,
        "attack_cd": 0, "special_cd": 0, "defense_cd": 0,
        "upgrade_hp": 0, "upgrade_atk": 0, "upgrade_def": 0,
        "skill_equipped": {"attack": 1, "special": 5, "defense": 10, "passive": 14},
        "skills_owned": [1, 5, 10, 14],
        "equipped": {}, "buffs": {},
    }

@pytest.fixture
def battle_flags():
    return {"p1_defending": False, "p2_defending": False, "p1_stunned": False, "p2_stunned": False}
