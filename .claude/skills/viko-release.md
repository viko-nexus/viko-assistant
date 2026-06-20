---
name: viko-release
description: Build a release .app bundle and create a GitHub release for VIKO.
---

# VIKO Release

## Pre-release Checklist

- [ ] All tests pass: `python -m pytest tests/ -v`
- [ ] Lint passes: `ruff check viko/ viko.py`
- [ ] Version bumped in `setup.py` (if applicable)
- [ ] `CHANGELOG` or release notes prepared

## Build the .app Bundle

```bash
./scripts/build.sh
```

This runs: ruff lint → PyInstaller → QtWebEngine path patch → `dist/VIKO.app`

Verify the build:
```bash
open dist/VIKO.app
```

VIKO should launch. Test voice, browser panel, and one tool call.

## Create a GitHub Release

```bash
# 1. Tag the release
git tag v<version> -m "Release v<version>"
git push origin v<version>

# 2. Create the release with gh CLI
gh release create v<version> \
  --title "VIKO v<version>" \
  --notes "$(cat <<'EOF'
## What's new

- <change 1>
- <change 2>

## Requirements

- macOS 13+
- Python 3.11+
- Google Gemini API key

## Setup

See [README.md](https://github.com/viko-nexus/viko-assistant#setup) for installation instructions.
EOF
)"
```

## Version Naming

- `v0.x.0` — minor feature release (new skill, new UI component)
- `v0.x.y` — patch release (bug fix, no new features)
- `v1.0.0` — first stable public release

## Notes

- The `dist/VIKO.app` bundle is ~200 MB — do not commit it to git (`dist/` is gitignored)
- Never commit `.env` — the `.app` bundle reads env vars from `~/.env` or the working directory
- If build fails with `QtWebEngine` errors: `./scripts/build.sh` handles the path patching automatically
