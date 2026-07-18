import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Bet:
    race_id: str
    race_name: str
    bet_type: str
    selection: str
    odds: float
    probability: float
    stake: float | None
    min_ev: float
    confidence: str
    reason: str


def parse_float(value: str, default: float | None = None) -> float | None:
    value = (value or "").strip()
    if value == "":
        return default
    return float(value)


def load_bets(path: Path) -> list[Bet]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        bets = []
        for row in rows:
            odds = parse_float(row.get("odds", ""))
            probability = parse_float(row.get("probability", ""))
            if odds is None or probability is None:
                continue
            bets.append(
                Bet(
                    race_id=row.get("race_id", "").strip(),
                    race_name=row.get("race_name", "").strip(),
                    bet_type=row.get("bet_type", "").strip(),
                    selection=row.get("selection", "").strip(),
                    odds=odds,
                    probability=probability,
                    stake=parse_float(row.get("stake", "")),
                    min_ev=parse_float(row.get("min_ev", ""), 0.0) or 0.0,
                    confidence=row.get("confidence", "").strip(),
                    reason=row.get("reason", "").strip(),
                )
            )
    return bets


def kelly_fraction(probability: float, odds: float) -> float:
    if odds <= 1:
        return 0.0
    return max(0.0, (probability * odds - 1) / (odds - 1))


def evaluate_bet(bet: Bet, bankroll: float, kelly_scale: float, max_fraction: float) -> dict[str, str]:
    break_even_probability = 1 / bet.odds
    ev_per_yen = bet.probability * bet.odds - 1
    probability_edge = bet.probability - break_even_probability
    full_kelly = kelly_fraction(bet.probability, bet.odds)
    scaled_fraction = min(full_kelly * kelly_scale, max_fraction)
    recommended_stake = bet.stake if bet.stake is not None else bankroll * scaled_fraction
    recommended_stake = max(0, int(recommended_stake // 100 * 100))
    expected_profit = recommended_stake * ev_per_yen
    decision = "BUY" if ev_per_yen >= bet.min_ev and recommended_stake > 0 else "PASS"

    return {
        "decision": decision,
        "race_id": bet.race_id,
        "race_name": bet.race_name,
        "bet_type": bet.bet_type,
        "selection": bet.selection,
        "odds": f"{bet.odds:.3f}",
        "probability": f"{bet.probability:.4f}",
        "break_even_probability": f"{break_even_probability:.4f}",
        "probability_edge": f"{probability_edge:.4f}",
        "ev_per_yen": f"{ev_per_yen:.4f}",
        "min_ev": f"{bet.min_ev:.4f}",
        "kelly_fraction": f"{full_kelly:.4f}",
        "recommended_stake": str(recommended_stake),
        "expected_profit": f"{expected_profit:.0f}",
        "confidence": bet.confidence,
        "reason": bet.reason,
    }


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "decision",
        "race_id",
        "race_name",
        "bet_type",
        "selection",
        "odds",
        "probability",
        "break_even_probability",
        "probability_edge",
        "ev_per_yen",
        "min_ev",
        "kelly_fraction",
        "recommended_stake",
        "expected_profit",
        "confidence",
        "reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="期待値のある馬券候補を抽出します。")
    parser.add_argument("--input", default="data/manual_bets.csv")
    parser.add_argument("--output", default="outputs/bets_recommended.csv")
    parser.add_argument("--bankroll", type=float, default=10000)
    parser.add_argument("--kelly-scale", type=float, default=0.25)
    parser.add_argument("--max-fraction", type=float, default=0.03)
    args = parser.parse_args()

    bets = load_bets(Path(args.input))
    rows = [
        evaluate_bet(bet, args.bankroll, args.kelly_scale, args.max_fraction)
        for bet in bets
    ]
    rows.sort(key=lambda row: (row["decision"] != "BUY", -float(row["ev_per_yen"])))
    write_rows(Path(args.output), rows)

    buy_rows = [row for row in rows if row["decision"] == "BUY"]
    total_stake = sum(int(row["recommended_stake"]) for row in buy_rows)
    total_expected_profit = sum(float(row["expected_profit"]) for row in buy_rows)
    print(f"evaluated={len(rows)} buy={len(buy_rows)} stake={total_stake} expected_profit={total_expected_profit:.0f}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
