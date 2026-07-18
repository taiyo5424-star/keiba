import argparse
import csv
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def parse_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def latest_pre_final_win_odds(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    odds_by_runner: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        if row.get("bet_type", "").strip() != "win":
            continue
        if truthy(row.get("is_final", "")):
            continue
        odds = parse_float(row.get("odds", ""))
        if odds is None or odds <= 1:
            continue

        key = (row.get("race_id", "").strip(), row.get("horse_no", "").strip())
        current = odds_by_runner.get(key)
        if current is None or row.get("observed_at", "") > current.get("observed_at", ""):
            odds_by_runner[key] = row
    return odds_by_runner


def build_dataset(input_dir: Path) -> list[dict[str, str]]:
    races = {row["race_id"]: row for row in read_csv(input_dir / "races.csv")}
    starts = read_csv(input_dir / "starts.csv")
    results = {
        (row.get("race_id", "").strip(), row.get("horse_no", "").strip()): row
        for row in read_csv(input_dir / "results.csv")
    }
    odds_by_runner = latest_pre_final_win_odds(read_csv(input_dir / "odds_snapshots.csv"))

    rows: list[dict[str, str]] = []
    for start in starts:
        race_id = start.get("race_id", "").strip()
        horse_no = start.get("horse_no", "").strip()
        result = results.get((race_id, horse_no))
        odds = odds_by_runner.get((race_id, horse_no))
        race = races.get(race_id, {})
        if not result or not odds:
            continue

        finish_rank = parse_int(result.get("finish_position", ""))
        win_odds = parse_float(odds.get("odds", ""))
        if finish_rank is None or win_odds is None:
            continue

        rows.append(
            {
                "race_id": race_id,
                "race_date": race.get("race_date", ""),
                "venue": race.get("venue", ""),
                "race_no": race.get("race_no", ""),
                "surface": race.get("surface", ""),
                "distance": race.get("distance", ""),
                "going": race.get("going", ""),
                "field_size": race.get("field_size", ""),
                "horse_no": horse_no,
                "horse_id": start.get("horse_id", ""),
                "horse_name": start.get("horse_name", ""),
                "jockey_name": start.get("jockey_name", ""),
                "trainer_name": start.get("trainer_name", ""),
                "post_position": start.get("post_position", ""),
                "carried_weight": start.get("carried_weight", ""),
                "horse_weight": start.get("horse_weight", ""),
                "weight_diff": start.get("weight_diff", ""),
                "finish_rank": str(finish_rank),
                "label_win": "1" if finish_rank == 1 else "0",
                "win_odds": f"{win_odds:.1f}",
                "win_popularity": odds.get("popularity", ""),
                "odds_observed_at": odds.get("observed_at", ""),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "race_id",
        "race_date",
        "venue",
        "race_no",
        "surface",
        "distance",
        "going",
        "field_size",
        "horse_no",
        "horse_id",
        "horse_name",
        "jockey_name",
        "trainer_name",
        "post_position",
        "carried_weight",
        "horse_weight",
        "weight_diff",
        "finish_rank",
        "label_win",
        "win_odds",
        "win_popularity",
        "odds_observed_at",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a minimal NAR win training dataset from normalized CSV exports.")
    parser.add_argument("--input-dir", default="data/nar_exports")
    parser.add_argument("--output", default="data/model/nar_win_training_minimal.csv")
    args = parser.parse_args()

    rows = build_dataset(Path(args.input_dir))
    write_csv(Path(args.output), rows)
    races = {row["race_id"] for row in rows}
    winners = sum(1 for row in rows if row["label_win"] == "1")
    print(f"rows={len(rows)} races={len(races)} winners={winners} output={args.output}")


if __name__ == "__main__":
    main()
