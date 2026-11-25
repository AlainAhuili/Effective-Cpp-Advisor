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
pip install pre-commit
pre-commit install
```

This installs the commit-message check (see `.pre-commit-config.yaml`), so a
non-conventional message is rejected before it is committed.
