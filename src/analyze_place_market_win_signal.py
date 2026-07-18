import argparse
import csv
from collections import defaultdict
from pathlib import Path

from backtest_place_ev import (
    PlaceRateModel,
    iter_training_races,
    load_validation_races,
    market_win_probabilities,
)
from rolling_backtest_race_features import field_bucket


SIGNAL_EDGES = [0.70, 0.85, 0.95, 1.05, 1.20, 1.50]


def signal_bucket(signal: float) -> str:
    labels = ["<0.70", "0.70-0.85", "0.85-0.95", "0.95-1.05", "1.05-1.20", "1.20-1.50", ">=1.50"]
    for edge, label in zip(SIGNAL_EDGES, labels):
        if signal < edge:
            return label
    return labels[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Test whether place-market disagreement with the win market predicts win outcomes. "
            "signal = place-market implied place prob / win-derived model place prob; "
            "signal > 1 means the place market is bullish relative to the win market."
        )
    )
    parser.add_argument("--training", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--validation", default="data/model/place_validation_2025_2026.csv")
    parser.add_argument("--output-dir", default="outputs/backtests/place_market_win_signal")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    validation = load_validation_races(Path(args.validation))
    model = PlaceRateModel()
    training_iter = iter_training_races(Path(args.training))
    pending = next(training_iter, None)

    detail: list[dict[str, str]] = []
    for race_id, runners in validation:
        race_date = race_id[:8]
        while pending is not None and pending[0] < race_date:
            for p_w, field, label in pending[1]:
                model.add(field, p_w, label)
            pending = next(training_iter, None)

        starters = int(runners[0]["num_starters"] or 0)
        if starters < 8:
            continue  # keep one payout regime (top-3) for a clean read
        field = field_bucket(starters)
        valid = []
        odds_list = []
        for r in runners:
            if not r["win_odds"] or not r["place_odds_min"] or not r["place_odds_max"]:
                continue
            try:
                odds_list.append(float(r["win_odds"]))
                valid.append(r)
            except ValueError:
                continue
        probs = market_win_probabilities(odds_list)
        if probs is None or len(valid) < 8:
            continue

        # place-market implied probabilities from mid odds, normalized to 3 paid places
        mids = [(float(r["place_odds_min"]) + float(r["place_odds_max"])) / 2 for r in valid]
        inv_sum = sum(1 / m for m in mids)
        if inv_sum <= 0:
            continue
        for p_w, r, mid in zip(probs, valid, mids):
            p_place_market = (1 / mid) / inv_sum * 3.0
            p_place_model, _ = model.estimate(field, p_w)
            signal = p_place_market / p_place_model
            won = 1 if r["finish_rank"] == "1" else 0
            detail.append(
                {
                    "race_id": race_id,
                    "horse_no": r["horse_no"],
                    "win_odds": r["win_odds"],
                    "market_win_probability": f"{p_w:.5f}",
                    "place_probability_model": f"{p_place_model:.5f}",
                    "place_probability_market": f"{p_place_market:.5f}",
                    "signal": f"{signal:.4f}",
                    "signal_bucket": signal_bucket(signal),
                    "label_win": str(won),
                    "place_label": r["place_label"],
                    "realized_place_return": f"{int(r['place_payout_yen']) / 100:.2f}",
                }
            )

    detail_path = output_dir / "signal_detail.csv"
    with detail_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(detail[0].keys()))
        writer.writeheader()
        writer.writerows(detail)

    # aggregate per signal bucket
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in detail:
        groups[row["signal_bucket"]].append(row)

    summary = []
    order = ["<0.70", "0.70-0.85", "0.85-0.95", "0.95-1.05", "1.05-1.20", "1.20-1.50", ">=1.50"]
    for bucket in order:
        rows = groups.get(bucket, [])
        n = len(rows)
        if n == 0:
            continue
        expected_wins = sum(float(r["market_win_probability"]) for r in rows)
        actual_wins = sum(int(r["label_win"]) for r in rows)
        win_roi = sum(float(r["win_odds"]) * int(r["label_win"]) for r in rows) / n
        expected_places_model = sum(float(r["place_probability_model"]) for r in rows)
        actual_places = sum(int(r["place_label"]) for r in rows)
        place_roi = sum(float(r["realized_place_return"]) for r in rows) / n
        summary.append(
            {
                "signal_bucket": bucket,
                "n": str(n),
                "expected_wins_by_win_market": f"{expected_wins:.1f}",
                "actual_wins": str(actual_wins),
                "win_edge_vs_market": f"{actual_wins / expected_wins:.4f}" if expected_wins else "",
                "win_roi_flat": f"{win_roi:.4f}",
                "expected_places_by_model": f"{expected_places_model:.1f}",
                "actual_places": str(actual_places),
                "place_edge_vs_model": f"{actual_places / expected_places_model:.4f}" if expected_places_model else "",
                "place_roi_flat": f"{place_roi:.4f}",
            }
        )

    summary_path = output_dir / "signal_summary.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    print(f"runners={len(detail)} outputs: {detail_path}, {summary_path}")
    for row in summary:
        print(row)


if __name__ == "__main__":
    main()
