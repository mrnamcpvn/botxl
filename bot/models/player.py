from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Player:
    id: str
    name: str
    class_id: str
    hp: int
    hp_max: int
    attack_min: int
    attack_max: int
    defense: int
    wins: int
    losses: int
    damage_dealt: int
    damage_taken: int
    coins: int
    xp: int
    level: int
    stat_points: int
    elo: int
    attack_cd: int
    special_cd: int
    defense_cd: int
    last_hp_update: Optional[float] = None
    upgrade_hp: int = 0
    upgrade_atk: int = 0
    upgrade_def: int = 0


@dataclass
class PlayerSnapshot:
    id: str
    name: str
    hp: int
    hp_max: int
    attack_min: int
    attack_max: int
    defense: int
    class_id: str
    damage_pct_bonus: int
    buffs: dict
    effects: dict
