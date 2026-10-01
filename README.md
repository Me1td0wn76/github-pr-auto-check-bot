# GitHub PR Auto Check Bot

English | [日本語](README_jp.md)

A minimal GitHub Actions bot that inspects every pull request through the
GitHub REST API and posts a summary comment back to it.

- **Zero dependencies.** It uses only the Python standard library.
- **No secrets to manage.** It uses the built-in `GITHUB_TOKEN`, so you don't need a Personal Access Token.
- **One comment per PR.** The bot edits the same comment on every push instead of adding new ones.
- **Safe with fork PRs.** It never checks out or runs pull request code.

## Example

When a PR changes `src/main.py`, `tests/test_main.py` and `README.md`, the bot comments:

> ##  PR Auto Check
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

## What it checks

| Check | How it is decided |
| --- | --- |
| Changed files / Additions / Deletions | Totals from the pull request |
| README changed | A file named `README` or `README.*`, in any directory |
| Test file changed | Paths under `test/`, `tests/`, `__tests__/` or `spec/`, or names like `test_*.py`, `*_test.go`, `*.test.ts`, `*.spec.js`, `*_spec.rb`, `MainTest.java` |
| TODO / FIXME added | Added lines in the diff that contain uppercase `TODO` or `FIXME`. The comment lists each file and line number. |
| PR size | Additions + deletions: ✅ up to 400, ⚠️ up to 1000, 🚨 above 1000 |

## How it works

```
Pull request opened / pushed
        │
        ▼
GitHub Actions (pull_request_target)
        │  checks out the default branch only
        ▼
bot/pr_checker.py
        │  GET  /repos/{owner}/{repo}/pulls/{number}
        │  GET  /repos/{owner}/{repo}/pulls/{number}/files
        │  GET  /repos/{owner}/{repo}/issues/{number}/comments
        ▼
POST  /repos/{owner}/{repo}/issues/{number}/comments    (first run)
PATCH /repos/{owner}/{repo}/issues/comments/{id}        (later runs)
```

The bot finds its own comment by the hidden marker `<!-- github-pr-auto-check-bot -->`
and the author `github-actions[bot]`. If nothing has changed, it skips the update.

## Setup

1. Create a **public** repository. Standard GitHub-hosted runners are free for public repositories.
2. Add `.github/workflows/pr-check.yml` and `bot/pr_checker.py` from this repository.
3. Push them to the default branch (for example `main`).
4. Open a pull request. The **PR Auto Check Bot** workflow runs and comments on it.

You don't need to change any repository settings. The workflow's `permissions:` block grants what it needs.

## Security

`pull_request_target` runs with a write-capable token, even for pull requests from forks.
That is why the bot can comment on fork PRs, and it is also why the workflow must never run untrusted code.
This workflow is built around that rule:

- It checks out the base repository's **default branch**, never the PR head.
- `persist-credentials: false` keeps the token out of the checked-out repository.
- PR data never appears in `${{ }}` expressions inside `run:`. The script reads it from the API, which avoids script injection.
- Permissions are limited to `contents: read` and `pull-requests: write`.
- File paths from the PR are shown as inline code, so they can't inject markdown or mentions.

> **Warning**
> Don't add steps that check out `github.event.pull_request.head.sha` or that build, install or test PR code in this workflow.
> If you need that, use a separate workflow triggered by `pull_request`.

## Customization

Edit the constants at the top of [`bot/pr_checker.py`](bot/pr_checker.py):

| Constant | Default | Meaning |
| --- | --- | --- |
| `SIZE_LARGE` | `400` | Above this many changed lines, the PR is marked ⚠️ Large |
| `SIZE_VERY_LARGE` | `1000` | Above this many changed lines, the PR is marked 🚨 Very large |
| `MAX_TODO_LOCATIONS` | `20` | Maximum TODO / FIXME locations listed in the comment |
| `TEST_PATTERNS` | see code | Regular expressions that identify test files |

## Support

If you find a bug or have a question, please [open an issue](../../issues).

## License

[MIT](LICENSE)

Hello GitHub PR Bot!
