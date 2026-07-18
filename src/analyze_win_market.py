import argparse
import csv
from collections import defaultdict
from pathlib import Path


ODDS_BUCKETS = [
    (1.0, 2.0),
    (2.0, 3.0),
    (3.0, 5.0),
    (5.0, 10.0),
    (10.0, 20.0),
    (20.0, 50.0),
    (50.0, 100.0),
    (100.0, 10000.0),
]


def bucket_for_odds(odds: float) -> str:
    for low, high in ODDS_BUCKETS:
        if low <= odds < high:
            return f"{low:g}-{high:g}"
    return "other"


def summarize(rows: list[dict[str, str]], key_name: str) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row[key_name]].append(row)

    out = []
    for key, group in groups.items():
        starts = len(group)
        wins = sum(int(row["label_win"]) for row in group)
        stake = starts
        payout = sum(float(row["win_odds"]) for row in group if row["label_win"] == "1")
        out.append(
            {
                key_name: key,
                "starts": str(starts),
                "wins": str(wins),
                "win_rate": f"{wins / starts:.4f}",
                "avg_odds": f"{sum(float(row['win_odds']) for row in group) / starts:.2f}",
                "flat_win_roi": f"{payout / stake - 1:.4f}",
            }
        )
    return out


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze flat-bet win market ROI by odds/popularity buckets.")
    parser.add_argument("--input", default="data/model/win_training_minimal.csv")
    parser.add_argument("--out-dir", default="outputs/market")
    args = parser.parse_args()

    with Path(args.input).open("r", encoding="utf-8-sig", newline="") as f:
        rows = [row for row in csv.DictReader(f) if row["win_odds"] and row["win_popularity"]]

    for row in rows:
        row["odds_bucket"] = bucket_for_odds(float(row["win_odds"]))

    pop_rows = summarize(rows, "win_popularity")
    pop_rows.sort(key=lambda row: int(row["win_popularity"]))
    bucket_rows = summarize(rows, "odds_bucket")
    bucket_rows.sort(key=lambda row: ODDS_BUCKETS.index(tuple(map(float, row["odds_bucket"].split("-")))) if "-" in row["odds_bucket"] else 999)

    out_dir = Path(args.out_dir)
    write_csv(out_dir / "win_by_popularity.csv", pop_rows, ["win_popularity", "starts", "wins", "win_rate", "avg_odds", "flat_win_roi"])
    write_csv(out_dir / "win_by_odds_bucket.csv", bucket_rows, ["odds_bucket", "starts", "wins", "win_rate", "avg_odds", "flat_win_roi"])
    print(f"rows={len(rows)}")
    print(f"popularity={out_dir / 'win_by_popularity.csv'}")
    print(f"odds_bucket={out_dir / 'win_by_odds_bucket.csv'}")


if __name__ == "__main__":
    main()
