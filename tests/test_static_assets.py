"""Tests for static assets: JS syntax, HTML validity, etc."""

import subprocess
from pathlib import Path


def test_javascript_syntax_valid():
    """Ensure static/app.js has no syntax errors."""
    app_js = Path(__file__).parent.parent / "static" / "app.js"
    assert app_js.exists(), f"app.js not found at {app_js}"

    result = subprocess.run(
        ["node", "-c", str(app_js)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"JS syntax error in app.js:\n{result.stderr}"


def test_app_js_no_unescaped_neapolitan_quotes():
    """Ensure JS strings don't have unescaped Neapolitan apostrophes.

    Neapolitan text uses ' characters that must be escaped or quoted properly
    to avoid breaking JavaScript string literals.
    """
    app_js = Path(__file__).parent.parent / "static" / "app.js"
    content = app_js.read_text(encoding="utf-8")

    # Ensure all single-quoted and double-quoted strings are properly balanced.
    # This catches broken Neapolitan text in strings where apostrophes aren't escaped.
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        # Skip comment lines and lines without single quotes
        if "//" in line or "'" not in line:
            continue

        # Count unescaped single quotes in the line
        # This is a simple check; a real parser would be better
        in_double_quotes = False
        in_single_quotes = False
        j = 0
        while j < len(line):
            char = line[j]

            # Handle escape sequences
            if char == "\\" and j + 1 < len(line):
                j += 2
                continue

            # Track quote state
            if char == '"' and not in_single_quotes:
                in_double_quotes = not in_double_quotes
            elif char == "'" and not in_double_quotes:
                in_single_quotes = not in_single_quotes

            j += 1

        # If we ended in a quote state, something is broken
        assert not in_single_quotes, f"Line {i} has unclosed single quote:\n{line}"
        assert not in_double_quotes, f"Line {i} has unclosed double quote:\n{line}"


def test_html_template_exists():
    """Ensure index.html exists."""
    html = Path(__file__).parent.parent / "templates" / "index.html"
    assert html.exists(), f"index.html not found at {html}"


def test_html_has_required_elements():
    """Ensure index.html has required structural elements."""
    html = Path(__file__).parent.parent / "templates" / "index.html"
    content = html.read_text(encoding="utf-8")

    required_ids = [
        "downloadForm",
        "urlInput",
        "progressContainer",
        "messageBox",
        "topbar",
        "metaCard",
    ]

    for elem_id in required_ids:
        assert f'id="{elem_id}"' in content, f"Missing HTML element with id='{elem_id}'"
