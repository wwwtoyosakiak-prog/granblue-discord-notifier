# グランブルーファンタジー Discord通知

グラブル公式サイトのNEWSを30分ごとに確認し、対象キーワードを含む新着記事をDiscordへ通知します。

## 通知対象（初期設定）

- イベント
- 古戦場
- ドレッドバラージュ
- コラボ
- キャンペーン
- メンテナンス
- アップデート
- 生放送
- 「これからのグランブルーファンタジー」

ゲームへのログインやゲーム内部APIの利用はせず、公開されている公式NEWSだけを監視します。

## 導入手順

### 1. GitHubへアップロード

このフォルダを新しいGitHubリポジトリへアップロードします。公開・非公開のどちらでも動きます。

### 2. Discord Webhookを作る

1. 通知したいDiscordチャンネルを開く
2. `チャンネルの編集` → `連携サービス` → `ウェブフック`
3. `新しいウェブフック` を作成
4. `ウェブフックURLをコピー`

Webhook URLは他人に見せないでください。

### 3. GitHub Secretへ登録

GitHubリポジトリで次を開きます。

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

| Name | Secret |
|---|---|
| `DISCORD_WEBHOOK_URL` | コピーしたDiscord Webhook URL |

### 4. 初回起動

`Actions` → `Granblue Discord Notifier` → `Run workflow`

初回は現在掲載中の記事を記録するだけで、過去記事は通知しません。

### 5. テスト通知

もう一度 `Run workflow` を押し、`Discordへテスト通知を送る` にチェックして実行します。

## 通知対象を変える

GitHubリポジトリで以下を開きます。

`Settings` → `Secrets and variables` → `Actions` → `Variables` → `New repository variable`

### KEYWORDS

カンマ区切りで指定します。

```text
イベント,古戦場,コラボ,キャンペーン,メンテナンス
```

### EXCLUDE_KEYWORDS

通知したくない語句をカンマ区切りで指定します。

```text
キャラクターソング,グッズ
```

### NOTIFY_ALL

すべての新着NEWSを通知する場合は、値を `true` にします。

## 確認間隔を変える

`.github/workflows/notifier.yml` のcronを変更します。現在は30分ごとです。

```yaml
- cron: "0,30 * * * *"
```

GitHub Actionsのスケジュールは混雑により数分以上遅れる場合があります。

## ローカルでテストする

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
DISCORD_WEBHOOK_URL="Webhook URL" SEND_TEST=true python src/notifier.py
```

## 仕組み

1. 公式NEWS一覧を取得
2. 記事URL・タイトル・日付・カテゴリを抽出
3. `data/state.json` と比較
4. 未確認かつキーワードに合う記事をDiscordへ投稿
5. 確認済みURLをGitHubへ自動保存

## 注意

- 公式サイトのHTML構造が大きく変わると、抽出処理の修正が必要になる場合があります。
- Webhook URLをソースコードや公開投稿へ直接書かないでください。
- GitHub Actionsを無効にすると通知も止まります。
