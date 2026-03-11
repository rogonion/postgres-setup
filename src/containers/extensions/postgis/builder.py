from src.core import BaseBuilder, BuildahContainer, prune_cache_images, BuildSpec, init_base_distro


class PostgisBuilder(BaseBuilder):
    def __init__(self, config: BuildSpec, ext_version: str = "", cache_prefix: str = ""):
        self._init_ext_version(config, ext_version)
        super().__init__(config, cache_prefix)
        self.base_image = f"{self.config.ProjectName}-core:{self.config.Postgres.Version}"
        self.image_name = f"{self.config.ProjectName}-postgis"
        self.image_tag = self.config.Postgres.Version + "-" + self.ext_version

    def _init_ext_version(self, config: BuildSpec, ext_version: str):
        if not len(ext_version) > 0 or ext_version == "latest":
            ext_version = config.Postgis.Current

        for version, data in config.Postgis.Versions.items():
            if version == ext_version:
                self.ext_version = ext_version
                self.version_config = data
                return

        raise RuntimeError(f"No config found for postgis extension version {ext_version}")

    def _init_cache_prefix(self, cache_prefix: str):
        if len(cache_prefix) > 0:
            self.cache_prefix = cache_prefix
        else:
            self.cache_prefix = f"{self.config.ProjectName}/cache/postgis/{self.ext_version}"

    def build(self):
        self.log(f"Starting build for Postgis {self.ext_version}", style="bold blue")

        current_step = 1
        total_no_of_steps = 4

        with BuildahContainer(
                base_image=self.base_image,
                image_name=self.image_name,
                config=self.config,
                cache_prefix=self.cache_prefix
        ) as container:
            base_distro = init_base_distro(self.config.Distro, container)
            if self.version_config.Build.Dependencies:
                total_no_of_steps += 1
                self.log(
                    f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Installing build dependencies")

                base_distro.refresh_package_repository()

                base_distro.install_packages(
                    packages=self.version_config.Build.Dependencies,
                    extra_cache_keys={"step": "deps", "packages": sorted(self.version_config.Build.Dependencies)}
                )
                current_step += 1

            self.log(
                f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Downloading source from {self.config.Postgres.SourceUrl}")

            src_dir = f"/tmp/postgis-{self.ext_version}"

            container.run_cached(
                command=[
                    "sh", "-c",
                    f"mkdir -p {src_dir} && curl -L '{self.version_config.SourceUrl}' | tar -xz -C {src_dir} --strip-components=1"
                ],
                extra_cache_keys={"step": "source", "url": self.version_config.SourceUrl, "src_dir": src_dir}
            )

            current_step += 1
            self.log(f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Configuring compilation")

            config_flags = self.version_config.Build.Flags
            if not any("pgconfig" in f for f in config_flags):
                config_flags.append(f"--with-pgconfig={self.config.Postgres.Prefix}/bin/pg_config")

            container.run_cached(
                command=[
                    "sh", "-c",
                    f"cd {src_dir} && ./configure {' '.join(config_flags)}"
                ],
                extra_cache_keys={"step": "configure", "flags": sorted(config_flags)}
            )

            current_step += 1
            self.log(f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Compiling and installing")

            container.run_cached(
                command=[
                    "sh", "-c",
                    f"cd {src_dir} && make -j$(nproc) && make install",
                ],
                extra_cache_keys={"step": "compile", "version": self.config.Postgres.Version}
            )

            current_step += 1
            self.log(
                f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Verifying installation.")

            pg_lib_dir = f"{self.config.Postgres.Prefix}/lib"
            pg_ext_dir = f"{self.config.Postgres.Prefix}/share/extension"

            # Check if control file exists
            try:
                container.run(["ls", f"{pg_ext_dir}/postgis.control"])
            except Exception:
                self.log(f"[bold red]Error[/bold red]: postgis.control not found in {pg_ext_dir}")
                raise

            # Check dynamic linking
            so_file_cmd = f"find {pg_lib_dir} -name 'postgis-*.so' | head -n 1"

            try:
                # We use sh -c to allow the pipe and find command
                output = container.run_get_output(["sh", "-c", f"ldd $({so_file_cmd})"])

                if "not found" in output:
                    self.log("[bold red]Linking Error[/bold red]: Missing dependencies detected")
                    self.log(output, style="dim red")
                    raise RuntimeError("PostGIS compiled, but system dependencies are missing.")

                self.log("Verification successful.", style="bold green")

            except Exception as e:
                self.log(f"[bold red]Verification Failed[/bold red]: {e}")
                raise

            current_step += 1
            image_name_tag = self.image_name + ":" + self.image_tag
            self.log(
                f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Tagging image and adding metadata.")

            container.configure([
                ("--label",
                 f'org.opencontainers.image.title="PostgreSQL {self.config.Postgres.Version} with PostGIS {self.ext_version}"'),
                ("--label", f'org.postgis.version={self.ext_version}'),
            ])
            container.commit(image_name_tag)

            self.log(f"Image tagged as: [green]{image_name_tag}[/green]")

    def prune_cache_images(self):
        prune_cache_images(self.config.Buildah.Path, self.cache_prefix)
