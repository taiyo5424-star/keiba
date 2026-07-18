import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

from rolling_backtest_race_features import field_bucket


PW_BIN_EDGES = [
    0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.04, 0.05, 0.065, 0.08,
    0.10, 0.125, 0.15, 0.175, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.65,
]


def pw_bin(p: float) -> int:
    for i, edge in enumerate(PW_BIN_EDGES):
        if p < edge:
            return i
    return len(PW_BIN_EDGES)


def place_label(finish_rank: int, starters: int) -> int | None:
    if starters < 5:
        return None
    paid = 2 if starters <= 7 else 3
    return 1 if 1 <= finish_rank <= paid else 0


class Cell:
    __slots__ = ("count", "placed")

    def __init__(self) -> None:
        self.count = 0
        self.placed = 0


class PlaceRateModel:
    """place rate by (field_bucket, win-market-probability bin), with shrinkage."""

    def __init__(self) -> None:
        self.by_field_bin: dict[tuple[str, int], Cell] = defaultdict(Cell)
        self.by_bin: dict[int, Cell] = defaultdict(Cell)
        self.total = Cell()

    def add(self, field: str, p_w: float, label: int) -> None:
        b = pw_bin(p_w)
        for cell in (self.by_field_bin[(field, b)], self.by_bin[b], self.total):
            cell.count += 1
            cell.placed += label

    def estimate(self, field: str, p_w: float) -> tuple[float, int]:
        b = pw_bin(p_w)
        base = self.total.placed / self.total.count if self.total.count else 0.25
        bin_cell = self.by_bin[b]
        p_bin = (bin_cell.placed + 200.0 * base) / (bin_cell.count + 200.0)
        fine = self.by_field_bin[(field, b)]
        p_fine = (fine.placed + 100.0 * p_bin) / (fine.count + 100.0)
        return min(0.99, max(0.001, p_fine)), fine.count


def market_win_probabilities(odds_list: list[float]) -> list[float] | None:
    if len(odds_list) < 5 or any(o < 1.0 for o in odds_list):
        return None
    implied_total = sum(1 / o for o in odds_list)
    if implied_total < 1.02 or implied_total > 1.55:
        return None
    return [(1 / o) / implied_total for o in odds_list]


def iter_training_races(path: Path):
    """Yield (race_date, [(p_w, field_bucket, place_label)]) in race_id order."""
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        current_race = None
        buffer: list[tuple[float, int]] = []

        def finish(race_id: str, rows: list[tuple[float, int]]):
            starters = len(rows)
            odds_list = [o for o, _ in rows]
            probs = market_win_probabilities(odds_list)
            if probs is None:
                return None
            field = field_bucket(starters)
            out = []
            for p_w, (_, rank) in zip(probs, rows):
                label = place_label(rank, starters)
                if label is not None:
                    out.append((p_w, field, label))
            return (race_id[:8], out) if out else None

        for row in reader:
            race_id = row["race_id"]
            if race_id != current_race:
                if current_race is not None:
                    result = finish(current_race, buffer)
                    if result:
                        yield result
                current_race = race_id
                buffer = []
            try:
                odds = float(row["win_odds"])
                rank = int(row["finish_rank"])
            except ValueError:
                continue
            buffer.append((odds, rank))
        if current_race is not None:
            result = finish(current_race, buffer)
            if result:
                yield result


def load_validation_races(path: Path) -> list[tuple[str, list[dict[str, str]]]]:
    by_race: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            by_race[row["race_id"]].append(row)
    return sorted(by_race.items())


def main() -> None:
    parser = argparse.ArgumentParser(description="No-leakage rolling backtest for place EV using real place odds and payouts.")
    parser.add_argument("--training", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--validation", default="data/model/place_validation_2025_2026.csv")
    parser.add_argument("--output-dir", default="outputs/backtests/place_ev")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    validation = load_validation_races(Path(args.validation))
    model = PlaceRateModel()
    training_iter = iter_training_races(Path(args.training))
    pending: tuple[str, list] | None = next(training_iter, None)

    detail_rows: list[dict[str, str]] = []
    for race_id, runners in validation:
        race_date = race_id[:8]
        while pending is not None and pending[0] < race_date:
            for p_w, field, label in pending[1]:
                model.add(field, p_w, label)
            pending = next(training_iter, None)

        starters = int(runners[0]["num_starters"] or 0)
        if starters < 5:
            continue
        field = field_bucket(starters)
        scored = [r for r in runners if r["win_odds"] and r["place_odds_min"]]
        odds_list = []
        valid = []
        for r in scored:
            try:
                odds_list.append(float(r["win_odds"]))
                valid.append(r)
            except ValueError:
                continue
        probs = market_win_probabilities(odds_list)
        if probs is None:
            continue
        for p_w, r in zip(probs, valid):
            p_place, fine_count = model.estimate(field, p_w)
            odds_min = float(r["place_odds_min"])
            ev_lower = p_place * odds_min
            realized = int(r["place_payout_yen"]) / 100.0
            detail_rows.append(
                {
                    "race_id": race_id,
                    "race_date": race_date,
                    "horse_no": r["horse_no"],
                    "horse_name": r["horse_name"],
                    "num_starters": str(starters),
                    "field_bucket": field,
                    "win_odds": r["win_odds"],
                    "market_win_probability": f"{p_w:.5f}",
                    "place_probability_est": f"{p_place:.5f}",
                    "model_cell_count": str(fine_count),
                    "place_odds_min": r["place_odds_min"],
                    "place_odds_max": r["place_odds_max"],
                    "ev_return_per_yen_lower": f"{ev_lower:.4f}",
                    "place_label": r["place_label"],
                    "realized_return_per_yen": f"{realized:.2f}",
                }
            )

    detail_path = output_dir / "place_ev_detail.csv"
    with detail_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)

    # calibration by predicted-probability bucket
    calib: dict[int, list] = defaultdict(list)
    for row in detail_rows:
        p = float(row["place_probability_est"])
        calib[min(9, int(p * 10))].append(row)
    calib_rows = []
    for bucket in sorted(calib):
        rows = calib[bucket]
        n = len(rows)
        pred = sum(float(r["place_probability_est"]) for r in rows) / n
        actual = sum(int(r["place_label"]) for r in rows) / n
        calib_rows.append(
            {
                "bucket": f"{bucket*10}-{bucket*10+10}%",
                "n": str(n),
                "mean_predicted": f"{pred:.4f}",
                "actual_place_rate": f"{actual:.4f}",
                "actual_minus_predicted": f"{actual-pred:+.4f}",
            }
        )
    calib_path = output_dir / "place_calibration.csv"
    with calib_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(calib_rows[0].keys()))
        writer.writeheader()
        writer.writerows(calib_rows)

    # threshold sweep, flat 1-unit stake, and one-bet-per-race variant
    sweep_rows = []
    for threshold in [0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.30]:
        bets = [r for r in detail_rows if float(r["ev_return_per_yen_lower"]) >= threshold]
        by_race: dict[str, dict] = {}
        for r in bets:
            cur = by_race.get(r["race_id"])
            if cur is None or float(r["ev_return_per_yen_lower"]) > float(cur["ev_return_per_yen_lower"]):
                by_race[r["race_id"]] = r
        for label, pool in (("all", bets), ("one_per_race", list(by_race.values()))):
            n = len(pool)
            if n == 0:
                sweep_rows.append({"ev_threshold": f"{threshold:.2f}", "variant": label, "bets": "0", "hits": "0", "hit_rate": "", "total_return": "", "roi": ""})
                continue
            hits = sum(int(r["place_label"]) for r in pool)
            ret = sum(float(r["realized_return_per_yen"]) for r in pool)
            sweep_rows.append(
                {
                    "ev_threshold": f"{threshold:.2f}",
                    "variant": label,
                    "bets": str(n),
                    "hits": str(hits),
                    "hit_rate": f"{hits/n:.4f}",
                    "total_return": f"{ret:.1f}",
                    "roi": f"{ret/n:.4f}",
                }
            )
    sweep_path = output_dir / "place_ev_threshold_sweep.csv"
    with sweep_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(sweep_rows[0].keys()))
        writer.writeheader()
        writer.writerows(sweep_rows)

    total = len(detail_rows)
    base_roi = sum(float(r["realized_return_per_yen"]) for r in detail_rows) / total if total else 0.0
    print(f"runners_scored={total} bet_all_roi={base_roi:.4f}")
    print(f"outputs: {detail_path}, {calib_path}, {sweep_path}")
    for row in sweep_rows:
        print(row)


if __name__ == "__main__":
    main()
