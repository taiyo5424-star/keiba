"""楽天競馬の払戻一覧ページのパーサとフェッチャ。

このソースの価値: 全レースの払戻に加えて**式別ごとの総票数**が載っており、
NARのプールサイズ(流動性)を実測できる(1票=100円。
docs/research/nar-market.md の券種別構成比はこのデータから算出した)。

URL形式(RACEID=18桁):
  https://keiba.rakuten.co.jp/race_dividend/list/RACEID/{YYYYMMDD}{場2}{節2}{回2}{日2}{R2}
  ゼロ埋め形式 {YYYYMMDD}{場2}00000000 でも当日一覧に解決する(実測確認済み)。

**robots.txt が Crawl-Delay: 60 を要求** — フェッチャは60秒間隔を強制する。
1リクエストで1場1日分(全レース+票数)が取れるため実用上は十分。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from keiba.ingest.fetch import polite_get
from keiba.ingest.nar_keibago import BET_TYPE_MAP

CRAWL_DELAY = 60.0  # robots.txt の Crawl-Delay(厳守)

# 楽天の場コード(keiba.go.jp NAR系と共通)
BABA_CODES = {
    "帯広ば": 3, "盛岡": 10, "水沢": 11, "浦和": 18, "船橋": 19, "大井": 20,
    "川崎": 21, "金沢": 22, "笠松": 23, "名古屋": 24, "園田": 27, "姫路": 28,
    "高知": 30, "佐賀": 31, "門別": 36,
}


def zeros_raceid(yyyymmdd: str, baba_code: int) -> str:
    """日付+場コードだけで当日一覧に解決するゼロ埋めRACEID。"""
    return f"{yyyymmdd}{baba_code:02d}00000000"


def dividend_list_url(yyyymmdd: str, baba_code: int) -> str:
    return (
        "https://keiba.rakuten.co.jp/race_dividend/list/RACEID/"
        + zeros_raceid(yyyymmdd, baba_code)
    )


def fetch_dividend_list(yyyymmdd: str, baba_code: int):
    html = polite_get(dividend_list_url(yyyymmdd, baba_code), min_interval=CRAWL_DELAY)
    return parse_dividend_list(html.decode("utf-8", errors="replace"))


@dataclass
class RaceDividends:
    race_no: int
    race_name: str
    refunds: list = field(default_factory=list)      # list[dict]
    votes: dict = field(default_factory=dict)        # bet_type -> 総票数(1票=100円)
    returned_votes: dict = field(default_factory=dict)


def _to_int(text: str) -> int | None:
    m = re.search(r"\d[\d,]*", text)
    return int(m.group().replace(",", "")) if m else None


def _parse_vote_table(td) -> dict:
    votes = {}
    inner = td.find("table")
    if inner is None:
        return votes
    for th in inner.find_all("th"):
        name = th.get_text(strip=True)
        val_td = th.find_next_sibling("td")
        if not name or val_td is None:
            continue
        key = BET_TYPE_MAP.get(name, name)
        votes[key] = _to_int(val_td.get_text()) or 0
    return votes


def parse_dividend_list(html: str) -> list[RaceDividends]:
    """1場1日分の払戻一覧ページ → レースごとの払戻+票数。"""
    soup = BeautifulSoup(html, "html.parser")
    races: list[RaceDividends] = []

    for headline in soup.find_all("h3", class_="headline"):
        text = headline.get_text(" ", strip=True)
        m = re.search(r"(\d+)\s*R", text)
        if not m:
            continue
        race_no = int(m.group(1))
        race_name = re.sub(r"^[■\s]*\d+\s*R", "", text).replace("\xa0", " ").strip()
        table = headline.find_next_sibling("table", class_="contentsTable")
        if table is None:
            continue
        race = RaceDividends(race_no=race_no, race_name=race_name)

        tbody = table.find("tbody", class_="repay") or table
        for tr in tbody.find_all("tr", recursive=False):
            children = [c for c in tr.find_all(["th", "td"], recursive=False)]
            i = 0
            while i < len(children):
                el = children[i]
                if el.name != "th":
                    i += 1
                    continue
                label = el.get_text(strip=True)
                if label in ("備考", ""):
                    break
                if label in ("総票数", "返還票数"):
                    vote_td = children[i + 1] if i + 1 < len(children) else None
                    if vote_td is not None:
                        parsed = _parse_vote_table(vote_td)
                        if label == "総票数":
                            race.votes.update(parsed)
                        else:
                            race.returned_votes.update(parsed)
                    i += 2
                    continue
                # 通常の払戻: th + number/money/rank の3セル
                if i + 4 > len(children):
                    break  # セルが揃っていない行(構造変化への防御)
                num_td, money_td, rank_td = children[i + 1: i + 4]
                if "none" in (num_td.get("class") or []):
                    i += 4
                    continue
                combs = [t.strip() for t in num_td.get_text("\n").split("\n") if t.strip()]
                moneys = [t for t in money_td.get_text("\n").split("\n") if t.strip()]
                ranks = [t for t in rank_td.get_text("\n").split("\n") if t.strip()]
                for j, comb in enumerate(combs):
                    amount = _to_int(moneys[j]) if j < len(moneys) else None
                    if amount is None:
                        continue
                    race.refunds.append(
                        {
                            "bet_type": BET_TYPE_MAP.get(label, label),
                            "bet_type_ja": label,
                            "combination": comb,
                            "amount": amount,
                            "popularity": _to_int(ranks[j]) if j < len(ranks) else None,
                        }
                    )
                i += 4
        races.append(race)
    return races
