import argparse
import csv
from collections import defaultdict
from pathlib import Path

from rolling_backtest_race_features import add_market_probabilities, distance_bucket


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def group_by_race(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_race: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_race[row["race_id"]].append(row)
    return by_race


class Agg:
    def __init__(self) -> None:
        self.count = 0
        self.wins = 0
        self.expected = 0.0
        self.flat_return = 0.0

    def update(self, row: dict[str, str]) -> None:
        odds = float(row["win_odds"])
        win = int(row["label_win"])
        self.count += 1
        self.wins += win
        self.expected += float(row["market_probability"])
        self.flat_return += odds if win else 0.0

    def to_row(self, key: tuple[str, ...], key_fields: list[str]) -> dict[str, str]:
        edge = self.wins / self.expected if self.expected else 0.0
        roi = self.flat_return / self.count - 1 if self.count else 0.0
        row = dict(zip(key_fields, key))
        row.update(
            {
                "count": str(self.count),
                "wins": str(self.wins),
                "expected_wins": f"{self.expected:.2f}",
                "market_edge": f"{edge:.4f}",
                "flat_win_roi": f"{roi:.4f}",
            }
        )
        return row


def write_edges(path: Path, aggs: dict[tuple[str, ...], Agg], key_fields: list[str], min_count: int) -> None:
    rows = [agg.to_row(key, key_fields) for key, agg in aggs.items() if agg.count >= min_count]
    rows.sort(key=lambda row: (float(row["market_edge"]), float(row["flat_win_roi"]), int(row["count"])), reverse=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = key_fields + ["count", "wins", "expected_wins", "market_edge", "flat_win_roi"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"rows={len(rows)} output={path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Descriptive pedigree market-edge tables.")
    parser.add_argument("--training", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--races", default="data/model/target_races_2004_2026.csv")
    parser.add_argument("--pedigree", default="data/model/target_pedigree_1986_2026.csv")
    parser.add_argument("--min-count", type=int, default=300)
    parser.add_argument("--out-dir", default="outputs/pedigree")
    args = parser.parse_args()

    race_meta = {row["race_id"]: row for row in read_csv(Path(args.races))}
    pedigree = {row["horse_id"]: row for row in read_csv(Path(args.pedigree))}

    sire_surface_distance: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    damsire_surface_distance: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    sire_surface: dict[tuple[str, str, str], Agg] = defaultdict(Agg)
    damsire_surface: dict[tuple[str, str, str], Agg] = defaultdict(Agg)

    skipped = defaultdict(int)
    for race_id, race_rows in group_by_race(read_csv(Path(args.training))).items():
        meta = race_meta.get(race_id)
        if not meta:
            skipped["missing_race_meta"] += 1
            continue
        ok, reason = add_market_probabilities(race_rows)
        if not ok:
            skipped[reason] += 1
            continue
        surface = meta.get("surface_group", "")
        dist_bucket = distance_bucket(meta.get("distance", ""))
        for row in race_rows:
            ped = pedigree.get(row["horse_id"], {})
            sire_id = ped.get("sire_id", "")
            sire_name = ped.get("sire_name", "")
            damsire_id = ped.get("dam_sire_id", "")
            damsire_name = ped.get("dam_sire_name", "")
            if sire_id:
                sire_surface_distance[(sire_id, sire_name, surface, dist_bucket)].update(row)
                sire_surface[(sire_id, sire_name, surface)].update(row)
            if damsire_id:
                damsire_surface_distance[(damsire_id, damsire_name, surface, dist_bucket)].update(row)
                damsire_surface[(damsire_id, damsire_name, surface)].update(row)

    out_dir = Path(args.out_dir)
    write_edges(out_dir / "sire_surface_distance_edges.csv", sire_surface_distance, ["sire_id", "sire_name", "surface_group", "distance_bucket"], args.min_count)
    write_edges(out_dir / "damsire_surface_distance_edges.csv", damsire_surface_distance, ["dam_sire_id", "dam_sire_name", "surface_group", "distance_bucket"], args.min_count)
    write_edges(out_dir / "sire_surface_edges.csv", sire_surface, ["sire_id", "sire_name", "surface_group"], args.min_count)
    write_edges(out_dir / "damsire_surface_edges.csv", damsire_surface, ["dam_sire_id", "dam_sire_name", "surface_group"], args.min_count)
    print(f"skipped={dict(sorted(skipped.items()))}")


if __name__ == "__main__":
    main()
