# AGENTS.md — AIエージェント向けプロジェクトガイド

このファイルは Codex CLI・Claude Code など、このリポジトリで作業する
全てのAIエージェントが最初に読む共通コンテキストです。

## プロジェクトの目的

中央競馬(JRA)・地方競馬(NAR)で期待値(EV)プラスの馬券を見つけ、
資金管理を伴って長期運用するための分析・実行基盤。
**戦略の根拠と制約は `docs/strategy.md` に集約されている。作業前に必読。**

## 絶対に守る原則(ガードレール)

1. **リークの排除が最優先**: 特徴量・購入判断に「発走前に確定していない情報」
   (確定オッズ・結果由来の集計)を混ぜない。特徴量生成は `features.py` の
   Point-in-Time 方式のみ。バックテストの学習/検証はレース日付順の分割のみ
   (`time_series_split`)。ランダム分割のコードを書いたらそれはバグ。
2. **モデル単体の確率でEVを計算しない**: 必ず `blend.py` で市場確率と
   ロジット結合してから使う(Benter 1994、docs/strategy.md §3.2)。
3. **実弾発注は既定で無効**: `execution.py` の既定は PaperBroker。
   実弾Adapterの実装・有効化は人間の明示的な指示があった場合のみ。
   キルスイッチ(KILL_SWITCH ファイル)と ExecutionGuard の多層上限を
   バイパスするコードは書かない。
4. **賭け判断の合格基準は対数尤度**: 評価期間で「結合 > 市場単体」を
   安定して満たさない限り、回収率が1を超えていても運用しない
   (数百レースの回収率はノイズ。docs/strategy.md 撤退基準)。
5. **全購入の記録**: 発注は必ず `store.bets` に記録される経路を通す
   (モデル検証と税務=雑所得認定の両方に必須。docs/research/tax.md)。
6. スクレイピングを書く場合はアクセス間隔を空け(目安2秒以上)、
   robots.txt と利用規約を尊重する(docs/research/automation-tos.md)。

## コマンド

```bash
pip install -e ".[dev]"        # セットアップ
python -m pytest tests/ -q     # テスト(全て通ること。現在51件)
python examples/pipeline_demo.py   # 全工程デモ(格納→PIT→学習→結合→バックテスト)
keiba --help                   # CLI(ev/kelly/decide/win5/summary/test)
```

## アーキテクチャ(データの流れ)

```
[データ取得: ingest/ (NAR公式・楽天=票数) + ローカルJRA-VAN] → store.py (SQLite)
  → features.py (PIT特徴量) → model.py (条件付きロジット等)
  → blend.py (市場確率と結合) ← ev.py (オッズ→市場確率)
  → decision.py (EV閾値+ケリー+上限 → BetOrder)
  → execution.py (既定Paper / ガード+キルスイッチ) → store.bets
  → calibration.py / backtest.py (評価) → docs/operations.md のPDCAへ
```

- `takeout.py`: 券種別払戻率(JRA/NAR主催者別、公式値)
- `harville.py`: 単勝確率→連系券種の確率(指数補正γ,δは日本データで要推定)
- `win5.py`: キャリーオーバー込み実効還元率

## コーディング規約

- Python 3.10+、numpy/pandas のみを標準依存とする(MLは optional extra)
- 新機能には必ず pytest テストを付ける。PIT性・ガードのテストは削らない
- ドキュメントとdocstringは日本語
- コミットメッセージは日本語で、変更の「なぜ」を書く

## PDCAでの各エージェントの役割

`docs/operations.md` の週次サイクルを参照。要点:
- **Plan**: 仮説はすべて docs/strategy.md §6(未解決の論点)から採る/そこに追記する
- **Do**: 実装+バックテスト。検証条件(期間・分割・購入ルール)は実行前に固定
- **Check**: 対数尤度・較正・ビン別回収率。もう一方のエージェント
  (Claude⇔Codex)が敵対的レビューを行い、リーク・多重比較を疑う
- **Act**: 撤退基準に該当したら停止が正解。継続は根拠を文書化

## 現在の状態と次の課題

- 分析・実行基盤とリサーチは完了(コミット履歴参照)
- 最重要の未完了: **実データの取り込み**(JRA-VAN DataLab はWindows必須)。
  `docs/local-setup.md` の手順でローカル環境に移行して進める
