import argparse
import csv
from pathlib import Path


FIELDS = [
    "bet_id",
    "race_date",
    "race_id",
    "race_name",
    "bet_type",
    "selection",
    "purchased_at",
    "purchase_odds",
    "closing_odds",
    "probability",
    "ev_per_yen",
    "stake",
    "result",
    "payout",
    "actual_profit",
    "expected_profit",
    "clv",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def settle(path: Path) -> list[dict[str, str]]:
    rows = []
    for row in read_rows(path):
        purchase_odds = float(row["purchase_odds"]) if row.get("purchase_odds") else 0.0
        closing_odds = float(row["closing_odds"]) if row.get("closing_odds") else 0.0
        probability = float(row["probability"]) if row.get("probability") else 0.0
        stake = float(row["stake"]) if row.get("stake") else 0.0
        result = int(row["result"]) if row.get("result") else 0

        ev_per_yen = probability * purchase_odds - 1 if purchase_odds else 0.0
        payout = stake * purchase_odds if result else 0.0
        actual_profit = payout - stake if stake else 0.0
        expected_profit = stake * ev_per_yen
        clv = purchase_odds / closing_odds if closing_odds else 0.0

        row["ev_per_yen"] = f"{ev_per_yen:.4f}"
        row["payout"] = f"{payout:.0f}"
        row["actual_profit"] = f"{actual_profit:.0f}"
        row["expected_profit"] = f"{expected_profit:.0f}"
        row["clv"] = f"{clv:.4f}"
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle bet log rows and calculate EV/CLV.")
    parser.add_argument("--input", default="data/bet_log.csv")
    parser.add_argument("--output", default="outputs/bet_log_settled.csv")
    args = parser.parse_args()

    rows = settle(Path(args.input))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    write_rows(Path(args.output), rows)

    total_expected = sum(float(row["expected_profit"]) for row in rows)
    total_actual = sum(float(row["actual_profit"]) for row in rows)
    avg_clv = sum(float(row["clv"]) for row in rows) / len(rows) if rows else 0.0
    print(f"bets={len(rows)} expected_profit={total_expected:.0f} actual_profit={total_actual:.0f} avg_clv={avg_clv:.4f}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
