"""地方競馬情報サイト(keiba.go.jp、NAR公式)のパーサとフェッチャ。

対象ページ(2026-08時点の実ページ構造に基づく。UTF-8・静的HTML):
- RaceMarkTable: 1レースの成績(着順・払戻・ラップ)
- RefundMoneyList: 1日1場の全レース払戻一括
- OddsTanFuku 等: 式別オッズ(単複はこのモジュールで取得URLのみ提供)

URL形式:
  https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable
      ?k_raceDate=YYYY%2FMM%2FDD&k_raceNo=N&k_babaCode=NN

babaCode(主要): 3=帯広ば 10=盛岡 11=水沢 18=浦和 19=船橋 20=大井 21=川崎
  22=金沢 23=笠松 24=名古屋 27=園田 28=姫路 30/31=高知/佐賀 36=門別
  (30・31は要実測確認。実測済み: 19,27,36,18,22,3,32)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote

from bs4 import BeautifulSoup

from keiba.ingest.fetch import polite_get

BASE = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo"

# サイト表記 → takeout.py のキー
BET_TYPE_MAP = {
    "単勝": "win",
    "複勝": "place",
    "枠連複": "bracket",
    "枠複": "bracket",
    "枠連単": "bracket_exacta",
    "枠単": "bracket_exacta",
    "馬連複": "quinella",
    "馬複": "quinella",
    "馬連単": "exacta",
    "馬単": "exacta",
    "ワイド": "wide",
    "三連複": "trio",
    "三連単": "trifecta",
}


TODAY_TOP_URL = f"{BASE}/TodayRaceInfoTop"

_MEETING_RE = re.compile(
    r"RaceList\?k_raceDate=([^&\"'\s>]+)&(?:amp;)?k_babaCode=(\d+)"
)
_RACE_NO_RE = re.compile(
    r"RaceMarkTable\?k_raceDate=[^&\"'\s>]+&(?:amp;)?k_raceNo=(\d+)&(?:amp;)?k_babaCode=\d+"
)


def parse_meetings(html: str) -> list[tuple[str, int]]:
    """TodayRaceInfoTop から (日付 'YYYY/MM/DD', babaCode) の一覧を抽出する。

    数日先の開催も含まれるため、呼び出し側で日付フィルタすること。
    HTMLに引用符なしhref等の揺れがあるため正規表現で抽出する。
    """
    from urllib.parse import unquote

    out = []
    for enc_date, baba in _MEETING_RE.findall(html):
        out.append((unquote(enc_date), int(baba)))
    return sorted(set(out))


def parse_race_numbers(html: str) -> list[int]:
    """RaceList ページから成績(RaceMarkTable)リンクのあるレース番号を抽出。"""
    return sorted({int(n) for n in _RACE_NO_RE.findall(html)})


def race_list_url(date: str, baba_code: int) -> str:
    return (
        f"{BASE}/RaceList?k_raceDate={quote(date, safe='')}&k_babaCode={baba_code}"
    )


def fetch_meetings(date: str, min_interval: float = 2.0) -> list[tuple[str, int]]:
    """指定日(YYYY/MM/DD)の開催 (date, babaCode) 一覧。"""
    html = polite_get(TODAY_TOP_URL, min_interval).decode("utf-8", errors="replace")
    return [(d, b) for d, b in parse_meetings(html) if d == date]


def fetch_race_numbers(date: str, baba_code: int, min_interval: float = 2.0) -> list[int]:
    html = polite_get(race_list_url(date, baba_code), min_interval).decode(
        "utf-8", errors="replace"
    )
    return parse_race_numbers(html)


def race_mark_table_url(date: str, race_no: int, baba_code: int) -> str:
    """date は 'YYYY/MM/DD'。"""
    return (
        f"{BASE}/RaceMarkTable?k_raceDate={quote(date, safe='')}"
        f"&k_raceNo={race_no}&k_babaCode={baba_code}"
    )


def refund_money_list_url(date: str, baba_code: int) -> str:
    return (
        f"{BASE}/RefundMoneyList?k_babaCode={baba_code}"
        f"&k_raceDate={quote(date, safe='')}"
    )


def fetch_race_result(date: str, race_no: int, baba_code: int, min_interval: float = 2.0):
    html = polite_get(race_mark_table_url(date, race_no, baba_code), min_interval)
    return parse_race_mark_table(html.decode("utf-8", errors="replace"))


@dataclass
class Finisher:
    rank: int | None          # 数値化できない(取消・失格等)場合 None
    rank_raw: str
    waku: int | None
    horse_no: int | None
    horse_name: str
    horse_id: str | None      # 血統登録番号(k_lineageLoginCode)
    affiliation: str
    sex_age: str
    weight_carried: float | None
    jockey: str
    trainer: str
    body_weight: int | None
    body_weight_diff: int | None
    time: str
    margin: str
    last3f: float | None
    popularity: int | None
    win_odds: float | None


@dataclass
class Refund:
    bet_type: str             # takeout.py キー(未知の式別は原文のまま)
    bet_type_ja: str
    combination: str          # '7' / '4-7' / '7-4-2'
    amount: int               # 100円あたり払戻(円)
    popularity: int | None


@dataclass
class RaceResult:
    title: str
    surface: str | None
    distance: int | None
    weather: str | None
    going: str | None
    finishers: list = field(default_factory=list)
    refunds: list = field(default_factory=list)


def _int_or_none(text: str) -> int | None:
    m = re.search(r"\d+", text.replace(",", ""))
    return int(m.group()) if m else None


def _float_or_none(text: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", text)
    return float(m.group()) if m else None


def parse_race_mark_table(html: str) -> RaceResult:
    soup = BeautifulSoup(html, "html.parser")

    # --- レースメタ ---
    title_el = soup.select_one("section.raceTitle h3")
    title = title_el.get_text(strip=True) if title_el else ""
    surface = distance = weather = going = None
    data_area = soup.select_one("section.raceTitle ul.dataArea li")
    if data_area:
        text = data_area.get_text(" ", strip=True)
        m = re.search(r"(ダート|芝)\s*([0-9０-９,]+)ｍ", text)
        if m:
            surface = m.group(1)
            distance = _int_or_none(m.group(2).translate(str.maketrans("０１２３４５６７８９", "0123456789")))
        mw = re.search(r"天候：(\S+)", text)
        weather = mw.group(1) if mw else None
        mg = re.search(r"馬場：(\S+)", text)
        going = mg.group(1) if mg else None

    result = RaceResult(title=title, surface=surface, distance=distance,
                        weather=weather, going=going)

    # --- 着順表 ---
    grade = soup.select_one("section.gradeTable table")
    if grade:
        for tr in grade.find_all("tr"):
            if tr.find("th"):
                continue  # ヘッダ行
            cells = {}
            for td in tr.find_all("td"):
                cls = td.get("class") or []
                if cls:
                    cells[cls[0]] = td
            if "a" not in cells or "d" not in cells:
                continue
            horse_a = cells["d"].find("a")
            horse_id = None
            if horse_a and horse_a.get("href"):
                m = re.search(r"k_lineageLoginCode=(\d+)", horse_a["href"])
                horse_id = m.group(1) if m else None
            bw_td = cells.get("j")
            body_weight = body_weight_diff = None
            if bw_td:
                bw_text = bw_td.get_text(strip=True)
                m = re.match(r"(\d+)\s*\(([+-]?\d+)\)", bw_text)
                if m:
                    body_weight, body_weight_diff = int(m.group(1)), int(m.group(2))
                else:
                    body_weight = _int_or_none(bw_text)
            rank_raw = cells["a"].get_text(strip=True)
            result.finishers.append(
                Finisher(
                    rank=_int_or_none(rank_raw) if rank_raw.isdigit() else None,
                    rank_raw=rank_raw,
                    waku=_int_or_none(cells["b"].get_text()) if "b" in cells else None,
                    horse_no=_int_or_none(cells["c"].get_text()) if "c" in cells else None,
                    horse_name=cells["d"].get_text(strip=True),
                    horse_id=horse_id,
                    affiliation=cells["e"].get_text(strip=True) if "e" in cells else "",
                    sex_age=re.sub(r"\s+", "", cells["f"].get_text()) if "f" in cells else "",
                    weight_carried=_float_or_none(cells["g"].get_text()) if "g" in cells else None,
                    jockey=cells["h"].find("a").get_text(strip=True).split("（")[0]
                    if "h" in cells and cells["h"].find("a") else "",
                    trainer=cells["i"].get_text(strip=True) if "i" in cells else "",
                    body_weight=body_weight,
                    body_weight_diff=body_weight_diff,
                    time=cells["k"].get_text(strip=True) if "k" in cells else "",
                    margin=cells["l"].get_text(strip=True) if "l" in cells else "",
                    last3f=_float_or_none(cells["m"].get_text()) if "m" in cells else None,
                    popularity=_int_or_none(cells["o"].get_text()) if "o" in cells else None,
                    win_odds=_float_or_none(cells["p"].get_text()) if "p" in cells else None,
                )
            )

    # --- 払戻表(rowspan の式別継続行に注意) ---
    for table in soup.select("section.newRefundTable table"):
        current_type_ja = None
        for tr in table.find_all("tr"):
            title_td = tr.find("td", class_="title")
            if title_td:
                current_type_ja = title_td.get_text(strip=True)
            if current_type_ja is None:
                continue
            comb_td = tr.find("td", class_="a") or tr.find("td", class_="d")
            money_td = tr.find("td", class_="refundMoney")
            pop_td = tr.find("td", class_="c")
            if comb_td is None or money_td is None:
                continue
            amount = _int_or_none(money_td.get_text())
            if amount is None:
                continue
            result.refunds.append(
                Refund(
                    bet_type=BET_TYPE_MAP.get(current_type_ja, current_type_ja),
                    bet_type_ja=current_type_ja,
                    combination=comb_td.get_text(strip=True),
                    amount=amount,
                    popularity=_int_or_none(pop_td.get_text()) if pop_td else None,
                )
            )
    return result
