import argparse
import csv
import sys
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("horse_no", "").strip(), row.get("horse_name", "").strip()


def validate(expected_path: Path, observed_path: Path) -> list[str]:
    expected = read_csv(expected_path)
    observed = read_csv(observed_path)
    expected_set = {key(row) for row in expected if key(row)[0] and key(row)[1]}
    observed_set = {key(row) for row in observed if key(row)[0] and key(row)[1]}

    errors = []
    if not expected_set:
        errors.append(f"expected lineup is empty: {expected_path}")
    if not observed_set:
        errors.append(f"observed lineup is empty: {observed_path}")

    missing = sorted(expected_set - observed_set)
    extra = sorted(observed_set - expected_set)
    if missing:
        errors.append("missing runners: " + ", ".join(f"{no}:{name}" for no, name in missing))
    if extra:
        errors.append("extra runners: " + ", ".join(f"{no}:{name}" for no, name in extra))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate that two runner lineups match exactly by horse_no and horse_name.")
    parser.add_argument("--expected", required=True)
    parser.add_argument("--observed", required=True)
    args = parser.parse_args()

    errors = validate(Path(args.expected), Path(args.observed))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)
    print("lineup_ok=true")


if __name__ == "__main__":
    main()
