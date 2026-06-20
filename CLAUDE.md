# CLAUDE.md — VIKO Assistant Developer Guide

This file tells Claude Code how to work in this repository.

## Repository

`https://github.com/viko-nexus/viko-assistant`

## Project Overview

VIKO (Virtual Intelligent Knowledge Operator) is a personal AI voice assistant built with PyQt6 and Google Gemini Live API. It listens to voice, executes 20+ tools, and can modify its own source code on command.

- Main agent loop: `viko.py`
- Skills (tools Gemini can call): `viko/skills/`
- Self-modification pipeline: `viko/self_engineer/`

## Running the App

```bash
.venv/bin/python viko.py                    # run VIKO
nohup .venv/bin/python -u viko.py > /tmp/viko.log 2>&1 &  # background + log

# Tests
python -m pytest tests/ -v                  # all tests (59 total)
python -m pytest tests/self_engineer/ -v    # self-engineer tests only
python -m pytest tests/core/ -v             # core tests (VAD + wake word)
```

Find running process: `pgrep -f "python viko.py"`
Kill: `pkill -f "python.*viko.py"`

## Code Conventions

- **Language**: All code, comments, docstrings, variable names → **English**
- **User-facing strings** (what VIKO says aloud) → **Indonesian** (VIKO speaks to its owner in Indonesian)
- **No unnecessary comments** — only add a comment when the WHY is non-obvious
- **No type annotation bloat** — use `| None` shorthand (Python 3.11+)
- **Tests first** for all testable modules (TDD)
- Run `ruff check viko/ viko.py` before committing

## Architecture

### Entry Point: `viko.py`

- `TOOL_DECLARATIONS` — full schema for every tool Gemini can call
- `_execute_tool()` — dispatches tool calls to skill functions
- `run()` — main async loop (Gemini Live session)

### Adding a Skill

1. Create `viko/skills/<skill_name>.py`:
   ```python
   def <skill_name>(parameters: dict, player=None, speak=None) -> str:
       ...
       return "result string"
   ```
2. Import in `viko.py` (near line 40, with other skill imports)
3. Add entry to `TOOL_DECLARATIONS` in `viko.py`
4. Add `elif name == "<skill_name>":` handler in `_execute_tool()`
5. Verify: `python3 -c "from viko.skills.<skill_name> import <skill_name>; print('OK')"`

Use `/add-skill` skill for the full checklist.

### Gemini Live Model (`viko.py`)

```python
LIVE_MODEL = "models/gemini-3.1-flash-live-preview"
```

The 3.1 model is stable for tool calls. Gemini 2.5 native-audio had a bug rejecting audio after `tool_call` → 1008 drops.

### Voice Configuration

Controlled via `.env`:
```env
VIKO_VOICE=Erinome          # prebuilt voice name (female, clear Indonesian)
VIKO_VOICE_LANG=id-ID       # BCP-47 language for TTS pronunciation
```

Female voices auditioned in id-ID: Erinome (clear) · Despina (smooth) · Algieba · Achernar · Vindemiatrix · Sulafat · Aoede · Leda.
Config accessors: `get_voice()` / `get_voice_language()` in `viko/core/config.py`.

### Speaker Verification (`viko.py`)

```python
SV_PASS_THRESHOLD  = 0.50   # similarity ≥ this → verified owner
SV_BLOCK_THRESHOLD = 0.40   # similarity < this → blocked non-owner
```

`WAKE_WORD_ENABLED = False` — wake-word output gate disabled (gating Gemini audio on input transcription is racy). Speaker verification is the sole security boundary.

Re-enroll: say `"viko, kenali suaraku"` (no passphrase needed — physical access implies owner).

### LLM Routing (`viko/self_engineer/llm.py`)

Code-generation LLM calls route through `llm.generate_text(prompt)`:
- `ANTHROPIC_API_KEY` set → **Claude Sonnet** (`claude-sonnet-4-6`)
- Not set → **Gemini** (`gemini-2.5-flash`)

Used by: `self_engineer/planner.py`, `self_engineer/generator.py`, `skills/dev_agent.py`, `skills/code_helper.py`

**Voice agent (Gemini Live) is always Gemini — never routed through Claude.**

### Self-Engineer Pipeline (`viko/self_engineer/`)

Two-gate state machine for voice-triggered self-modification:

```
self_update(action="create_skill"|"fix_bug"|"modify_prompt"|"modify_ui")
  → analyzer.build_context() → planner.generate()  → saves pending_plan.json
  → returns "Here's the plan. Proceed?"

self_update(action="confirm")   ← user says "ya"
  → generator.generate() → backup.save() → generator.apply_changes()
  → tester.run() → saves pending_restart.json
  → returns "Tests passed. Restart now?"

self_update(action="confirm")   ← user says "ya restart"
  → restarter.restart() → os.execv (process replace)
  → new VIKO detects restart flag → announces update
```

Mutex in `SelfEngineerEngine` prevents concurrent modifications. Automatic rollback on test failure.

## Key Files

| File | Purpose |
|------|---------|
| `viko.py` | Main agent, tool routing, Gemini Live session |
| `viko/prompt.txt` | System prompt — VIKO's personality and tool rules |
| `viko/core/config.py` | API key loading from `.env` (works frozen and unfrozen) |
| `viko/core/logger.py` | Structured logging — `get_logger()`, `read_recent()` |
| `viko/core/client.py` | LLM client (OpenRouter / Gemini wrapper) |
| `viko/core/memory.py` | Long-term memory extraction and storage |
| `viko/core/speaker_verifier.py` | Speaker embedding, enroll, verify (resemblyzer) |
| `viko/core/conversation.py` | Session message history |
| `viko/core/context_builder.py` | Builds Gemini system context |
| `viko/ui/window.py` | PyQt6 main window + CoreLocation GPS |
| `viko/ui/theme.py` | Colors, fonts, stylesheet constants |
| `viko/ui/widgets.py` | HUD canvas, panels, chat bubbles |
| `viko/ui/browser_panel.py` | Embedded Chromium browser widget |
| `viko/ui/agent_browser.py` | CDP browser server for AI control |
| `viko/self_engineer/engine.py` | Self-modification orchestrator |
| `viko/self_engineer/llm.py` | LLM router (Claude / Gemini) |
| `viko/skills/self_update.py` | Voice-facing self-modification skill |

## Environment

See `.env.example` for the full list. Key variables:

```env
GEMINI_API_KEY=...           # required — Gemini Live voice agent
ANTHROPIC_API_KEY=...        # optional — Claude for code generation (claude-sonnet-4-6)
OPENROUTER_API_KEY=...       # optional
OS_SYSTEM=mac                # mac | windows | linux
CAMERA_INDEX=0               # webcam index (default: 0)
OWNER_PASSPHRASE=...         # optional — typed bypass for speaker verification
VIKO_VOICE=Erinome           # Gemini TTS voice (default: Aoede)
VIKO_VOICE_LANG=id-ID        # BCP-47 TTS language (default: id-ID)
LATITUDE=...                 # optional — fixed coords for map/weather
LONGITUDE=...
OLLAMA_MODEL=qwen2.5:1.5b   # optional — offline LLM fallback
VIKO_CDP_PORT=9222           # optional — Chrome DevTools Protocol port
VIKO_MEMORY_RETENTION_DAYS=365  # optional — long-term memory cutoff
```

`.env` is gitignored. Never commit API keys.

## What NOT to Do

- Do not commit `.env`, `memory/*.db`, `memory/*.sqlite3`, `memory/voice_profile.npy`, or `workspace/` files
- Do not modify `viko/self_engineer/backups/` manually (gitignored, managed by `backup.py`)
- Do not run destructive git commands (`reset --hard`, `push --force`) without explicit user confirmation
- Do not add Indonesian comments or docstrings — user-facing strings only
- Do not refactor beyond the task scope — YAGNI
- Do not skip tests — run `pytest tests/self_engineer/` after any self-engineer change
- Do not hardcode paths like `/Users/<name>/` — use relative paths or `Path(__file__).parent`

## Tests

```
tests/
  core/
    test_wake_word.py         — 11 tests: phonetic wake-word detection
    test_vad_smoke.py         — 3 tests: silero-vad loads, scores silence, scores tone
  self_engineer/
    test_backup.py            — 5 tests: save, manifest, restore, delete created files
    test_tester.py            — 5 tests: syntax check, import check, run()
    test_analyzer.py          — 5 tests: intent categorization, build_context
    test_generator_apply.py   — 4 tests: create, overwrite, patch, patch miss
    test_engine_state.py      — 5 tests: pending plan/restart state persistence
```

Total: **59 tests**. All must pass before any commit.

Run: `python -m pytest tests/ -v`

## Docs

- [docs/overview/ARCHITECTURE.md](docs/overview/ARCHITECTURE.md) — component breakdown, data flow
- [docs/overview/DEVELOPMENT.md](docs/overview/DEVELOPMENT.md) — detailed dev setup, building, linting
- [docs/overview/SKILLS.md](docs/overview/SKILLS.md) — all 21 skills documented
- [docs/overview/CONTRIBUTING.md](docs/overview/CONTRIBUTING.md) — how to contribute
- [docs/overview/SECURITY.md](docs/overview/SECURITY.md) — security model, responsible disclosure
