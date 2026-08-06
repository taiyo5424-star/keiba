# ローカル環境への移行ガイド

このリポジトリはGitHub(`taiyo5424-star/keiba`)にあり、ローカルへの「移行」は
クローンするだけで完了する。実データ取得(JRA-VAN)がWindows必須のため、
本格運用はローカル(Windows または Windows VM)が前提になる。

## 1. クローンとセットアップ(全OS共通)

```bash
git clone https://github.com/taiyo5424-star/keiba.git
cd keiba
git checkout claude/horse-racing-expected-value-8skl1r   # 現在の開発ブランチ

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m pytest tests/ -q       # 全件パスすることを確認
python examples/pipeline_demo.py # 全工程デモ
keiba --help                     # CLI
```

依存は numpy / pandas / pytest のみ。LightGBM等を使う場合は `pip install -e ".[ml]"`。

## 2. Codex CLI との協業体制

リポジトリ直下の **AGENTS.md** を Codex が、**CLAUDE.md** を Claude Code が
自動で読む。プロジェクト知識は AGENTS.md に一元化してあるので、
どちらのエージェントも同じ前提・同じガードレールで作業する。

```bash
# Codex CLI(要Node.js): https://github.com/openai/codex
npm install -g @openai/codex
cd keiba && codex        # AGENTS.md を自動読み込み

# Claude Code(ローカル版)
npm install -g @anthropic-ai/claude-code
cd keiba && claude       # CLAUDE.md → AGENTS.md を読み込み
```

推奨する協業パターン(詳細は [operations.md](operations.md)):
- 一方が実装 → もう一方が敵対的レビュー(リーク・多重比較・過学習を疑う)
- レビュー依頼の定型: 「tests/を含む差分を読み、AGENTS.mdのガードレール
  違反(特にPIT違反・確定オッズ参照・分割のリーク)を探せ」
- 共有はgit経由(ブランチ+コミット)で行い、口頭合意をコードに残さない

## 3. 実データ取得(Windows)

| データ | 手段 | 備考 |
|---|---|---|
| 中央(蓄積+リアルタイムオッズ) | JRA-VAN DataLab.(月2,090円)+ JV-Link | ActiveX COM、**Windows必須**。速報オッズ最短10秒間隔・時系列オッズあり |
| 地方 | 地方競馬DATA + UmaConn | Windows前提 |
| 参考実装 | [kmy-keiba](https://github.com/kmycode/kmy-keiba) | JVLink+地方競馬DATA両対応のOSS(C#) |

- Mac/Linuxの場合はWindows VM(またはWindowsマシン)でJV-Link→SQLite/CSVに
  書き出し、本リポジトリの `store.py` スキーマに流し込む構成を推奨。
- PythonからのJV-Link呼び出しは `pywin32` + COM で可能(要Windows上のPython)。
- 取り込みアダプタは `src/keiba/ingest/` に追加していく(store.pyのスキーマが受け口)。

## 4. 運用開始前チェックリスト

1. `docs/strategy.md` の撤退基準を読み、自分の数値(資金・DD上限)を決める
2. `KILL_SWITCH` ファイルの場所を確認(置けば全発注停止)
3. `ExecutionGuard` の日次上限を自分の資金に合わせて設定
4. ペーパートレードを最低数百レース回し、`keiba summary` で
   バックテストとの乖離を確認してから実弾を検討する
5. 実弾接続(ipatgo等のAdapter実装)の前に
   `docs/research/automation-tos.md`(規約リスク)と
   `docs/research/tax.md`(税務・記録要件)を必ず読む
