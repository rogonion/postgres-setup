from typing import List, Dict

from pydantic import BaseModel, Field


class BuildConfig(BaseModel):
    Dependencies: List[str] = Field(default_factory=list)
    Flags: List[str] = Field(default_factory=list)


class RuntimeConfig(BaseModel):
    Dependencies: List[str] = Field(default_factory=list)


class PgvectorVersion(BaseModel):
    SourceUrl: str
    Build: BuildConfig = Field(default_factory=BuildConfig)
    Runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)


class PgvectorConfig(BaseModel):
    Current: str
    Versions: Dict[str, PgvectorVersion] = Field(default_factory=list)
