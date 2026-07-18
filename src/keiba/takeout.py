"""券種ごとの払戻率(=1-控除率)テーブル。

JRAは2014年6月改定以降、券種ごとに払戻率が異なる。
地方競馬(NAR)は2012年改正競馬法(2014年4月施行)により各主催者が
70〜80%の範囲で券種ごとに設定する。主催者別の確認値は
PAYOUT_RATE_NAR_OVERRIDES を参照(2026-07時点の各主催者公表値)。

数値は変更されうるため、運用前に必ず主催者公表の最新値を確認すること。
出典: JRA公式(jra.go.jp/kouza/baken/)、各主催者公式サイト。
"""

from __future__ import annotations

# JRA 券種別払戻率(2014年6月7日以降の体系)
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

# 地方競馬の標準的な券種別払戻率(大半の主催者が採用する値)
# 注意: JRAと異なり 馬連・ワイド75%、三連複72.5% が標準(JRAより不利)。
PAYOUT_RATE_NAR_TYPICAL: dict[str, float] = {
    "win": 0.800,
    "place": 0.800,
    "bracket": 0.750,        # 枠連(枠単も同率の主催者が多い)
    "quinella": 0.750,       # 馬連
    "wide": 0.750,
    "exacta": 0.750,         # 馬単
    "trio": 0.725,           # 三連複
    "trifecta": 0.725,       # 三連単
    "triple_exacta": 0.700,  # トリプル馬単(SPAT4 LOTO、南関4場+門別)
    "multi_win": 0.700,      # 重勝式(オッズパークLOTO等)
}

# 標準値から乖離する主催者の確認済み差分(キー: 主催者スラッグ)
PAYOUT_RATE_NAR_OVERRIDES: dict[str, dict[str, float]] = {
    # ホッカイドウ(門別): ワイド80%は全国唯一の高設定、三連系は下限70%
    "hokkaido": {"wide": 0.800, "trio": 0.700, "trifecta": 0.700},
    # 兵庫(園田・姫路): 馬連77.5%(二次資料ベース、公式一次未確認)
    "hyogo": {"quinella": 0.775},
    # 高知: 最終競走(一発逆転ファイナルレース)の三連単のみ77.0%
    "kochi_final_race": {"trifecta": 0.770},
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
    "triple_exacta": "トリプル馬単",
    "multi_win": "重勝式",
}


def payout_rate(
    bet_type: str,
    organizer: str = "jra",
    overrides: dict[str, float] | None = None,
) -> float:
    """券種の払戻率を返す。

    Args:
        bet_type: "win", "place", "quinella" 等のキー。
        organizer: "jra"、"nar"(標準値)、または PAYOUT_RATE_NAR_OVERRIDES の
            主催者スラッグ("hokkaido" 等)。
        overrides: 任意の料率で上書きする辞書(最優先)。
    """
    if overrides and bet_type in overrides:
        return overrides[bet_type]
    org = organizer.lower()
    if org == "jra":
        table = PAYOUT_RATE_JRA
    else:
        table = dict(PAYOUT_RATE_NAR_TYPICAL)
        if org in PAYOUT_RATE_NAR_OVERRIDES:
            table.update(PAYOUT_RATE_NAR_OVERRIDES[org])
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
