import argparse
import csv
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def max_drawdown(equity: list[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        worst = min(worst, value - peak)
    return worst


def evaluate(path: Path, min_ev: float) -> dict[str, float]:
    total_stake = 0.0
    actual_profit = 0.0
    expected_profit = 0.0
    bets = 0
    wins = 0
    equity = []
    running_profit = 0.0

    for row in read_rows(path):
        odds = float(row["odds"])
        probability = float(row["probability"])
        result = int(row["result"])
        stake = float(row.get("stake") or 100)
        ev_per_yen = probability * odds - 1
        if ev_per_yen < min_ev:
            continue

        profit = stake * (odds - 1) if result else -stake
        running_profit += profit
        equity.append(running_profit)

        bets += 1
        wins += result
        total_stake += stake
        actual_profit += profit
        expected_profit += stake * ev_per_yen

    roi = actual_profit / total_stake if total_stake else 0.0
    expected_roi = expected_profit / total_stake if total_stake else 0.0
    hit_rate = wins / bets if bets else 0.0

    return {
        "bets": bets,
        "wins": wins,
        "hit_rate": hit_rate,
        "stake": total_stake,
        "actual_profit": actual_profit,
        "expected_profit": expected_profit,
        "roi": roi,
        "expected_roi": expected_roi,
        "max_drawdown": max_drawdown(equity),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest EV-filtered historical bets.")
    parser.add_argument("--input", default="data/historical_bets_example.csv")
    parser.add_argument("--min-ev", type=float, default=0.05)
    args = parser.parse_args()

    metrics = evaluate(Path(args.input), args.min_ev)
    for name, value in metrics.items():
        if isinstance(value, float):
            print(f"{name}={value:.4f}")
        else:
            print(f"{name}={value}")


if __name__ == "__main__":
    main()
