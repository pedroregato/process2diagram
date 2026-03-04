from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional


class Step(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    actor: Optional[str] = None
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)


class Edge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None


class ProcessModel(BaseModel):
    name: str = "Process"
    steps: List[Step]
    edges: List[Edge]
