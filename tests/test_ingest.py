"""インジェストパーサのテスト。

フィクスチャは実ページの構造を再現した合成HTML(実データはコミットしない)。
実際に取得した生HTMLに対する検証は、環境変数 KEIBA_RECON_DIR に
サンプル保存ディレクトリを指定した場合のみ実行される(統合テスト)。
"""

import os
from pathlib import Path

import pytest

from keiba.ingest.nar_keibago import (
    parse_race_mark_table,
    race_mark_table_url,
    refund_money_list_url,
)
from keiba.ingest.rakuten import parse_dividend_list, zeros_raceid, dividend_list_url

FIXTURES = Path(__file__).parent / "fixtures"


def test_nar_url_builders():
    url = race_mark_table_url("2026/08/06", 1, 27)
    assert "k_raceDate=2026%2F08%2F06" in url and "k_raceNo=1" in url and "k_babaCode=27" in url
    assert "RefundMoneyList" in refund_money_list_url("2026/08/06", 27)


def test_parse_nar_result_fixture():
    r = parse_race_mark_table((FIXTURES / "nar_result_sample.html").read_text(encoding="utf-8"))
    assert r.title == "テストレース"
    assert r.surface == "ダート" and r.distance == 1400
    assert r.weather == "晴" and r.going == "良"

    assert len(r.finishers) == 3
    f1 = r.finishers[0]
    assert f1.rank == 1 and f1.horse_no == 7
    assert f1.horse_name == "テストホースA"
    assert f1.horse_id == "30000000001"
    assert f1.jockey == "試験騎手"
    assert f1.body_weight == 467 and f1.body_weight_diff == 1
    assert f1.win_odds == pytest.approx(2.8)
    assert f1.popularity == 2
    f2 = r.finishers[1]
    assert f2.body_weight_diff == -3
    # 除外馬: rankはNoneでrank_rawに原文
    f3 = r.finishers[2]
    assert f3.rank is None and f3.rank_raw == "除外"

    # 払戻: rowspan継続行(複勝2行目)が正しく複勝として読めている
    kinds = [(x.bet_type, x.combination, x.amount) for x in r.refunds]
    assert ("win", "7", 280) in kinds
    assert ("place", "4", 100) in kinds
    assert ("quinella", "4-7", 290) in kinds
    assert ("exacta", "7-4", 660) in kinds
    assert ("trifecta", "7-4-2", 2160) in kinds  # カンマ入り金額


def test_parse_rakuten_fixture():
    races = parse_dividend_list(
        (FIXTURES / "rakuten_dividend_sample.html").read_text(encoding="utf-8")
    )
    assert len(races) == 2
    r1 = races[0]
    assert r1.race_no == 1
    # 複勝・ワイドの<br>区切り3件が展開されている
    places = [x for x in r1.refunds if x["bet_type"] == "place"]
    wides = [x for x in r1.refunds if x["bet_type"] == "wide"]
    assert len(places) == 3 and len(wides) == 3
    assert places[1]["amount"] == 470 and places[1]["popularity"] == 8
    # 票数(プールサイズ)
    assert r1.votes["win"] == 50185
    assert r1.votes["trifecta"] == 304023
    assert r1.returned_votes["wide"] == 10
    # 2R: 高額配当のカンマ除去
    r2 = races[1]
    exacta = [x for x in r2.refunds if x["bet_type"] == "exacta"][0]
    assert exacta["amount"] == 74770 and exacta["popularity"] == 106


def test_rakuten_raceid():
    assert zeros_raceid("20251007", 20) == "202510072000000000"
    assert dividend_list_url("20251007", 20).endswith("202510072000000000")


# ---- 統合テスト(実取得済みHTMLがある環境でのみ実行) ----

RECON = os.environ.get("KEIBA_RECON_DIR")


@pytest.mark.skipif(not RECON, reason="KEIBA_RECON_DIR not set")
def test_parse_real_nar_result():
    r = parse_race_mark_table(
        (Path(RECON) / "nar_result.html").read_text(encoding="utf-8")
    )
    assert len(r.finishers) >= 8
    assert len(r.refunds) >= 10
    assert all(f.horse_id for f in r.finishers if f.rank is not None)


@pytest.mark.skipif(not RECON, reason="KEIBA_RECON_DIR not set")
def test_parse_real_rakuten():
    races = parse_dividend_list(
        (Path(RECON) / "rakuten_dividend.html").read_text(encoding="utf-8")
    )
    assert len(races) == 12
    assert all(r.votes.get("win") for r in races)
