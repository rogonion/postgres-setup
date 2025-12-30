from pydantic import BaseModel, Field

from postgres_setup.core.spec.build.postgis import PostgisConfig
from postgres_setup.core.spec.build.postgres import PostgresConfig


class BuildahConfig(BaseModel):
    Path: str = 'buildah'


class BuildSpec(BaseModel):
    ProjectName: str
    BaseImage: str = "registry.opensuse.org/opensuse/tumbleweed:latest"
    Buildah: BuildahConfig = Field(default_factory=BuildahConfig)
    Postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    Postgis: PostgisConfig = Field(default_factory=PostgisConfig)
