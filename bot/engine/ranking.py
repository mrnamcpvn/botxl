def calculate_elo(p1_elo: int, p2_elo: int, winner: int, battles_count: int = 0) -> tuple[int, int]:
    k_factor = max(16, 32 - battles_count // 10)
    expected_p1 = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
    expected_p2 = 1 - expected_p1
    if winner == 1:
        return (round(p1_elo + k_factor * (1 - expected_p1)),
                round(p2_elo + k_factor * (0 - expected_p2)))
    return (round(p1_elo + k_factor * (0 - expected_p1)),
            round(p2_elo + k_factor * (1 - expected_p2)))
