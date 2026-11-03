# setup

The CLI (driving adapter) of postgres-setup. Commands stay thin — parse flags,
delegate to `composition.py` (the composition root), translate `CoreError`
into exit code 1:

```shell
uv run setup build                          # core + each enabled extension + runtime
uv run setup build-core                     # only postgres:<profile>-<version>
uv run setup build-extension pgvector       # only extension/pgvector:... (FROM core)
uv run setup assemble                       # assemble runtime:<profile>-<version> (--from auto|build|pull)
uv run setup runtime                        # alias of assemble — the runtime image is the product
uv run setup push                           # publish all final images (config/registry.toml)
uv run setup pull                           # fetch them back, retagged local
uv run setup clean --cache                  # prune layer-cache images
uv run setup tag                            # print the runtime image tag
uv run setup profiles                       # list distro profiles
```

All commands accept `--config-dir` to read config from elsewhere, and the
build commands accept `--profile` / `--force` / `--jobs`. Via poe from the
repo root: `uv run poe apps-cli-setup:<command> <args>` (args append
directly; no `--` separator with this poe version).

Wiring lives in `src/setup/composition.py`; the typer surface in
`src/setup/cli.py`. The use cases themselves live in the `core` library
(`libs/python/core`).
