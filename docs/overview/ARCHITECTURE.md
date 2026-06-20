# VIKO Architecture

## System Overview

VIKO is a personal AI voice assistant that runs locally on macOS. It uses Google Gemini Live API for the real-time voice session and routes tool calls to a set of Python skill functions.

```
Microphone → Silero VAD → Gemini Live Session → tool_call → _execute_tool()
                                                    ↓
                                             viko/skills/*
                                                    ↓
                                          Speaker / PyQt6 UI
```

## Components

### Entry Point — `viko.py`

The main agent file. Contains:
- `TOOL_DECLARATIONS` — full JSON schema for every tool Gemini can call
- `_execute_tool()` — async dispatcher: receives a tool name + args, calls the skill function
- `run()` — main async loop: manages the Gemini Live session, audio I/O, speaker verification
- Voice activity detection (Silero VAD) for accurate speech segmentation
- Speaker verification gate: compares incoming voice against enrolled profile

### UI — `viko/ui/`

| File | Purpose |
|------|---------|
| `window.py` | PyQt6 main window; CoreLocation GPS integration; setup overlay |
| `widgets.py` | HUD canvas (system metrics, clock, animated vector map), activity log, chat |
| `browser_panel.py` | Embedded Chromium browser widget (QtWebEngine) |
| `agent_browser.py` | CDP (Chrome DevTools Protocol) server for AI browser control |
| `theme.py` | Colors, fonts, stylesheet constants |

### Core — `viko/core/`

| File | Purpose |
|------|---------|
| `config.py` | `.env` loading; works in frozen (PyInstaller) and unfrozen mode |
| `logger.py` | Structured rotating log (`/tmp/viko.log`); `get_logger()`, `read_recent()` |
| `client.py` | LLM client wrapper (OpenRouter / Gemini) |
| `memory.py` | Long-term memory extraction — key facts extracted via LLM and stored in ChromaDB |
| `speaker_verifier.py` | Voice enrollment and verification using resemblyzer embeddings |
| `conversation.py` | Session message history; periodic summarization |
| `context_builder.py` | Builds Gemini system context from memory and conversation history |
| `vector_store.py` | ChromaDB semantic search (Gemini embeddings) |
| `workspace.py` | File storage for generated content (code, documents, etc.) |
| `offline.py` | Ollama fallback for offline LLM access |
| `offline_stt.py` | Whisper STT fallback for offline speech-to-text |

### Skills — `viko/skills/`

21 tool functions Gemini can call. See [SKILLS.md](SKILLS.md) for the full list.

Each skill has the signature:
```python
def skill_name(parameters: dict, player=None, speak=None) -> str
```

Skills run in a thread executor (synchronous/blocking). They return a result string Gemini uses to formulate its spoken response.

### Self-Engineer — `viko/self_engineer/`

Pipeline for voice-triggered self-modification. See [DEVELOPMENT.md](DEVELOPMENT.md#self-modification-pipeline) for details.

| File | Purpose |
|------|---------|
| `engine.py` | State machine orchestrator (mutex-protected, two-gate confirmation) |
| `analyzer.py` | Reads codebase to build LLM context (token-budgeted) |
| `planner.py` | Generates structured change plan via LLM |
| `generator.py` | Generates code patches and new files |
| `backup.py` | Versioned backup before every change; manifest for rollback |
| `tester.py` | Syntax check, import check, core load test |
| `restarter.py` | Graceful restart via `os.execv` |
| `llm.py` | LLM router: Claude (`claude-sonnet-4-6`) if `ANTHROPIC_API_KEY` set, else Gemini |

### Agent — `viko/agent/`

Higher-level planning layer for multi-step goals.

| File | Purpose |
|------|---------|
| `planner.py` | Breaks a goal into sequential tool-call steps via LLM |
| `executor.py` | Runs steps, handles retries and replanning |
| `recovery.py` | Error analysis and fix generation |
| `queue.py` | Priority task queue with cancellation |

## Data Flow

### Voice Conversation

```
1. Microphone input → PyAudio stream
2. Silero VAD detects speech → chunks sent to Gemini Live
3. Gemini Live transcribes, reasons, and decides:
   a. Generate a spoken reply → text-to-speech output
   b. Call a tool → sends tool_call event
4. If tool_call: _execute_tool() dispatches to skill function
5. Skill result returned to Gemini as tool_response
6. Gemini formulates spoken reply based on tool result
7. Activity log updated in PyQt6 UI
```

### Speaker Verification

```
Enrollment: user says "viko, kenali suaraku"
  → 10 seconds of voice captured
  → resemblyzer extracts 256-dim embedding
  → saved to memory/voice_profile.npy

Verification (every conversation turn):
  → resemblyzer extracts embedding from incoming audio
  → cosine similarity vs stored profile
  → ≥ 0.50 → verified (owner), < 0.40 → blocked, between → uncertain
```

### Long-Term Memory

```
After each session:
  → conversation.py summarizes session (LLM call, max 300 tokens)
  → memory.py extracts key facts (LLM call, max 1024 tokens)
  → facts stored in ChromaDB (vector_store.py)

On next session:
  → context_builder.py retrieves relevant memories via semantic search
  → injected into Gemini system context
```

## Security Model

| Threat | Mitigation |
|--------|-----------|
| Unauthorized access | Speaker verification (resemblyzer embeddings, cosine similarity ≥ 0.50) |
| API key exposure | All keys from `.env` via `config.py`; `.env` is gitignored |
| Self-modification gone wrong | Two-gate confirmation, mandatory backup before changes, automatic rollback on test failure |
| Wake-word spoofing | Wake word disabled (unreliable); speaker verification is the sole gate |
| Passphrase bypass | `OWNER_PASSPHRASE` typed bypass only — not accessible via voice when SV is active |

## Technology Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Voice AI | Gemini Live API | Real-time bidirectional audio; native tool calling |
| Code generation LLM | Claude Sonnet (with Gemini fallback) | Claude has stronger code generation; Gemini for users without Anthropic key |
| Speaker verification | resemblyzer | Lightweight CPU inference; 256-dim embeddings; no cloud dependency |
| VAD | Silero VAD | Accurate, CPU-only, low latency |
| UI framework | PyQt6 + QtWebEngine | Native macOS feel; embedded browser (Chromium) for AI browser control |
| Memory | ChromaDB + SQLite | Local-only; no cloud dependency; semantic search |
| Packaging | PyInstaller | Single `.app` bundle for macOS distribution |
| Offline STT | faster-whisper | CPU-only, ~500MB model, no cloud |
| Offline LLM | Ollama | Local model server; `qwen2.5:1.5b` default |
