# VIKO — Virtual Intelligent Knowledge Operator

VIKO is a personal AI voice assistant built with PyQt6 and Google Gemini Live API. It listens to your voice, executes tools, and can even modify its own source code on command.

> **Non-commercial use only. See [LICENSE](LICENSE) for terms.**

---

## Preview

| Dashboard | Text Chat | Voice Chat |
|:---------:|:---------:|:----------:|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Text Chat](docs/screenshots/text-chat.png) | ![Voice Chat](docs/screenshots/voice-chat.png) |
| Live metrics, GPS map, system status | Activity log with conversation history | Real-time audio visualizer while speaking |

---

## Features

- **Real-time voice conversation** — Gemini 3.1 Live API with Silero VAD for accurate speech detection and low-latency responses
- **Configurable female Indonesian voice** — Erinome by default; 10+ voices selectable via `VIKO_VOICE` env var
- **Futuristic HUD** — sci-fi dark UI with live system metrics, clock, animated vector map, and timestamped activity log
- **Live location & map** — GPS via macOS CoreLocation with Nominatim reverse geocoding; falls back to IP geolocation
- **Embedded browser** — built-in Chromium browser panel with full AI control via CDP
- **20+ skills** — web search, file management, app control, code generation, weather, flight lookup, reminders, and more
- **Speaker verification** — voice profile enrollment and verification via resemblyzer embeddings (owner-only responses)
- **Self-modification** — VIKO can add new skills, fix bugs, update its own prompt, or modify its UI via voice command
- **Long-term memory** — vector memory and conversation history (SQLite + ChromaDB + Gemini embeddings)
- **Dev agent** — builds complete projects from a voice description (plan → code → test → commit)
- **Claude + Gemini routing** — uses Claude Sonnet for code generation if `ANTHROPIC_API_KEY` is set, falls back to Gemini
- **Personality** — absurd humor mode with context-aware tone (serious for technical/emotional topics)

---

## Requirements

- Python 3.11+
- macOS (primary; Windows partially supported)
- [uv](https://docs.astral.sh/uv/) for dependency management
- Google Gemini API key (required)
- Anthropic API key (optional — enables Claude for code generation)

---

## Setup

```bash
# 1. Clone
git clone git@github.com:viko-nexus/viko-assistant.git
cd viko-assistant

# 2. Install dependencies
python setup.py

# 3. Configure environment
cp .env.example .env   # fill in your API keys
```

### Environment Variables

See [`.env.example`](.env.example) for the full reference with all voice options.

```env
GEMINI_API_KEY=your_gemini_api_key        # required
ANTHROPIC_API_KEY=your_anthropic_key      # optional — Claude for code gen
OPENROUTER_API_KEY=your_openrouter_key    # optional
OS_SYSTEM=mac                             # mac | windows | linux
CAMERA_INDEX=0                            # webcam index
OWNER_PASSPHRASE=...                      # optional — typed bypass for speaker verification
VIKO_VOICE=Erinome                        # TTS voice name (default: Aoede)
VIKO_VOICE_LANG=id-ID                     # BCP-47 language for TTS (default: id-ID)
LATITUDE=-6.2088                          # optional — fixed coords for map/weather
LONGITUDE=106.8456
```

---

## Running

```bash
# Dev mode — Python venv, logs to /tmp/viko.log
./scripts/start.sh

# Release mode — opens the built .app bundle
./scripts/start.sh --app

# Monitor logs
tail -f /tmp/viko.log
```

### Building the .app bundle

```bash
./scripts/build.sh
```

Runs lint → PyInstaller → patches QtWebEngine paths → outputs `dist/VIKO.app`.

---

## Architecture

```
viko.py                      — Main agent: Gemini Live session, tool routing
assets/
  icon.png                   — App icon (1024×1024 PNG)
  icon.icns                  — Multi-resolution macOS icon bundle
scripts/
  start.sh                   — Dev / release launcher
  build.sh                   — PyInstaller build + QtWebEngine path fix
viko/
  prompt.txt                 — System prompt (VIKO's personality + tool rules)
  core/
    config.py                — .env loading; works in source and frozen app
    logger.py                — Structured logging (RotatingFileHandler)
    client.py                — LLM client (OpenRouter / Gemini wrapper)
    memory.py                — Long-term memory extraction
    speaker_verifier.py      — Speaker embedding, enroll, verify (resemblyzer)
    conversation.py          — Session management, SQLite history
    context_builder.py       — Builds system context for Gemini
    vector_store.py          — ChromaDB semantic search (Gemini embeddings)
    workspace.py             — File storage for generated content
  ui/
    window.py                — PyQt6 main window; CoreLocation GPS integration
    widgets.py               — HUD canvas, activity panel, vector map
    theme.py                 — Colors, fonts, stylesheet constants
    browser_panel.py         — Embedded Chromium browser widget
    agent_browser.py         — CDP browser server for AI control
  skills/
    self_update.py           — Voice-facing self-modification skill
    dev_agent.py             — Build complete projects from scratch
    code_helper.py           — Code assistance, debugging, file editing
    browser_tool.py          — Embedded browser control (JS + CDP)
    computer_control.py      — Mouse, keyboard, screenshot automation
    file_controller.py       — File system operations
    web_search.py            — DuckDuckGo search
    weather_report.py        — Weather lookup
    ... (20+ skills total)
  agent/
    planner.py               — Breaks goals into tool-call steps via LLM
    executor.py              — Runs steps, handles retries and replanning
    recovery.py              — Error analysis and fix generation
    queue.py                 — Priority task queue with cancellation
  self_engineer/
    engine.py                — Self-modification state machine (mutex-protected)
    analyzer.py              — Reads codebase to build LLM context
    planner.py               — Generates structured change plan via LLM
    generator.py             — Generates code patches and new files
    backup.py                — File versioning before every change
    tester.py                — Syntax + import + core load checks
    restarter.py             — Graceful restart via os.execv
    llm.py                   — LLM router: Claude if key set, else Gemini
```

---

## Self-Modification Flow

```
User: "Viko, add a skill to check Bitcoin price"
  → Gemini calls self_update(intent="...", action="create_skill")
  → ANALYZE → PLAN → "I'll create crypto_price.py. Proceed?"

User: "yes"
  → self_update(action="confirm")
  → BACKUP → GENERATE → APPLY → TEST → "Tests passed. Restart now?"

User: "restart"
  → self_update(action="confirm")
  → os.execv restart → "Updated and ready."
```

Two confirmation gates (plan + restart) prevent accidental changes.  
Automatic rollback on test failure.

---

## Development

```bash
# Run all tests (59 total)
python -m pytest tests/ -v

# Self-engineer tests only
python -m pytest tests/self_engineer/ -v

# Core tests (VAD + wake word)
python -m pytest tests/core/ -v

# Lint (auto-fix safe issues)
ruff check viko/ viko.py --select F401,F811,F841 --fix
```

### Adding a New Skill

1. Create `viko/skills/your_skill.py`:
   ```python
   def your_skill(parameters: dict, player=None, speak=None) -> str:
       ...
       return "result"
   ```
2. Import in `viko.py`
3. Add entry to `TOOL_DECLARATIONS` in `viko.py`
4. Add handler in `_execute_tool()` in `viko.py`

Or say: *"Viko, add a skill to [description]"* and let VIKO build it.

---

## License

[PolyForm Noncommercial License 1.0.0](LICENSE) — free for personal, educational, and non-commercial use. © 2026 Viko Nexus.
