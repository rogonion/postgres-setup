from pydantic import BaseModel, Field

from postgres_setup.core.spec.build.pgvector import PgvectorConfig
from postgres_setup.core.spec.build.postgis import PostgisConfig
from postgres_setup.core.spec.build.postgres import PostgresConfig
from postgres_setup.core.spec.build.rum import RumConfig


class BuildahConfig(BaseModel):
    Path: str = 'buildah'


class BuildSpec(BaseModel):
    ProjectName: str
    BaseImage: str
    Buildah: BuildahConfig = Field(default_factory=BuildahConfig)
    Postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    Postgis: PostgisConfig = Field(default_factory=PostgisConfig)
    Pgvector: PgvectorConfig = Field(default_factory=PgvectorConfig)
    Rum: RumConfig = Field(default_factory=RumConfig)
