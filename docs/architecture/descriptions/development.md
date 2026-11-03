# Development

## Setup

```bash
uv sync        # one lockfile + one venv for the whole workspace (root is a virtual package)
```

Python is uv's job: `uv run`, `uv add`, `uv lock`; commit `uv.lock` and
`.python-version`. Never system Python or pip. Build dependencies (gcc,
make, geo/math devel packages) are installed inside the build sandbox by
the profile — never on the host (ADR 0003).

## Everyday commands (poe; run from the repo root)

| Task | What it does |
| --- | --- |
| `poe lint` / `poe format` | ruff check (+format check) / format + autofix, whole workspace |
| `poe apps-cli-setup:test` | use-case tests (fakes — no buildah/network/filesystem) |
| `poe apps-cli-setup:build` | build all profile images: core + each extension + runtime |
| `poe apps-cli-setup:build-core` | build only `postgres:<profile>-<version>` |
| `poe apps-cli-setup:build-extension` | build one extension image (arg: name, e.g. `pgvector`) |
| `poe apps-cli-setup:assemble` / `:runtime` | assemble `runtime:<profile>-<version>` from core + extensions |
| `poe apps-cli-setup:push` / `:pull` | publish/fetch all of the profile's final images via `config/registry.toml` |
| `poe apps-cli-setup:clean` | prune layer-cache images (add `--cache`) |
| `poe apps-cli-setup:tag` | print the runtime image tag |
| `poe apps-cli-setup:profiles` | list the distro profiles |

Task names follow `<path-to-repo>:<action>` with `/` → `-` (poe task names
cannot contain `/`). CLI args append directly (this poe version passes them
through verbatim, no `--` separator):
`uv run poe apps-cli-setup:build --profile suse --force`.

Direct CLI (accepts `--config-dir` to read config from elsewhere):
`uv run setup <command> --help` from the repo root.

## Rules of the road

- Hexagonal dependency rule: `domain` does no I/O; `application` imports
  `domain` only; `adapters` import both; the app wires everything in
  `apps/cli/setup/src/setup/composition.py` (ADR 0002).
- Ports are `typing.Protocol`s; one directory per port under
  `core/adapters/`; swapping an implementation = adding a file there.
  New distro = one profile table + one `Distro` adapter + one factory entry.
  New extension = one `[extensions.<name>]` pin + one
  `[[profiles.<distro>.extensions]]` table + one recipe in
  `application/extensions.py`.
- Errors come from `core.domain.errors`; adapters translate infra failures
  into them; the CLI catches `CoreError` → exit 1.
- Config lives in `config/`; `--config-dir` overrides the location (ADR 0007).
- Tests use fakes — no buildah, network, or real filesystem in the suite.
- A change that alters the build contract = ADR first, then implementation.
