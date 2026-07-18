from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RoundLog:
    r: int
    actor: str
    skill: str
    damage: int
    heal: int
    hp1: int
    hp2: int
    effects: list


@dataclass
class RoundResult:
    p1: dict
    p2: dict
    log_messages: list
    finished: bool
    winner_id: Optional[str] = None


@dataclass
class BattleFlags:
    p1_defending: bool = False
    p2_defending: bool = False
    p1_stunned: bool = False
    p2_stunned: bool = False
