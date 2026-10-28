from __future__ import annotations

import pandas as pd


def build_interpretation_cards(composites: pd.DataFrame) -> list[dict[str, str]]:
    if composites.empty:
        return []

    score_map = composites.set_index("composite")["score"].to_dict()
    cards = [
        {
            "title": "Physical tightness confirmed",
            "status": _status(score_map.get("Paper vs Physical Stress Index", 50)),
            "body": "Higher scores mean prompt physical proxies and logistics are reinforcing, not just paper futures.",
        },
        {
            "title": "East-of-Suez stress leading",
            "status": _status(score_map.get("East-of-Suez Stress Index", 50)),
            "body": "Higher scores mean Oman/Dubai/Murban-style proxies are leading the cross-market stress picture.",
        },
        {
            "title": "Inland U.S. congestion risk",
            "status": _status(score_map.get("U.S. Inland Dislocation Index", 50)),
            "body": "Higher scores mean inland U.S. pressure and export-barrel strength are diverging from flat-price CL.",
        },
        {
            "title": "Products tighter than crude",
            "status": _status(score_map.get("Product Stress Index", 50)),
            "body": "Higher scores mean downstream product and crack stress is carrying more of the signal than crude itself.",
        },
        {
            "title": "Freight / logistics bottleneck intensifying",
            "status": _status(score_map.get("Logistics Constraint Index", 50)),
            "body": "Higher scores mean movement and insurability constraints are reinforcing the market story.",
        },
    ]
    return cards


def build_daily_narrative(
    composites: pd.DataFrame,
    snapshot: pd.DataFrame,
    divergences: pd.DataFrame,
) -> str:
    if composites.empty or snapshot.empty:
        return "The dashboard is waiting for data."

    top = composites.sort_values("score", ascending=False).iloc[0]
    dominant = top["composite"]
    brent_cl = snapshot.loc["BRENT_CL_SPREAD", "last"] if "BRENT_CL_SPREAD" in snapshot.index else 0.0
    northsea = snapshot.loc["NORTHSEA_PHYSICAL_PREMIUM", "last"] if "NORTHSEA_PHYSICAL_PREMIUM" in snapshot.index else 0.0
    east = snapshot.loc["EAST_OF_SUEZ_PREMIUM", "last"] if "EAST_OF_SUEZ_PREMIUM" in snapshot.index else 0.0

    story = [
        f"Dominant heuristic today: {dominant} ({top['score']:.1f}/100).",
        f"Brent minus CL is {brent_cl:.2f}, North Sea physical premium is {northsea:.2f}, and East-of-Suez premium is {east:.2f}.",
    ]

    if top["score"] >= 67:
        story.append("The dashboard sees a reinforced stress regime rather than a mild or isolated dislocation.")
    elif top["score"] <= 45:
        story.append("The dashboard sees relatively contained stress in the dominant channel.")
    else:
        story.append("The dashboard sees mixed conditions with stress building but not fully confirmed.")

    if not divergences.empty:
        story.append(f"{len(divergences)} historically linked relationships are currently diverging and need closer attention.")
    else:
        story.append("Major tracked relationships are still broadly holding together.")

    return " ".join(story)


def _status(score: float) -> str:
    if score >= 67:
        return "Red"
    if score >= 45:
        return "Amber"
    return "Green"
