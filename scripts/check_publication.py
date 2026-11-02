"""Check publication paths and export review snapshots without private data."""

from __future__ import annotations

import argparse
import shutil
import stat
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = {
    ".env.example",
    ".gitignore",
    "MANIFEST.in",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "LICENSE",
    "LICENSE.md",
    "SECURITY.md",
    "knowledge/user_preference.example.txt",
}
PUBLIC_DIRECTORIES = ("src/scratch_project/", "tests/", "scripts/", ".github/")
PRIVATE_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "reports",
    "traces",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".vscode",
    ".idea",
    ".ssh",
    ".aws",
    ".azure",
    "build",
    "dist",
    "htmlcov",
}
PRIVATE_SUFFIXES = {
    ".log",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".bak",
    ".backup",
    ".orig",
    ".tmp",
    ".pyc",
    ".pyo",
}


def private_path(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or ":" in name:
        return True
    normalized = path.as_posix().lower()
    if normalized in {
        ".env.example",
        "knowledge/user_preference.example.txt",
    }:
        return False
    parts = tuple(part.lower() for part in path.parts)
    if not parts:
        return True
    leaf = parts[-1]
    return (
        any(part in PRIVATE_DIRECTORIES for part in parts)
        or parts[0] == "knowledge"
        or leaf.startswith((".env", "id_rsa", "id_ed25519", ".coverage"))
        or path.suffix.lower() in PRIVATE_SUFFIXES
        or leaf.endswith("~")
        or (leaf.endswith(".json") and ("credentials" in leaf or "secret" in leaf))
    )


def public_path(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/")).as_posix()
    return (
        not private_path(path)
        and not any(part.endswith(".egg-info") for part in path.split("/"))
        and (path in PUBLIC_FILES or path.startswith(PUBLIC_DIRECTORIES))
    )


def git_output(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            "Git check failed. Initialize/review a project-root repository "
            "before checking its index; no Git state was changed."
        )
    return result.stdout


def checked_index(root: Path) -> list[str]:
    git_root = Path(
        git_output(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()
    ).resolve()
    if git_root != root.resolve():
        raise ValueError("The project must be the Git repository root.")
    names = [
        name.decode("utf-8")
        for name in git_output(root, "ls-files", "-z").split(b"\0")
        if name
    ]
    if not names:
        raise ValueError("Empty index; stage only reviewed public files.")
    forbidden = [name for name in names if not public_path(name)]
    entries = git_output(root, "ls-files", "--stage", "-z").split(b"\0")
    if any(entry.startswith(b"120000 ") for entry in entries):
        raise ValueError("Publication symlinks are not permitted.")
    if forbidden:
        raise ValueError(
            "Private or unreviewed paths in the index:\n" + "\n".join(sorted(forbidden))
        )
    return names


def export_snapshot(root: Path, destination: Path, staged: bool = False) -> int:
    destination = destination.resolve()
    if destination.is_relative_to(root.resolve()):
        raise ValueError("Review snapshots must be outside the project.")
    if staged:
        names = checked_index(root)
    else:
        names = [name for name in PUBLIC_FILES if (root / name).is_file()]
        for directory in PUBLIC_DIRECTORIES:
            names.extend(
                path.relative_to(root).as_posix()
                for path in (root / directory).rglob("*")
                if path.is_file() and public_path(path.relative_to(root).as_posix())
            )
    destination.mkdir(parents=True, exist_ok=False)
    for name in sorted(set(names)):
        source = root / name
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError("Snapshot paths must stay inside the project.")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if staged:
            target.write_bytes(git_output(root, "show", f":{name}"))
        else:
            shutil.copyfile(source, target)
    return len(set(names))


def check_archives(directory: Path) -> int:
    archives = sorted(directory.glob("*.whl")) + sorted(directory.glob("*.tar.gz"))
    if not archives:
        raise ValueError("No wheel or source archives found.")
    for archive in archives:
        if archive.suffix == ".whl":
            with zipfile.ZipFile(archive) as package:
                names = [
                    item.filename for item in package.infolist() if not item.is_dir()
                ]
                symlinks = any(
                    stat.S_ISLNK(item.external_attr >> 16)
                    for item in package.infolist()
                )
            relative_names = names
        else:
            with tarfile.open(archive, "r:gz") as package:
                members = package.getmembers()
                names = [item.name for item in members if not item.isdir()]
                symlinks = any(item.issym() or item.islnk() for item in members)
            if any(
                PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                for name in names
            ):
                raise ValueError(f"Unsafe archive paths in {archive.name}")
            relative_names = [name.partition("/")[2] for name in names if "/" in name]
        forbidden = [name for name in relative_names if private_path(name)]
        if symlinks or forbidden:
            raise ValueError(f"Private paths or symlinks in {archive.name}")
        for config in ("agents.yaml", "tasks.yaml"):
            if not any(
                name.endswith(f"scratch_project/config/{config}") for name in names
            ):
                raise ValueError(f"Missing {config} in {archive.name}")
    return len(archives)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--snapshot", type=Path)
    mode.add_argument("--staged-snapshot", type=Path)
    mode.add_argument("--archives", type=Path)
    arguments = parser.parse_args(argv)
    try:
        if arguments.snapshot or arguments.staged_snapshot:
            count = export_snapshot(
                ROOT,
                arguments.snapshot or arguments.staged_snapshot,
                staged=arguments.staged_snapshot is not None,
            )
            print(f"Exported {count} candidate files for secret scanning.")
        elif arguments.archives:
            count = check_archives(arguments.archives)
            print(f"Checked {count} package archives.")
        else:
            count = len(checked_index(ROOT))
            print(f"Checked {count} indexed publication paths.")
    except (
        ValueError,
        OSError,
        UnicodeError,
        subprocess.SubprocessError,
    ) as error:
        parser.exit(1, f"Publication check failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
