def calculate_elo(p1_elo: int, p2_elo: int, winner: int, battles_count: int = 0) -> tuple[int, int]:
    """ELO chuẩn cho PvP 1v1. K-factor giảm dần theo số trận (player giàu kinh nghiệm ổn định hơn)."""
    k_factor = max(16, 32 - battles_count // 10)
    expected_p1 = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
    expected_p2 = 1 - expected_p1
    if winner == 1:
        return (round(p1_elo + k_factor * (1 - expected_p1)),
                round(p2_elo + k_factor * (0 - expected_p2)))
    return (round(p1_elo + k_factor * (0 - expected_p1)),
            round(p2_elo + k_factor * (1 - expected_p2)))


def calculate_elo_tournament(winner_elo: int, loser_elo: int,
                              is_final: bool = False, is_semi: bool = False) -> tuple[int, int]:
    """
    ELO cho từng trận trong Đấu Trường Sinh Tử.

    K-factor cao hơn PvP thường vì tournament ít cơ hội hơn:
      - Chung kết: k=32 (trận quan trọng nhất)
      - Bán kết:   k=24
      - Các vòng:  k=20

    Trả về (new_winner_elo, new_loser_elo).
    """
    if is_final:
        k = 32
    elif is_semi:
        k = 24
    else:
        k = 20

    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser  = 1 - expected_winner

    new_winner_elo = round(winner_elo + k * (1 - expected_winner))
    new_loser_elo  = round(loser_elo  + k * (0 - expected_loser))

    # ELO tối thiểu 100 — không để ai về 0
    new_winner_elo = max(100, new_winner_elo)
    new_loser_elo  = max(100, new_loser_elo)

    return new_winner_elo, new_loser_elo
