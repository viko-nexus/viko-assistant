---
name: viko-debug
description: Debug a running or failed VIKO instance. Check logs, processes, audio, and connectivity.
---

# VIKO Debug

## 1. Check if VIKO is Running

```bash
pgrep -f "python.*viko.py"
```

If empty: VIKO is not running. Start it:
```bash
nohup .venv/bin/python -u viko.py > /tmp/viko.log 2>&1 &
```

## 2. Read Recent Logs

```bash
tail -50 /tmp/viko.log
```

Look for:
- `ERROR` or `CRITICAL` lines → identify the failing module
- `WebSocket closed` → Gemini Live connection dropped
- `tool_call` → which skill was called last
- `1008` close code → audio bug (use `gemini-3.1-flash-live-preview`, not 2.5)

## 3. Check Audio Devices

```bash
python3 -c "
import subprocess
result = subprocess.run(['system_profiler', 'SPAudioDataType'], capture_output=True, text=True)
print(result.stdout[:2000])
"
```

Verify the expected input/output device appears. If mic is missing, check macOS Privacy Settings → Microphone.

## 4. Check Speaker Verification State

```bash
python3 -c "
import os
from pathlib import Path
profile = Path('memory/voice_profile.npy')
print('Voice profile:', 'exists' if profile.exists() else 'NOT FOUND — run enrollment first')
"
```

If profile missing, tell VIKO: `"Viko, kenali suaraku"` to enroll.

## 5. Check Environment

```bash
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
keys = ['GEMINI_API_KEY', 'ANTHROPIC_API_KEY', 'OS_SYSTEM', 'VIKO_VOICE', 'VIKO_VOICE_LANG']
for k in keys:
    v = os.environ.get(k, '')
    print(f'{k}: {v[:8]}...' if v and 'KEY' in k else f'{k}: {v or \"(not set)\"}')
"
```

## 6. Test Gemini API Connectivity

```bash
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
r = client.models.generate_content(model='gemini-2.5-flash', contents='Say OK')
print(r.text)
"
```

## 7. Test Imports

```bash
python3 -c "import viko; print('OK')"
```

If import fails, read the full traceback — usually a missing package or syntax error in a skill file.

## 8. Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError` | Missing package | `.venv/bin/pip install <package>` |
| `1008 WebSocket close` | Wrong Gemini model | Ensure `LIVE_MODEL = "models/gemini-3.1-flash-live-preview"` |
| Voice not detected | Mic permissions | macOS: System Settings → Privacy → Microphone |
| `SV_BLOCK` all the time | No voice profile | Say `"viko, kenali suaraku"` to enroll |
| VIKO crashes after self-update | Bad generated code | Run `restore_latest()` from self-engineer-debug |
| PyQt6 display error | Missing Qt libs | `brew install qt@6` then reinstall `PyQt6` |
| Memory import fails | ChromaDB issue | Delete `memory/` dir — VIKO will recreate it |
