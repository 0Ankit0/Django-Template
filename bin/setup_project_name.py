#!/usr/bin/env python3
"""Initialize a project created from the Django template."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


OLD_NAME = "django_template"
ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "staticfiles",
    "media",
}

TEXT_EXTENSIONS = {
    ".py",
    ".pyi",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".conf",
    ".md",
    ".rst",
    ".txt",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".sh",
    ".bash",
    ".env",
    ".example",
    ".xml",
    ".po",
    ".pot",
    ".sql",
}


def get_repository_name() -> str | None:
    """Get the repository name from the Git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    remote = result.stdout.strip()

    match = re.search(r"/([^/]+?)(?:\.git)?$", remote)

    if not match:
        match = re.search(r":([^/]+?)(?:\.git)?$", remote)

    return match.group(1) if match else None


def make_python_package_name(name: str) -> str:
    """Convert a project/repository name into a valid Python package name."""
    name = name.strip().lower()

    # Replace hyphens, spaces, dots, etc. with underscores.
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", name)

    # Collapse multiple underscores.
    name = re.sub(r"_+", "_", name)

    # Remove underscores at the beginning/end.
    name = name.strip("_")

    # Python package names cannot start with a number.
    if name and name[0].isdigit():
        name = f"project_{name}"

    if not name:
        raise ValueError("Please provide a valid project name.")

    return name


def should_skip(path: Path) -> bool:
    """Return whether a path should be skipped."""
    return any(part in SKIP_DIRS for part in path.parts)


def is_text_file(path: Path) -> bool:
    """Return whether a file should be treated as text."""
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True

    return path.name in {
        "Dockerfile",
        "Procfile",
        "Makefile",
        "justfile",
        ".gitignore",
        ".dockerignore",
        ".editorconfig",
    }


def replace_references(old_name: str, new_name: str) -> None:
    """Replace references to the old package name."""
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        if should_skip(path):
            continue

        if not is_text_file(path):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        if old_name not in content:
            continue

        new_content = content.replace(old_name, new_name)

        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            print(f"Updated: {path.relative_to(ROOT)}")


def rename_package(old_name: str, new_name: str) -> None:
    """Rename the Django package directory."""
    old_path = ROOT / old_name
    new_path = ROOT / new_name

    if not old_path.exists():
        raise FileNotFoundError(
            f"Could not find {old_name!r} at {old_path}"
        )

    if new_path.exists():
        raise FileExistsError(
            f"Destination already exists: {new_path}"
        )

    shutil.move(str(old_path), str(new_path))


def main() -> None:
    print()
    print("=" * 60)
    print("Django Template Project Setup")
    print("=" * 60)
    print()

    repository_name = get_repository_name()

    if repository_name:
        default_name = make_python_package_name(repository_name)

        print(f"Detected repository: {repository_name}")
        print(f"Default package name: {default_name}")
    else:
        default_name = ""

        print("Could not detect the GitHub repository name.")

    print()

    if default_name:
        prompt = f"Python package name [{default_name}]: "
    else:
        prompt = "Python package name: "

    user_input = input(prompt).strip()

    # Pressing Enter accepts the detected repository name.
    new_name = user_input or default_name

    if not new_name:
        print("Error: a project name is required.")
        return

    new_name = make_python_package_name(new_name)

    if new_name == OLD_NAME:
        print("The new name cannot be 'django_template'.")
        return

    print()
    print(f"Renaming package:")
    print(f"  {OLD_NAME} → {new_name}")
    print()

    confirm = input("Continue? [y/N]: ").strip().lower()

    if confirm != "y":
        print("Cancelled.")
        return

    print()
    print("Renaming package...")
    rename_package(OLD_NAME, new_name)

    print()
    print("Updating references...")
    replace_references(OLD_NAME, new_name)

    print()
    print("=" * 60)
    print("Project setup complete!")
    print("=" * 60)
    print()
    print(f"Package name: {new_name}")
    print()
    print("Run:")
    print("  uv sync")
    print("  git status")
    print()


if __name__ == "__main__":
    main()