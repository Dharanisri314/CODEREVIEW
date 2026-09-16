import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
import git
import requests
import typer
from rich.console import Console
from rich.markdown import Markdown
from prompt_toolkit import prompt

app = typer.Typer(help="Code Review Agent Terminal CLI")
console = Console()

DEFAULT_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
SUPPORTED_EXTENSIONS = {".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".rs", ".c", ".cpp"}


def send_chat_request(base_url: str, payload: dict):
    """Sends code payload to backend API and outputs review markdown."""
    with console.status("[bold green]Agent reviewing code...[/bold green]"):
        try:
            response = requests.post(f"{base_url}/chat", json=payload, timeout=300)
            if response.status_code == 200:
                reply = response.json().get("reply", "")
                console.print("\n" + "─" * 55)
                console.print(Markdown(reply))
                console.print("─" * 55 + "\n")
            else:
                console.print(f"\n[bold red]Error ({response.status_code}):[/bold red] {response.text}\n")
        except requests.exceptions.RequestException as exc:
            console.print(f"\n[bold red]Connection Error:[/bold red] Ensure backend server is running on {base_url}\n")


def convert_github_file_url_to_raw(github_url: str) -> str:
    """Converts a standard GitHub file blob URL into its raw download URL."""
    # Pattern: https://github.com/user/repo/blob/branch/path/to/file.ts
    pattern = r"https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)"
    match = re.match(pattern, github_url)
    if match:
        user, repo, branch, filepath = match.groups()
        return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{filepath}"
    return github_url


def fetch_github_file(github_url: str) -> tuple[str, str]:
    """Fetches single raw file content from GitHub."""
    raw_url = convert_github_file_url_to_raw(github_url)
    filename = github_url.split("/")[-1]
    
    response = requests.get(raw_url, timeout=30)
    if response.status_code == 200:
        return filename, response.text
    else:
        raise RuntimeError(f"Failed to fetch GitHub file (HTTP {response.status_code}): {response.text[:200]}")


def scan_directory_path(target_path: Path, base_url: str, user_id: str, active_session: str, comment: str = ""):
    """Recursively collects and sends supported code files to backend."""
    comment_prefix = f"User Context/Comment: {comment}\n\n" if comment else ""

    if target_path.is_file():
        files_to_scan = [target_path]
    elif target_path.is_dir():
        files_to_scan = [
            f for f in target_path.rglob("*")
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS and not any(part.startswith(".") for part in f.parts)
        ]
    else:
        console.print(f"[bold red]Invalid path:[/bold red] {target_path}")
        return

    if not files_to_scan:
        console.print("[bold yellow]No supported code files found to scan.[/bold yellow]")
        return

    console.print(f"[bold cyan]Found {len(files_to_scan)} file(s) to scan.[/bold cyan]\n")

    for file_path in files_to_scan:
        console.print(f"[bold blue]Scanning:[/bold blue] {file_path}")
        try:
            code_content = file_path.read_text(encoding="utf-8", errors="ignore")
            message = f"{comment_prefix}File: {file_path.name}\n```\n{code_content}\n```"
            payload = {
                "message": message,
                "user_id": user_id,
                "session_id": active_session,
            }
            send_chat_request(base_url, payload)
        except Exception as exc:
            console.print(f"[bold red]Failed to read {file_path}:[/bold red] {exc}")


@app.command()
def main(
    agent: bool = typer.Option(
        False, "--agent", "-a", help="Launch interactive Code Review Agent mode"
    ),
    path: str = typer.Option(
        None, "--path", "-p", help="Path to local file or folder/repo to scan"
    ),
    github: str = typer.Option(
        None, "--github", "-g", help="GitHub repository URL or specific file URL to scan"
    ),
    comment: str = typer.Option(
        None, "--comment", "-c", help="Custom instructions or context for the scan"
    ),
    user_id: str = typer.Option(
        "cli_user", "--user", "-u", help="User ID for tracking"
    ),
    session_id: str = typer.Option(
        None, "--session", "-s", help="Custom session ID"
    ),
    url: str = typer.Option(
        DEFAULT_URL, "--url", help="Backend API server base URL"
    ),
):
    """Code Review CLI supporting interactive paste, file, folder, and GitHub repository/file scanning."""
    active_session = session_id or f"cli-{uuid.uuid4().hex[:8]}"
    base_url = url.rstrip("/")

    console.print(f"\n[bold green]🤖 Code Review Agent CLI[/bold green]")
    console.print(f"Backend Server: [dim]{base_url}[/dim]")
    console.print(f"User ID: [bold magenta]{user_id}[/bold magenta]")
    console.print(f"Session ID: [bold yellow]{active_session}[/bold yellow]\n")

    comment_prefix = f"User Context/Comment: {comment}\n\n" if comment else ""

    # Mode 1: Local file or directory scan
    if path:
        target_path = Path(path).resolve()
        scan_directory_path(target_path, base_url, user_id, active_session, comment or "")
        return

    # Mode 2: GitHub repo or specific file scan
    if github:
        if "/blob/" in github:
            # Single GitHub File
            console.print(f"[bold cyan]Fetching GitHub File:[/bold cyan] {github}")
            try:
                filename, code_content = fetch_github_file(github)
                message = f"{comment_prefix}File: {filename}\n```\n{code_content}\n```"
                payload = {
                    "message": message,
                    "user_id": user_id,
                    "session_id": active_session,
                }
                send_chat_request(base_url, payload)
            except Exception as exc:
                console.print(f"[bold red]Fetch failed:[/bold red] {exc}")
        else:
            # Full GitHub Repository
            with tempfile.TemporaryDirectory() as tmp_dir:
                console.print(f"[bold cyan]Cloning repository:[/bold cyan] {github}")
                try:
                    git.Repo.clone_from(github, tmp_dir, depth=1)
                    scan_directory_path(Path(tmp_dir), base_url, user_id, active_session, comment or "")
                except Exception as exc:
                    console.print(f"[bold red]Git clone failed:[/bold red] {exc}")
        return

    # Mode 3: Interactive paste mode
    console.print(
        "[dim]Paste code block, then press Alt+Enter (or Esc then Enter) to submit.[/dim]\n"
        "[dim]Type '/clear' to reset memory, or 'exit'/'quit' to exit.[/dim]\n"
        + "─" * 55
    )

    while True:
        try:
            console.print("[bold yellow]Enter/Paste Code (Press Alt+Enter to Submit):[/bold yellow]")
            user_code = prompt(multiline=True).strip()

            if user_code.lower() in ["exit", "quit"]:
                console.print("[bold red]Session closed.[/bold red]")
                sys.exit(0)

            if user_code.lower() == "/clear":
                try:
                    requests.post(
                        f"{base_url}/clear",
                        json={"user_id": user_id, "session_id": active_session},
                    )
                    console.print("[bold green]Session history cleared.[/bold green]\n")
                except Exception as exc:
                    console.print(f"[bold red]Connection Error:[/bold red] {exc}\n")
                continue

            if not user_code:
                continue

            payload = {
                "message": f"{comment_prefix}{user_code}",
                "user_id": user_id,
                "session_id": active_session,
            }
            send_chat_request(base_url, payload)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Session terminated.[/bold red]")
            sys.exit(0)


if __name__ == "__main__":
    app()