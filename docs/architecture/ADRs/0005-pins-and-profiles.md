# ADR 0005: Pinned sources and distro-keyed build profiles

- Status: accepted
- Date: 2026-11-03

## Context

The daemon must be identical in every environment (dev laptop, CI,
production): no floating versions, no distro packages, auditable sources —
and the build environment must be selectable per distro (openSUSE today,
Ubuntu later).

## Decision

- `config/pins.toml` is the single versions file: the core under `[postgres]`,
  each extension under `[extensions.<name>]` — version + archive + url +
  sha256, plus the extension's control file (verification marker) and
  recipe-specific configure/make flags. The `SourceFetcher` port verifies
  sha256 on download and on every later use of the `.cache/` copy.
- `config/profiles.toml` holds one `[profiles.<distro>]` table per distro;
  **the profile name selects the `Distro` adapter** (`suse` -> zypper via
  `core/adapters/distro/`, `ubuntu` -> one apt adapter later). Each profile
  carries:
  - `version` — part of every image tag; bump when pins change;
  - `base_image`, `prefix`, `output_dir` (in-image output dir, set as
    `POSTGRES_SETUP_OUTPUT_DIR` in the runtime image; defaults to `prefix`);
  - `build_packages` (core build deps, sandbox only) and `runtime_packages`
    (installed into the runtime image);
  - `configure_flags` (postgres `./configure` flags);
  - the runtime image shape: `uid`/`gid`, `data_dir`, `config_dir`, `ports`;
  - `jobs` (bounded `make -j`; unset = half the CPUs) and `cache_prefix`;
  - `extensions` — an array of tables (`[[profiles.suse.extensions]]`), each
    with `name` plus its own per-distro `build_packages` and
    `runtime_packages`. The extension is compiled FROM the core artifact
    image into its own image, then merged into the runtime image.
- Image tags are profile-keyed: `postgres:<profile>-<version>`,
  `extension/<name>:<profile>-<version>`, `runtime:<profile>-<version>`.
  Pin versions are recorded in image labels and layer-cache keys, not in tags.
- Verification is in-image: `postgres --version` must match the pin, and each
  extension's control file must be present in `<prefix>/share/extension`.
  Extension recipes are code in `core/application/extensions.py`, not
  configuration.

## Consequences

Reproducible from-source builds; upgrading = edit `config/pins.toml`, bump
the profile `version`, re-run (a stale image rebuilds automatically);
adding a distro = one profile table + one `Distro` adapter + one factory
entry; adding an extension = one pin + one `[[...extensions]]` table + one
recipe in `application/extensions.py`.
