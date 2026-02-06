# GitHub Copilot Repository Instructions

These instructions help Copilot and agents work optimally with this repository.

## Project Overview
- This repository is a modular Flask web app for downloading YouTube videos and audio using yt-dlp.
- Package structure:
  - youtube_napoletano/: Main Python package
    - app.py: Flask app, routes, Neapolitan messages
    - downloader.py: yt-dlp logic and progress parsing
    - utils.py: update checks and helpers
    - config.py: configuration (paths, environment)
  - youtube_napoletano.py: Entry point script (imports from package)
  - tests/: pytest test suite for all modules
  - templates/: HTML templates
  - static/: JS and static assets
  - config.py.example: Example configuration file

## Imports & Structure
- All core logic is in the `youtube_napoletano/` package
- Use absolute imports: `from youtube_napoletano.module import function`
- Tests import from the package: `from youtube_napoletano.downloader import parse_progress`
- Entry point (youtube_napoletano.py) imports app from package
- Configuration lives in youtube_napoletano/config.py (copy from config.py.example)

## Coding Standards
- Always use Test-Driven Development (TDD): write tests before implementing features.
- All code must comply with PEP8 style guidelines.
- Use type annotations everywhere.
- Modularize code: keep logic separated in downloader.py, utils.py, etc.
- Validate all user input and handle errors gracefully.
- Write clear, descriptive docstrings for all functions and classes.
- Favor composition over inheritance; keep functions small and focused.
- User-facing messages must be in Neapolitan dialect (see youtube_napoletano.py).

## Build & Validation Steps
- Python 3.12+ required. Always use a venv.
- Install dependencies: `python3.12 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt`
- Lint: `make lint` or `.venv/bin/ruff check .`
- Format: `make format` or `.venv/bin/ruff format .`
- Test: `make test` or `.venv/bin/python -m pytest` (ensure venv is activated).
- Run: `make run` or `.venv/bin/python youtube_napoletano.py`
- Clean: `make clean` or remove .venv and __pycache__ folders.
- All pushes and PRs must pass CI (lint, format, test).

## Agent Guidance
- Prefer composition over inheritance.
- Modularize logic (never mix config, business logic, and UI).
- Document reasoning in commit messages.
- If unsure, search README.md and config.py for guidance.
- Always check .gitignore before adding new files (downloads/ is ignored).

## Error Handling & User Experience
- All user-facing errors must be in Neapolitan dialect.
- Validate all user input (especially URLs).

## Testing & Quality
- All new features must have tests.
- Tests should cover edge cases and error handling.
- Run tests in venv before every commit.

## Code Style & Documentation
- Use type annotations everywhere.
- Write docstrings for all functions and classes.
- Keep functions small and focused.

## Common Pitfalls
- yt-dlp path: must point to .venv/bin/yt-dlp (see youtube_napoletano/config.py)
- venv activation: always activate before running commands
- Makefile quirks: VENV variable can be overridden
- Import structure: use `from youtube_napoletano.module import ...` for all package imports
- Config file: copy config.py.example to youtube_napoletano/config.py before running

## Contribution Etiquette
- Encourage clear, descriptive PRs and issues.
- Reference related issues or discussions in PRs.

## CI Pipeline
- All pushes and pull requests are checked for lint, formatting, and tests via GitHub Actions.

---

For more information, see [Copilot repository instructions documentation](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions).
