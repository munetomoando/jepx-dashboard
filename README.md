# JEPX スポット価格ダッシュボード

日本卸電力取引所（JEPX）のスポット市場の約定価格を、システムプライスと9エリアについて表示するダッシュボードです。
気温・日射量と並べて見たり、過去1年分を遡ったりできます。Macのデスクトップにウィジェットとして置くこともできます。

**公開中のページ：https://munetomoando.github.io/jepx-dashboard/**

## できること

- **日別の推移**：30分ごと（48コマ）の約定価格を10本の折れ線で表示します。システムプライスと同じ価格のエリアは太線の下に隠れるので、市場分断が起きたエリアだけが浮き出て見えます。分断したエリア同士が同じ価格の区間は、それぞれの色の縞模様で示します。マウスでなぞるか、スマートフォンではタップすると、そのコマの値を表に表示します。「システムとの差」に切り替えると、分断の方向と幅を直接見られます。選んだエリアの気温と日射量も同じ時間軸で表示します。日付を選べば、おおむね過去1年分を表示できます。
- **長期の推移**：日平均価格の推移を90日・180日・365日の期間で表示します（7日移動平均も可）。
- **気象と価格の分析**：気温・日射量と価格の関係を散布図にし、二次曲線を当てはめて、今日と明日の予報を当てはめた参考値を示します。燃料価格や電源の停止を考慮しない単純な関係なので、価格の予測ではありません。

## Macのデスクトップにウィジェットとして置く

データの取得は不要です。公開中のページをそのまま表示します。

1. デスクトップにウィジェットを置ける無料アプリ [Übersicht](https://tracesof.net/uebersicht/) を入れて、一度起動します。
   ```
   brew install --cask ubersicht
   open -a "Übersicht"
   ```
2. ターミナルで次の2行を実行します（1行目はウィジェット用のフォルダがなければ作るものです）。
   ```
   mkdir -p "$HOME/Library/Application Support/Übersicht/widgets"
   curl -fsSL https://raw.githubusercontent.com/munetomoando/jepx-dashboard/main/widget/jepx.jsx -o "$HOME/Library/Application Support/Übersicht/widgets/jepx.jsx"
   ```
3. 数秒で、デスクトップの左上にダッシュボードが現れます。

ウィジェット上部の「今日」「明日」「長期の推移」「気象と価格」のボタンで表示を切り替えます。
Übersichtでは、ウィジェットの中に埋め込んだページにはクリックが届かないことがあるため、切り替えボタンはウィジェット側に置き、
中のページは操作部を隠した表示（`?embed=1`）にしています。グラフをなぞって数値を見るなどの細かい操作は、「ブラウザで開く」から行ってください。
「今日」の表示は、日付が変わると自動で翌日に進みます。

大きさと位置は、`jepx.jsx` の `ZOOM`（縮小率）と `top`・`left`（位置）で変えられます。
Übersichtのメニューの「Open Widgets Folder」から開いて書き換え、保存するとすぐに反映されます。

うまく表示されないとき：

- 何も表示されない場合は、Übersichtのメニューでウィジェット一覧の `jepx` にチェックが入っているか確認してください。
- ボタンが反応しない場合は、Übersichtの Preferences で「Enable interaction」にチェックを入れてください。

### URLで表示内容を指定する

ページのURLに次の指定を付けると、最初からその画面を表示します。

| 指定 | 内容 |
|---|---|
| `?page=day` / `long` / `analysis` | 日別の推移／長期の推移／気象と価格の分析 |
| `?date=tomorrow` / `2026-03-10` | 明日／指定した日（日別の推移） |
| `?area=東京` | 気象と分析で使うエリア |
| `?mode=diff` | 「システムとの差」で表示 |
| `?span=90` / `180` / `365` | 長期の推移・分析の期間（日） |
| `?zoom=0.8` | ページ全体の縮小率 |
| `?embed=1` | 操作部を隠した埋め込み用の表示 |

## 自分で運用する（GitHub Pages）

このリポジトリを複製すれば、自分のGitHubアカウントで同じページを運用できます。サーバーは不要で、公開リポジトリならGitHub ActionsとGitHub Pagesは無料です。

1. このリポジトリをフォークします（無料プランのGitHub Pagesは公開リポジトリのみ）。
2. Settings → Pages → Build and deployment の Source を **GitHub Actions** にします。
3. Actions タブを開き、ワークフローを有効にします（フォークしたリポジトリでは、定期実行が最初は止まっています）。
4.「JEPXデータ更新」→ Run workflow で初回を実行します。数分後に `https://（ユーザー名）.github.io/jepx-dashboard/` で表示されます。
5. ウィジェットで自分のページを表示するには、`widget/jepx.jsx` の `BASE` を自分のURLに書き換えます。

### 仕組み

```
.github/workflows/update.yml   15分ごとの定期実行（取得 → 変化の判定 → 公開）
scripts/jepx_fetch.py          データ取得（標準ライブラリのみ）
scripts/should_deploy.py       公開が必要かの判定（実際に公開中のデータと比べ、変化があったとき、または2時間ごと）
site/index.html                ダッシュボード本体（data.js と archive/ は実行時に生成）
widget/jepx.jsx                Übersicht用ウィジェット
```

JEPXへのアクセスは、キャッシュが古いときと、翌日分の公表を待つ時間帯だけに絞っています（1日数回程度）。
いつ取得したかは記録ファイル（state.json）で管理し、失敗したときも20分は再試行しません。
正常に動いていれば、ページ右下の「JEPXから取得」の時刻は1日に数回しか変わりません。
取得したCSVや気象データはリポジトリに入れず、Actionsのキャッシュで次回に引き継ぎます。
過去分は月ごとのファイルに分け、画面は表示する月だけを読み込みます。

公開リポジトリでは、60日間活動がないと定期実行が自動で止まります。
対策として、最後のコミットから50日たつとワークフローが空コミットを作ります。

## データと利用条件

このリポジトリにはデータは含まれていません。自分で運用する場合、データはそれぞれがJEPXとOpen-Meteoから取得することになるので、利用条件を各自で確認してください（以下は2026年9月時点の確認内容です）。

- **JEPX**：[免責事項・著作権](https://www.jepx.jp/disclaimer/)によると、掲載内容の著作権はJEPXにあり、出所を明示すれば利用できるとされています。リンクはトップページへのものに限られます。商用利用については明示的な定めがないので、事業で使う場合はJEPXに確認してください。JEPXのサーバーに負荷をかけないよう、取得の間隔を短くしないでください。
- **Open-Meteo**：[利用規約](https://open-meteo.com/en/terms)によると、無料APIは非商用の利用に限られます。データは CC BY 4.0 で、出典、ライセンスへのリンク、加工の有無の表示が必要です（画面に表示済み）。商用で使う場合は有料プランが必要です。

## 免責

- このツールは個人が作成したもので、日本卸電力取引所（JEPX）およびOpen-Meteoとは関係ありません。また、作者が関わる公的な検討とも関係ありません。
- 表示内容の正確性・完全性・即時性は保証しません。取引や投資の判断には使わないでください。
- 気象データはエリアごとの代表2地点の平均で、エリア全体の状況を正確に表すものではありません。

## ライセンス

ソースコードは [MIT License](LICENSE) で公開しています。データにはそれぞれの提供元の利用条件が適用されます。

---

## English summary

A dashboard for JEPX (Japan Electric Power Exchange) day-ahead spot prices — system price and nine area prices in 30-minute slots — with temperature and solar radiation from Open-Meteo, a one-year history, and a long-term view. It runs entirely on GitHub Actions and GitHub Pages, and can be placed on the macOS desktop as an [Übersicht](https://tracesof.net/uebersicht/) widget:

```
curl -fsSL https://raw.githubusercontent.com/munetomoando/jepx-dashboard/main/widget/jepx.jsx -o "$HOME/Library/Application Support/Übersicht/widgets/jepx.jsx"
```

This is a personal project, not affiliated with JEPX or Open-Meteo. No warranty; not for trading decisions. Code: MIT License. Data: subject to each provider's terms.
