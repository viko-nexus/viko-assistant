# Development Guide

## Prerequisites

- Python 3.11+
- macOS 13+ (primary platform; Windows partially supported)
- [uv](https://docs.astral.sh/uv/) or `pip` for package management
- Google Gemini API key (required)
- Anthropic API key (optional — enables Claude for code generation)

## First-time Setup

```bash
git clone git@github.com:viko-nexus/viko-assistant.git
cd viko-assistant

# Install dependencies (setup.py handles venv creation)
python setup.py

# Configure environment
cp .env.example .env
# Edit .env and fill in your API keys
```

## Running VIKO

```bash
# Dev mode (shows logs in terminal)
./scripts/start.sh

# Background with log file
nohup .venv/bin/python -u viko.py > /tmp/viko.log 2>&1 &

# Monitor logs
tail -f /tmp/viko.log

# Release mode (opens built .app bundle)
./scripts/start.sh --app
```

## Tests

```bash
# All tests (59 total) — must all pass before committing
python -m pytest tests/ -v

# By category
python -m pytest tests/core/ -v           # VAD, wake-word (14 tests)
python -m pytest tests/self_engineer/ -v  # self-modification pipeline (29 tests)

# Single file
python -m pytest tests/self_engineer/test_engine_state.py -v
```

## Linting

```bash
# Check (safe issues only)
ruff check viko/ viko.py

# Auto-fix safe issues
ruff check viko/ viko.py --select F401,F811,F841 --fix
```

ruff config is in `ruff.toml`. The main rules: no unused imports (`F401`), no redefinitions (`F811`), no unused variables (`F841`).

## Adding a New Skill

See `.claude/skills/add-skill.md` or the [add-skill](../.claude/skills/add-skill.md) Claude skill for the complete step-by-step checklist.

Quick summary:
1. Create `viko/skills/<name>.py` with `def <name>(parameters, player=None, speak=None) -> str`
2. Import in `viko.py`
3. Add to `TOOL_DECLARATIONS` in `viko.py`
4. Add handler in `_execute_tool()` in `viko.py`
5. Verify import, run tests, commit

## Self-Modification Pipeline

VIKO can modify its own source code via the `self_update` skill. The pipeline is a two-gate state machine:

```
Gate 1: Plan confirmation
  "Viko, add a skill to check Bitcoin price"
  → VIKO: "I'll create crypto_price.py in viko/skills/. Proceed?"
  → User: "ya"

Gate 2: Restart confirmation
  → VIKO generates code, creates backup, applies changes, runs tests
  → VIKO: "Tests passed. Restart now?"
  → User: "ya restart"
  → VIKO restarts via os.execv, announces "Updated and ready."
```

Rollback is automatic if tests fail. Manual rollback via `restore_latest()` in `viko.self_engineer.backup`.

Use `/self-engineer-debug` Claude skill to inspect stuck states or force a rollback.

## Building the .app Bundle

```bash
./scripts/build.sh
```

This runs:
1. `ruff check` — lint (fails build on error)
2. `pyinstaller VIKO.spec` — bundle into `dist/VIKO.app`
3. QtWebEngine path fix — patches `Info.plist` for Chromium to work correctly

The bundle is ~200 MB. It is gitignored (`dist/` and `build/`).

Test the bundle before releasing:
```bash
open dist/VIKO.app
```

## Environment Variables

All config is in `.env`. See `.env.example` for the full list.

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key (voice agent) |
| `ANTHROPIC_API_KEY` | No | Claude for code generation (falls back to Gemini) |
| `OPENROUTER_API_KEY` | No | Alternative LLM provider |
| `OS_SYSTEM` | No | `mac` \| `windows` \| `linux` (default: `mac`) |
| `CAMERA_INDEX` | No | Webcam index (default: `0`) |
| `OWNER_PASSPHRASE` | No | Typed bypass for speaker verification |
| `VIKO_VOICE` | No | Gemini TTS voice (default: `Aoede`) |
| `VIKO_VOICE_LANG` | No | BCP-47 TTS language (default: `id-ID`) |
| `LATITUDE` / `LONGITUDE` | No | Fixed GPS coordinates for map/weather |
| `OLLAMA_MODEL` | No | Offline LLM model (default: `qwen2.5:1.5b`) |
| `VIKO_CDP_PORT` | No | Chrome DevTools Protocol port (default: `9222`) |
| `VIKO_MEMORY_RETENTION_DAYS` | No | Memory cutoff in days (default: `365`) |

## Code Style

- **Language**: English for all code, comments, docstrings, variable names
- **User-facing strings** (what VIKO says aloud): Indonesian
- **Type hints**: Use `| None` shorthand (Python 3.11+); avoid `Optional[T]`
- **Comments**: Only add when the WHY is non-obvious — not WHAT
- **Tests**: TDD for all testable modules. Tests go in `tests/` mirroring the source tree.
- No `print()` in library code — use `get_logger(__name__)` from `viko.core.logger`

## Project Structure

```
viko-assistant/
├── viko.py                  ← Main agent loop (entry point)
├── viko/
│   ├── prompt.txt           ← System prompt (VIKO's personality + tool rules)
│   ├── core/                ← 13 core modules (config, logger, memory, etc.)
│   ├── ui/                  ← PyQt6 UI (window, widgets, browser)
│   ├── skills/              ← 21 tool functions Gemini can call
│   ├── agent/               ← Higher-level planner/executor
│   └── self_engineer/       ← Self-modification pipeline (8 modules)
├── tests/
│   ├── core/                ← 14 core tests
│   └── self_engineer/       ← 29 self-engineer tests
├── scripts/
│   ├── start.sh             ← Dev / release launcher
│   └── build.sh             ← PyInstaller builder
├── assets/
│   ├── icon.png             ← App icon
│   └── icon.icns            ← macOS icon bundle
├── docs/                    ← Documentation
├── .env.example             ← Environment variable template
├── requirements.txt         ← Python dependencies (35 packages)
├── VIKO.spec                ← PyInstaller spec
└── ruff.toml                ← Lint config
```

## Debugging

Use `/viko-debug` Claude skill for a systematic debug checklist.

Quick commands:
```bash
# Check if VIKO is running
pgrep -f "python.*viko.py"

# Tail logs
tail -50 /tmp/viko.log

# Test imports
python3 -c "import viko; print('OK')"

# Verify environment
python3 -c "from viko.core.config import get_gemini_key; print(get_gemini_key()[:10])"
```
