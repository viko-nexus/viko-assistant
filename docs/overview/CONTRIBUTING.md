# Contributing to VIKO

## What Counts as a Contribution

- Bug fixes with a test that reproduces the bug
- New skills (tools Gemini can call)
- Improvements to existing skills (accuracy, performance, error handling)
- Documentation improvements
- macOS/Windows compatibility fixes

For larger features (new UI components, architectural changes), open an issue first to align before writing code.

## Getting Started

1. Fork the repo on GitHub.
2. Clone your fork: `git clone git@github.com:<your-username>/viko-assistant.git`
3. Follow [DEVELOPMENT.md](DEVELOPMENT.md) for setup.
4. Create a branch: `git checkout -b feature/short-description`

## Development Workflow

1. Write or update tests first (TDD).
2. Implement the change.
3. Ensure all checks pass:

```bash
# All 59 tests must pass
python -m pytest tests/ -v

# Lint
ruff check viko/ viko.py
```

4. Commit and open a pull request.

## Commit Messages

Format: `<type>: <short description>`

| Type | Use for |
|------|---------|
| `feat` | New skill or feature |
| `fix` | Bug fix |
| `refactor` | Code improvement (no behavior change) |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Build, deps, tooling |

Subject line under 72 characters.

## Adding a New Skill

See [DEVELOPMENT.md](DEVELOPMENT.md#adding-a-new-skill) for the step-by-step checklist.
Document the new skill in [SKILLS.md](SKILLS.md) under the appropriate category.

## Pull Request Guidelines

- One change per PR — bug fix, one skill, or one improvement
- All tests must pass
- Add a test for any new skill or bug fix
- Keep it small — large PRs are hard to review

## Code Style

All code, comments, docstrings, and variable names → **English**
User-facing strings (what VIKO says aloud) → **Indonesian**

See [DEVELOPMENT.md](DEVELOPMENT.md#code-style) for the full style guide.

## Security Issues

Do not open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the PolyForm Noncommercial License 1.0.0. See [LICENSE](../LICENSE).
