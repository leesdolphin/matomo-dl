import os
import pathlib
import shutil
import subprocess
import sys
import typing as typ

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
# Use committer time, change to `%at` to use author time.
GIT_TIME_FORMAT = "%ct"


def run_output(
    cmd: typ.Sequence[str], *, check: bool = True, universal_newlines: bool = True, **k
):
    return subprocess.run(
        cmd,
        check=check,
        universal_newlines=universal_newlines,
        stdout=subprocess.PIPE,
        **k,
    ).stdout.strip()


def repo_mtime(
    file: typ.Union[None, str, pathlib.Path] = None,
    *,
    file_default: typ.Optional[int] = None,
) -> int:
    cmd = ["git", "log", "-1", f"--format={GIT_TIME_FORMAT}"]
    if file is not None:
        cmd += ["--", str(file)]
    out = run_output(cmd)
    if out:
        return int(out)
    elif file_default is not None:
        return file_default
    else:
        raise ValueError(
            f"File {file!r} does not exist in the repo, and there is no default to use."
        )


def get_version_info() -> typ.Tuple[str, str]:
    full_tag = run_output(["git", "describe", "--long"])
    assert full_tag and full_tag[0] == "v"
    tag_commit, _, sha = full_tag[1:].rpartition("-")
    tag, _, commit_count = tag_commit.rpartition("-")
    if commit_count == "0":
        # Tagged
        return tag, sha
    else:
        # 'beta'
        return f"{tag}.b{commit_count}", sha


def get_build_time(sha: str):
    if "SOURCE_DATE_EPOCH" in os.environ:
        return int(os.environ["SOURCE_DATE_EPOCH"])
    else:
        return int(repo_mtime())


def fix_times(timestamp: int, folder: pathlib.Path = REPO_ROOT) -> int:
    most_recent_time = 0
    for item in folder.iterdir():
        item_mtime = item.stat().st_mtime
        if item.is_dir():
            mtime = fix_times(timestamp, item)
            # Directory's mtime is the largest mtime in it.
            if mtime <= 0:
                mtime = timestamp
        elif item.is_file():
            mtime = repo_mtime(item, file_default=item_mtime)
        else:
            continue
        mtime = min(timestamp, mtime)
        if item_mtime != mtime:
            os.utime(item, times=(mtime, mtime))
        most_recent_time = max(most_recent_time, mtime)
    return most_recent_time


def do_multistage_release(file_paths: typ.Iterable[pathlib.Path]):
    files = sorted(map(str, file_paths))
    subprocess.run(["pip", "hash"] + files, check=True)

    # We need to keep all the environmant variables that aren't related to twine
    # so that python path and the like is passed through.
    base_env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("TWINE_")
    }
    release_env = {
        name: value
        for name, value in os.environ.items()
        if (
            name not in base_env
            and name.startswith("TWINE_")
            and not name.startswith("TWINE_TEST_")
        )
    }
    test_env = {
        name.replace("TWINE_TEST_", "TWINE_"): value
        for name, value in os.environ.items()
        if name not in base_env and name.startswith("TWINE_TEST_")
    }
    if not test_env and not release_env:
        print(
            "Not releasing code. Specify a `TWINE_TEST_` or a `TWINE_` "
            "variable to enable test and production releases respectively"
        )
    if test_env:
        # Any variable starting with `TWINE_TEST_` indicates a test upload
        # should be done
        env = dict(release_env)
        env.update(test_env)
        env.update(base_env)
        if "TWINE_REPOSITORY_URL" in env:
            assert env["TWINE_REPOSITORY_URL"] != release_env["TWINE_REPOSITORY_URL"], (
                "Refusing to test upload to the release server. "
                "Set `TWINE_TEST_REPOSITORY_URL` or unset `TWINE_REPOSITORY_URL`"
            )
        else:
            env["TWINE_REPOSITORY_URL"] = "https://test.pypi.org/legacy/"
        subprocess.run(["twine", "upload"] + files, check=True, env=env)
    if release_env:
        env = dict(release_env)
        env.update(base_env)
        if "TWINE_REPOSITORY_URL" not in env:
            env["TWINE_REPOSITORY_URL"] = "https://upload.pypi.org/legacy/"
        subprocess.run(["twine", "upload"] + files, check=True, env=env)


def main():
    tag, sha = get_version_info()
    build_time = get_build_time(sha)
    version_path = REPO_ROOT / "matomo_dl/__version__.py"
    old_version_content = version_path.read_text()
    try:
        version_path.write_text(f'# Autogenerated from {sha}\n__version__ = "{tag}"\n')
        fix_times(build_time)
        for folder in [REPO_ROOT / "build", REPO_ROOT / "dist"]:
            if folder.exists():
                shutil.rmtree(folder)
        subprocess.run(
            [sys.executable, "setup.py", "sdist", "bdist_wheel"],
            check=True,
            env={"SOURCE_DATE_EPOCH": str(build_time)},
        )
        wheels = []
        tarballs = []
        for item in (REPO_ROOT / "dist").iterdir():
            if item.suffix == ".whl":
                # Already consistent
                wheels.append(item)
            if ".tar" in item.suffixes:
                # Not reproducable. but meh.
                tarballs.append(item)
        if os.environ.get("CI") or "upload" in sys.argv:
            do_multistage_release(wheels + tarballs)
        else:
            print(
                "Refusing to upload without explicit command(add a `upload` argument) "
                "or running in CI(set the `CI` environment variable.)"
            )
    finally:
        version_path.write_text(old_version_content)


if __name__ == "__main__":
    main()
