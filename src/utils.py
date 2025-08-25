# # utils.py
# from typing import Any, Dict, List
# import os, requests

# def load_env() -> None:
#     # optional: from dotenv import load_dotenv; load_dotenv()
#     pass

# def get_repo_tree(repo_url: str) -> Dict[str, Any]:
#     """Return nested dict (folder -> dict, file -> None)."""
#     ...

# def fetch_github_file(repo_url: str, file_path: str) -> str:
#     """Return raw text of a single file from default branch."""
#     ...

# def fetch_multiple_files(repo_url: str, file_paths: List[str]) -> List[str]:
#     """Fetch many files and return contents in order."""
#     ...

# def is_textual_file(name: str) -> bool:
#     return name.endswith((".py", ".md", ".txt"))


# # utils.py
# from typing import List, Tuple
# import requests
# import os

# TEXT_EXTS = (".py", ".md", ".txt")

# def load_env():
#     """
#     Load environment variables (from .env if available).
#     Fallback: do nothing if python-dotenv not installed.
#     """
#     try:
#         from dotenv import load_dotenv
#         load_dotenv()  # will look for a .env file in current dir
#     except ImportError:
#         # if python-dotenv isn't installed, just skip
#         pass

# def get_repo_tree(repo_url: str) -> dict[str, any]:
#     """Return nested dict (folder -> dict, file -> None)."""

# def is_textual_file(name: str) -> bool:
#     return name.lower().endswith(TEXT_EXTS)

# def fetch_raw_from_github(repo_url: str, file_path: str) -> str | None:
#     """
#     Fetch raw text from GitHub for a single file. Returns None on error/binary.
#     """
#     # naive default-branch guess; you can improve by hitting the repo API
#     owner_repo = repo_url.rstrip("/").split("github.com/")[-1]
#     for branch in ("main", "master"):
#         raw_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{file_path.lstrip('/')}"
#         try:
#             r = requests.get(raw_url, timeout=20)
#             if r.status_code == 200:
#                 # quick binary sniff
#                 text = r.text
#                 return text
#         except requests.RequestException:
#             pass
#     return None

# def fetch_multiple_files(repo_url: str, file_paths: List[str], filter_textual: bool = True) -> Tuple[List[str], List[str]]:
#     """
#     Fetch many files. Returns (contents, kept_names).
#     - Never returns None
#     - Skips missing/non-text files when filter_textual=True
#     """
#     contents: List[str] = []
#     kept_names: List[str] = []

#     for p in file_paths:
#         if filter_textual and not is_textual_file(p):
#             continue
#         text = fetch_raw_from_github(repo_url, p)
#         if text is None:
#             # skip files we couldn't fetch or that aren’t text
#             continue
#         contents.append(text)
#         kept_names.append(p)

#     return contents, kept_names

# utils.py
from __future__ import annotations
import os, re, requests
from typing import Dict, Any, List, Tuple

TEXT_EXTS = (".py", ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml",
             ".ini", ".cfg", ".csv", ".tsv", ".xml", ".html", ".css", ".js", ".ts")
SKIP_DIRS = {".git", ".github", ".venv", "venv", "node_modules", "__pycache__"}

def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

def is_textual_file(name: str) -> bool:
    return name.lower().endswith(TEXT_EXTS)

def _parse_owner_repo(repo_url: str) -> Tuple[str, str]:
    url = repo_url.strip()
    m = re.match(r"git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/\.]+)(?:\.git)?$", url)
    if m:
        return m.group("owner"), m.group("repo")
    m = re.match(r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/\.]+)(?:\.git)?/?", url)
    if not m:
        raise ValueError(f"Unrecognized GitHub URL: {repo_url}")
    return m.group("owner"), m.group("repo")

def _gh_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def _get_default_branch(owner: str, repo: str) -> str:
    r = requests.get(f"https://api.github.com/repos/{owner}/{repo}",
                     headers=_gh_headers(), timeout=30)
    if r.status_code == 200 and isinstance(r.json(), dict):
        db = r.json().get("default_branch")
        if db:
            return db
    # fallbacks if API is throttled
    for b in ("main", "master"):
        rr = requests.get(f"https://api.github.com/repos/{owner}/{repo}/branches/{b}",
                          headers=_gh_headers(), timeout=20)
        if rr.status_code == 200:
            return b
    return "main"

def _get_branch_tree_sha(owner: str, repo: str, branch: str) -> str | None:
    # get the tree sha for the branch head
    r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch}",
                     headers=_gh_headers(), timeout=30)
    if r.status_code == 200 and isinstance(r.json(), dict):
        obj = r.json().get("object") or {}
        commit_sha = obj.get("sha")
        if commit_sha:
            # now get the commit to find its tree sha
            c = requests.get(f"https://api.github.com/repos/{owner}/{repo}/git/commits/{commit_sha}",
                             headers=_gh_headers(), timeout=30)
            if c.status_code == 200 and isinstance(c.json(), dict):
                return c.json().get("tree", {}).get("sha")
    return None

def _git_tree_recursive(owner: str, repo: str, tree_sha: str) -> List[dict]:
    r = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}",
        params={"recursive": "1"},
        headers=_gh_headers(), timeout=60
    )
    if r.status_code == 200 and isinstance(r.json(), dict):
        # returns {'tree': [...], 'truncated': bool, ...}
        return r.json().get("tree", [])
    return []

def _nest_paths(paths: List[str]) -> Dict[str, Any]:
    """
    Given ['a/b.py', 'a/c/d.md', 'README.md'] return nested dict,
    mapping files to None and directories to dicts.
    """
    root: Dict[str, Any] = {}
    for p in paths:
        parts = [seg for seg in p.split("/") if seg]
        cur = root
        for i, seg in enumerate(parts):
            is_last = (i == len(parts) - 1)
            if is_last:
                cur[seg] = None
            else:
                cur = cur.setdefault(seg, {})
    return root

def get_repo_tree(repo_url: str, *, max_files: int = 5000) -> Dict[str, Any]:
    """
    Build a nested dict for the repo using the Git Trees API (recursive).
    Filters to textual files and skips common large/system dirs.
    Never returns None (returns {} on error).
    """
    try:
        owner, repo = _parse_owner_repo(repo_url)
        branch = _get_default_branch(owner, repo)
        tree_sha = _get_branch_tree_sha(owner, repo, branch)
        if not tree_sha:
            return {}
        tree_items = _git_tree_recursive(owner, repo, tree_sha)
        if not tree_items:
            return {}

        # collect file paths (filter dirs & skip unwanted dirs)
        file_paths: List[str] = []
        for it in tree_items:
            if it.get("type") != "blob":
                continue
            path = it.get("path") or ""
            # skip big/system dirs early
            head = path.split("/", 1)[0] if "/" in path else path
            if head in SKIP_DIRS:
                continue
            if is_textual_file(path):
                file_paths.append(path)
                if len(file_paths) >= max_files:
                    break

        if not file_paths:
            return {}

        return _nest_paths(file_paths)
    except Exception:
        # never propagate; caller can handle empty dict
        return {}

# ---------- You likely already have this ----------
def fetch_raw_from_github(repo_url: str, file_path: str) -> str | None:
    owner, repo = _parse_owner_repo(repo_url)
    # try real default branch for raw URL
    branch = _get_default_branch(owner, repo)
    for b in (branch, "main", "master"):
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{b}/{file_path}"
        try:
            r = requests.get(raw_url, timeout=20)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
    return None

def fetch_multiple_files(repo_url: str, file_paths: List[str], filter_textual: bool = True):
    contents, kept = [], []
    for p in file_paths:
        if filter_textual and not is_textual_file(p):
            continue
        txt = fetch_raw_from_github(repo_url, p)
        if txt is None:
            continue
        contents.append(txt)
        kept.append(p)
    return contents, kept
