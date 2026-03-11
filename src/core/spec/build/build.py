from enum import StrEnum

from pydantic import BaseModel, Field

from .pgvector import PgvectorConfig
from .postgis import PostgisConfig
from .postgres import PostgresConfig
from .rum import RumConfig


class BuildahConfig(BaseModel):
    Path: str = 'buildah'


class Distro(StrEnum):
    SUSE = "suse"


class BuildSpec(BaseModel):
    ProjectName: str
    BaseImage: str
    Distro: Distro
    Buildah: BuildahConfig = Field(default_factory=BuildahConfig)
    Postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    Postgis: PostgisConfig = Field(default_factory=PostgisConfig)
    Pgvector: PgvectorConfig = Field(default_factory=PgvectorConfig)
    Rum: RumConfig = Field(default_factory=RumConfig)
