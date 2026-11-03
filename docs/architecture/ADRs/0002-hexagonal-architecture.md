# ADR 0002: Hexagonal architecture in `core`

- Status: accepted
- Date: 2026-11-03

## Context

Build logic must not depend on CLI frameworks, buildah, HTTP clients, or
the filesystem, so it stays testable with in-memory fakes and swappable at
runtime.

## Decision

`libs/python/core` is a hexagon with dependencies pointing inward only:

```
core/
├── domain/
│   ├── errors.py   # single error taxonomy (CoreError base)
│   ├── models.py   # pydantic: pins, profiles, registry, image naming
│   └── ports.py    # shared ports (Reporter, Distro, ConfigLoader) + build ports
├── application/    # use cases: BuildCoreImage, BuildExtensionImage, AssembleRuntimeImage, Push/PullImages
└── adapters/       # one directory per port
    ├── config/toml.py
    ├── distro/{__init__,suse}.py
    ├── source_fetcher/httpx.py
    ├── sandbox/buildah.py
    ├── image_registry/buildah.py
    ├── image_transport/buildah.py
    └── reporter/rich.py
```

Rules:

1. `domain` performs no I/O and imports nothing from other layers;
   `application` imports `domain` only; `adapters` may import both.
2. Ports are `typing.Protocol` classes (structural typing — adapters never
   subclass them); one concern per port; one adapter directory per port, so
   alternative implementations slot in without touching use cases.
3. All state is pydantic models validated at the boundary; errors are raised
   from the `core.domain.errors` taxonomy — adapters translate subprocess /
   HTTP / fs failures into domain errors at the boundary, and CLIs catch
   `CoreError` and map it to exit code 1.
4. The composition root lives in the app
   (`apps/cli/setup/src/setup/composition.py`): it loads config, constructs
   adapters, injects them into use cases. Use cases receive only domain
   models and ports — never argv, CLI paths, or raw toml.
5. Host subprocess calls use argument lists (no `shell=True` on the host);
   `sh -c` strings appear only as the command executed *inside* the
   container, where the shell is the point.

## Consequences

Use cases are unit-testable with fakes (no buildah/network); swapping an
adapter is adding a file in its port directory; the CLI layer knows nothing
about infra.
