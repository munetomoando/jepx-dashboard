# JEPXスポット価格ダッシュボード（GitHub Pages版）

GitHub Actions が15分ごとにJEPXと気象のデータを取得し、変化があったときだけ GitHub Pages に公開します。
サーバーは不要で、公開リポジトリならActionsもPagesも無料で使えます。

## 構成

```
.github/workflows/update.yml   定期実行（取得 → 変化の判定 → 公開）
scripts/jepx_fetch.py          データ取得（Mac版と同じスクリプト）
scripts/should_deploy.py       公開が必要かの判定（変化があったとき、または2時間ごと）
site/index.html                ダッシュボード本体（data.js は実行時に生成）
```

取得したCSVや気象データ（jepx-cache/）はリポジトリには入れず、Actionsのキャッシュに保存して次回に引き継ぎます。
JEPXへのアクセスはMac版と同じく、必要なときだけ（1日数回程度）です。

## 設置手順

1. GitHubで**公開**リポジトリを作ります（例：`jepx-dashboard`）。無料プランのPagesは公開リポジトリのみです。
2. このフォルダをプッシュします。
   ```
   cd jepx-pages
   git init -b main
   git add .
   git commit -m "JEPXダッシュボード"
   git remote add origin https://github.com/munetomoando/jepx-dashboard.git
   git push -u origin main
   ```
3. リポジトリの Settings → Pages → Build and deployment の Source を **GitHub Actions** にします。
4. Actions タブ →「JEPXデータ更新」→ Run workflow で初回を手動実行します
   （手順3の前にプッシュ時の実行が失敗していても、ここでやり直せば大丈夫です）。
5. 数分後に `https://munetomoando.github.io/jepx-dashboard/` で表示されます。

ホームページからは、このURLへ普通にリンクを張れば使えます。

## 知っておくこと

- **公開範囲**：GitHub Pages のサイトは誰でも見られます（無料プランではパスワード保護はできません）。
  出典表示（JEPXはトップページへのリンク、Open-Meteoは CC BY 4.0 の表示）は画面に入れてあります。
- **更新の遅れ**：GitHubの定期実行は混雑時に数分〜十数分遅れたり、まれに飛ばされたりします。
  翌日分の価格が画面に出るまで、公表から30分程度かかることがあります。
- **60日ルール**：公開リポジトリでは、60日間活動がないと定期実行が自動で止まります。
  対策として、最後のコミットから50日たつとワークフローが空コミットを1つ作ります。
- **JEPXへの接続**：Actionsは海外（米国）のサーバーで動きます。JEPXが海外からのアクセスを受け付けない場合は、
  Actionsのログに 403 などのエラーが出ます。その場合はMac版で取得したデータをプッシュする方式に切り替えられます。
