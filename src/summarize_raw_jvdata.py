import argparse
import csv
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize raw JV-Link exported records.")
    parser.add_argument("--input", default="data/jra_van_exports/raw_race_records.csv")
    args = parser.parse_args()

    path = Path(args.input)
    counts = Counter()
    files = Counter()
    lengths = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = row["raw"]
            counts[row["record_type"]] += 1
            files[row["filename"]] += 1
            lengths[(row["record_type"], len(raw))] += 1

    print("record_types")
    for key, value in counts.most_common():
        print(f"{key},{value}")

    print("files")
    for key, value in files.most_common():
        print(f"{key},{value}")

    print("lengths")
    for (record_type, length), value in lengths.most_common():
        print(f"{record_type},{length},{value}")


if __name__ == "__main__":
    main()
