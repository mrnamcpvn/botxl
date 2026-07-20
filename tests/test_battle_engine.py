import pytest
from bot.engine.battle import execute_action, get_effective_stats

class TestGetEffectiveStats:
    def test_basic_stats(self, basic_player):
        stats = get_effective_stats(basic_player)
        assert stats["attack_min"] == 12
        assert stats["defense"] == 20

class TestExecuteAction:
    @pytest.mark.asyncio
    async def test_attack_damage(self, basic_player, battle_flags):
        p1 = basic_player.copy()
        p2 = basic_player.copy()
        p2["id"] = "test2"
        result = await execute_action(p1, p2, 0, {"type": "attack", "skill_id": 1}, battle_flags)
        assert not result["finished"]
        assert result["p2"]["hp"] < 120

    @pytest.mark.asyncio
    async def test_defend_heal(self, basic_player, battle_flags):
        p1 = basic_player.copy()
        p2 = basic_player.copy()
        p2["id"] = "test2"
        p1["hp"] = 60
        result = await execute_action(p1, p2, 0, {"type": "defense", "skill_id": 10}, battle_flags)
        assert result["p1"]["hp"] > 60
