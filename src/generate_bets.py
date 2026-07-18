import argparse
import csv
import json
from pathlib import Path

from expected_value import Bet, evaluate_bet, write_rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_config(path: Path) -> dict[str, float]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("race_id", "").strip(),
        row.get("bet_type", "").strip(),
        row.get("selection", "").strip(),
    )


def generate_bets(
    predictions_path: Path,
    odds_path: Path,
    config_path: Path,
) -> list[dict[str, str]]:
    config = load_config(config_path)
    odds_by_key = {key(row): row for row in read_csv(odds_path)}
    rows = []

    for prediction in read_csv(predictions_path):
        odds_row = odds_by_key.get(key(prediction))
        if not odds_row:
            continue

        bet = Bet(
            race_id=prediction.get("race_id", "").strip(),
            race_name=prediction.get("race_name", "").strip(),
            bet_type=prediction.get("bet_type", "").strip(),
            selection=prediction.get("selection", "").strip(),
            odds=float(odds_row["odds"]),
            probability=float(prediction["probability"]),
            stake=None,
            min_ev=float(config.get("min_ev_per_yen", 0.0)),
            confidence=prediction.get("confidence", "").strip(),
            reason=prediction.get("reason", "").strip(),
        )
        rows.append(
            evaluate_bet(
                bet=bet,
                bankroll=float(config.get("bankroll", 10000)),
                kelly_scale=float(config.get("kelly_scale", 0.25)),
                max_fraction=float(config.get("max_fraction_per_bet", 0.03)),
            )
        )

    rows.sort(key=lambda row: (row["decision"] != "BUY", -float(row["ev_per_yen"])))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Join model probabilities and live odds into EV-ranked bets.")
    parser.add_argument("--predictions", default="data/upcoming_predictions.csv")
    parser.add_argument("--odds", default="data/live_odds.csv")
    parser.add_argument("--config", default="config/bankroll.json")
    parser.add_argument("--output", default="outputs/bets_recommended.csv")
    args = parser.parse_args()

    rows = generate_bets(Path(args.predictions), Path(args.odds), Path(args.config))
    write_rows(Path(args.output), rows)

    buy_rows = [row for row in rows if row["decision"] == "BUY"]
    total_stake = sum(int(row["recommended_stake"]) for row in buy_rows)
    total_expected_profit = sum(float(row["expected_profit"]) for row in buy_rows)
    print(f"evaluated={len(rows)} buy={len(buy_rows)} stake={total_stake} expected_profit={total_expected_profit:.0f}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
