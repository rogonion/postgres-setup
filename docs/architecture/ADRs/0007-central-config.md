# ADR 0007: Central configuration directory

- Status: accepted
- Date: 2026-11-03

## Context

Config files (pins, profiles, registry, root paths) scattered at the repo
root clutter it and complicate discovery.

## Decision

Everything user-editable lives under `config/`:

```
config/
├── default.toml             # root config: cache_dir, resources_dir
├── pins.toml                # pinned sources (sha256) — ADR 0005
├── profiles.toml            # distro build profiles — ADR 0005
└── registry.toml(.example)  # registry namespace — ADR 0006
```

A single `ConfigLoader` port (implemented by
`core/adapters/config/toml.py::TomlConfigLoader`) loads all of them into
validated pydantic models. The workspace root is discovered by walking up
from the cwd to the pyproject.toml that declares the uv workspace (or names
postgres-setup, or holds `config/default.toml`). The CLI accepts
`--config-dir` to read from a different directory.

## Consequences

One obvious place for configuration; the root stays clean; tests and
alternate environments can point `--config-dir` at a fixture tree.
