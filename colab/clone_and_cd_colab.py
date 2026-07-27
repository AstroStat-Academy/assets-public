def clone_and_cd_colab() -> None:
    """
    Detect the source GitHub repository, clone it, and move into the notebook
    subfolder when running in Google Colab.

    Detection works when:
    - the notebook is opened directly from GitHub/Jupyter Book; or
    - a Drive copy still contains its original GitHub/Colab source link.
    """

    import json
    import os
    import re
    import sys
    import subprocess
    from pathlib import Path
    from urllib.parse import unquote

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

    candidates = [unquote(str(ipynbname.name()))]

    try:
        from google.colab import _message

        response = _message.blocking_request("get_ipynb")
        notebook = response.get("ipynb", response)

        candidates.append(json.dumps(notebook))

        for cell in notebook.get("cells", []):
            source = cell.get("source", "")
            if isinstance(source, list):
                source = "".join(source)
            candidates.append(source)

    except Exception:
        pass

    patterns = [
        re.compile(
            r"https?://colab\.research\.google\.com/github/"
            r"([^/\s\"'<>]+)/([^/\s\"'<>]+)/blob/"
            r"([^/\s\"'<>]+)/([^\s\"'<>?#]+\.ipynb)"
        ),
        re.compile(
            r"https?://github\.com/"
            r"([^/\s\"'<>]+)/([^/\s\"'<>]+)/blob/"
            r"([^/\s\"'<>]+)/([^\s\"'<>?#]+\.ipynb)"
        ),
    ]

    match = None

    for candidate in candidates:
        candidate = unquote(candidate)

        for pattern in patterns:
            match = pattern.search(candidate)

            if match:
                break

        if match:
            break

    if match is None:
        raise RuntimeError(
            "Cannot determine the source GitHub repository automatically. "
            "The Drive copy does not contain an original GitHub or Colab link."
        )

    owner, repo_name, branch, notebook_path = match.groups()

    repo_name = repo_name.removesuffix(".git")
    repo_url = f"https://github.com/{owner}/{repo_name}.git"
    repo_path = Path("/content") / repo_name
    subfolder = Path(notebook_path).parent

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

    repo_url = subprocess.check_output(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        text=True,
    ).strip()

    branch = subprocess.check_output(
        ["git", "-C", str(repo_path), "branch", "--show-current"],
        text=True,
    ).strip()

    target = (repo_path / subfolder).resolve()

    if not target.is_dir():
        raise FileNotFoundError(
            f"Notebook directory does not exist: {target}"
        )

    os.chdir(target)

    print("Repository:")
    print(repo_url)

    print("\nBranch:")
    print(branch)

    print("\nWorking in:")
    print(target)

    print("\nContent:")
    print("\t", sorted(os.listdir(".")))


clone_and_cd_colab()
