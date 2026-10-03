"""
Git Investigation Tools
========================
Inspects the local payment-api Git repository.

🎓 SECURITY — GIT SHELL INJECTION PREVENTION:
We use GitPython (not subprocess with shell=True).
GitPython uses subprocess internally with argument arrays.
User input (commit SHA, file path) is validated before use.
Path traversal is prevented by resolving against the repo root.

🎓 WHY LOCAL GIT?
For MVP, we clone/use the local payment-api repository.
The tool interface is identical to what a GitHub API version would look like.
If you add GitHub token support later, only this file changes.
"""

import re
from pathlib import Path
from typing import Any

from git import Repo, InvalidGitRepositoryError, BadName
from langchain_core.tools import tool

from app.core.config import get_settings

settings = get_settings()

# Validate repo path is within allowed location
_REPO_PATH = Path(settings.incident_lab_repo_path).resolve()

# SHA validation regex — only hex characters, 4-40 chars
_SHA_PATTERN = re.compile(r"^[0-9a-f]{4,40}$")


def _get_repo() -> Repo:
    """Get the Git repository. Raises if not found."""
    try:
        return Repo(_REPO_PATH)
    except InvalidGitRepositoryError:
        raise RuntimeError(
            f"No git repository at {_REPO_PATH}. "
            "Run scripts/build_git_history.py first."
        )


def _validate_sha(sha: str) -> str:
    """Validate commit SHA to prevent injection."""
    sha = sha.strip().lower()
    if not _SHA_PATTERN.match(sha):
        raise ValueError(f"Invalid commit SHA format: {sha!r}")
    return sha


@tool
async def search_commits(
    service: str,
    since: str = "",
    until: str = "",
    keyword: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search Git commits in the payment-api repository.

    Args:
        service: Service name (used for filtering, currently 'payment-api')
        since: ISO date string to filter commits after (e.g., '2026-09-05')
        until: ISO date string to filter commits before (e.g., '2026-09-07')
        keyword: Keyword to search in commit messages
        limit: Maximum commits to return (default 20)

    Returns:
        dict with 'commits' list containing SHA, message, author, timestamp, files
    """
    try:
        repo = _get_repo()
        limit = min(limit, 50)

        commits = []
        kwargs: dict = {"max_count": limit}
        if since:
            kwargs["after"] = since
        if until:
            kwargs["before"] = until

        for commit in repo.iter_commits("HEAD", **kwargs):
            message = commit.message.strip()

            # Apply keyword filter if specified
            if keyword and keyword.lower() not in message.lower():
                continue

            # Get changed files
            if commit.parents:
                diff = commit.parents[0].diff(commit)
                changed_files = [d.a_path or d.b_path for d in diff]
            else:
                changed_files = list(commit.stats.files.keys())

            commits.append({
                "sha": commit.hexsha[:8],
                "full_sha": commit.hexsha,
                "message": message,
                "author": commit.author.name,
                "email": commit.author.email,
                "timestamp": commit.authored_datetime.isoformat(),
                "changed_files": changed_files,
                "files_changed_count": len(changed_files),
            })

        return {
            "success": True,
            "commits": commits,
            "count": len(commits),
            "repository": "payment-api",
            "note": "Use get_commit_diff with a SHA to inspect specific code changes",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "commits": [],
            "count": 0,
        }


@tool
async def get_commit_diff(commit_sha: str) -> dict[str, Any]:
    """
    Get the full diff for a specific commit.

    This shows exactly what code changed in a commit — critical for
    determining whether a code change could have caused an incident.

    Args:
        commit_sha: The commit SHA (short or full, 4-40 hex characters)

    Returns:
        dict with commit details and full diff per file
    """
    try:
        commit_sha = _validate_sha(commit_sha)
        repo = _get_repo()

        try:
            commit = repo.commit(commit_sha)
        except BadName:
            return {
                "success": False,
                "error": f"Commit {commit_sha!r} not found in repository",
            }

        # Get diff against parent
        file_diffs = []
        if commit.parents:
            parent = commit.parents[0]
            diffs = parent.diff(commit, create_patch=True)
            for diff in diffs:
                file_diffs.append({
                    "file": diff.a_path or diff.b_path,
                    "change_type": diff.change_type,  # A=added, D=deleted, M=modified, R=renamed
                    "additions": diff.diff.decode("utf-8", errors="replace").count("\n+") if diff.diff else 0,
                    "deletions": diff.diff.decode("utf-8", errors="replace").count("\n-") if diff.diff else 0,
                    "diff": diff.diff.decode("utf-8", errors="replace") if diff.diff else "",
                })
        else:
            # Initial commit — show all files
            for item in commit.tree.traverse():
                if item.type == "blob":
                    file_diffs.append({
                        "file": item.path,
                        "change_type": "A",
                        "diff": "(initial commit — file added)",
                    })

        return {
            "success": True,
            "sha": commit.hexsha[:8],
            "full_sha": commit.hexsha,
            "message": commit.message.strip(),
            "author": commit.author.name,
            "timestamp": commit.authored_datetime.isoformat(),
            "files_changed": [d["file"] for d in file_diffs],
            "file_diffs": file_diffs,
            "total_files": len(file_diffs),
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
async def search_files(
    file_path: str,
    commit_sha: str = "HEAD",
) -> dict[str, Any]:
    """
    Read the contents of a file at a specific commit.

    Useful for inspecting the actual code state at the time of an incident.

    Args:
        file_path: Relative path within the repository (e.g., 'app/config.py')
        commit_sha: Commit SHA or branch name (default: 'HEAD')

    Returns:
        dict with file content
    """
    try:
        # Validate file path — prevent path traversal
        clean_path = Path(file_path).as_posix()
        if ".." in clean_path or clean_path.startswith("/"):
            return {"success": False, "error": "Invalid file path"}

        repo = _get_repo()

        try:
            commit = repo.commit(commit_sha)
        except BadName:
            return {"success": False, "error": f"Commit {commit_sha!r} not found"}

        try:
            blob = commit.tree[clean_path]
            content = blob.data_stream.read().decode("utf-8", errors="replace")
        except KeyError:
            return {"success": False, "error": f"File {clean_path!r} not found at commit {commit_sha}"}

        return {
            "success": True,
            "file_path": clean_path,
            "commit_sha": commit.hexsha[:8],
            "content": content,
            "size_bytes": len(content),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
