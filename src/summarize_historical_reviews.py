import csv
from pathlib import Path


RUNS = [
    ("2004 日本ダービー", "derby"),
    ("2004 スプリンターズS", "sprinters"),
    ("2004 天皇賞秋", "tenno_autumn"),
    ("2004 有馬記念", "arima"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    rows = []
    for race_name, slug in RUNS:
        prediction_path = Path(f"outputs/historical_2004_{slug}_win_ev.csv")
        evaluation_path = Path(f"outputs/historical_2004_{slug}_evaluation.csv")
        predictions = read_csv(prediction_path)
        evaluations = read_csv(evaluation_path)
        winner = next(row for row in evaluations if row["actual_win"] == "1")
        buy_rows = [row for row in predictions if row["decision"] == "BUY"]
        winner_prediction = next(row for row in predictions if row["horse_no"] == winner["horse_no"])
        top_ev = predictions[0]
        rows.append(
            {
                "race_name": race_name,
                "buy_count": str(len(buy_rows)),
                "winner": winner["selection"],
                "winner_horse_no": winner["horse_no"],
                "winner_odds": winner["win_odds"],
                "winner_predicted_probability": winner_prediction["probability"],
                "winner_ev_per_yen": winner_prediction["ev_per_yen"],
                "top_ev_selection": top_ev["selection"],
                "top_ev_odds": top_ev["win_odds"],
                "top_ev_per_yen": top_ev["ev_per_yen"],
                "paper_stake": str(sum(int(row["paper_stake"]) for row in evaluations)),
                "paper_profit": str(sum(int(float(row["paper_profit"])) for row in evaluations)),
                "prediction_file": str(prediction_path),
                "evaluation_file": str(evaluation_path),
            }
        )

    out = Path("outputs/historical_2004_candidate_reviews_summary.csv")
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"summary={out}")
    for row in rows:
        print(
            f"{row['race_name']}: buy={row['buy_count']} "
            f"winner={row['winner']}({row['winner_odds']}x) "
            f"winner_ev={row['winner_ev_per_yen']} top_ev={row['top_ev_selection']}({row['top_ev_per_yen']})"
        )


if __name__ == "__main__":
    main()
