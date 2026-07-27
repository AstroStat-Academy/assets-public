def clone_and_cd_colab() -> None:
    import json
    import os
    import re
    import sys
    import subprocess
    from pathlib import Path
    from urllib.parse import unquote, urlparse

    if "google.colab" not in sys.modules:
        print("Running locally, skipping Colab setup.")
        return

    try:
        import ipynbname
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "ipynbname"],
            check=True,
        )
        import ipynbname

    def decode_repeatedly(value: object) -> str:
        text = str(value)

        for _ in range(5):
            decoded = unquote(text)

            if decoded == text:
                break

            text = decoded

        return text.replace("\\/", "/").replace("\\u002F", "/")

    def extract_github_info(value: object):
        text = decode_repeatedly(value)

        prefixes = (
            "https://colab.research.google.com/github/",
            "http://colab.research.google.com/github/",
        )

        for prefix in prefixes:
            text = text.replace(prefix, "https://github.com/")

        patterns = (
            r"https?://github\.com/"
            r"(?P<owner>[^/\s\"'<>?&]+)/"
            r"(?P<repo>[^/\s\"'<>?&]+?)(?:\.git)?/"
            r"blob/"
            r"(?P<branch>[^/\s\"'<>?&]+)/"
            r"(?P<path>[^\s\"'<>?&#]+?\.ipynb)",

            r"github\.com/"
            r"(?P<owner>[^/\s\"'<>?&]+)/"
            r"(?P<repo>[^/\s\"'<>?&]+?)(?:\.git)?/"
            r"blob/"
            r"(?P<branch>[^/\s\"'<>?&]+)/"
            r"(?P<path>[^\s\"'<>?&#]+?\.ipynb)",
        )

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)

            if match:
                owner = match.group("owner")
                repo = match.group("repo").removesuffix(".git")
                branch = match.group("branch")
                notebook_path = match.group("path")

                return {
                    "repo_url": f"https://github.com/{owner}/{repo}.git",
                    "repo_name": repo,
                    "branch": branch,
                    "notebook_path": notebook_path,
                }

        if "/blob/" in text:
            candidate = text

            if "fileId=" in candidate:
                candidate = candidate.split("fileId=", 1)[1]

            github_index = candidate.find("https://github.com/")

            if github_index >= 0:
                candidate = candidate[github_index:]

            candidate = candidate.split("#", 1)[0]
            candidate = candidate.split("?", 1)[0]

            try:
                before, after = candidate.split("/blob/", 1)
                parsed = urlparse(before)
                parts = [part for part in parsed.path.split("/") if part]

                if parsed.netloc == "github.com" and len(parts) >= 2:
                    owner = parts[0]
                    repo = parts[1].removesuffix(".git")
                    branch, notebook_path = after.split("/", 1)

                    notebook_match = re.search(
                        r"(.+?\.ipynb)",
                        notebook_path,
                        flags=re.IGNORECASE,
                    )

                    if notebook_match:
                        notebook_path = notebook_match.group(1)

                        return {
                            "repo_url": f"https://github.com/{owner}/{repo}.git",
                            "repo_name": repo,
                            "branch": branch,
                            "notebook_path": notebook_path,
                        }
            except Exception:
                pass

        return None

    candidates = []

    for getter in (
        lambda: ipynbname.name(),
        lambda: ipynbname.path(),
    ):
        try:
            candidates.append(getter())
        except Exception:
            pass

    try:
        from google.colab import _message

        for request_name in (
            "get_ipynb",
            "get_notebook_info",
        ):
            try:
                response = _message.blocking_request(request_name)
                candidates.append(response)
                candidates.append(json.dumps(response))
            except Exception:
                pass

        try:
            response = _message.blocking_request("get_ipynb")
            notebook = response.get("ipynb", response)

            candidates.append(notebook.get("metadata", {}))

            for cell in notebook.get("cells", []):
                candidates.append(cell.get("source", ""))
                candidates.append(cell.get("metadata", {}))
                candidates.append(cell.get("outputs", []))
        except Exception:
            pass

    except Exception:
        pass

    for key, value in os.environ.items():
        if any(
            token in key.upper()
            for token in ("COLAB", "NOTEBOOK", "GITHUB", "IPYNB")
        ):
            candidates.append(value)

    info = None

    for candidate in candidates:
        if isinstance(candidate, (dict, list, tuple)):
            candidate = json.dumps(candidate)

        info = extract_github_info(candidate)

        if info is not None:
            break

    if info is None:
        raise RuntimeError(
            "Could not determine the source GitHub repository automatically."
        )

    repo_url = info["repo_url"]
    repo_name = info["repo_name"]
    branch = info["branch"]
    notebook_path = Path(info["notebook_path"])

    repo_path = Path("/content") / repo_name

    if repo_path.exists():
        if not (repo_path / ".git").is_dir():
            raise FileExistsError(
                f"{repo_path} exists but is not a Git repository."
            )

        subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "origin", branch],
            check=True,
        )

        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", branch],
            check=True,
        )

        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "reset",
                "--hard",
                f"origin/{branch}",
            ],
            check=True,
        )

    else:
        subprocess.run(
            [
                "git",
                "clone",
                "--branch",
                branch,
                "--single-branch",
                repo_url,
                str(repo_path),
            ],
            check=True,
        )

    target = (repo_path / notebook_path.parent).resolve()

    if not target.is_dir():
        matches = list(repo_path.rglob(notebook_path.name))

        if len(matches) == 1:
            target = matches[0].parent.resolve()
        else:
            raise FileNotFoundError(
                f"Notebook directory does not exist: {target}"
            )

    os.chdir(target)

    print("Repository:")
    print(
        subprocess.check_output(
            ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
            text=True,
        ).strip()
    )

    print("\nBranch:")
    print(
        subprocess.check_output(
            ["git", "-C", str(repo_path), "branch", "--show-current"],
            text=True,
        ).strip()
    )

    print("\nWorking in:")
    print(target)

    print("\nContent:")
    print("\t", sorted(os.listdir(".")))


clone_and_cd_colab()
