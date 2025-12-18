from pydantic import BaseModel, Field
from typing import List
from theus.context import BaseSystemContext

class GlobalState(BaseModel):
    app_mode: str = "DEV"
    uptime: float = 0.0

class DomainData(BaseModel):
    # This is the data we process linearly
    items: List[str] = Field(default_factory=list)
    status: str = "READY"
    processed_count: int = 0

class DemoSystemContext(BaseSystemContext):
    def __init__(self):
        self.global_ctx = GlobalState()
        self.domain_ctx = DomainData()
