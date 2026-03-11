from typing import List, Dict

from pydantic import BaseModel, Field


class BuildConfig(BaseModel):
    Dependencies: List[str] = Field(default_factory=list)


class RuntimeConfig(BaseModel):
    Dependencies: List[str] = Field(default_factory=list)


class RumVersion(BaseModel):
    SourceUrl: str
    Build: BuildConfig = Field(default_factory=BuildConfig)
    Runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)


class RumConfig(BaseModel):
    Current: str
    Versions: Dict[str, RumVersion] = Field(default_factory=list)
