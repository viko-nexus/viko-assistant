---
name: self-engineer-debug
description: Debug the VIKO self-modification pipeline. Check state files, backup manifest, and run tests.
---

# Debugging the SelfEngineer Pipeline

## Check State Files

```bash
# Check if there's a pending plan waiting for confirmation
cat viko/self_engineer/backups/pending_plan.json 2>/dev/null || echo "No pending plan"

# Check if there's a pending restart waiting for confirmation
cat viko/self_engineer/backups/pending_restart.json 2>/dev/null || echo "No pending restart"

# Check restart flag in temp dir
cat /tmp/viko_restart_pending.json 2>/dev/null || echo "No restart flag"
```

## Check Backup Manifest

```bash
python3 -c "
from viko.self_engineer.backup import list_history
for e in list_history():
    print(e['id'], e['timestamp'], e['intent'], '| restorable:', e['restorable'])
"
```

## Clear Stuck State

```bash
python3 -c "
from viko.self_engineer.engine import _clear_pending_plan, _clear_pending_restart
_clear_pending_plan()
_clear_pending_restart()
print('State cleared')
"
```

## Run Tests

```bash
python -m pytest tests/self_engineer/ -v
```

## Restore Latest Backup

```bash
python3 -c "
from viko.self_engineer.backup import restore_latest
print(restore_latest())
"
```

## Check Active LLM Provider

```bash
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
key = os.environ.get('ANTHROPIC_API_KEY')
print('Provider: Claude (claude-sonnet-4-6)' if key else 'Provider: Gemini (gemini-2.5-flash)')
"
```

## Pipeline Flow

```
self_update(action="create_skill"|"fix_bug"|"modify_prompt"|"modify_ui")
  → analyzer.build_context()
  → planner.generate()       ← LLM call (Claude or Gemini)
  → saves pending_plan.json
  → returns "Plan summary. Lanjutkan?"

self_update(action="confirm")   ← user said "ya"
  → generator.generate()    ← LLM call (Claude or Gemini)
  → backup.save()
  → generator.apply_changes()
  → tester.run()
  → saves pending_restart.json
  → returns "Test berhasil. Restart sekarang?"

self_update(action="confirm")   ← user said "ya restart"
  → restarter.restart()
  → os.execv (process replace)
  → new VIKO detects restart flag → announces update
```

## Common Issues

**"Stuck in pending_plan state"**
→ Clear with `_clear_pending_plan()` above. Then retry the voice command.

**"Test failed after generate"**
→ Automatic rollback should have run. Check: `list_history()` — verify latest backup has `restorable: True`.
→ Manual restore: `restore_latest()` then restart VIKO.

**"os.execv restart loop"**
→ Clear `/tmp/viko_restart_pending.json` if it exists. Restart VIKO manually.

**"LLM call timeout"**
→ Check ANTHROPIC_API_KEY / GEMINI_API_KEY are valid: `python3 -c "from viko.core.config import get_gemini_key; print(get_gemini_key()[:10])"`
