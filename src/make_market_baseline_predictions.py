import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["race_id", "race_name", "bet_type", "selection", "probability", "confidence", "reason"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create no-edge market baseline probabilities from live odds.")
    parser.add_argument("--odds", default="data/live_odds.csv")
    parser.add_argument("--output", default="data/upcoming_predictions.csv")
    parser.add_argument("--race-name", default="")
    args = parser.parse_args()

    odds_rows = [row for row in read_csv(Path(args.odds)) if float(row["odds"]) > 1]
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in odds_rows:
        groups[(row["race_id"], row["bet_type"])].append(row)

    prediction_rows: list[dict[str, str]] = []
    for (race_id, bet_type), rows in groups.items():
        implied_total = sum(1 / float(row["odds"]) for row in rows)
        if implied_total <= 0:
            continue
        for row in rows:
            probability = (1 / float(row["odds"])) / implied_total
            prediction_rows.append(
                {
                    "race_id": race_id,
                    "race_name": args.race_name,
                    "bet_type": bet_type,
                    "selection": row["selection"],
                    "probability": f"{probability:.6f}",
                    "confidence": "baseline",
                    "reason": "market_no_vig_probability_no_edge",
                }
            )

    prediction_rows.sort(key=lambda row: (row["race_id"], row["bet_type"], row["selection"]))
    write_csv(Path(args.output), prediction_rows)
    print(f"predictions={len(prediction_rows)} output={args.output}")


if __name__ == "__main__":
    main()
