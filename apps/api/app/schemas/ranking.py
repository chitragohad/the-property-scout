from pydantic import BaseModel, Field


class RankResult(BaseModel):
    listing_id: str
    score: float
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    excluded: bool = False
    exclusion_reasons: list[str] = Field(default_factory=list)
    reason: str


class Citation(BaseModel):
    id: str
    title: str
    url: str
    snippet: str
    locality: str | None = None
    topic: str | None = None
