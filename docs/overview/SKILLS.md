# VIKO Skills Reference

VIKO has 21 built-in skills (tools) that Gemini can call. Each skill is a Python function in `viko/skills/`.

## Adding a New Skill

See [DEVELOPMENT.md](DEVELOPMENT.md#adding-a-new-skill) or use the `/add-skill` Claude skill.

## Skill Signature

Every skill has the same signature:

```python
def skill_name(parameters: dict, player=None, speak=None) -> str:
    # player → VikoUI instance (log writes, browser control)
    # speak  → callable to make VIKO speak mid-execution
    return "Result string"
```

---

## Built-in Skills

### Web & Information

| Skill | File | Description |
|-------|------|-------------|
| `web_search` | `web_search.py` | DuckDuckGo search — returns top results with URLs and snippets |
| `weather_report` | `weather_report.py` | Current weather for a city using Open-Meteo (no API key required) |
| `flight_finder` | `flight_finder.py` | Search for flights between airports |
| `youtube_video` | `youtube_video.py` | Search and play YouTube videos in the embedded browser |

### Computer Control

| Skill | File | Description |
|-------|------|-------------|
| `computer_control` | `computer_control.py` | Mouse clicks, keyboard input, window management via PyAutoGUI |
| `computer_settings` | `computer_settings.py` | macOS system settings (volume, brightness, dark mode, etc.) |
| `desktop` | `desktop.py` | Desktop screenshot and analysis |
| `screen_processor` | `screen_processor.py` | Capture and analyze screen regions |
| `open_app` | `open_app.py` | Open macOS applications by name |

### File System

| Skill | File | Description |
|-------|------|-------------|
| `file_controller` | `file_controller.py` | Read, write, list, delete, move files |
| `file_processor` | `file_processor.py` | Process file content (parse, transform, summarize) |

### Browser

| Skill | File | Description |
|-------|------|-------------|
| `browser_tool` | `browser_tool.py` | Control the embedded browser: navigate, click, fill forms, extract content |
| `browser_control` | `browser_control.py` | Low-level CDP browser control (JavaScript execution, screenshots) |

### Code & Development

| Skill | File | Description |
|-------|------|-------------|
| `code_helper` | `code_helper.py` | Code assistance: explain, debug, refactor, write new code |
| `dev_agent` | `dev_agent.py` | Build complete projects from a voice description (plan → code → test → commit) |

### Communication

| Skill | File | Description |
|-------|------|-------------|
| `send_message` | `send_message.py` | Send messages (WhatsApp, email, etc.) |
| `reminder` | `reminder.py` | Set and list reminders |
| `cmd_control` | `cmd_control.py` | Execute shell commands |

### Self-Modification

| Skill | File | Description |
|-------|------|-------------|
| `self_update` | `self_update.py` | Voice-triggered self-modification pipeline (two-gate: plan → restart) |

---

## Skill Parameters

Parameters are defined in `TOOL_DECLARATIONS` in `viko.py`. Each skill declares its parameter schema so Gemini knows what arguments to pass.

Example:
```python
{
    "name": "web_search",
    "description": "Search the web for current information. Use for facts, news, prices, or anything that requires current data.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The search query"
            }
        },
        "required": ["query"]
    }
}
```

---

## Writing a Good Skill

**Do:**
- Return a concise string result — Gemini uses this to formulate its spoken reply
- Use `player.write_log("...")` to show progress in the activity log
- Use `speak("...")` to make VIKO say something mid-execution (Indonesian)
- Handle errors and return a descriptive error string (don't raise exceptions)
- Use relative paths or `Path(__file__).parent` — never hardcode absolute paths

**Don't:**
- Return `None` (use `return "Done."` as fallback)
- Make the skill `async` — all skills run in a thread executor
- Import packages not in `requirements.txt` without adding them first
- Hardcode user-specific paths, API keys, or any config values
