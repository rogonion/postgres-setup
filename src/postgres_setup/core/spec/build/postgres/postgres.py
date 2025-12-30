from typing import List

from pydantic import BaseModel, Field


class BuildConfig(BaseModel):
    Dependencies: List[str] = Field(default_factory=list)
    Flags: List[str] = Field(default_factory=list)


class RuntimeConfig(BaseModel):
    Dependencies: List[str] = Field(default_factory=list)
    Resources: str = "resources"


class PostgresConfig(BaseModel):
    Version: str
    MajorVersion: str
    SourceUrl: str
    Prefix: str = '/usr/local/pgsql'
    Build: BuildConfig = Field(default_factory=BuildConfig)
    Runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
