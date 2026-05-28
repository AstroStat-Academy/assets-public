def clone_and_cd_colab() -> None:
    """
    Clone the GitHub repository from which the notebook was opened
    and move into the notebook subfolder when running in Google Colab.

    Returns
    -------
    None
    """

    import os
    import sys
    import subprocess
    from pathlib import Path
    from urllib.parse import unquote

    if "google.colab" not in sys.modules:
        print('Running locally, skipping Colab setup.')
        return

    try:
        import ipynbname

    except ImportError:

        subprocess.run(
            ["pip", "-q", "install", "ipynbname"],
            check=True
        )

        import ipynbname

    s = unquote(ipynbname.name())
    url = s.split("fileId=")[-1]

    before, after = url.split("/blob/", 1)

    repo_url = before + ".git"

    branch, notebook_path = after.split("/", 1)

    repo_name = Path(before).name
    subfolder = Path(notebook_path).parent

    if not Path(f"/content/{repo_name}").exists():

        subprocess.run(
            [
                "git",
                "clone",
                "-b",
                branch,
                repo_url
            ],
            check=True
        )

    target = f"/content/{repo_name}/{subfolder}"

    print("Working in:")
    print(target)

    os.chdir(target)

    print("\nContent:")
    print("\t", sorted(os.listdir(".")))

clone_and_cd_colab()