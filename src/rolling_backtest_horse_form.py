import argparse
import csv
from collections import defaultdict
from pathlib import Path

from predict_historical_win_ev import odds_bucket
from rolling_backtest_race_features import add_market_probabilities


def parse_date(yyyymmdd: str) -> int:
    """days since epoch-ish ordinal, good enough for layoff gaps"""
    y, m, d = int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8])
    return y * 372 + m * 31 + d  # monotone approximation, exact gaps not needed at bucket granularity


def layoff_bucket(gap_days: int | None) -> str:
    if gap_days is None:
        return "first_start"
    if gap_days <= 16:
        return "<=16d"
    if gap_days <= 35:
        return "17-35d"
    if gap_days <= 70:
        return "36-70d"
    if gap_days <= 190:
        return "71-190d"
    return "190d+"


def last_finish_bucket(rank: int | None, field: int | None) -> str:
    if rank is None:
        return "none"
    if rank == 1:
        return "won"
    if rank <= 3:
        return "2-3"
    if field and rank >= field - 1 and rank >= 10:
        return "tailed_off"
    if rank <= 9:
        return "4-9"
    return "10+"


def form3_bucket(history: list[tuple[int, int, int]]) -> str:
    """history items: (date_ord, finish_rank, field_size), newest last"""
    recent = history[-3:]
    if len(recent) < 2:
        return "unknown"
    scores = []
    for _, rank, field in recent:
        if field > 1:
            scores.append(1.0 - (min(rank, field) - 1) / (field - 1))
    if not scores:
        return "unknown"
    avg = sum(scores) / len(scores)
    if avg >= 0.75:
        return "high"
    if avg >= 0.50:
        return "mid"
    if avg >= 0.25:
        return "low"
    return "poor"


def beaten_fav_bucket(last_pop: int | None, last_rank: int | None) -> str:
    if last_pop is None or last_rank is None:
        return "none"
    if last_pop <= 2 and last_rank >= 6:
        return "beaten_fav"
    if last_pop >= 8 and last_rank <= 3:
        return "surprise_placer"
    return "normal"


class Agg:
    __slots__ = ("count", "wins", "expected", "ret")

    def __init__(self) -> None:
        self.count = 0
        self.wins = 0
        self.expected = 0.0
        self.ret = 0.0

    def update(self, market_prob: float, won: int, odds: float) -> None:
        self.count += 1
        self.wins += won
        self.expected += market_prob
        self.ret += odds * won


def group_races(path: Path):
    """Yield (race_id, rows) in chronological (race_id) order."""
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        current = None
        buffer: list[dict[str, str]] = []
        for row in reader:
            if row["race_id"] != current:
                if buffer:
                    yield current, buffer
                current = row["race_id"]
                buffer = []
            buffer.append(row)
        if buffer:
            yield current, buffer


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rolling no-leakage ablation for horse-history features. Each race is evaluated with "
            "feature-cell aggregates built ONLY from earlier races, then added to them. Reports "
            "market-relative edge and flat ROI per (feature, odds bucket) cell, split by year."
        )
    )
    parser.add_argument("--input", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--eval-start", default="20050101", help="skip evaluation before this date (warm-up)")
    parser.add_argument("--output-dir", default="outputs/backtests/horse_form")
    parser.add_argument("--min-cell-count", type=int, default=2000)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # per-horse history: (date_ord, finish_rank, field_size, popularity)
    history: dict[str, list[tuple[int, int, int, int]]] = defaultdict(list)
    # cell aggregates keyed (family, feature_value, odds_bucket); "@year" split kept separately
    total_aggs: dict[tuple[str, str, str], Agg] = defaultdict(Agg)
    year_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)

    races = 0
    evaluated = 0
    for race_id, rows in group_races(Path(args.input)):
        races += 1
        race_date = rows[0]["race_date"]
        date_ord = parse_date(race_date)
        field_size = len(rows)

        ok, _ = add_market_probabilities(rows)
        features_per_row = []
        for row in rows:
            h = history.get(row["horse_id"], [])
            if h:
                last = h[-1]
                gap = date_ord - last[0]
                feats = {
                    "layoff": layoff_bucket(gap),
                    "last_finish": last_finish_bucket(last[1], last[2]),
                    "form3": form3_bucket([(d, r, f) for d, r, f, _ in h]),
                    "fav_signal": beaten_fav_bucket(last[3] if last[3] > 0 else None, last[1]),
                }
            else:
                feats = {
                    "layoff": layoff_bucket(None),
                    "last_finish": last_finish_bucket(None, None),
                    "form3": "unknown",
                    "fav_signal": "none",
                }
            features_per_row.append(feats)

        if ok and race_date >= args.eval_start:
            evaluated += 1
            year = race_date[:4]
            for row, feats in zip(rows, features_per_row):
                try:
                    odds = float(row["win_odds"])
                    won = int(row["label_win"])
                    mp = float(row["market_probability"])
                except (KeyError, ValueError):
                    continue
                bucket = odds_bucket(odds)
                for family, value in feats.items():
                    total_aggs[(family, value, bucket)].update(mp, won, odds)
                    year_aggs[(family, value, bucket, year)].update(mp, won, odds)

        # update history AFTER evaluating (no leakage)
        for row in rows:
            try:
                rank = int(row["finish_rank"])
            except ValueError:
                continue
            if rank <= 0:
                continue
            try:
                pop = int(row["win_popularity"])
            except ValueError:
                pop = 0
            history[row["horse_id"]].append((date_ord, rank, field_size, pop))
            if len(history[row["horse_id"]]) > 6:
                history[row["horse_id"]] = history[row["horse_id"]][-6:]

    # report
    out_rows = []
    for (family, value, bucket), agg in sorted(total_aggs.items()):
        if agg.count < args.min_cell_count or agg.expected <= 0:
            continue
        years = [
            (year, ya)
            for (f2, v2, b2, year), ya in year_aggs.items()
            if f2 == family and v2 == value and b2 == bucket and ya.expected > 0 and ya.count >= 50
        ]
        pos_years = sum(1 for _, ya in years if ya.wins / ya.expected > 1.0)
        out_rows.append(
            {
                "family": family,
                "value": value,
                "odds_bucket": bucket,
                "count": str(agg.count),
                "wins": str(agg.wins),
                "expected_wins": f"{agg.expected:.1f}",
                "edge_vs_market": f"{agg.wins / agg.expected:.4f}",
                "flat_roi": f"{agg.ret / agg.count:.4f}",
                "years_evaluated": str(len(years)),
                "years_edge_positive": str(pos_years),
                "year_consistency": f"{pos_years / len(years):.2f}" if years else "",
            }
        )

    out_rows.sort(key=lambda r: -float(r["edge_vs_market"]))
    report_path = output_dir / "form_cell_edges.csv"
    with report_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"races={races} evaluated={evaluated} cells_reported={len(out_rows)} output={report_path}")
    print("top edges (count>=2000):")
    for row in out_rows[:12]:
        print(
            f"  {row['family']}={row['value']} odds={row['odds_bucket']} n={row['count']} "
            f"edge={row['edge_vs_market']} roi={row['flat_roi']} "
            f"consistency={row['years_edge_positive']}/{row['years_evaluated']}"
        )
    print("bottom edges:")
    for row in out_rows[-6:]:
        print(
            f"  {row['family']}={row['value']} odds={row['odds_bucket']} n={row['count']} "
            f"edge={row['edge_vs_market']} roi={row['flat_roi']} "
            f"consistency={row['years_edge_positive']}/{row['years_evaluated']}"
        )


if __name__ == "__main__":
    main()
