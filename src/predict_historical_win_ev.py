import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


TARGET_RACE_ID = "2004062709030411"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def odds_bucket(odds: float) -> str:
    if odds < 2:
        return "01_1-2"
    if odds < 3:
        return "02_2-3"
    if odds < 5:
        return "03_3-5"
    if odds < 10:
        return "04_5-10"
    if odds < 20:
        return "05_10-20"
    if odds < 50:
        return "06_20-50"
    if odds < 100:
        return "07_50-100"
    return "08_100+"


def rate(rows: list[dict[str, str]], default: float) -> tuple[float, int]:
    if not rows:
        return default, 0
    return sum(int(row["label_win"]) for row in rows) / len(rows), len(rows)


def add_market_probabilities(rows: list[dict[str, str]]) -> None:
    by_race: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_race[row["race_id"]].append(row)
    for race_rows in by_race.values():
        total = sum(1 / float(row["win_odds"]) for row in race_rows)
        if total <= 0:
            continue
        for row in race_rows:
            row["market_probability"] = (1 / float(row["win_odds"])) / total


def edge_factor(rows: list[dict[str, str]], prior_strength: float = 25.0) -> tuple[float, float, int]:
    if not rows:
        return 1.0, 0.0, 0
    wins = sum(int(row["label_win"]) for row in rows)
    expected = sum(float(row["market_probability"]) for row in rows)
    factor = (wins + prior_strength) / (expected + prior_strength)
    return factor, expected, len(rows)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind historical win EV estimate using only pre-race-visible fields.")
    parser.add_argument("--input", default="data/model/target_win_training_2000_2004.csv")
    parser.add_argument("--race-id", default=TARGET_RACE_ID)
    parser.add_argument("--race-name", default="宝塚記念")
    parser.add_argument("--output", default="outputs/historical_2004_takarazuka_win_ev.csv")
    parser.add_argument("--min-ev", type=float, default=0.05)
    args = parser.parse_args()

    rows = read_csv(Path(args.input))
    target = [row for row in rows if row["race_id"] == args.race_id]
    if not target:
        raise SystemExit(f"target race not found: {args.race_id}")

    race_date = target[0]["race_date"]
    train = [row for row in rows if row["race_date"] < race_date]
    add_market_probabilities(train)
    add_market_probabilities(target)

    global_rate, global_n = rate(train, 1 / 14)
    by_pop: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_bucket: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_pop_bucket: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_jockey: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_trainer: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in train:
        odds = float(row["win_odds"])
        bucket = odds_bucket(odds)
        by_pop[row["win_popularity"]].append(row)
        by_bucket[bucket].append(row)
        by_pop_bucket[(row["win_popularity"], bucket)].append(row)
        by_jockey[row["jockey_code"]].append(row)
        by_trainer[row["trainer_code"]].append(row)

    out = []
    for row in target:
        odds = float(row["win_odds"])
        bucket = odds_bucket(odds)
        combo_rows = by_pop_bucket[(row["win_popularity"], bucket)]
        jockey_rows = by_jockey[row["jockey_code"]]
        trainer_rows = by_trainer[row["trainer_code"]]
        combo_rate, combo_n = rate(combo_rows, global_rate)
        jockey_rate, jockey_n = rate(jockey_rows, global_rate)
        trainer_rate, trainer_n = rate(trainer_rows, global_rate)

        # Use historical edge versus market expectation, not raw win rates.
        market_p = float(row["market_probability"])
        combo_edge, combo_expected, _ = edge_factor(combo_rows, 35.0)
        jockey_edge, jockey_expected, _ = edge_factor(jockey_rows, 50.0)
        trainer_edge, trainer_expected, _ = edge_factor(trainer_rows, 50.0)
        blended_edge = 0.60 * combo_edge + 0.25 * jockey_edge + 0.15 * trainer_edge
        blended_edge = clamp(blended_edge, 0.70, 1.25)
        probability = market_p * blended_edge

        ev = probability * odds - 1
        required_probability = (1 + args.min_ev) / odds
        out.append(
            {
                "decision": "BUY" if ev >= args.min_ev else "PASS",
                "race_id": row["race_id"],
                "race_date": row["race_date"],
                "race_name": args.race_name,
                "horse_no": row["horse_no"],
                "selection": row["horse_name"],
                "jockey": row["jockey_name"],
                "trainer": row["trainer_name"],
                "win_odds": f"{odds:.1f}",
                "popularity": row["win_popularity"],
                "probability": f"{probability:.4f}",
                "break_even_probability": f"{market_p:.4f}",
                "required_probability": f"{required_probability:.4f}",
                "ev_per_yen": f"{ev:.4f}",
                "training_rows": str(len(train)),
                "global_win_rate": f"{global_rate:.4f}",
                "pop_bucket_rate": f"{combo_rate:.4f}",
                "pop_bucket_n": str(combo_n),
                "pop_bucket_edge": f"{combo_edge:.4f}",
                "pop_bucket_expected_wins": f"{combo_expected:.1f}",
                "jockey_rate": f"{jockey_rate:.4f}",
                "jockey_n": str(jockey_n),
                "jockey_edge": f"{jockey_edge:.4f}",
                "jockey_expected_wins": f"{jockey_expected:.1f}",
                "trainer_rate": f"{trainer_rate:.4f}",
                "trainer_n": str(trainer_n),
                "trainer_edge": f"{trainer_edge:.4f}",
                "trainer_expected_wins": f"{trainer_expected:.1f}",
                "blended_edge": f"{blended_edge:.4f}",
                "note": "blind_estimate_no_target_result_used",
            }
        )

    out.sort(key=lambda r: (r["decision"] != "BUY", -float(r["ev_per_yen"])))
    fields = list(out[0].keys())
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)

    buys = [r for r in out if r["decision"] == "BUY"]
    print(f"target_rows={len(target)} training_rows={len(train)} buy={len(buys)} output={args.output}")
    for row in out[:8]:
        print(row["decision"], row["horse_no"], row["selection"], row["win_odds"], row["probability"], row["ev_per_yen"])


if __name__ == "__main__":
    main()
