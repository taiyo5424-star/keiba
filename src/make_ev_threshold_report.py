import argparse
import csv
import json
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create probability thresholds required to clear the EV filter.")
    parser.add_argument("--odds", default="data/live_odds.csv")
    parser.add_argument("--config", default="config/bankroll.json")
    parser.add_argument("--output", default="outputs/ev_thresholds.csv")
    args = parser.parse_args()

    with Path(args.config).open("r", encoding="utf-8") as f:
        config = json.load(f)
    min_ev = float(config.get("min_ev_per_yen", 0.0))

    rows = []
    for row in read_csv(Path(args.odds)):
        odds = float(row["odds"])
        break_even = 1 / odds
        required = (1 + min_ev) / odds
        rows.append(
            {
                "race_id": row["race_id"],
                "bet_type": row["bet_type"],
                "selection": row["selection"],
                "odds": f"{odds:.1f}",
                "break_even_probability": f"{break_even:.4f}",
                "required_probability": f"{required:.4f}",
                "required_edge_points": f"{(required - break_even) * 100:.2f}",
                "source": row["source"],
                "observed_at": row["observed_at"],
            }
        )

    rows.sort(key=lambda r: (r["bet_type"], float(r["required_probability"])))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "race_id",
        "bet_type",
        "selection",
        "odds",
        "break_even_probability",
        "required_probability",
        "required_edge_points",
        "source",
        "observed_at",
    ]
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"thresholds={len(rows)} output={args.output}")


if __name__ == "__main__":
    main()
