from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any
# Theus V2: Using Pydantic for robust type checking.

class GlobalContext(BaseModel):
    """Reads-only configuration and constants."""
    app_name: str = "My Theus Agent"
    version: str = "0.1.3"

class DomainContext(BaseModel):
    """Mutable domain state."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    counter: int = 0
    data: List[str] = Field(default_factory=list)

class SystemContext(BaseModel):
    """Root container."""
    global_ctx: GlobalContext
    domain_ctx: DomainContext
    is_running: bool = True
    
    # Engine Compatibility: Lock Manager Hook
    _lock_manager: Any = None
    
    def set_lock_manager(self, manager: Any):
        self._lock_manager = manager
