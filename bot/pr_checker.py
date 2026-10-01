#!/usr/bin/env python3
"""Minimal GitHub PR Auto Check Bot.

Reads pull request data through the GitHub REST API and posts a single
summary comment back to the pull request. Later runs update that same
comment instead of adding new ones.

This script intentionally uses only Python's standard library.
No third-party package or external service is required.
It never checks out or executes code from the pull request.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

API_VERSION = "2022-11-28"
API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com")
COMMENT_MARKER = "<!-- github-pr-auto-check-bot -->"
# Author of comments posted with the workflow's built-in GITHUB_TOKEN.
BOT_LOGIN = "github-actions[bot]"
PER_PAGE = 100

# PR size thresholds, counted as additions + deletions.
SIZE_LARGE = 400
SIZE_VERY_LARGE = 1000
# Maximum number of TODO / FIXME locations listed in the comment.
MAX_TODO_LOCATIONS = 20

README_PATTERN = re.compile(r"(^|/)readme(\.[^/]*)?$", re.IGNORECASE)
TEST_PATTERNS = (
    re.compile(r"(^|/)(tests?|__tests__|specs?)/", re.IGNORECASE),
    re.compile(r"(^|/)test_[^/]+$", re.IGNORECASE),
    re.compile(r"_(test|spec)\.[^/.]+$", re.IGNORECASE),
    re.compile(r"\.(test|spec)\.[^/.]+$", re.IGNORECASE),
    re.compile(r"[^/]Tests?\.[^/.]+$"),  # e.g. MainTest.java, FooTests.cs
)
TODO_PATTERN = re.compile(r"\b(TODO|FIXME)\b")
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class GitHubAPI:
    def __init__(self, token: str, base_url: str = API_URL) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "github-pr-auto-check-bot",
        }
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            self.base_url + path, data=data, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API {method} {path} failed: {error.code} {error.reason}\n{detail}"
            ) from None
        return json.loads(body) if body else None

    def paginate(self, path: str) -> list[Any]:
        items: list[Any] = []
        page = 1
        while True:
            batch = self.request("GET", f"{path}?per_page={PER_PAGE}&page={page}")
            items.extend(batch)
            if len(batch) < PER_PAGE:
                return items
            page += 1


def is_readme(path: str) -> bool:
    return bool(README_PATTERN.search(path))


def is_test_file(path: str) -> bool:
    return any(pattern.search(path) for pattern in TEST_PATTERNS)


def find_added_todos(files: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Return (path, line number) for each added line containing TODO or FIXME."""
    hits = []
    for file in files:
        line_no = 0
        for line in (file.get("patch") or "").split("\n"):
            header = HUNK_HEADER.match(line)
            if header:
                line_no = int(header.group(1))
                continue
            # Removed lines and "\ No newline at end of file" don't exist in the new file.
            if line.startswith(("-", "\\")):
                continue
            if line.startswith("+") and TODO_PATTERN.search(line):
                hits.append((file["filename"], line_no))
            line_no += 1
    return hits


def inline_code(text: str) -> str:
    """Render untrusted text such as a file path as inline code."""
    return "`" + text.replace("`", "'").replace("\n", " ") + "`"


def size_result(changed_lines: int) -> str:
    if changed_lines <= SIZE_LARGE:
        return f"✅ Reasonable size ({changed_lines} lines)"
    if changed_lines <= SIZE_VERY_LARGE:
        return f"⚠️ Large ({changed_lines} lines), consider splitting"
    return f"🚨 Very large ({changed_lines} lines), please split"


def build_comment(pr: dict[str, Any], files: list[dict[str, Any]]) -> str:
    paths = [file["filename"] for file in files]
    additions = pr["additions"]
    deletions = pr["deletions"]
    todos = find_added_todos(files)
    # GitHub omits the patch for diffs that are too large to display.
    unscanned = [f for f in files if not f.get("patch") and f.get("changes", 0) > 0]

    rows = [
        ("Changed files", str(pr["changed_files"])),
        ("Additions", f"+{additions}"),
        ("Deletions", f"-{deletions}"),
        ("README changed", "✅ Yes" if any(map(is_readme, paths)) else "➖ No"),
        ("Test file changed", "✅ Yes" if any(map(is_test_file, paths)) else "⚠️ No"),
        ("TODO / FIXME added", f"⚠️ {len(todos)} found" if todos else "✅ None detected"),
        ("PR size", size_result(additions + deletions)),
    ]

    lines = [
        COMMENT_MARKER,
        "##  PR Auto Check",
        "",
        "| Check | Result |",
        "| --- | --- |",
        *(f"| {name} | {result} |" for name, result in rows),
    ]

    if todos:
        lines += ["", "<details><summary>TODO / FIXME locations</summary>", ""]
        lines += [
            f"- {inline_code(path)} line {line_no}"
            for path, line_no in todos[:MAX_TODO_LOCATIONS]
        ]
        if len(todos) > MAX_TODO_LOCATIONS:
            lines.append(f"- …and {len(todos) - MAX_TODO_LOCATIONS} more")
        lines += ["", "</details>"]

    if unscanned:
        lines += [
            "",
            f"> {len(unscanned)} file(s) were not scanned for TODO / FIXME "
            "because GitHub did not return their diff (too large).",
        ]

    lines += [
        "",
        f"<sub>Checked commit {pr['head']['sha']}. "
        "This comment is updated automatically on every push.</sub>",
    ]
    return "\n".join(lines) + "\n"


def find_bot_comment(api: GitHubAPI, repository: str, number: int) -> dict[str, Any] | None:
    for comment in api.paginate(f"/repos/{repository}/issues/{number}/comments"):
        author = (comment.get("user") or {}).get("login")
        if author == BOT_LOGIN and COMMENT_MARKER in (comment.get("body") or ""):
            return comment
    return None


def main() -> int:
    api = GitHubAPI(get_env("GITHUB_TOKEN"))
    repository = get_env("GITHUB_REPOSITORY")
    number = int(get_env("PR_NUMBER"))

    pr = api.request("GET", f"/repos/{repository}/pulls/{number}")
    files = api.paginate(f"/repos/{repository}/pulls/{number}/files")
    body = build_comment(pr, files)
    print(body)

    existing = find_bot_comment(api, repository, number)
    if existing is None:
        created = api.request(
            "POST", f"/repos/{repository}/issues/{number}/comments", {"body": body}
        )
        print(f"Created comment: {created['html_url']}")
    elif existing.get("body") == body:
        print(f"Comment already up to date: {existing['html_url']}")
    else:
        api.request(
            "PATCH", f"/repos/{repository}/issues/comments/{existing['id']}", {"body": body}
        )
        print(f"Updated comment: {existing['html_url']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"::error::{error}")
        sys.exit(1)
