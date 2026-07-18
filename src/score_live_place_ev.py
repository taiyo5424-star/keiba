import argparse
import csv
from collections import defaultdict
from pathlib import Path

from backtest_place_ev import PlaceRateModel, iter_training_races, market_win_probabilities
from rolling_backtest_race_features import field_bucket
from score_live_win_ev import group_by_race, read_csv


# The 2025-06..2026-01 no-leakage backtest (outputs/backtests/place_ev) was negative at
# every EV threshold: high win-market-derived place EV is adversely selected against the
# place pool. BUY stays locked until a place-specific positive backtest exists.
PLACE_VALIDATION_STATUS = "negative_backtest_20250614_20260118"


def latest_odds(odds_rows: list[dict[str, str]], bet_type: str) -> dict[tuple[str, str], dict[str, str]]:
    rows = [row for row in odds_rows if row.get("bet_type") == bet_type and row.get("horse_no")]
    rows.sort(key=lambda row: row.get("observed_at", ""))
    return {(row["race_id"], row["horse_no"]): row for row in rows}


def build_place_model(training_path: Path, before_date: str) -> PlaceRateModel:
    model = PlaceRateModel()
    for race_date, runners in iter_training_races(training_path):
        if race_date >= before_date:
            continue
        for p_w, field, label in runners:
            model.add(field, p_w, label)
    return model


def score_race(
    starts: list[dict[str, str]],
    race: dict[str, str],
    win_lookup: dict[tuple[str, str], dict[str, str]],
    place_lookup: dict[tuple[str, str], dict[str, str]],
    model: PlaceRateModel,
    allow_buy: bool,
    min_ev: float,
) -> list[dict[str, str]]:
    rows = []
    missing = []
    for start in starts:
        key = (start["race_id"], start["horse_no"])
        win = win_lookup.get(key)
        place = place_lookup.get(key)
        if not win or not place:
            missing.append({**start, **race, "decision": "PASS", "reason": "missing_latest_odds"})
            continue
        rows.append({**start, **race, "_win": win, "_place": place})

    odds_list = []
    valid = []
    for row in rows:
        try:
            odds_list.append(float(row["_win"]["odds"]))
            valid.append(row)
        except ValueError:
            missing.append({**row, "decision": "PASS", "reason": "bad_win_odds"})
    probs = market_win_probabilities(odds_list)
    if probs is None:
        return [
            {**row, "decision": "PASS", "reason": "abnormal_or_small_win_market"}
            for row in valid
        ] + missing

    field = field_bucket(len(valid))
    paid_places = 2 if len(valid) <= 7 else 3
    inv_mid_sum = 0.0
    for row in valid:
        place = row["_place"]
        odds_min = float(place.get("odds_min") or place["odds"])
        odds_max = float(place.get("odds_max") or place["odds"])
        inv_mid_sum += 2.0 / (odds_min + odds_max)
    scored = []
    for p_w, row in zip(probs, valid):
        place = row.pop("_place")
        win = row.pop("_win")
        odds_min = float(place.get("odds_min") or place["odds"])
        odds_max = float(place.get("odds_max") or place["odds"])
        # place-market implied prob: informative for ranking/audit, never for EV vs its own pool
        p_place_market = (2.0 / (odds_min + odds_max)) / inv_mid_sum * paid_places if inv_mid_sum else 0.0
        p_place, cell_count = model.estimate(field, p_w)
        ev_lower = p_place * odds_min
        can_buy = allow_buy and ev_lower >= min_ev
        scored.append(
            {
                **row,
                "decision": "BUY" if can_buy else "PASS",
                "reason": "meets_gate_and_buy_enabled" if can_buy else f"place_gate_locked:{PLACE_VALIDATION_STATUS}",
                "win_odds": win["odds"],
                "win_popularity": win.get("popularity", ""),
                "market_win_probability": f"{p_w:.5f}",
                "place_odds_min": f"{odds_min:.1f}",
                "place_odds_max": f"{odds_max:.1f}",
                "place_popularity": place.get("popularity", ""),
                "place_probability": f"{p_place:.5f}",
                "place_probability_market": f"{p_place_market:.5f}",
                "place_market_signal": f"{p_place_market / p_place:.4f}" if p_place else "",
                "place_model_cell_count": str(cell_count),
                "ev_return_per_yen_lower": f"{ev_lower:.4f}",
                "ev_per_yen": f"{ev_lower - 1:.4f}",
                "field_bucket": field,
                "observed_at": place.get("observed_at", ""),
                "validation_status": PLACE_VALIDATION_STATUS,
            }
        )
    scored.sort(key=lambda r: -float(r["ev_return_per_yen_lower"]))
    return scored + missing


def main() -> None:
    parser = argparse.ArgumentParser(description="Score latest place odds for live rankings. BUY is locked until a positive place backtest exists.")
    parser.add_argument("--training", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--races", default="data/jra_van_exports/races_minimal.csv")
    parser.add_argument("--starts", default="data/jra_van_exports/starts_minimal.csv")
    parser.add_argument("--odds", default="data/jra_van_exports/odds_win_place_minimal.csv")
    parser.add_argument("--race-date", required=True)
    parser.add_argument("--race-id", default="", help="score only this race (default: all races of the date)")
    parser.add_argument("--min-ev", type=float, default=1.20, help="return-per-yen threshold, only active with --allow-buy")
    parser.add_argument(
        "--allow-buy",
        action="store_true",
        help="enable the BUY gate; only set after a place-specific no-leakage backtest is positive",
    )
    parser.add_argument("--output", default="outputs/live_predictions/live_place_ev.csv")
    args = parser.parse_args()

    model = build_place_model(Path(args.training), args.race_date)
    race_rows = {row["race_id"]: row for row in read_csv(Path(args.races)) if row["race_date"] == args.race_date}
    starts_by_race = group_by_race([row for row in read_csv(Path(args.starts)) if row["race_date"] == args.race_date])
    odds_rows = read_csv(Path(args.odds))
    win_lookup = latest_odds(odds_rows, "win")
    place_lookup = latest_odds(odds_rows, "place")

    output_rows = []
    for race_id, starts in sorted(starts_by_race.items()):
        if args.race_id and race_id != args.race_id:
            continue
        race = race_rows.get(race_id)
        if not race:
            continue
        output_rows.extend(
            score_race(starts, race, win_lookup, place_lookup, model, args.allow_buy, args.min_ev)
        )

    fields = [
        "decision",
        "reason",
        "race_id",
        "race_date",
        "race_no",
        "race_name",
        "post_time",
        "horse_no",
        "horse_name",
        "jockey_name",
        "trainer_name",
        "win_odds",
        "win_popularity",
        "market_win_probability",
        "place_odds_min",
        "place_odds_max",
        "place_popularity",
        "place_probability",
        "place_probability_market",
        "place_market_signal",
        "place_model_cell_count",
        "ev_return_per_yen_lower",
        "ev_per_yen",
        "field_bucket",
        "surface_group",
        "distance",
        "observed_at",
        "validation_status",
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)

    buys = [row for row in output_rows if row["decision"] == "BUY"]
    print(f"rows={len(output_rows)} buys={len(buys)} output={args.output}")


if __name__ == "__main__":
    main()
