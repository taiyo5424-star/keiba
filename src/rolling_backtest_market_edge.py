import argparse
import csv
from collections import defaultdict
from pathlib import Path

from predict_historical_win_ev import odds_bucket, clamp


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def group_by_race(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    by_race: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_race[row["race_id"]].append(row)
    return sorted(by_race.items(), key=lambda item: item[0])


class Agg:
    def __init__(self) -> None:
        self.count = 0
        self.wins = 0
        self.expected = 0.0

    def update(self, row: dict[str, str]) -> None:
        self.count += 1
        self.wins += int(row["label_win"])
        self.expected += float(row["market_probability"])

    def edge(self, prior: float) -> float:
        if self.count == 0:
            return 1.0
        return (self.wins + prior) / (self.expected + prior)


def add_market_probabilities(race_rows: list[dict[str, str]]) -> None:
    total = sum(1 / float(row["win_odds"]) for row in race_rows if float(row["win_odds"]) > 1)
    for row in race_rows:
        row["market_probability"] = (1 / float(row["win_odds"])) / total if total > 0 else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Rolling no-leakage backtest for market-relative win EV model.")
    parser.add_argument("--input", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--start-date", default="20050101")
    parser.add_argument("--min-ev", type=float, default=0.05)
    parser.add_argument("--stake", type=int, default=100)
    parser.add_argument("--output", default="outputs/backtests/rolling_market_edge_win_bets.csv")
    parser.add_argument("--summary", default="outputs/backtests/rolling_market_edge_win_summary.csv")
    args = parser.parse_args()

    races = group_by_race(read_csv(Path(args.input)))
    pop_bucket_aggs: dict[tuple[str, str], Agg] = defaultdict(Agg)
    jockey_aggs: dict[str, Agg] = defaultdict(Agg)
    trainer_aggs: dict[str, Agg] = defaultdict(Agg)

    bets = []
    summaries: dict[str, dict[str, float]] = defaultdict(lambda: {"races": 0, "bets": 0, "stake": 0, "return": 0, "wins": 0})

    for race_id, race_rows in races:
        add_market_probabilities(race_rows)
        race_date = race_rows[0]["race_date"]
        year = race_date[:4]
        if race_date >= args.start_date:
            summaries[year]["races"] += 1
            for row in race_rows:
                odds = float(row["win_odds"])
                bucket = odds_bucket(odds)
                combo_edge = pop_bucket_aggs[(row["win_popularity"], bucket)].edge(35.0)
                jockey_edge = jockey_aggs[row["jockey_code"]].edge(50.0)
                trainer_edge = trainer_aggs[row["trainer_code"]].edge(50.0)
                blended_edge = clamp(0.60 * combo_edge + 0.25 * jockey_edge + 0.15 * trainer_edge, 0.70, 1.25)
                probability = float(row["market_probability"]) * blended_edge
                ev = probability * odds - 1
                if ev >= args.min_ev:
                    payout = args.stake * odds if row["label_win"] == "1" else 0.0
                    profit = payout - args.stake
                    summaries[year]["bets"] += 1
                    summaries[year]["stake"] += args.stake
                    summaries[year]["return"] += payout
                    summaries[year]["wins"] += int(row["label_win"])
                    bets.append(
                        {
                            "race_id": race_id,
                            "race_date": race_date,
                            "horse_no": row["horse_no"],
                            "selection": row["horse_name"],
                            "win_odds": f"{odds:.1f}",
                            "probability": f"{probability:.4f}",
                            "ev_per_yen": f"{ev:.4f}",
                            "actual_win": row["label_win"],
                            "stake": str(args.stake),
                            "return": f"{payout:.0f}",
                            "profit": f"{profit:.0f}",
                            "blended_edge": f"{blended_edge:.4f}",
                        }
                    )

        for row in race_rows:
            bucket = odds_bucket(float(row["win_odds"]))
            pop_bucket_aggs[(row["win_popularity"], bucket)].update(row)
            jockey_aggs[row["jockey_code"]].update(row)
            trainer_aggs[row["trainer_code"]].update(row)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    bet_fields = ["race_id", "race_date", "horse_no", "selection", "win_odds", "probability", "ev_per_yen", "actual_win", "stake", "return", "profit", "blended_edge"]
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=bet_fields)
        writer.writeheader()
        writer.writerows(bets)

    summary_rows = []
    total = {"races": 0, "bets": 0, "stake": 0, "return": 0, "wins": 0}
    for year in sorted(summaries):
        s = summaries[year]
        for key in total:
            total[key] += s[key]
        roi = s["return"] / s["stake"] - 1 if s["stake"] else 0.0
        hit = s["wins"] / s["bets"] if s["bets"] else 0.0
        summary_rows.append({**{"year": year}, **{k: f"{v:.0f}" for k, v in s.items()}, "hit_rate": f"{hit:.4f}", "roi": f"{roi:.4f}"})
    total_roi = total["return"] / total["stake"] - 1 if total["stake"] else 0.0
    total_hit = total["wins"] / total["bets"] if total["bets"] else 0.0
    summary_rows.append({**{"year": "TOTAL"}, **{k: f"{v:.0f}" for k, v in total.items()}, "hit_rate": f"{total_hit:.4f}", "roi": f"{total_roi:.4f}"})

    with Path(args.summary).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "races", "bets", "stake", "return", "wins", "hit_rate", "roi"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"bets={len(bets)} output={args.output}")
    print(f"summary={args.summary}")
    print(summary_rows[-1])


if __name__ == "__main__":
    main()
