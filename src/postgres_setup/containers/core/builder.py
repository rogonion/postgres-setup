from postgres_setup.core import BaseBuilder, BuildahContainer, prune_cache_images, BuildSpec


class CoreBuilder(BaseBuilder):
    def __init__(self, config: BuildSpec, cache_prefix: str = ""):
        super().__init__(config, cache_prefix)
        self.image_name = f"{self.config.ProjectName}-core"
        self.image_tag = self.config.Postgres.Version

    def _init_cache_prefix(self, cache_prefix: str):
        if len(cache_prefix) > 0:
            self.cache_prefix = cache_prefix
        else:
            self.cache_prefix = f"{self.config.ProjectName}/cache/core/{self.config.Postgres.Version}"

    def build(self):
        self.log(f"Starting build for Postgres {self.config.Postgres.Version} core", style="bold blue")

        current_step = 1
        total_no_of_steps = 6

        with BuildahContainer(
                base_image=self.config.BaseImage,
                image_name=self.image_name,
                config=self.config,
                cache_prefix=self.cache_prefix
        ) as container:
            self.log(
                f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Installing build dependencies")

            container.run_cached(
                command=["zypper", "install", "-y"] + self.config.Postgres.Build.Dependencies,
                extra_cache_keys={"step": "deps", "packages": sorted(self.config.Postgres.Build.Dependencies)}
            )

            current_step += 1
            self.log(
                f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Downloading source from {self.config.Postgres.SourceUrl}")

            tar_path = f"/tmp/postgresql-{self.config.Postgres.Version}.tar.bz2"
            src_dir = f"/tmp/postgresql-{self.config.Postgres.Version}"

            container.run_cached(
                command=[
                    "sh", "-c",
                    f"curl -L '{self.config.Postgres.SourceUrl}' -o {tar_path} && tar -xf {tar_path} -C /tmp"
                ],
                extra_cache_keys={"step": "source", "url": self.config.Postgres.SourceUrl, "src_dir": src_dir,
                                  "tar_path": tar_path}
            )

            current_step += 1
            self.log(f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Configuring compilation")

            configure_args = ["./configure",
                              f"--prefix={self.config.Postgres.Prefix}"] + self.config.Postgres.Build.Flags

            container.run_cached(
                command=[
                    "sh", "-c",
                    f"cd {src_dir} && {' '.join(configure_args)}"
                ],
                extra_cache_keys={"step": "configure", "flags": sorted(self.config.Postgres.Build.Flags)}
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

            try:
                container.run(["test", "-x", f"{self.config.Postgres.Prefix}/bin/postgres"])
                container.run([f"{self.config.Postgres.Prefix}/bin/postgres", "--version"])
                self.log("Verification successful.", style="bold green")
            except Exception:
                self.log("[bold red]Verification Failed[/bold red]: Postgres binary missing or corrupt.")
                raise

            current_step += 1
            self.log(
                f"[bold blue]Step {current_step}/{total_no_of_steps}[/bold blue]: Tagging image and adding metadata.")

            container.configure([
                ("--env",
                 f"PATH={self.config.Postgres.Prefix}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
                ("--label", f"org.postgres.version={self.config.Postgres.Version}"),
                ("--label", f"org.postgres.prefix={self.config.Postgres.Prefix}"),
            ])
            image_name_tag = self.image_name + ":" + self.image_tag
            container.commit(image_name_tag)

            self.log(f"Image tagged as: [green]{image_name_tag}[/green]")

    def prune_cache_images(self):
        prune_cache_images(self.config.Buildah.Path, self.cache_prefix)
