import argparse
import csv
import re
import time
import urllib.request
from html import unescape
from pathlib import Path


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def result_url(race: dict[str, str], url_map: dict[str, str] | None = None) -> str:
    if url_map and race["race_id"] in url_map:
        return url_map[race["race_id"]]
    race_date = race["race_date"]
    year = race_date[:4]
    course_code = str(int(race["course_code"]))
    cname = (
        f"pw01sde010{course_code}{year}{race['meeting']}"
        f"{race['day']}{race['race_no']}{race_date}%2FCD"
    )
    return f"https://www.jra.go.jp/JRADB/accessS.html?CNAME={cname}"


def fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    data = urllib.request.urlopen(request, timeout=30).read()
    return data.decode("cp932", errors="ignore")


def race_id_from_cname(cname: str) -> str:
    body = cname.split("/", 1)[0]
    if not body.startswith("pw01sde01"):
        return ""
    payload = body[len("pw01sde01") :]
    race_date = payload[-8:]
    race_no = payload[-10:-8]
    day = payload[-12:-10]
    meeting = payload[-14:-12]
    course = payload[:-18]
    if not (race_date.isdigit() and race_no.isdigit() and day.isdigit() and meeting.isdigit() and course.isdigit()):
        return ""
    return f"{race_date}{course.zfill(2)}{meeting}{day}{race_no}"


def extract_result_cnames(html: str) -> list[str]:
    cnames = re.findall(r"CNAME=([^'\"&<> ]+)", html)
    return [unescape(cname) for cname in cnames if cname.startswith("pw01sde01")]


def build_result_url_map(seed_urls: list[str], race_date: str, max_pages: int = 80) -> dict[str, str]:
    url_map: dict[str, str] = {}
    queue = list(seed_urls)
    seen: set[str] = set()
    while queue and len(seen) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            html = fetch_html(url)
        except Exception:
            continue
        for cname in extract_result_cnames(html):
            race_id = race_id_from_cname(cname)
            if not race_id or not race_id.startswith(race_date):
                continue
            mapped_url = "https://www.jra.go.jp/JRADB/accessS.html?CNAME=" + cname.replace("/", "%2F")
            if race_id not in url_map:
                url_map[race_id] = mapped_url
                queue.append(mapped_url)
    return url_map


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value or "", flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def table_htmls(html: str) -> list[str]:
    return re.findall(r"<table[\s\S]*?</table>", html, flags=re.I)


def row_htmls(table: str) -> list[str]:
    return re.findall(r"<tr[\s\S]*?</tr>", table, flags=re.I)


def cell_htmls(row: str) -> list[tuple[str, str, str]]:
    pattern = re.compile(r"<(td|th)\b([^>]*)>([\s\S]*?)</\1>", flags=re.I)
    cells: list[tuple[str, str, str]] = []
    for tag, attrs, body in pattern.findall(row):
        class_match = re.search(r'class="([^"]+)"', attrs, flags=re.I)
        class_name = class_match.group(1).split()[0] if class_match else ""
        cells.append((tag.lower(), class_name, body))
    return cells


def text_for_class(html: str, class_name: str) -> str:
    pattern = rf'<li class="{re.escape(class_name)}"[\s\S]*?<span class="txt">([\s\S]*?)</span>'
    match = re.search(pattern, html, flags=re.I)
    return strip_tags(match.group(1)) if match else ""


def parse_key_value_table(table: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for row in row_htmls(table):
        cells = cell_htmls(row)
        if len(cells) >= 2:
            rows.append((strip_tags(cells[0][2]), strip_tags(cells[1][2])))
    return rows


def parse_corner_ranks(corner_cell_html: str) -> list[str]:
    ranks = [
        strip_tags(item)
        for item in re.findall(r"<li\b[^>]*>([\s\S]*?)</li>", corner_cell_html or "", flags=re.I)
    ]
    ranks = [rank for rank in ranks if rank]
    return ranks[:4] + [""] * max(0, 4 - len(ranks))


def parse_result_table(table: str, race: dict[str, str], url: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in row_htmls(table):
        cells = {class_name: body for tag, class_name, body in cell_htmls(row) if tag == "td" and class_name}
        finish_position = strip_tags(cells.get("place", ""))
        horse_no = strip_tags(cells.get("num", "")).zfill(2)
        horse_name = strip_tags(cells.get("horse", ""))
        if not finish_position or not horse_no.strip("0") or not horse_name:
            continue

        corners = parse_corner_ranks(cells.get("corner", ""))
        rows.append(
            {
                "race_id": race["race_id"],
                "race_date": race["race_date"],
                "course_code": race["course_code"],
                "meeting": race["meeting"],
                "day": race["day"],
                "race_no": race["race_no"],
                "horse_no": horse_no,
                "horse_id": "",
                "horse_name": horse_name,
                "finish_position": finish_position,
                "label_win": "1" if finish_position == "1" else "0",
                "sex_age": strip_tags(cells.get("age", "")),
                "carried_weight": strip_tags(cells.get("weight", "")),
                "jockey_name": strip_tags(cells.get("jockey", "")),
                "race_time": strip_tags(cells.get("time", "")),
                "margin": strip_tags(cells.get("margin", "")),
                "corner1_rank": corners[0],
                "corner2_rank": corners[1],
                "corner3_rank": corners[2],
                "corner4_rank": corners[3],
                "corner_passage": strip_tags(cells.get("corner", "")),
                "runner_last3f_time": strip_tags(cells.get("f_time", "")),
                "horse_weight_text": strip_tags(cells.get("h_weight", "")),
                "trainer_name": strip_tags(cells.get("trainer", "")),
                "win_popularity": strip_tags(cells.get("pop", "")),
                "confirmed_at": "",
                "source_url": url,
            }
        )
    return rows


def parse_race(
    race: dict[str, str], delay_sec: float, url_map: dict[str, str] | None = None
) -> tuple[list[dict[str, str]], dict[str, str]]:
    url = result_url(race, url_map)
    html = fetch_html(url)
    if delay_sec > 0:
        time.sleep(delay_sec)

    tables = table_htmls(html)
    race_result = {
        **race,
        "source_url": url,
        "weather": text_for_class(html, "weather"),
        "going": text_for_class(html, "turf") or text_for_class(html, "dirt"),
        "hurdle_going": text_for_class(html, "obstacle"),
        "lap_times": "",
        "last4f": "",
        "last3f": "",
        "corner1": "",
        "corner2": "",
        "corner3": "",
        "corner4": "",
        "status": "ok",
    }
    if len(tables) < 1:
        race_result["status"] = "missing_tables"
        return [], race_result

    if len(tables) >= 2:
        for index, (_, value) in enumerate(parse_key_value_table(tables[1])):
            if index == 0:
                race_result["lap_times"] = value
            elif index == 1:
                race_result["last4f"] = value
                match = re.search(r"3F\s*([0-9.]+)", value)
                if match:
                    race_result["last3f"] = match.group(1)

    if len(tables) >= 3:
        for key, value in parse_key_value_table(tables[2]):
            if key.startswith("1"):
                race_result["corner1"] = value
            elif key.startswith("2"):
                race_result["corner2"] = value
            elif key.startswith("3"):
                race_result["corner3"] = value
            elif key.startswith("4"):
                race_result["corner4"] = value

    result_rows = parse_result_table(tables[0], race, url)
    if not result_rows:
        race_result["status"] = "missing_result_rows"
    return result_rows, race_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape JRA official web race results for a race date.")
    parser.add_argument("--race-date", required=True)
    parser.add_argument("--races", required=True)
    parser.add_argument("--out-dir", default="data/jra_web_results")
    parser.add_argument("--delay-sec", type=float, default=0.2)
    parser.add_argument("--seed-url", action="append", default=[])
    args = parser.parse_args()

    races = [row for row in read_csv(Path(args.races)) if row.get("race_date") == args.race_date]
    races.sort(key=lambda row: (row.get("post_time", ""), row["race_id"]))
    url_map = build_result_url_map(args.seed_url, args.race_date) if args.seed_url else {}
    if url_map:
        print(f"url_map={len(url_map)}")
    all_results: list[dict[str, str]] = []
    race_results: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for race in races:
        try:
            rows, race_row = parse_race(race, args.delay_sec, url_map)
            all_results.extend(rows)
            race_results.append(race_row)
            print(f"{race['race_id']} rows={len(rows)} status={race_row['status']}")
        except Exception as exc:
            errors.append({**race, "error": repr(exc), "source_url": result_url(race, url_map)})
            print(f"{race['race_id']} error={exc!r}")

    out_dir = Path(args.out_dir) / args.race_date
    result_fields = [
        "race_id",
        "race_date",
        "course_code",
        "meeting",
        "day",
        "race_no",
        "horse_no",
        "horse_id",
        "horse_name",
        "finish_position",
        "label_win",
        "sex_age",
        "carried_weight",
        "jockey_name",
        "race_time",
        "margin",
        "corner1_rank",
        "corner2_rank",
        "corner3_rank",
        "corner4_rank",
        "corner_passage",
        "runner_last3f_time",
        "horse_weight_text",
        "trainer_name",
        "win_popularity",
        "confirmed_at",
        "source_url",
    ]
    race_fields = [
        "race_id",
        "race_date",
        "course_code",
        "meeting",
        "day",
        "race_no",
        "race_name",
        "surface_group",
        "distance",
        "post_time",
        "weather",
        "going",
        "hurdle_going",
        "lap_times",
        "last4f",
        "last3f",
        "corner1",
        "corner2",
        "corner3",
        "corner4",
        "status",
        "source_url",
    ]
    write_csv(out_dir / "results.csv", all_results, result_fields)
    write_csv(out_dir / "race_results.csv", race_results, race_fields)
    write_csv(out_dir / "errors.csv", errors, list(errors[0].keys()) if errors else ["race_id", "error", "source_url"])
    print(f"races={len(races)} result_rows={len(all_results)} errors={len(errors)} output_dir={out_dir}")


if __name__ == "__main__":
    main()
