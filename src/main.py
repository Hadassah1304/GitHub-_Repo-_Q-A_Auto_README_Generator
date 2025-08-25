
# # main.py
# import utils
# import inference
# import agent

# def main():
#     utils.load_env()

#     repo_url = input("Enter GitHub repo URL: ").strip()

#     # 1) discover file list (flatten tree)
#     tree = utils.get_repo_tree(repo_url)
#     file_paths = [...]  # flatten tree logic here

#     # 2) fetch code
#     code_list = utils.fetch_multiple_files(repo_url, file_paths)

#     # 3) index
#     collection = inference.get_or_create_collection("chroma_db", "repo_files")
#     inference.index_files(collection, code_list, file_paths)

#     # 4) agent
#     llm = agent.build_llm()
#     retrieve_tool = agent.make_retrieve_tool(collection)
#     ag = agent.build_agent(llm, tools=[retrieve_tool])

#     # 5) simple question loop
#     while True:
#         q = input("\nAsk a question (or type 'exit' to quit): ").strip()
#         if q.lower() in {"exit", "quit"}:
#             break
#         answer = ag.run(q)
#         print("\nAnswer:", answer)

# if __name__ == "__main__":
#     main()




# main.py
from __future__ import annotations

import os
import sys
import traceback

import utils
import inference
import agent


def _flatten_tree(tree, prefix: str = "") -> list[str]:
    """
    Flatten a nested dict produced by utils.get_repo_tree into a list of file paths.
    Expects: {'dir': {...}, 'file.py': None}
    Returns: ['dir/file.py', 'file.py', ...]
    """
    if not isinstance(tree, dict):
        return []

    paths: list[str] = []
    for name, node in tree.items():
        full = f"{prefix}{name}" if not prefix else f"{prefix.rstrip('/')}/{name}"
        if node is None:  # file
            paths.append(full)
        elif isinstance(node, dict):  # directory
            paths.extend(_flatten_tree(node, full))
        # ignore anything else (symlinks/submodules/etc.)
    return paths


def _require_env(var: str) -> None:
    """Warn if an env var is missing (doesn't exit—just warns)."""
    if not os.getenv(var):
        print(f"⚠️  Warning: {var} is not set. If you use that provider, set it in your shell or .env.")


def main() -> None:
    # Load .env if available (no-op if python-dotenv is not installed)
    try:
        utils.load_env()
    except Exception:
        # Don't crash if load_env isn't present or throws
        pass

    # Optional: warn about common keys you might use
    _require_env("OPENAI_API_KEY")
    # _require_env("GITHUB_TOKEN")  # uncomment if you need private repo access / higher rate limits

    repo_url = input("Enter GitHub repo URL: ").strip()
    if not repo_url:
        print("No URL provided. Exiting.")
        return

    print("→ Discovering repository files …")
    try:
        tree = utils.get_repo_tree(repo_url) or {}
    except Exception as e:
        print("❌ Failed to fetch repo tree.")
        traceback.print_exc()
        return

    if not isinstance(tree, dict) or not tree:
        print("⚠️  Could not fetch a valid repo tree (got empty or invalid).")
        print("   - Check the URL is correct and public")
        print("   - If private, export GITHUB_TOKEN")
        print("   - You may be rate-limited by GitHub (try again later)")
        return

    file_paths = _flatten_tree(tree)
    if not file_paths:
        print("⚠️  Repo tree found, but no files to index (did filters remove everything?).")
        return

    print(f"→ Found {len(file_paths)} paths. Fetching textual files (.py/.md/.txt) …")
    try:
        code_list, kept_names = utils.fetch_multiple_files(
            repo_url, file_paths, filter_textual=True
        )
    except Exception:
        print("❌ Failed while fetching raw files from GitHub.")
        traceback.print_exc()
        return

    if not code_list:
        print("⚠️  No textual files fetched.")
        print("   - Is the repo empty or only binaries?")
        print("   - Is the default branch unusual (not main/master)?")
        print("   - For private repos, set GITHUB_TOKEN.")
        return

    print(f"→ Fetched {len(code_list)} files. Indexing into Chroma …")
    try:
        collection = inference.get_or_create_collection("chroma_db", "repo_files")
        added = inference.index_files(collection, code_list, kept_names)
    except Exception:
        print("❌ Failed while creating the vector index.")
        traceback.print_exc()
        return

    if added == 0:
        print("⚠️  Nothing was indexed (all docs filtered or an ID collision occurred).")
        return
    print(f"→ Indexed {added} documents.")

    print("→ Spinning up the agent …")
    try:
        llm = agent.build_llm()
        retrieve_tool = agent.make_retrieve_tool(collection)
        ag = agent.build_agent(llm, tools=[retrieve_tool])
    except Exception:
        print("❌ Failed to initialize the agent/LLM.")
        traceback.print_exc()
        return

    print("\n✅ Ready. Ask questions about the repo (type 'exit' to quit).")
    try:
        while True:
            q = input("Q: ").strip()
            if q.lower() in {"exit", "quit"}:
                print("bye!")
                break
            if not q:
                continue
            try:
                ans = ag.run(q)
            except KeyboardInterrupt:
                print("\n(interrupted)"); continue
            except Exception as e:
                ans = f"[agent error] {e}"
            print(f"A: {ans}\n")
    except KeyboardInterrupt:
        print("\nbye!")


if __name__ == "__main__":
    # Make unhandled exceptions obvious instead of a silent exit
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)