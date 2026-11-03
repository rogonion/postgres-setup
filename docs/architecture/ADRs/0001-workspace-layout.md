# ADR 0001: Monorepo workspace layout

- Status: accepted
- Date: 2026-11-03

## Context

The project produces one thing — a pinned, from-source PostgreSQL build
packaged as container images, with the runtime image as the product — but it
needs a CLI entry point and a shared library, one lockfile, one venv, and one
config root.

## Decision

One uv workspace at the repository root. The root project is virtual
(`[tool.uv] package = false`) — it carries no code, only shared dev tooling.
Members live under globs:

```
apps/cli/setup/       CLI (driving adapter): build / build-core / build-extension / assemble / push / pull / clean / tag / profiles
libs/python/core/     the hexagonal library the CLI drives (package `core`)
config/               all user-editable toml (see ADR 0007)
docs/                 architecture docs (ADRs + descriptions)
resources/            runtime-image resources (entrypoint.sh, postgresql.conf, pg_hba.conf)
deploy/               podman quadlet units for running the runtime image
poe_tasks.toml        root task registry (includes each member's file)
```

A new member = one folder matching `apps/*/*` or `libs/python/*` plus an
`include` entry in the root `poe_tasks.toml`.

## Consequences

One `uv.lock`/`.venv` for everything; the CLI is a thin app over the shared
`core` lib; task names follow the `<path-to-repo>:<action>` convention (poe
task names cannot contain `/`, so separators become dashes:
`apps-cli-setup:build`).
