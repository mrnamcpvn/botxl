from bot.engine.rewards import calc_level, calc_rewards, apply_rewards

class TestCalcLevel:
    def test_level_1_zero_xp(self):
        assert calc_level(0) == (1, 0)

    def test_level_up(self):
        assert calc_level(80) == (2, 0)

class TestCalcRewards:
    def test_win_rewards(self):
        c, x = calc_rewards(True, 1, 1)
        assert c == 50
        assert x == 25

    def test_lose_rewards(self):
        c, x = calc_rewards(False)
        assert c == 0
        assert x == 0

    def test_win_lower_level(self):
        c, x = calc_rewards(True, my_level=1, opponent_level=3)
        assert c == 100  # 50 * (1 + 2*0.5) = 100
        assert x == 50   # 25 * 2 = 50

    def test_win_higher_level_gap1(self):
        c, x = calc_rewards(True, my_level=3, opponent_level=2)
        assert c == 35  # 50 * (1 - 0.3) = 35
        assert x == 17  # 25 * 0.7 = 17

    def test_win_higher_level_gap3(self):
        c, x = calc_rewards(True, my_level=5, opponent_level=2)
        assert c == 0
        assert x == 0
