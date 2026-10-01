# GitHub PR Auto Check Bot

[English](README.md) | 日本語

Pull Requestの内容をGitHub REST APIで調べ、結果をまとめたコメントをPRに自動で投稿する、小さなGitHub Actions Botです。

- **外部ライブラリは不要**：Pythonの標準ライブラリだけで動きます。
- **シークレットの管理も不要**：GitHub Actionsが自動で用意する `GITHUB_TOKEN` を使うので、Personal Access Tokenを作る必要はありません。
- **コメントはPRごとに1件だけ**：pushのたびにコメントを増やさず、同じコメントを書き換えます。
- **forkからのPRでも安全**：PRのコードをcheckoutしたり実行したりすることはありません。

## 実行例

`src/main.py`、`tests/test_main.py`、`README.md` を変更したPRには、次のようなコメントが付きます（コメントは英語で投稿されます）。

> ## PR Auto Check
>
> | Check | Result |
> | --- | --- |
> | Changed files | 3 |
> | Additions | +42 |
> | Deletions | -8 |
> | README changed | ✅ Yes |
> | Test file changed | ✅ Yes |
> | TODO / FIXME added | ✅ None detected |
> | PR size | ✅ Reasonable size (50 lines) |

## チェック項目

| 項目 | 判定方法 |
| --- | --- |
| Changed files / Additions / Deletions | PR全体の変更ファイル数・追加行数・削除行数 |
| README changed | `README` または `README.*` という名前のファイルが変更されたか（どのディレクトリでも対象） |
| Test file changed | `test/`、`tests/`、`__tests__/`、`spec/` 配下のファイル、または `test_*.py`、`*_test.go`、`*.test.ts`、`*.spec.js`、`*_spec.rb`、`MainTest.java` のような名前のファイルが変更されたか |
| TODO / FIXME added | 差分の追加行に大文字の `TODO` または `FIXME` が含まれるか。見つかった場合は、ファイル名と行番号を一覧で表示します |
| PR size | 追加行数＋削除行数が400行以下なら ✅、1000行以下なら ⚠️、1000行を超えると 🚨 |

## 仕組み

```
PRの作成・push
        │
        ▼
GitHub Actions (pull_request_target)
        │  default branch だけを checkout
        ▼
bot/pr_checker.py
        │  GET  /repos/{owner}/{repo}/pulls/{number}
        │  GET  /repos/{owner}/{repo}/pulls/{number}/files
        │  GET  /repos/{owner}/{repo}/issues/{number}/comments
        ▼
POST  /repos/{owner}/{repo}/issues/{number}/comments    （初回：新しく投稿）
PATCH /repos/{owner}/{repo}/issues/comments/{id}        （2回目以降：書き換え）
```

それぞれのAPIでは、PRの情報、変更ファイルと差分、既存のコメントを取得します。

Botは、隠しマーカー `<!-- github-pr-auto-check-bot -->` と、投稿者が `github-actions[bot]` であることの2つで自分のコメントを見分けます。前回と内容が変わっていなければ、書き換えはしません。

## セットアップ

1. **Public** リポジトリを作成します。Publicリポジトリなら、GitHubが用意する標準のrunnerを無料で使えます。
2. このリポジトリの `.github/workflows/pr-check.yml` と `bot/pr_checker.py` を追加します。
3. default branch（たとえば `main`）にpushします。
4. Pull Requestを作成すると、**PR Auto Check Bot** ワークフローが動いてPRにコメントが付きます。

リポジトリの設定を変える必要はありません。必要な権限は、ワークフローの `permissions:` で指定してあります。

## セキュリティ

`pull_request_target` で動くワークフローには、forkからのPRであっても書き込み権限のあるトークンが渡されます。そのおかげでforkからのPRにもコメントできますが、裏を返せば、信頼できないコードを絶対に実行してはいけないということです。このワークフローは、その前提で次のように作っています。

- checkoutするのはベースリポジトリの **default branch** だけで、PR側のコードはcheckoutしません。
- `persist-credentials: false` を指定して、checkoutしたリポジトリにトークンを残しません。
- `run:` の中で `${{ }}` を使ってPRのデータを埋め込むことはしません。スクリプトがAPIから読み取るので、スクリプトインジェクションを防げます。
- 権限は `contents: read` と `pull-requests: write` だけに絞っています。
- PRに含まれるファイル名はインラインコードとして表示するので、Markdownやメンションを埋め込まれることはありません。

> **注意**
> このワークフローに、`github.event.pull_request.head.sha` をcheckoutするステップや、PRのコードをビルド・インストール・テストするステップを追加しないでください。
> それらが必要な場合は、`pull_request` で起動する別のワークフローを用意してください。

## カスタマイズ

[`bot/pr_checker.py`](bot/pr_checker.py) の先頭にある定数を書き換えてください。

| 定数 | 初期値 | 意味 |
| --- | --- | --- |
| `SIZE_LARGE` | `400` | 変更行数がこの値を超えると ⚠️ Large になります |
| `SIZE_VERY_LARGE` | `1000` | 変更行数がこの値を超えると 🚨 Very large になります |
| `MAX_TODO_LOCATIONS` | `20` | コメントに一覧表示するTODO / FIXMEの最大件数です |
| `TEST_PATTERNS` | コードを参照 | テストファイルを見分けるための正規表現です |

## サポート

不具合の報告や質問は、[Issue](../../issues) からお願いします。

## ライセンス

[MIT](LICENSE)
