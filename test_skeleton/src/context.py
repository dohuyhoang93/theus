from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any
from theus.context import BaseSystemContext

# --- 1. Global (Configuration) ---
class DemoGlobal(BaseModel):
    app_name: str = "Theus V2 Industrial Demo"
    version: str = "0.2.0"
    max_retries: int = 3

# --- 2. Domain (Mutable State) ---
class DemoDomain(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # State flags
    status: str = "IDLE"          # System Status
    processed_count: int = 0      # Logic Counter
    items: List[str] = Field(default_factory=list) # Data Queue
    
    # Error tracking
    # Error tracking (META Zone)
    meta_last_error: Optional[str] = None

# --- 3. System (Root Container) ---
class DemoSystemContext(BaseSystemContext):
    def __init__(self):
        self.global_ctx = DemoGlobal()
        self.domain_ctx = DemoDomain()
