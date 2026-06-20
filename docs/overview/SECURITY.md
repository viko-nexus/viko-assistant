# Security

## Responsible Disclosure

If you discover a security vulnerability in VIKO, please report it privately.

**Contact:** eksant@gmail.com

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact

You will receive a response within 72 hours. We will credit you in the security advisory if you wish.

Do not disclose publicly until we have had a reasonable opportunity to address it.

## Security Model

### Speaker Verification

VIKO's primary security boundary is speaker verification using voice embeddings:

- Enrollment: captures ~10 seconds of voice, extracts a 256-dimensional embedding via resemblyzer
- Verification: compares each incoming audio segment against the enrolled embedding using cosine similarity
  - Score ≥ 0.50 → verified owner
  - Score < 0.40 → blocked (non-owner)
  - Between → uncertain (VIKO may ask for passphrase)
- Profile stored at `memory/voice_profile.npy` (gitignored, local only)

### Passphrase Bypass

`OWNER_PASSPHRASE` can be set in `.env` to allow typed bypass of speaker verification when needed. It is:
- Stored only in `.env` (gitignored)
- Never logged
- Never transmitted

### API Key Handling

All API keys are loaded from `.env` via `viko/core/config.py`. They are:
- Never hardcoded in source code
- Never logged (the logger masks credentials)
- `.env` is gitignored — never committed

### Self-Modification Safety

The self-modification pipeline has multiple safeguards:
- **Two confirmation gates**: the plan and the restart both require explicit verbal confirmation
- **Mandatory backup**: every file change is backed up before modification
- **Automatic rollback**: if syntax check, import check, or core load fails — automatic restore
- **Mutex**: `SelfEngineerEngine` uses a mutex to prevent concurrent modifications
- **No network in tester**: the test suite runs offline (import checks, not integration tests)

### Wake Word

`WAKE_WORD_ENABLED = False` — the phonetic wake-word gate is disabled. Gating Gemini audio output on input transcription is racy and caused audio drop issues. Speaker verification is the sole security boundary.

### Local-only Storage

VIKO stores all user data locally:
- `memory/` — SQLite conversation history, ChromaDB vectors, voice profile (all gitignored)
- `workspace/` — generated files (gitignored)
- `/tmp/viko.log` — session logs (cleared on reboot)

No user data is sent to external services except:
- Audio → Google Gemini Live API (required for voice processing)
- Text queries → Google Gemini / Anthropic Claude / OpenRouter (only when those skills are used)

## Known Limitations

- Speaker verification is not perfect — high ambient noise can cause false negatives
- The `OWNER_PASSPHRASE` bypass is available to anyone with physical keyboard access
- Self-modification can produce broken code — always keep a manual backup of important modifications
- The embedded browser runs with full network access and can execute arbitrary JavaScript

## Dependency Updates

VIKO uses `requirements.txt` for Python dependencies. Keep them updated, especially for security patches. Before upgrading, run the full test suite: `python -m pytest tests/ -v`.
