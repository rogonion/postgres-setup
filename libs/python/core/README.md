# core

The hexagonal library the `setup` CLI drives. Dependencies point inward only
(ADR 0002):

```
src/core/
├── domain/       # pure: no I/O, imports nothing from other layers
│   ├── errors.py #   single error taxonomy (CoreError base)
│   ├── models.py #   pydantic: pins, distro profiles, extensions, registry, image naming
│   └── ports.py  #   typing.Protocol ports: shared (Reporter, Distro, ConfigLoader)
│                 #   + build (SourceFetcher, Sandbox, ImageRegistry, ImageTransport)
├── application/  # use cases — orchestrate ports only
│   ├── build.py       #   BuildCoreImage        -> postgres:<profile>-<version>
│   ├── extensions.py  #   BuildExtensionImage   -> extension/<name>:... (FROM core)
│   ├── runtime.py     #   AssembleRuntimeImage  -> runtime:<profile>-<version> (the product)
│   └── publish.py     #   PushImages / PullImages
└── adapters/     # one directory per port
    ├── config/toml.py
    ├── distro/{__init__.py,suse.py}   # profile name -> package operations
    ├── source_fetcher/httpx.py
    ├── sandbox/buildah.py             # incl. copy_from_image (buildah copy --from) + image shaping
    ├── image_registry/buildah.py
    ├── image_transport/buildah.py
    └── reporter/rich.py
```

Adapters translate subprocess / HTTP / filesystem failures into
`core.domain.errors` at the boundary; raw exceptions never cross it.
