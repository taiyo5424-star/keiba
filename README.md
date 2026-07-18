# keiba — 期待値ベース馬券戦略ツールキット

中央競馬(JRA)・地方競馬(NAR)で **期待値(EV)がプラスの馬券** を見つけ、
資金管理を伴って長期的に運用するための分析基盤とリサーチドキュメント。

> ⚠️ 馬券購入は損失リスクを伴います。本リポジトリは分析・研究用であり、
> 利益を保証するものではありません。控除率20〜30%の市場で長期プラスを
> 出すのは統計的に極めて難しいことを前提に、余剰資金の範囲で運用してください。

## 構成

```
docs/
  strategy.md       # リサーチに基づく戦略ドキュメント(本丸)
  data-sources.md   # データソースと収集設計のガイド
src/keiba/
  takeout.py        # 券種別払戻率(JRA/NAR)
  ev.py             # オッズ⇔確率変換・期待値計算・合成オッズ
  kelly.py          # ケリー基準(単一賭け・同一レース内複数賭けの陽解法)
  calibration.py    # 予測確率の較正評価(Brier・対数損失・信頼度曲線・ビン別回収率)
  backtest.py       # EV閾値+flat/kelly配分のバックテストエンジン
examples/
  demo_ev_analysis.py  # 1レースのEV分析とケリー配分のデモ
tests/              # pytest(合成パリミュチュエル市場での挙動検証を含む)
```

## セットアップ

```bash
pip install -e .          # numpy, pandas
pip install -e ".[dev]"   # + pytest
python -m pytest tests/ -q
python examples/demo_ev_analysis.py
```

## 基本の考え方

1. **期待値の定義**: `EV = 自分の推定勝率 × オッズ`。EV > 1 の馬券だけを買う
2. **エッジの源泉**: 市場(オッズ)より正確な確率推定。控除率20%超を上回る
   精度差が必要 — 「当てる」ことではなく「確率を正しく見積もる」ことが本質
3. **較正が命**: モデルの推定確率は必ず `calibration.py` で実測的中率と照合する
4. **資金管理**: フルケリーは推定誤差に脆弱。1/4ケリー等に落とす(`kelly.py`)
5. **バックテストの罠**: 確定オッズでなく購入可能時点のオッズを使う。
   時系列分割でリークを防ぐ(`docs/data-sources.md` 参照)

詳細な戦略・市場分析・先行研究は [docs/strategy.md](docs/strategy.md) を参照。
