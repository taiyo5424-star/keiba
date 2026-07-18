import argparse
import csv
from collections import defaultdict
from pathlib import Path

from predict_historical_win_ev import odds_bucket
from rolling_backtest_race_features import add_market_probabilities
from rolling_backtest_horse_form import (
    Agg,
    beaten_fav_bucket,
    form3_bucket,
    group_races,
    last_finish_bucket,
    layoff_bucket,
    parse_date,
)


# candidate cells promoted from form_combo_edges.csv for year-by-year inspection
CANDIDATES = [
    ("last_finish*layoff", "tailed_off|71-190d", "06_20-50"),
    ("form3*layoff", "low|71-190d", "05_10-20"),
    ("form3*layoff", "poor|36-70d", "06_20-50"),
    ("layoff", "71-190d", "05_10-20"),  # robust single-feature baseline
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Year-by-year detail for candidate form-combo cells.")
    parser.add_argument("--input", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--eval-start", default="20050101")
    parser.add_argument("--output", default="outputs/backtests/horse_form/candidate_cells_yearly.csv")
    args = parser.parse_args()

    history: dict[str, list[tuple[int, int, int, int]]] = defaultdict(list)
    cell_year: dict[tuple[int, str], Agg] = defaultdict(Agg)

    for race_id, rows in group_races(Path(args.input)):
        race_date = rows[0]["race_date"]
        date_ord = parse_date(race_date)
        field_size = len(rows)
        ok, _ = add_market_probabilities(rows)

        feats_rows = []
        for row in rows:
            h = history.get(row["horse_id"], [])
            if h:
                last = h[-1]
                feats = {
                    "layoff": layoff_bucket(date_ord - last[0]),
                    "last_finish": last_finish_bucket(last[1], last[2]),
                    "form3": form3_bucket([(d, r, f) for d, r, f, _ in h]),
                    "fav_signal": beaten_fav_bucket(last[3] if last[3] > 0 else None, last[1]),
                }
            else:
                feats = {"layoff": "first_start", "last_finish": "none", "form3": "unknown", "fav_signal": "none"}
            feats_rows.append(feats)

        if ok and race_date >= args.eval_start:
            year = race_date[:4]
            for row, feats in zip(rows, feats_rows):
                try:
                    odds = float(row["win_odds"])
                    won = int(row["label_win"])
                    mp = float(row["market_probability"])
                except (KeyError, ValueError):
                    continue
                bucket = odds_bucket(odds)
                for idx, (family, value, cell_bucket) in enumerate(CANDIDATES):
                    if bucket != cell_bucket:
                        continue
                    if "*" in family:
                        fam_a, fam_b = family.split("*")
                        cell_value = f"{feats[fam_a]}|{feats[fam_b]}"
                    else:
                        cell_value = feats[family]
                    if cell_value == value:
                        cell_year[(idx, year)].update(mp, won, odds)

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

    out_rows = []
    for idx, (family, value, bucket) in enumerate(CANDIDATES):
        years = sorted(year for (i, year) in cell_year if i == idx)
        for year in years:
            agg = cell_year[(idx, year)]
            out_rows.append(
                {
                    "cell": f"{family} {value} {bucket}",
                    "year": year,
                    "n": str(agg.count),
                    "wins": str(agg.wins),
                    "expected_wins": f"{agg.expected:.1f}",
                    "edge": f"{agg.wins / agg.expected:.3f}" if agg.expected else "",
                    "flat_roi": f"{agg.ret / agg.count:.3f}" if agg.count else "",
                }
            )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"output={args.output}")
    current = None
    for row in out_rows:
        if row["cell"] != current:
            current = row["cell"]
            print(f"\n{current}")
        print(f"  {row['year']}: n={row['n']:>4} wins={row['wins']:>3} edge={row['edge']} roi={row['flat_roi']}")

    # recent-half summary
    print("\nrecent halves:")
    for idx, (family, value, bucket) in enumerate(CANDIDATES):
        for lo, hi, label in [("2005", "2015", "2005-2015"), ("2016", "2025", "2016-2025"), ("2021", "2025", "2021-2025")]:
            n = w = 0
            e = r = 0.0
            for (i, year), agg in cell_year.items():
                if i == idx and lo <= year <= hi:
                    n += agg.count
                    w += agg.wins
                    e += agg.expected
                    r += agg.ret
            if n:
                print(f"  {family} {value} {bucket} [{label}]: n={n} edge={w/e:.3f} roi={r/n:.3f}")


if __name__ == "__main__":
    main()
