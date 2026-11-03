# ADR 0006: Registry distribution of the final images

- Status: accepted
- Date: 2026-11-03

## Context

ADR 0003's image store is local to one machine; a fresh machine (CI, second
laptop) rebuilds from source — the compile time is the whole cost.

## Decision

1. **Final images only** are published — never the hash-keyed cache layers
   (`<cache_prefix>/<scope>:*`), which are internal build accelerators with
   no consumer-facing identity. A profile's final images are the runtime
   image (`runtime:<p>-<v>`, the product), the core (`postgres:<p>-<v>`), and
   one per enabled extension (`extension/<name>:<p>-<v>`) — so a consumer
   can pull exactly the granularity it needs.
2. User-local `config/registry.toml` (git-ignored;
   `config/registry.toml.example` committed) declares a `namespace` that
   replaces the `localhost/` prefix —
   `localhost/postgres-setup/runtime:suse-0.1.0` →
   `<namespace>/postgres-setup/runtime:suse-0.1.0` — plus `tls_verify` for
   plain-HTTP LAN registries. Authentication stays out of the file:
   `buildah login` once.
3. `setup push` / `setup pull` move all of the profile's final images
   between the local store and the registry. `setup runtime --from auto`
   resolves a missing runtime image by pulling when a registry is configured,
   else builds from source; `--from pull` refuses to compile, `--from build`
   never pulls.

## Consequences

Build once, distribute everywhere; the registry is the accelerator and the
from-source build remains the audit path.
