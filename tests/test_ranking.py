from bot.engine.ranking import calculate_elo

class TestCalculateElo:
    def test_equal_elo(self):
        new_p1, new_p2 = calculate_elo(1000, 1000, 1)
        assert new_p1 > 1000
        assert new_p2 < 1000
        assert new_p1 - 1000 == 1000 - new_p2

    def test_large_gap(self):
        new_p1, new_p2 = calculate_elo(1500, 1000, 2)
        assert new_p1 < 1500
        assert new_p2 > 1000
        assert abs(new_p1 - 1500) > 16
