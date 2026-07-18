import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from expected_value import Bet, evaluate_bet


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def latest_odds(
    odds_rows: list[dict[str, str]],
    bet_type: str,
    as_of: str | None,
) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in odds_rows:
        if row.get("bet_type", "").strip() != bet_type:
            continue
        if truthy(row.get("is_final", "")):
            continue
        observed_at = row.get("observed_at", "").strip()
        if as_of and observed_at and observed_at > as_of:
            continue
        key = (row.get("race_id", "").strip(), row.get("horse_no", "").strip())
        if not key[0] or not key[1]:
            continue
        current = out.get(key)
        if current is None or observed_at > current.get("observed_at", ""):
            out[key] = row
    return out


def group_by(rows: list[dict[str, str]], field: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(field, "")].append(row)
    return grouped


def load_model_probabilities(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows = read_csv(path)
    out = {}
    for row in rows:
        race_id = row.get("race_id", "").strip()
        horse_no = row.get("horse_no", "").strip()
        probability = row.get("probability", "").strip()
        if not race_id or not horse_no or not probability:
            continue
        out[(race_id, horse_no)] = row
    return out


def enforce_caps(rows: list[dict[str, str]], config: dict) -> list[dict[str, str]]:
    risk = config.get("risk", {})
    bankroll = float(risk.get("bankroll", 10000))
    race_cap = int(bankroll * float(risk.get("max_fraction_per_race", 0.05)) // 100 * 100)
    day_cap = int(bankroll * float(risk.get("max_fraction_per_day", 0.15)) // 100 * 100)

    spent_by_race: dict[str, int] = defaultdict(int)
    spent_day = 0
    capped = []
    for row in rows:
        stake = int(row["recommended_stake"])
        if row["decision"] != "BUY":
            capped.append(row)
            continue

        race_id = row["race_id"]
        allowed = max(0, min(stake, race_cap - spent_by_race[race_id], day_cap - spent_day))
        if allowed <= 0:
            row = {**row, "decision": "PASS", "reason": f'{row.get("reason", "")}; cap_reached'}
        elif allowed < stake:
            row = {**row, "recommended_stake": str(allowed), "expected_profit": f'{allowed * float(row["ev_per_yen"]):.0f}'}
            spent_by_race[race_id] += allowed
            spent_day += allowed
        else:
            spent_by_race[race_id] += stake
            spent_day += stake
        capped.append(row)
    return capped


def write_output(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "decision",
        "race_date",
        "venue",
        "race_no",
        "post_time",
        "race_id",
        "race_name",
        "horse_no",
        "selection",
        "bet_type",
        "odds",
        "probability",
        "break_even_probability",
        "probability_edge",
        "ev_per_yen",
        "min_ev",
        "kelly_fraction",
        "recommended_stake",
        "expected_profit",
        "confidence",
        "reason",
        "observed_at",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def generate(
    races_path: Path,
    starts_path: Path,
    odds_path: Path,
    probabilities_path: Path,
    config_path: Path,
    race_date: str | None,
    as_of: str | None,
) -> list[dict[str, str]]:
    config = load_json(config_path)
    risk = config.get("risk", {})
    probabilities = load_model_probabilities(probabilities_path)
    odds_lookup = latest_odds(read_csv(odds_path), "win", as_of)
    races = {row["race_id"]: row for row in read_csv(races_path)}
    starts = read_csv(starts_path)
    if race_date:
        starts = [row for row in starts if races.get(row.get("race_id", ""), {}).get("race_date") == race_date]

    rows = []
    for start in starts:
        key = (start.get("race_id", "").strip(), start.get("horse_no", "").strip())
        prediction = probabilities.get(key)
        odds = odds_lookup.get(key)
        race = races.get(key[0], {})
        if not prediction or not odds:
            continue

        bet = Bet(
            race_id=key[0],
            race_name=race.get("race_name", ""),
            bet_type="win",
            selection=start.get("horse_name", ""),
            odds=float(odds["odds"]),
            probability=float(prediction["probability"]),
            stake=None,
            min_ev=float(risk.get("min_ev_per_yen", 0.05)),
            confidence=prediction.get("confidence", ""),
            reason=prediction.get("reason", ""),
        )
        row = evaluate_bet(
            bet=bet,
            bankroll=float(risk.get("bankroll", 10000)),
            kelly_scale=float(risk.get("kelly_scale", 0.25)),
            max_fraction=float(risk.get("max_fraction_per_bet", 0.03)),
        )
        row["horse_no"] = key[1]
        row["race_date"] = race.get("race_date", "")
        row["venue"] = race.get("venue", "")
        row["race_no"] = race.get("race_no", "")
        row["post_time"] = race.get("post_time", "")
        row["observed_at"] = odds.get("observed_at", "")
        rows.append(row)

    rows.sort(key=lambda row: (row["decision"] != "BUY", -float(row["ev_per_yen"])))
    return enforce_caps(rows, config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate NAR live win EV candidates from normalized CSV files.")
    parser.add_argument("--races", default="data/nar_exports/races.csv")
    parser.add_argument("--starts", default="data/nar_exports/starts.csv")
    parser.add_argument("--odds", default="data/nar_exports/odds_snapshots.csv")
    parser.add_argument("--probabilities", default="data/nar_predictions.csv")
    parser.add_argument("--config", default="config/nar_operation.json")
    parser.add_argument("--race-date", default=None)
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--output", default="outputs/nar_live_ev.csv")
    args = parser.parse_args()

    rows = generate(
        races_path=Path(args.races),
        starts_path=Path(args.starts),
        odds_path=Path(args.odds),
        probabilities_path=Path(args.probabilities),
        config_path=Path(args.config),
        race_date=args.race_date,
        as_of=args.as_of,
    )
    write_output(Path(args.output), rows)
    buys = [row for row in rows if row["decision"] == "BUY"]
    stake = sum(int(row["recommended_stake"]) for row in buys)
    expected_profit = sum(float(row["expected_profit"]) for row in buys)
    print(f"rows={len(rows)} buys={len(buys)} stake={stake} expected_profit={expected_profit:.0f} output={args.output}")


if __name__ == "__main__":
    main()
