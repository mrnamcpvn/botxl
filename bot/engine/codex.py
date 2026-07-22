from bot.config import CODEX_DATA, CODEX_MILESTONES


def get_codex_bonuses(codex_kills: dict[str, int]) -> dict[str, int]:
    bonuses: dict[str, int] = {}
    for npc_id_str, kills in codex_kills.items():
        npc_id = int(npc_id_str)
        cd = CODEX_DATA.get(npc_id)
        if not cd:
            continue
        bt = cd["bonus"]
        for i, ms in enumerate(CODEX_MILESTONES):
            if kills >= ms and i < len(cd["tiers"]):
                bonuses[bt] = bonuses.get(bt, 0) + cd["tiers"][i]
            else:
                break
    return bonuses
