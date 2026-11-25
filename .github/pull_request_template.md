<!--
PR title must follow Conventional Commits, e.g.
  feat(fix): add verify-and-retry loop for Item 13
  fix(detectors): handle placement new
It becomes the squash-merge commit on main.
-->

## What

<!-- One or two sentences. -->

## Why

<!-- The problem solved, or the Effective C++ item addressed. -->

## How it was tested

- [ ] `python -m pytest -q` passes locally
- [ ] Checked against `examples/sample_violations.cpp` (if detection, review or fix changed)

## Checklist

- [ ] PR title follows Conventional Commits
- [ ] README or docs updated if behaviour changed
- [ ] No secrets, keys or local paths committed
