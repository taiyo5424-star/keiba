import argparse
import csv
from pathlib import Path


COURSE_NAMES = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}


def b(raw: str, start: int, end: int) -> str:
    return raw.encode("cp932", errors="ignore")[start:end].decode("cp932", errors="ignore")


def clean(value: str) -> str:
    return value.replace("\u3000", " ").strip()


def read_ys(path: Path) -> list[dict[str, str]]:
    rows = []
    for line in path.read_bytes().splitlines():
        raw = line.decode("cp932", errors="ignore").rstrip("\r\n\0")
        if not raw.startswith("YS"):
            continue
        race_date = raw[11:19]
        course_code = raw[19:21]
        meeting = raw[21:23]
        day = raw[23:25]
        main_race_name = clean(raw[31:61])
        if main_race_name in {"@", "000", ""}:
            main_race_name = ""
        rows.append(
            {
                "race_date": race_date,
                "course_code": course_code,
                "course_name": COURSE_NAMES.get(course_code, course_code),
                "meeting": meeting,
                "day": day,
                "main_race_name": main_race_name,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a weekend JRA race manifest from TARGET/JRA-VAN schedule data.")
    parser.add_argument("--schedule", default=r"C:\TFJV\SE_DATA\2026\SCHD2026.DAT")
    parser.add_argument("--dates", nargs="+", default=["20260620", "20260621"])
    parser.add_argument("--output", default="outputs/weekend_20260620_21_manifest.csv")
    args = parser.parse_args()

    schedule_rows = [row for row in read_ys(Path(args.schedule)) if row["race_date"] in set(args.dates)]
    out = []
    for row in schedule_rows:
        for race_no in range(1, 13):
            race_no_s = f"{race_no:02d}"
            out.append(
                {
                    **row,
                    "race_no": race_no_s,
                    "race_id": f"{row['race_date']}{row['course_code']}{row['meeting']}{row['day']}{race_no_s}",
                    "status": "pending_entries_and_odds",
                }
            )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    fields = ["race_id", "race_date", "course_code", "course_name", "meeting", "day", "race_no", "main_race_name", "status"]
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)

    print(f"rows={len(out)} output={args.output}")
    for row in out[:6]:
        print(row["race_id"], row["course_name"], row["race_no"], row["main_race_name"])


if __name__ == "__main__":
    main()
