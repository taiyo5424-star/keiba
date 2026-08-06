"""外部データソースからの取り込み(インジェスト)。

- nar_keibago: 地方競馬情報サイト(keiba.go.jp、NAR公式)の成績・払戻パーサ
- rakuten: 楽天競馬の払戻・式別票数(プールサイズ)パーサ

共通ルール(docs/research/automation-tos.md):
- robots.txt と Crawl-Delay を尊重(楽天は60秒。フェッチャに組み込み済み)
- 取得データはプロジェクト内部の分析用に限定。生HTMLのリポジトリへの
  コミットや再配布はしない
- User-Agent を明示し、失敗時のリトライは指数バックオフで最小限に
"""
