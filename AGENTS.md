# AGENTS.md — postgres-setup

Guidance for AI coding agents working in this repository. Read fully before
your first change. Nested `AGENTS.md` files may add narrower rules; the
nearest one wins for the paths it covers.

## Project purpose

`postgres-setup` builds a pinned PostgreSQL (plus pinned extensions: postgis,
pgvector, rum) from source into three tiers of container images per distro
profile — core, per-extension, runtime; **the runtime image is the product**
(ADR 0004). Never consume system PostgreSQL packages (ADR 0009).

## Environment

- Python is **uv's job**: `uv run`, `uv add`, `uv lock`; commit `uv.lock` and
  `.python-version`. Never system Python, `pip`, or a hand-made venv.
- This repo is a **uv workspace** with a virtual root (`[tool.uv] package =
  false`): members are `apps/*/*` and `libs/python/*` under one lockfile and
  one venv (ADR 0001).
- The host needs only **uv + buildah** (+ a container runtime store). Build
  dependencies are installed inside the build sandbox by the profile —
  never on the host (ADR 0003).
- Runtime deps: pydantic, httpx, rich (in `core`); typer (the CLI app).
  `pytest`, `ruff`, `poethepoet` are the dev group.

## Architecture — hexagonal (ADR 0002)

```
libs/python/core/src/core/
  domain/          # pure: no I/O, no subprocess, no fs
    errors.py      #   single error taxonomy (CoreError base)
    models.py      #   pydantic: pins, distro profiles, extensions, registry, 3-tier image naming
    ports.py       #   shared ports (Reporter, Distro, ConfigLoader) + build ports
  application/     # use cases — orchestrate ports only
    build.py       #   BuildCoreImage        -> postgres:<profile>-<version>
    extensions.py  #   BuildExtensionImage   -> extension/<name>:... (FROM core)
    runtime.py     #   AssembleRuntimeImage  -> runtime:<profile>-<version> (the product)
    publish.py     #   PushImages / PullImages (all final images)
  adapters/        # one directory per port
    config/toml.py, distro/{__init__,suse}.py, sandbox/buildah.py,
    image_registry/buildah.py, image_transport/buildah.py,
    source_fetcher/httpx.py, reporter/rich.py
apps/cli/setup/    # driving adapter: cli.py (typer) + composition.py (wiring)
```

**Dependency rule (inviolable):** dependencies point inward. `domain` imports
nothing from other layers; `application` imports `domain` only; `adapters`
may import both; apps depend on `core`. If a change would make `domain`
import an adapter or perform I/O, redesign — do not relax the rule.

1. **pydantic everywhere** for state: config, entities, request/result
   models. Validate at the boundary; trust valid state inside.
2. **Classes over free functions** for use cases.
3. **Ports are `typing.Protocol` classes** — structural typing, adapters
   never subclass them; one directory per port under `adapters/`.
4. **Errors** from `core.domain.errors` only. Adapters translate subprocess
   exit codes, missing binaries, HTTP and fs failures into domain errors at
   the boundary; the CLI catches `CoreError` and exits 1.
5. The **composition root** is `apps/cli/setup/src/setup/composition.py`:
   load config, build adapters, inject into use cases. Use cases receive
   only domain models and ports — never argv, CLI paths, or raw toml.
6. Host subprocess calls use argument lists; `sh -c` only as the command
   executed *inside* the container.
7. Adding a distro = one `[profiles.<distro>]` table + one `Distro` adapter
   + one entry in `core/adapters/distro/__init__.py`. Adding an extension =
   one `[extensions.<name>]` pin in `config/pins.toml` + one
   `[[profiles.<distro>.extensions]]` table + one recipe in
   `application/extensions.py`.

## Task runner

poe (poethepoet), run from the repo root. Root `poe_tasks.toml` includes each
member's `poe_tasks.toml` by file path with `cwd` set to the member. Task
names: `<path-to-repo>:<action>` with `/` → `-` (poe forbids `/` in task
names), e.g. `apps-cli-setup:build`. Root utilities (`lint`, `format`) are
unprefixed. Args append directly (this poe version passes them through
verbatim, no `--` separator):
`uv run poe apps-cli-setup:build --profile suse --force`.

## Repository map

| Path | Role |
| --- | --- |
| `apps/cli/setup/` | CLI app (build/build-core/build-extension/assemble/runtime/push/pull/clean/tag/profiles) + tests |
| `libs/python/core/` | domain/application/adapters (above) |
| `config/` | default.toml, pins.toml, profiles.toml, registry.toml(.example) |
| `resources/` | entrypoint.sh, postgresql.conf, pg_hba.conf (copied into the runtime image) |
| `deploy/` | podman quadlet units for the runtime image |
| `docs/architecture/ADRs/` | numbered decisions, genesis numbering from 0001 |
| `docs/architecture/descriptions/` | overview, development |
| `.cache/` | verified source tarballs (git-ignored, derived) |
| `.tmp/` | scratch space |

## Testing

`poe apps-cli-setup:test`. Tests use in-memory fakes over the ports — no
buildah, network, or filesystem. Keep it that way; `poe lint` must stay
green.

## Architecture decisions

Decisions and their context live in `docs/architecture/ADRs/` (genesis
numbering 0001-0009). The runtime picture is
`docs/architecture/descriptions/overview.md`. A change that alters the build
contract = ADR first, then implementation.
