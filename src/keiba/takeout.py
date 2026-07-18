"""券種ごとの払戻率(=1-控除率)テーブル。

JRAは2014年6月改定以降、券種ごとに払戻率が異なる。
地方競馬(NAR)は主催者ごとに設定が異なるが、多くの主催者がJRAに近い
券種別料率を採用している。個別主催者の正確な値は各主催者の公表値で
上書きすること(`takeout_rate()` の `overrides` 引数)。

払戻率の出典はJRA公式サイト・各主催者公表資料。数値は変更されうるため、
運用前に必ず最新値を確認すること。
"""

from __future__ import annotations

# JRA 券種別払戻率(2014年6月以降の体系)
PAYOUT_RATE_JRA: dict[str, float] = {
    "win": 0.800,        # 単勝
    "place": 0.800,      # 複勝
    "bracket": 0.775,    # 枠連
    "quinella": 0.775,   # 馬連
    "wide": 0.775,       # ワイド(拡大馬連)
    "exacta": 0.750,     # 馬単
    "trio": 0.750,       # 三連複
    "trifecta": 0.725,   # 三連単
    "win5": 0.700,       # WIN5
}

# 地方競馬の代表的な券種別払戻率(主催者により差異あり)
PAYOUT_RATE_NAR_TYPICAL: dict[str, float] = {
    "win": 0.800,
    "place": 0.800,
    "bracket": 0.775,
    "quinella": 0.775,
    "wide": 0.775,
    "exacta": 0.750,
    "trio": 0.750,
    "trifecta": 0.725,
}

BET_TYPE_JA: dict[str, str] = {
    "win": "単勝",
    "place": "複勝",
    "bracket": "枠連",
    "quinella": "馬連",
    "wide": "ワイド",
    "exacta": "馬単",
    "trio": "三連複",
    "trifecta": "三連単",
    "win5": "WIN5",
}


def payout_rate(
    bet_type: str,
    organizer: str = "jra",
    overrides: dict[str, float] | None = None,
) -> float:
    """券種の払戻率を返す。

    Args:
        bet_type: "win", "place", "quinella" 等のキー。
        organizer: "jra" または "nar"。
        overrides: 主催者固有の料率で上書きする辞書。
    """
    if overrides and bet_type in overrides:
        return overrides[bet_type]
    table = PAYOUT_RATE_JRA if organizer.lower() == "jra" else PAYOUT_RATE_NAR_TYPICAL
    if bet_type not in table:
        raise KeyError(f"unknown bet type: {bet_type!r} (valid: {sorted(table)})")
    return table[bet_type]


def takeout_rate(
    bet_type: str,
    organizer: str = "jra",
    overrides: dict[str, float] | None = None,
) -> float:
    """券種の控除率(1 - 払戻率)を返す。"""
    return 1.0 - payout_rate(bet_type, organizer, overrides)
