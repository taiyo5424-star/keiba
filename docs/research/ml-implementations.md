# 日本競馬のML予測 — 実装事例・研究・「回収率100%超」の信頼性評価

調査日: 2026-07-19。報告されている精度・回収率はすべて発表者の自己申告値であり、
検証方法に問題を含むものが多い(§4参照)。

## 1. 公開実装(GitHub / Qiita / Zenn)

| 実装 | データ源 | モデル | 報告値 | 評価 |
|---|---|---|---|---|
| [Zenn書籍「競馬予想で始める機械学習〜完全版〜」(dijzpeb)](https://zenn.dev/dijzpeb/books/848d4d8e47001193f3fb) | netkeibaスクレイピング | LightGBM(分類/ランキング) | 「単勝回収率122%」を謳う | 日本語圏の定番教材。シミュレーション条件は有料部で第三者検証困難 |
| [stockedge/netkeiba-scraper](https://github.com/stockedge/netkeiba-scraper) (117★) | netkeiba | 特徴量生成に特化(モデル無し) | ─ | collecturl→scrapehtml→extract→genfeature の4段パイプライン、SQLite格納 |
| [KHTTakuya/KeibaPrediction](https://github.com/KHTTakuya/KeibaPrediction) | netkeiba | LightGBM+TF(ターゲットエンコーディング、PCA、直近5走) | 特定開催日で「回収率119%」 | 単日実戦のみ=統計的に無意味なサンプル数 |
| [kmycode/kmy-keiba「KMY競馬」](https://github.com/kmycode/kmy-keiba) | **JRA-VAN(JVLink)+地方競馬DATA公式連携** | Keras.NET(メンテ対象外) | ─ | スクレイピング非依存で中央+地方をカバーする貴重な参照実装(C#/.NET 8) |
| [Enigmo技術ブログ ランク学習(2020)](https://tech.enigmo.co.jp/entry/2020/12/09/100000) | netkeiba | LightGBM LGBMRanker(lambdarank/NDCG) | テスト48レースで回収率110.56%(ベースライン78.54%) | テストは2日間48レースのみ。オッズ特徴量の時点管理が未確認でリーク疑い残る |

補助: [kiccho1101/keiba](https://github.com/kiccho1101/keiba)(線形/LightGBM/XGBoost比較)。
ryutoro-galois/keiba-predictor は実在を確認できず(**未確認**)。

## 2. 学術研究

- **杉山・山下(上智大)JSAI2023** [「部分再帰型NNを用いた最適な競馬のbetting戦略」](https://www.jstage.jst.go.jp/article/pjsai/JSAI2023/0/JSAI2023_2L6GS302/_article/-char/ja/):
  時系列+属性の混合データを部分再帰型NNで勝率予測し、オッズとの期待値でベット決定。
  「勝率だけでbetを決め利益を考えない」先行研究の問題を明示的に指摘。回収率数値は抄録から未確認。
- [What AI can do for horse-racing? (arXiv:2207.04981)](https://arxiv.org/abs/2207.04981):
  Benter流ロジット以降のML競馬予測の展望論文。
- [OU過程によるJRA単勝オッズの時間発展モデル (arXiv:2503.16470)](https://arxiv.org/html/2503.16470v2):
  日本市場を直接扱う数少ないarXiv論文(ハーディング/情報投票者のミクロ・マクロ分析)。
- [Systematic Review of ML in Sports Betting (arXiv:2410.21484)](https://arxiv.org/html/2410.21484v1)
- **較正の実例**: [Qiita「時系列MLのリーク監査と確率較正」](https://qiita.com/architectJapan/items/1f7cfb2b156038c65f99):
  LightGBM出力にIsotonic較正+**Benter較正**(モデル確率^α × 市場確率^β、MLEで α≈0.28, β≈0.86)。
  市場側の重みが大きく推定される = 「モデル単体では市場に勝ちにくい」ことの傍証であり、
  本リポジトリの `blend.py` の設計を裏付ける。

## 3. 商用AI予想サービス

- **netkeiba AI予想群**([AI予想](https://race.netkeiba.com/AI/AI.html)、勝ち馬サーチ、調子偏差値、AI展開予測):
  アルゴリズム・学習データ・検証方法いずれも非公開。
- **SIVA**(スポニチ、[siva-ai.com](https://siva-ai.com/)): JRA全レース対象(新馬・障害除く)、月額制。手法非公開。
  第三者検証([umabi.jp 2024](https://umabi.jp/keibasite/siva-ai/))では直近3ヶ月で回収率100%に遠く及ばずとの報告
  (検証サイト自体の透明性も限定的)。
- オッズパークはAI予想の的中率・回収率を開示するFAQあり。

## 4. 「回収率100%超」報告の典型的な問題(重要)

無情報ベットの期待回収率は約80%(単勝)。100%超の主張は「市場に恒常的に勝つ」強い主張であり、
公開事例の多くは以下で説明できる:

1. **確定オッズによるリーク**: 最終オッズ・最終人気は締切前には分からない。特徴量に入れる/
   確定配当で回収率を計算するのは典型的リーク([開発者による指摘](http://keibasys.seesaa.net/article/493406221.html))。
   極端な例では着順由来の値の混入で「ROI 988%」→リーク除去後は約80%(控除率水準)に低下
   ([リーク監査記事](https://qiita.com/architectJapan/items/1f7cfb2b156038c65f99))。
2. **時系列リーク**: 騎手勝率等の集計特徴量を全期間で計算すると未来情報が過去のレースに混入。
   バックテストROI 200%超→フォワードテストで85%未満に急落した実例
   ([Zenn 競馬AI開発記録#15](https://zenn.dev/ricotiler/articles/keiba-ai-15-pit-generation-leak-prevention))。
   対策は**Point-in-Time(時点固定)でのデータ生成**。
3. **サンプル不足**: 単勝回収率の分散は極大(高オッズ1本で数十%動く)。数十〜数百レースの
   100%超は偶然と区別不能。
4. **事後選択(多重比較)**: テスト結果を見た後に購入条件・閾値・券種・競馬場を選ぶと
   バックテストは容易に「勝てる」([168%報告の構図](https://qiita.com/Mshimia/items/6c54d82b3792925b8199)
   — 時系列分割やオッズ除外は良心的だが、スコア差閾値がテスト後に追加され約100レースまで絞られた数値)。

**総合評価**: (a)〜(d)を全て回避した上で長期フォワードテストで100%超を実証した公開事例は
**確認できなかった**。信頼できる検証の条件: ①特徴量とオッズのPoint-in-Time管理を明記
②購入ルールを検証前に固定した厳密な時系列分割 ③数千レース規模・複数年のテスト
④確率較正と市場オッズ統合(Benter流)。日本の単勝市場は概ね効率的で、
公開手法の水準で控除率20%を恒常的に上回るのは極めて困難、が妥当な結論。

## 本リポジトリへの反映

- `blend.py`(Benter較正)・`calibration.py`(較正評価)・`backtest.py`(時系列バックテスト)は
  上記の失敗パターンを避ける最小構成として設計済み。
- データ生成をPoint-in-Time化するETL(§4-2対策)が次の実装課題。
- kmy-keiba(JVLink+地方競馬DATA連携)はデータ取得層の実装参考として最有力。
