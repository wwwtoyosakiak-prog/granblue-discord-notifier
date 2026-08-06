# グラブル公式NEWS → Discord通知

グランブルーファンタジー公式NEWSを30分ごとに確認し、キーワードに合う新着記事だけをDiscordへ通知します。

## 最初の設定（GitHubのWeb画面だけでできます）

1. このZIPをMacでダブルクリックして解凍します。
2. GitHubで空のリポジトリを作ります（Private推奨）。
3. **Add file → Upload files** を開き、解凍したフォルダの「中身」をすべてアップロードします。
4. アップロード一覧に `.github/workflows/notifier.yml` があることを確認して **Commit changes** を押します。
5. **Settings → Secrets and variables → Actions → New repository secret** を開きます。
6. Nameを `DISCORD_WEBHOOK_URL`、SecretをDiscordのWebhook URLにして保存します。

> `.github` はMacでは隠しフォルダです。Finderで見えない場合は `command + shift + .` で表示できます。ZIPには確実に収録されています。

## テスト通知

1. GitHubの **Actions** タブを開きます。
2. **Granblue Discord Notifier** を選びます。
3. **Run workflow** を押します。`test_notification` はチェックしたまま実行します。
4. Discordに「テストに成功しました」と届けば設定完了です。

手動テストは既読データを変更しません。通常のNEWS確認を手動実行したい場合だけ、チェックを外して実行してください。

## 動作仕様

- 毎時7分と37分（約30分ごと）に実行
- 初回の通常実行は現在の記事を既読登録するだけで、過去記事を大量通知しない
- `data/seen.json` に記事IDを保存して重複通知を防止
- 通知成功後だけ既読データを更新
- キーワードに該当しない新着も既読にし、設定変更時の大量通知を防止
- 同時実行を抑止

GitHub Actionsの定時実行は混雑により数分以上遅れる場合があります。

## キーワードを変更する

初期値は次のとおりです。

`イベント,キャンペーン,コラボ,フェス,古戦場,ブレイブグラウンド,四象降臨,撃滅戦,復刻`

変更する場合は **Settings → Secrets and variables → Actions → Variables → New repository variable** で、Nameを `KEYWORDS`、Valueをカンマ区切りの語句にします。空の変数は初期値として扱われます。すべての記事を通知したい場合は `src/notifier.py` の `DEFAULT_KEYWORDS` を空文字にしてください。

## 困ったとき

- Actionsにワークフローが出ない: リポジトリのCode画面で `.github/workflows/notifier.yml` が存在するか確認
- Webhookエラー: Secret名が正確に `DISCORD_WEBHOOK_URL` か、URLが有効か確認
- 既読保存時に403: **Settings → Actions → General → Workflow permissions** を `Read and write permissions` に変更
- 通知されない: Actionsの実行ログと、キーワード設定を確認

公式NEWS: https://granbluefantasy.com/ja/news/
