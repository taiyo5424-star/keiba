import argparse
import csv
from pathlib import Path


PEDIGREE_SLOTS = [
    "sire",
    "dam",
    "sire_sire",
    "sire_dam",
    "dam_sire",
    "dam_dam",
    "sire_sire_sire",
    "sire_sire_dam",
    "sire_dam_sire",
    "sire_dam_dam",
    "dam_sire_sire",
    "dam_sire_dam",
    "dam_dam_sire",
    "dam_dam_dam",
]


def b(raw: str, start: int, end: int) -> str:
    return raw.encode("cp932", errors="ignore")[start:end].decode("cp932", errors="ignore")


def clean(value: str) -> str:
    return value.replace("\u3000", " ").strip()


def chunk_records(data: bytes, record_len: int = 1609):
    if b"\n" in data:
        for line in data.splitlines():
            if line:
                yield line.decode("cp932", errors="ignore")
        return
    for i in range(0, len(data), record_len):
        chunk = data[i : i + record_len]
        if chunk:
            yield chunk.decode("cp932", errors="ignore").rstrip("\r\n\0")


def normalize_um(raw: str) -> dict[str, str] | None:
    if not raw.startswith("UM"):
        return None
    row = {
        "record_type": b(raw, 0, 2),
        "data_kubun": b(raw, 2, 3),
        "created_date": b(raw, 3, 11),
        "horse_id": b(raw, 11, 21),
        "horse_deleted": b(raw, 21, 22),
        "horse_registered_date": b(raw, 22, 30),
        "horse_deleted_date": b(raw, 30, 38),
        "birth_date": b(raw, 38, 46),
        "horse_name": clean(b(raw, 46, 82)),
        "horse_name_kana": clean(b(raw, 82, 118)),
        "horse_name_eng": clean(b(raw, 118, 178)),
        "horse_symbol_code": b(raw, 198, 200).strip(),
        "sex_code": b(raw, 200, 201).strip(),
        "breed_code": b(raw, 201, 202).strip(),
        "coat_color_code": b(raw, 202, 204).strip(),
        "trainer_code": b(raw, 849, 854).strip(),
        "trainer_name": clean(b(raw, 854, 862)),
        "breeder_code": b(raw, 882, 890).strip(),
        "breeder_name": clean(b(raw, 890, 962)),
        "birthplace": clean(b(raw, 962, 982)),
    }
    pedigree_start = 204
    pedigree_width = 46
    for idx, slot in enumerate(PEDIGREE_SLOTS):
        offset = pedigree_start + idx * pedigree_width
        row[f"{slot}_id"] = b(raw, offset, offset + 10).strip()
        row[f"{slot}_name"] = clean(b(raw, offset + 10, offset + 46))
    return row


def iter_um_files(root: Path, start_year: int, end_year: int):
    for year in range(start_year, end_year + 1):
        year_dir = root / str(year)
        if not year_dir.exists():
            continue
        yield from sorted(year_dir.glob("UM*.DAT"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract pedigree fields from TARGET frontier JV UM files.")
    parser.add_argument("--target-um-dir", default=r"C:\TFJV\UM_DATA")
    parser.add_argument("--start-year", type=int, default=1986)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--output", default="data/model/target_pedigree_1986_2026.csv")
    args = parser.parse_args()

    rows = []
    seen = set()
    for path in iter_um_files(Path(args.target_um_dir), args.start_year, args.end_year):
        for raw in chunk_records(path.read_bytes()):
            row = normalize_um(raw)
            if not row:
                continue
            horse_id = row["horse_id"]
            if horse_id in seen:
                continue
            seen.add(horse_id)
            row["source_file"] = path.name
            rows.append(row)

    fields = [
        "horse_id",
        "horse_name",
        "horse_name_kana",
        "horse_name_eng",
        "birth_date",
        "sex_code",
        "breed_code",
        "coat_color_code",
        "horse_symbol_code",
        "horse_registered_date",
        "horse_deleted",
        "horse_deleted_date",
        "trainer_code",
        "trainer_name",
        "breeder_code",
        "breeder_name",
        "birthplace",
    ]
    for slot in PEDIGREE_SLOTS:
        fields.extend([f"{slot}_id", f"{slot}_name"])
    fields.extend(["record_type", "data_kubun", "created_date", "source_file"])

    rows.sort(key=lambda row: row["horse_id"])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"rows={len(rows)} output={args.output}")


if __name__ == "__main__":
    main()
