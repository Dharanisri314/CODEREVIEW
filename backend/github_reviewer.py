# backend/github_reviewer.py

import os
import sys

import ollama
import requests


# Safely import static analysis tools and prompt from agent.py
try:
    from agent import SYSTEM_PROMPT, analyze_code, run_deep_scan
except Exception as exc:
    print(f"⚠️ Warning during agent import: {exc}")

    SYSTEM_PROMPT = (
        "You are a senior code review assistant with deep expertise in "
        "software security, performance, and best practices. Your purpose is "
        "to analyze code, find vulnerabilities, and suggest fixes."
    )

    def analyze_code(code: str, language: str = "python"):
        return {
            "info": "Static analysis skipped or unavailable in CI environment."
        }

    def run_deep_scan(code: str, language: str = "python"):
        return {
            "info": "Deep scan skipped or unavailable in CI environment."
        }


# GitHub Actions environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_FULL_NAME = os.getenv("REPO_FULL_NAME")
PR_NUMBER = os.getenv("PR_NUMBER")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

if not GITHUB_TOKEN or not REPO_FULL_NAME or not PR_NUMBER:
    print(
        "❌ Missing required environment variables: "
        "GITHUB_TOKEN, REPO_FULL_NAME, or PR_NUMBER."
    )
    sys.exit(1)


GITHUB_API_URL = "https://api.github.com"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def fetch_pr_diff() -> str:
    """Fetch the Git diff for the target pull request."""
    url = (
        f"{GITHUB_API_URL}/repos/{REPO_FULL_NAME}"
        f"/pulls/{PR_NUMBER}"
    )

    diff_headers = {
        **HEADERS,
        "Accept": "application/vnd.github.v3.diff",
    }

    try:
        response = requests.get(
            url,
            headers=diff_headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"❌ Error fetching PR diff: {exc}")
        sys.exit(1)

    if response.status_code != 200:
        print(
            f"❌ Failed to fetch PR diff: "
            f"{response.status_code} - {response.text}"
        )
        sys.exit(1)

    return response.text


def post_pr_comment(comment_body: str) -> None:
    """Post a Markdown comment to the GitHub pull request."""
    url = (
        f"{GITHUB_API_URL}/repos/{REPO_FULL_NAME}"
        f"/issues/{PR_NUMBER}/comments"
    )

    payload = {"body": comment_body}

    try:
        response = requests.post(
            url,
            headers=HEADERS,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"❌ Error posting PR comment: {exc}")
        return

    if response.status_code in (200, 201):
        print("✅ Successfully posted code review comment to GitHub PR.")
    else:
        print(
            f"❌ Failed to post PR comment: "
            f"{response.status_code} - {response.text}"
        )


def format_analysis_result(result) -> str:
    """Convert static-analysis output into readable text."""
    if isinstance(result, dict):
        return "\n".join(
            f"**{key}:** {value}"
            for key, value in result.items()
        )

    return str(result)


def has_code_additions(diff: str) -> bool:
    """Return True if the diff contains non-empty added lines."""
    added_lines = [
        line
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]

    return any(line[1:].strip() for line in added_lines)


def main() -> None:
    print(
        f"🔍 Fetching diff for PR #{PR_NUMBER} "
        f"in {REPO_FULL_NAME}..."
    )

    diff = fetch_pr_diff()

    # Check for an empty diff
    if not diff.strip():
        print("ℹ️ Diff is empty. Skipping review.")

        post_pr_comment(
            "ℹ️ **AI Code Review Skipped:** "
            "The pull request contains no code changes."
        )
        return

    # Check whether the diff contains actual code additions
    if not has_code_additions(diff):
        print(
            "ℹ️ Diff contains no code additions or meaningful changes. "
            "Skipping LLM review."
        )

        post_pr_comment(
            "ℹ️ **AI Code Review Skipped:** "
            "Only empty files or blank lines were added."
        )
        return

    # Step 1: Run static analysis
    print("⚡ Running static analysis checks...")

    try:
        static_analysis = analyze_code(
            diff,
            language="python",
        )

        static_analysis_text = format_analysis_result(
            static_analysis
        )

    except Exception as exc:
        print(f"⚠️ Static analysis error: {exc}")
        static_analysis_text = (
            "Static analysis encountered an error and was skipped."
        )

    # Limit diff size to avoid exceeding the model context window
    diff_for_review = diff[:10000]

    # Step 2: Query Ollama
    print(f"🦙 Analyzing diff with Ollama model: {OLLAMA_MODEL}...")

    prompt = f"""
{SYSTEM_PROMPT}

Static Analysis Pre-check Findings:
{static_analysis_text}

Review the following Git diff and provide clear, structured feedback.

Your response must include:

1. A short overall summary.
2. Critical or high-severity issues.
3. Security vulnerabilities.
4. Bugs or correctness problems.
5. Performance concerns.
6. Maintainability and style suggestions.
7. Concrete recommended fixes.

If no issues are found, clearly state that.

Git Diff:
```diff
{diff_for_review}
```
"""

    try:
        client = ollama.Client(host=OLLAMA_HOST)

        response = client.generate(
            model=OLLAMA_MODEL,
            prompt=prompt,
        )

        if isinstance(response, dict):
            ai_review = response.get(
                "response",
                "No review response returned.",
            )
        else:
            ai_review = getattr(
                response,
                "response",
                "No review response returned.",
            )

    except Exception as exc:
        print(f"❌ Error communicating with Ollama: {exc}")
        ai_review = f"⚠️ **Error running AI review:** {exc}"

    # Step 3: Format and post the review
    formatted_comment = (
        f"## 🤖 AI Code Review (`{OLLAMA_MODEL}`)\n\n"
        f"{ai_review}"
    )

    post_pr_comment(formatted_comment)


if __name__ == "__main__":
    main()