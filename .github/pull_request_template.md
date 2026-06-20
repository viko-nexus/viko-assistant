## What does this PR do?

<!-- One-paragraph summary of the change -->

## Type of change

- [ ] New skill
- [ ] Bug fix
- [ ] UI improvement
- [ ] Performance improvement
- [ ] Documentation
- [ ] Chore (deps, tooling, CI)

## Checklist

- [ ] `python -m pytest tests/ -v` — all 59 tests pass
- [ ] `ruff check viko/ viko.py` — no lint errors
- [ ] If adding a skill: documented in `docs/overview/SKILLS.md`
- [ ] If changing the self-engineer pipeline: `pytest tests/self_engineer/ -v` passes
- [ ] No hardcoded paths, no API keys in code
- [ ] No Indonesian comments or docstrings (user-facing strings only)
