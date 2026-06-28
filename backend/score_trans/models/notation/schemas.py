from __future__ import annotations

from pydantic import BaseModel, Field

from ..common.types import InstrumentProfile


class PerformanceMarkCatalogItem(BaseModel):
    id: str
    syntax: str
    name: str
    description: str
    category: str
    placement: str


class SyntaxExample(BaseModel):
    syntax: str
    description: str


class InstrumentProfileCatalog(BaseModel):
    id: InstrumentProfile
    name: str
    marks: list[PerformanceMarkCatalogItem] = Field(default_factory=list)
    range_examples: list[SyntaxExample] = Field(default_factory=list)
    combination_examples: list[SyntaxExample] = Field(default_factory=list)
