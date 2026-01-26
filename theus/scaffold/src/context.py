from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any, Dict
from theus.context import BaseSystemContext

# --- 1. Global (Configuration) ---
class DemoGlobal(BaseModel):
    app_name: str = "Theus Universal Demo"
    version: str = "3.0.2"
    max_retries: int = 3
    
    def to_dict(self, *args, **kwargs):
        return self.model_dump()

# --- 2. Domain (Mutable State) ---
class DemoDomain(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # --- Shared / Standard ---
    status: str = "IDLE"
    processed_count: int = 0
    batch_items: List[str] = Field(default_factory=list) # Renamed from 'items'

    # --- E-Commerce Example ---
    order_request: Optional[dict] = None
    orders: List[dict] = Field(default_factory=list)
    balance: float = 0.0
    processed_orders: List[str] = Field(default_factory=list)
    
    # --- Async Outbox Example ---
    active_tasks: Dict[str, Any] = Field(default_factory=dict) # Holds asyncio.Task objects
    sync_ops_count: int = 0
    async_job_result: Optional[str] = None
    outbox_queue: List[Any] = Field(default_factory=list) # OutboxMsg objects

    # --- Parallel Demo inputs aren't in Domain usually, but we can store results here ---
    parallel_consensus: float = 0.0

    def to_dict(self, *args, **kwargs):
        return self.model_dump()

# --- 3. System (Root Container) ---
class DemoSystemContext(BaseSystemContext):
    def __init__(self):
        self.global_ctx = DemoGlobal()
        self.domain = DemoDomain()
