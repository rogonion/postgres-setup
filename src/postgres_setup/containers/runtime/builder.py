from pathlib import Path
from typing import Tuple, List, Optional

from postgres_setup.containers.extensions.pgvector import PgvectorRuntime
from postgres_setup.containers.extensions.postgis import PostgisRuntime
from postgres_setup.containers.extensions.rum import RumRuntime
from postgres_setup.core import BaseBuilder, BuildSpec, prune_cache_images, BuildahContainer, init_base_distro

EXTENSIONS = ["postgis", "pgvector", "rum"]


class RuntimeBuilder(BaseBuilder):
    def __init__(self, config: BuildSpec, cache_prefix: str = "", image_name: str = "", image_tag: str = "",
                 extensions: Optional[List[Tuple[str, str]]] = None, remove_package_manager: bool = True,
                 squash: bool = True):
        super().__init__(config, cache_prefix)

        if len(image_name) > 0:
            self.image_name = image_name
        else:
            self.image_name = f"{self.config.ProjectName}-runtime"

        if len(image_tag) > 0:
            self.image_tag = image_tag
        else:
            self.image_tag = self.config.Postgres.Version

        if extensions:
            for extension in extensions:
                if not extension[0] in EXTENSIONS:
                    raise RuntimeError(f"Extension '{extension[0]}' not found.")

        self.extensions = extensions
        self.remove_package_manager = remove_package_manager
        self.squash = squash

    def _init_cache_prefix(self, cache_prefix: str):
        if len(cache_prefix) > 0:
            self.cache_prefix = cache_prefix
        else:
            self.cache_prefix = f"{self.config.ProjectName}/cache/runtime/{self.config.Postgres.Version}"

    def build(self):
        self.log(f"Starting build for Postgres {self.config.Postgres.Version} runtime", style="bold blue")

        current_step = 1

        with BuildahContainer(
                base_image=self.config.BaseImage,
                image_name=self.image_name,
                config=self.config,
                cache_prefix=self.cache_prefix
        ) as container:
            base_distro = init_base_distro(self.config.Distro, container)

            self.log(f"[bold blue]Step {current_step}[/bold blue]: Retrieving postgres binaries")

            self.image_tag = self.config.Postgres.Version
            container.copy_container_current(f"{self.config.ProjectName}-core:{self.config.Postgres.Version}",
                                             self.config.Postgres.Prefix, self.config.Postgres.Prefix)

            current_step += 1
            self.log(
                f"[bold blue]Step {current_step}[/bold blue]: Installing postgres runtime dependencies")

            base_distro.refresh_package_repository()

            base_distro.install_packages(
                packages=self.config.Postgres.Runtime.Dependencies,
                extra_cache_keys={"step": "deps", "packages": sorted(self.config.Postgres.Runtime.Dependencies)}
            )

            if self.extensions:
                self.log(
                    f"[bold blue]Step {current_step}[/bold blue]: Installing extensions {self.extensions}")

                for extension in self.extensions:
                    match (extension[0]):
                        case 'postgis':
                            postgis_build = PostgisRuntime(self.config, container, extension[1])
                            postgis_build.build()
                        case 'pgvector':
                            pgvector_build = PgvectorRuntime(self.config, container, extension[1])
                            pgvector_build.build()
                        case 'rum':
                            rum_build = RumRuntime(self.config, container, extension[1])
                            rum_build.build()
                        case _:
                            self.log(f'[bold red]Error[/bold red]: ')
                            raise RuntimeError(f"Extension {extension[0]} not found.")

            if self.config.Postgres.Runtime.RemoveDependencies:
                base_distro.remove_packages(
                    packages=self.config.Postgres.Runtime.RemoveDependencies
                )
            base_distro.clean_package_repository_cache()

            container.run(
                command=["update-ca-certificates"]
            )

            current_step += 1
            self.log(
                f"[bold blue]Step {current_step}[/bold blue]: Setting up system user")

            base_psql_dir = "/var/lib/pgsql"

            container.run(
                command=["groupadd", "-r", "-g", str(self.config.Postgres.Runtime.Gid), "postgres"]
            )

            container.run(
                command=["useradd", "-r", "-u", str(self.config.Postgres.Runtime.Uid), "-g",
                         str(self.config.Postgres.Runtime.Gid), "-d", base_psql_dir, "-s", "/sbin/nologin", "-c",
                         '"PostgreSQL Server"', "postgres"]
            )

            container.configure(
                [
                    ("--label", f"io.postgres.user.uid={self.config.Postgres.Runtime.Uid}"),
                    ("--label", f"io.postgres.user.gid={self.config.Postgres.Runtime.Gid}"),
                    ("--label", f"io.postgres.user.name=postgres"),
                ]
            )

            current_step += 1
            self.log(
                f"[bold blue]Step {current_step}[/bold blue]: Setting up directories & permissions")

            data_dir = f"{base_psql_dir}/data/{self.config.Postgres.MajorVersion}"
            container.run(
                command=["mkdir", "-p", data_dir]
            )
            container.run(
                command=["chown", "-R", f"{self.config.Postgres.Runtime.Uid}:{self.config.Postgres.Runtime.Gid}",
                         data_dir]
            )
            env_configuration: List[Tuple[str, str]] = []
            if self.config.Postgres.Runtime.Environment:
                for env in self.config.Postgres.Runtime.Environment:
                    env_configuration.append(("--env", env))
            container.configure([
                                    ("--env", f"PGDATA={data_dir}"),
                                    ("--volume", data_dir),
                                    ("--env",
                                     f"PATH={self.config.Postgres.Prefix}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
                                ] + env_configuration)

            # Config storage folder
            container.run(
                command=["mkdir", "-p", "/usr/share/postgresql/config"]
            )

            # Postgres config files
            for config_file in ["postgresql.conf", "pg_hba.conf"]:
                container.copy_host_container(Path(f"{self.config.Postgres.Runtime.Resources}/{config_file}"),
                                              f"/usr/share/postgresql/config/{config_file}")

            # Postgres entrypoint script
            container.copy_host_container(Path(f"{self.config.Postgres.Runtime.Resources}/entrypoint.sh"),
                                          "/usr/local/bin/entrypoint.sh")

            # Setup permissions
            container.run(
                command=[
                    "chown", "-R", f"{self.config.Postgres.Runtime.Uid}:{self.config.Postgres.Runtime.Gid}",
                    "/usr/share/postgresql/config",
                    "/usr/local/bin/entrypoint.sh"
                ]
            )

            if self.remove_package_manager:
                if not self.squash:
                    self.log("[bold yellow]Warning[/bold yellow]: Please enable squashing to reduce image size.")
                self.log("[blue dim]Removing package manager[/blue dim]")
                base_distro.remove_package_manager()

            container.run(
                command=[
                    "chmod", "+x", "/usr/local/bin/entrypoint.sh"
                ]
            )
            container.configure([
                ("--entrypoint", '["/usr/local/bin/entrypoint.sh"]'),
                ("--cmd", '["postgres"]'),
                ("--user", str(self.config.Postgres.Runtime.Uid))
            ])

            current_step += 1
            self.log(
                f"[bold blue]Step {current_step}[/bold blue]: Tagging image and adding metadata.")

            container.configure([
                ("--label", f"org.postgres.version={self.config.Postgres.Version}"),
                ("--label", f"org.postgres.prefix={self.config.Postgres.Prefix}")
            ])
            if self.config.Postgres.Runtime.Ports:
                for port in self.config.Postgres.Runtime.Ports:
                    container.configure([
                        ("--port", f"{port}")
                    ])
            image_name_tag = self.image_name + ":" + self.image_tag
            container.commit(image_name_tag, squash=self.squash)

            self.log(f"Image tagged as: [green]{image_name_tag}[/green]")

    def prune_cache_images(self):
        prune_cache_images(self.config.Buildah.Path, self.cache_prefix)
