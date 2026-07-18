import argparse
import csv
from pathlib import Path

from build_win_training_dataset import normalize_se


def iter_target_records(path: Path):
    data = path.read_bytes()
    for line in data.splitlines():
        if not line:
            continue
        raw = line.decode("cp932", errors="ignore").rstrip("\r\n\0")
        if raw.startswith("SE"):
            yield raw


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract win training rows from TARGET frontier JV SE_DATA files.")
    parser.add_argument("--target-se-dir", default=r"C:\TFJV\SE_DATA")
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2004)
    parser.add_argument("--output", default="data/model/target_win_training_2000_2004.csv")
    args = parser.parse_args()

    rows = []
    root = Path(args.target_se_dir)
    for year in range(args.start_year, args.end_year + 1):
        year_dir = root / str(year)
        if not year_dir.exists():
            continue
        for path in sorted(year_dir.glob("SU*.DAT")):
            for raw in iter_target_records(path):
                row = normalize_se(raw)
                if row:
                    row["source_file"] = path.name
                    rows.append(row)

    fields = [
        "race_id",
        "race_date",
        "course_code",
        "meeting",
        "day",
        "race_no",
        "horse_no",
        "horse_id",
        "horse_name",
        "jockey_code",
        "jockey_name",
        "trainer_code",
        "trainer_name",
        "horse_weight",
        "weight_diff_sign",
        "weight_diff",
        "arrival_order",
        "finish_rank",
        "label_win",
        "race_time",
        "margin_code",
        "runner_last3f_time",
        "result_detail_raw",
        "win_odds",
        "win_popularity",
        "source_file",
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    races = {row["race_id"] for row in rows}
    print(f"rows={len(rows)} races={len(races)} output={args.output}")


if __name__ == "__main__":
    main()
