from pathlib import Path
from typing import Tuple, List, Optional

from postgres_setup.containers.extensions.pgvector import PgvectorRuntime
from postgres_setup.containers.extensions.postgis import PostgisRuntime
from postgres_setup.containers.extensions.rum import RumRuntime
from postgres_setup.core import BaseBuilder, BuildSpec, prune_cache_images, BuildahContainer

EXTENSIONS = ["postgis", "pgvector", "rum"]


class RuntimeBuilder(BaseBuilder):
    def __init__(self, config: BuildSpec, cache_prefix: str = "", image_name: str = "", image_tag: str = "",
                 extensions: Optional[List[Tuple[str, str]]] = None):
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

            self.log(f"[bold blue]Step {current_step}[/bold blue]: Retrieving postgres binaries")

            self.image_tag = self.config.Postgres.Version
            container.copy_container_current(f"{self.config.ProjectName}-core:{self.config.Postgres.Version}",
                                             self.config.Postgres.Prefix, self.config.Postgres.Prefix)

            current_step += 1
            self.log(
                f"[bold blue]Step {current_step}[/bold blue]: Installing postgres runtime dependencies")

            container.run_cached(
                command=[
                    "sh", "-c",
                    f"""
                        zypper --non-interactive refresh &&
                        zypper --non-interactive install """ + " ".join(self.config.Postgres.Runtime.Dependencies)],
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

            container.run(
                command=[
                    "sh", "-c",
                    f"""
                    zypper --non-interactive remove -y --clean-deps rsync &&
                    zypper clean --all"""]
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
            container.configure([
                ("--env", f"PGDATA={data_dir}"),
                ("--volume", data_dir),
                ("--env",
                 f"PATH={self.config.Postgres.Prefix}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
            ])

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
                ("--label", f"org.postgres.prefix={self.config.Postgres.Prefix}"),
            ])
            image_name_tag = self.image_name + ":" + self.image_tag
            container.commit(image_name_tag)

            self.log(f"Image tagged as: [green]{image_name_tag}[/green]")

    def prune_cache_images(self):
        prune_cache_images(self.config.Buildah.Path, self.cache_prefix)
