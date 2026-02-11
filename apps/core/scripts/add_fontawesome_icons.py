"""
Populate Icon table with FontAwesome icons by parsing the CSS.

Usage:
  python scripts/add_fontawesome_icons.py [--css PATH] [--library NAME] [--dry-run]

Defaults:
  --css apps/core/static/core/css/fontawesome.min.css
  --library fontawesome

This script expects Django settings at config.settings.
"""

import argparse
import os
import re
import sys


def setup_django():
    # Ensure project root is on sys.path so 'config' is importable
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django  # noqa: F401

        django.setup()
    except Exception as e:
        print(f"Failed to setup Django: {e}")
        sys.exit(1)


def parse_fontawesome_css(css_text):
    """
    Extract icon class names and optional unicode values from FontAwesome CSS.

    Returns list of dicts: {name: 'fa-users', unicode: 'f0c0'}
    """
    icons = {}

    # Font Awesome 6 pattern: .fa-<name>{ --fa:"\fxxx" }
    pattern_var = re.compile(
        r"\.fa-([a-z0-9-]+)\s*\{[^}]*--fa\s*:\s*([\"\'])(\\?[a-fA-F0-9]+)\2",
        re.IGNORECASE,
    )

    for match in pattern_var.finditer(css_text):
        icon_name = match.group(1)
        unicode_raw = match.group(3)
        unicode_val = unicode_raw.lstrip("\\")

        # Exclude non-icon utility/style classes that start with fa-
        if icon_name in {
            "solid",
            "regular",
            "brands",
            "classic",
            "sharp",
            "thin",
            "light",
            "duotone",
            "fw",
            "li",
            "border",
            "pull-left",
            "pull-right",
            "spin",
            "pulse",
            "rotate-90",
            "rotate-180",
            "rotate-270",
            "flip-horizontal",
            "flip-vertical",
            "stack",
            "inverse",
        }:
            continue

        full_class = f"fa-{icon_name}"
        # De-duplicate; last seen wins, but only one record stored
        icons[full_class] = unicode_val

    # Fallback for older FA versions: .fa-<name>:before { content:"\fxxx" }
    if not icons:
        pattern_before = re.compile(
            r"\.fa-([a-z0-9-]+)\s*:(?:before|after)\s*\{[^}]*content\s*:\s*([\"\'])(\\?[a-fA-F0-9]+)\1",
            re.IGNORECASE,
        )
        for match in pattern_before.finditer(css_text):
            icon_name = match.group(1)
            unicode_raw = match.group(3)
            unicode_val = unicode_raw.lstrip("\\")
            if icon_name in {
                "solid",
                "regular",
                "brands",
                "classic",
                "sharp",
                "thin",
                "light",
                "duotone",
                "fw",
                "li",
                "border",
                "pull-left",
                "pull-right",
                "spin",
                "pulse",
                "rotate-90",
                "rotate-180",
                "rotate-270",
                "flip-horizontal",
                "flip-vertical",
                "stack",
                "inverse",
            }:
                continue
            full_class = f"fa-{icon_name}"
            icons[full_class] = unicode_val

    # Convert to list of dicts
    result = []
    for name, unicode_val in icons.items():
        # Create display name from class (remove fa- prefix, replace dashes with spaces, title case)
        disp = name[3:].replace("-", " ").title()
        result.append({"name": name, "display_name": disp, "unicode_char": unicode_val})
    return result


def save_icons(records, library, dry_run=False):
    from apps.core.models import Icon

    created = 0
    updated = 0
    for rec in records:
        name = rec["name"]
        defaults = {
            "display_name": rec["display_name"],
            "unicode_char": rec.get("unicode_char", ""),
            "category": "",
            "library": library,
        }
        if dry_run:
            print(f"DRY RUN: would upsert {library}:{name} -> {defaults}")
            continue

        obj, was_created = Icon.objects.update_or_create(
            library=library,
            name=name,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return created, updated


def main():
    parser = argparse.ArgumentParser(description="Populate icons from FontAwesome CSS")
    parser.add_argument(
        "--css",
        default="apps/core/static/css/fontawesome.min.css",
        help="Path to fontawesome.min.css",
    )
    parser.add_argument(
        "--library",
        default="fontawesome",
        help="Icon library name to store with records",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and show actions without writing to DB",
    )
    args = parser.parse_args()

    # Read CSS
    if not os.path.exists(args.css):
        print(f"CSS file not found: {args.css}")
        sys.exit(2)

    with open(args.css, "r", encoding="utf-8", errors="ignore") as f:
        css_text = f.read()

    records = parse_fontawesome_css(css_text)
    print(f"Parsed {len(records)} icon entries from CSS")

    setup_django()
    created, updated = save_icons(records, args.library, dry_run=args.dry_run)
    if args.dry_run:
        print("Dry run complete.")
    else:
        print(f"Icons upserted. Created: {created}, Updated: {updated}")


if __name__ == "__main__":
    main()
