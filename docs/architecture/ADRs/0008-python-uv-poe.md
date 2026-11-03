# ADR 0008: Python (uv) tooling and poe task runner

- Status: accepted
- Date: 2026-11-03

## Context

The build routine needs real application logic (validation models, HTTP
fetching, reporting, a test suite) and a single task-runner entry point for
humans and coding agents.

## Decision

1. The routine is a **Python uv workspace** (ADR 0001); one `uv sync` sets
   up the whole workspace from one committed `uv.lock` + `.python-version`.
   Never system Python or pip.
2. Tasks are declared in poe (poethepoet) files: the root `poe_tasks.toml`
   includes each member's `poe_tasks.toml` by path with its `cwd` set, and
   the universal entry point is `uv run poe <task>`. Task names follow
   `<path-to-repo>:<action>` with `/` → `-` (`apps-cli-setup:build`); root
   utilities (`lint`, `format`) are unprefixed. Args append directly to a
   task (this poe version passes them through verbatim, no `--` separator):
   `uv run poe apps-cli-setup:build --profile suse --force`.
3. The CLI is a thin typer adapter over framework-free use cases; host
   subprocess calls use argument lists (ADR 0002).

## Consequences

One language and one lockfile across tooling, tests, and the task runner;
`uv run poe --help` documents every workflow.
