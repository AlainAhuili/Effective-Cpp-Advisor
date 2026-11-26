# Contributing

## Workflow

`main` is protected. Every change goes through a pull request, and PRs are
squash-merged, so each PR becomes exactly one commit on `main`.

1. Branch from `main` (`feat/...`, `fix/...`, `ci/...`, `docs/...`).
2. Open a PR. Fill in the template.
3. CI must be green: tests and the PR-title check.
4. Squash-merge. The PR title becomes the commit message.

## Commit messages and PR titles

Both follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <summary>
```

| Type       | Use for                                   | Version bump |
|------------|-------------------------------------------|--------------|
| `feat`     | A new user-facing capability              | minor        |
| `fix`      | A bug fix                                 | patch        |
| `perf`     | A performance improvement                 | patch        |
| `refactor` | Code change with no behaviour change      | none         |
| `docs`     | Documentation only                        | none         |
| `test`     | Tests only                                | none         |
| `build`    | Dependencies, packaging, Docker           | none         |
| `ci`       | GitHub Actions and other CI configuration | none         |
| `chore`    | Anything else that ships no code          | none         |
| `revert`   | Reverting an earlier commit               | depends      |

A breaking change adds `!` after the type, e.g. `feat(cli)!: rename review to explain`.

Useful scopes: `detectors`, `rag`, `agent`, `fix`, `cli`, `mcp`, `docker`.

## Local hooks

```bash
pip install -e ".[dev]"
pre-commit install
pre-commit run --all-files   # optional: check the whole repo once
```

Every `git commit` then runs these checks on the staged files:

| Hook | What it checks |
|------|----------------|
| pre-commit-hooks | Trailing whitespace, final newline, valid YAML/TOML, merge markers, files over 500 KB |
| ruff | Python lint (autofixes what it can) and formatting |
| mypy | Python types in `agent`, `cli`, `rag`, `static_analysis` |
| clang-format | C++ formatting per `.clang-format` (`examples/` is excluded: test fixtures) |
| gitleaks | API keys, tokens and private keys |
| conventional-pre-commit | The commit message follows Conventional Commits |

If a hook changes files (ruff, clang-format, whitespace), the commit stops:
review the changes, `git add` them and commit again.

The gitleaks hook builds with Go; pre-commit downloads Go itself the first
time if it is not installed.

Configuration lives in `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`),
`.clang-format` and `.pre-commit-config.yaml`.
