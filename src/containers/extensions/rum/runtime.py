from src.core import BaseRuntime, init_base_distro


class RumRuntime(BaseRuntime):
    def _init_ext_version(self, ext_version: str):
        if not len(ext_version) > 0 or ext_version == "latest":
            ext_version = self.config.Rum.Current

        for version, data in self.config.Rum.Versions.items():
            if version == ext_version:
                self.ext_version = ext_version
                self.version_config = data
                return

        raise RuntimeError(f"No config found for rum extension version {ext_version}")

    def build(self):
        self.log(f"Adding Rum extension version {self.ext_version}", style="bold blue")

        rum_source_image = f"{self.config.ProjectName}-rum" + ":" + self.config.Postgres.Version + "-" + self.ext_version

        base_distro = init_base_distro(self.config.Distro, self.src_container)
        if self.version_config.Runtime and self.version_config.Runtime.Dependencies:
            deps = self.version_config.Runtime.Dependencies
            self.log(f"[bold blue]Installing dependencies[/bold blue]: {deps}")

            base_distro.install_packages(
                packages=deps,
                extra_cache_keys={"step": "deps", "packages": sorted(deps)}
            )

        staging_dir = f"/tmp/stage_rum-{self.ext_version}"
        self.log(f"[bold blue]Copying rum source into staging directory[/bold blue]: {staging_dir}")

        self.src_container.copy_container_current(
            rum_source_image,
            self.config.Postgres.Prefix,
            staging_dir
        )

        self.log(f"Syncing {staging_dir} to {self.config.Postgres.Prefix}", style="bold blue")
        self.src_container.run(
            command=[
                "rsync", "-av", "--ignore-existing",
                f"{staging_dir}/",
                f"{self.config.Postgres.Prefix}/"
            ]
        )

        self.log(f"[bold blue]Removing staging directory[/bold blue]: {staging_dir}")
        self.src_container.run(
            command=["rm", "-rf", staging_dir]
        )
