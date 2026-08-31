#!/usr/bin/env python3
"""
Release-gate verification used by CI (and runnable locally before tagging).

Two independent checks, run separately so a failure clearly states which
release requirement was violated:

  verify_release.py versions [--tag vX.Y.Z]
      pyproject.toml [project.version], the __init__.py fallback
      __version__, and the latest CHANGELOG.md entry must all agree.
      With --tag, the tag (vX.Y.Z) must also match.

  verify_release.py package <path-to-wheel-or-sdist> [...]
      Each archive must contain the netbox_ip_history package, its
      migrations, templates, locale files, management commands, and
      (sdist only) LICENSE.

Exit status is non-zero on any mismatch; CI treats that as a release gate
failure. This script ships only in the source tree (see pyproject.toml
`tool.setuptools.packages.find` excludes `tools*`) and is never installed.
"""
from __future__ import annotations

import argparse
import re
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read_pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit("FAIL: could not find [project].version in pyproject.toml")
    return m.group(1)


def _read_init_fallback_version() -> str:
    text = (ROOT / "netbox_ip_history" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'(?m)^\s*__version__\s*=\s*"([^"]+)"\s*$', text)
    if not m:
        raise SystemExit("FAIL: could not find fallback __version__ in netbox_ip_history/__init__.py")
    return m.group(1)


def _read_latest_changelog_version() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"(?m)^## \[(\d+\.\d+\.\d+)\]", text)
    if not m:
        raise SystemExit("FAIL: could not find a '## [X.Y.Z]' entry in CHANGELOG.md")
    return m.group(1)


def check_versions(tag: str | None) -> int:
    pyproject_v = _read_pyproject_version()
    init_v = _read_init_fallback_version()
    changelog_v = _read_latest_changelog_version()

    problems = []
    if pyproject_v != init_v:
        problems.append(
            f"pyproject.toml version ({pyproject_v}) != netbox_ip_history/__init__.py fallback __version__ ({init_v})"
        )
    if pyproject_v != changelog_v:
        problems.append(
            f"pyproject.toml version ({pyproject_v}) != latest CHANGELOG.md entry ([{changelog_v}])"
        )
    if tag is not None:
        tag_v = tag[1:] if tag.startswith("v") else tag
        if tag_v != pyproject_v:
            problems.append(f"git tag ({tag}) != pyproject.toml version ({pyproject_v})")

    if problems:
        print("FAIL: version metadata is inconsistent:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"OK: version {pyproject_v} is consistent across pyproject.toml, __init__.py, and CHANGELOG.md"
          + (f", and matches tag {tag}" if tag else ""))
    return 0


REQUIRED_WHEEL_SUBSTRINGS = [
    "netbox_ip_history/__init__.py",
    "netbox_ip_history/models.py",
    "netbox_ip_history/migrations/0001_initial.py",
    "netbox_ip_history/templates/",
    "netbox_ip_history/locale/",
    "netbox_ip_history/management/commands/import_ip_history.py",
    "netbox_ip_history/management/commands/sync_netbox_ip_history.py",
    ".dist-info/METADATA",
]

REQUIRED_SDIST_SUBSTRINGS = [
    "netbox_ip_history/__init__.py",
    "netbox_ip_history/models.py",
    "netbox_ip_history/migrations/0001_initial.py",
    "netbox_ip_history/templates/",
    "netbox_ip_history/locale/",
    "netbox_ip_history/management/commands/import_ip_history.py",
    "LICENSE",
    "PKG-INFO",
]


def _archive_names(path: Path) -> list[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as zf:
            return zf.namelist()
    if path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as tf:
            return tf.getnames()
    raise SystemExit(f"FAIL: unrecognized archive type: {path}")


def check_package(paths: list[str]) -> int:
    overall_ok = True
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            print(f"FAIL: {path} does not exist")
            overall_ok = False
            continue

        names = _archive_names(path)
        required = REQUIRED_WHEEL_SUBSTRINGS if path.suffix == ".whl" else REQUIRED_SDIST_SUBSTRINGS

        missing = [
            req for req in required
            if not any(req in name for name in names)
        ]
        if missing:
            print(f"FAIL: {path.name} is missing required content:")
            for m in missing:
                print(f"  - {m}")
            overall_ok = False
        else:
            print(f"OK: {path.name} contains all {len(required)} required paths ({len(names)} entries total)")

    return 0 if overall_ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_versions = sub.add_parser("versions", help="Check version consistency across the repo")
    p_versions.add_argument("--tag", default=None, help="Git tag (e.g. v0.3.1) to also validate against")

    p_package = sub.add_parser("package", help="Check built wheel/sdist contents")
    p_package.add_argument("paths", nargs="+", help="Path(s) to .whl / .tar.gz files")

    args = parser.parse_args()

    if args.command == "versions":
        return check_versions(args.tag)
    if args.command == "package":
        return check_package(args.paths)
    return 1


if __name__ == "__main__":
    sys.exit(main())
