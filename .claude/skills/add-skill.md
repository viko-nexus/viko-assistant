---
name: add-skill
description: Add a new skill to VIKO. Creates the skill file, registers it in viko.py, and runs tests.
---

# Adding a New VIKO Skill

## Checklist

1. **Create** `viko/skills/<skill_name>.py`

   ```python
   def <skill_name>(parameters: dict, player=None, speak=None) -> str:
       """Brief description of what this skill does."""
       # player  → VikoUI instance (browser panel, log writes)
       # speak   → callable to make VIKO say something mid-execution
       ...
       return "Result string (English)"
   ```

   - Return a string result — never `None`
   - Skills run in a thread executor (blocking/synchronous — no `async`)
   - Use only stdlib or already-listed packages in `requirements.txt`
   - User-facing messages that VIKO speaks aloud → Indonesian; code → English

2. **Import** in `viko.py` (after line ~47, with other skill imports):

   ```python
   from viko.skills.<skill_name> import <skill_name>
   ```

3. **Register** in `TOOL_DECLARATIONS` in `viko.py`:

   ```python
   {
       "name": "<skill_name>",
       "description": "What this skill does, so Gemini knows when to call it",
       "parameters": {
           "type": "OBJECT",
           "properties": {
               "param": {"type": "STRING", "description": "..."}
           },
           "required": ["param"]
       }
   },
   ```

4. **Handle** in `_execute_tool()` in `viko.py`:

   ```python
   elif name == "<skill_name>":
       r = await loop.run_in_executor(
           None,
           lambda: <skill_name>(parameters=args, player=self.ui, speak=self.speak)
       )
       result = r or "Done."
   ```

5. **Verify import**:

   ```bash
   python3 -c "from viko.skills.<skill_name> import <skill_name>; print('OK')"
   ```

6. **Run tests** (ensure nothing is broken):

   ```bash
   python -m pytest tests/ -v
   ```

7. **Commit**:

   ```bash
   git add viko/skills/<skill_name>.py viko.py
   git commit -m "feat: add <skill_name> skill"
   git push
   ```

## Notes

- `player` is the `VikoUI` instance — use `player.write_log("message")` to add lines to the activity log
- `speak` is a callable — call `speak("Selesai!")` to make VIKO speak mid-execution (Indonesian)
- For HTTP calls: prefer `httpx` (already in requirements) over `requests`
- If the skill needs a new package, add it to `requirements.txt` and document it in [docs/SKILLS.md](../../docs/SKILLS.md)
