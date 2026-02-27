from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext, Namespace
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict


# --- 1. Global (Configuration) ---
@dataclass
class DemoGlobal(BaseGlobalContext):
    # [Policy: IMMUTABLE]
    meta_app_name: str = "Theus Universal Demo"
    meta_version: str = "3.0.2"
    max_retries: int = 3


# --- 2. Namespaced Contexts (Modular State) ---

@dataclass
class EcommerceContext(BaseDomainContext):
    # [Policy: APPEND_ONLY]
    log_orders: List[dict] = field(default_factory=list)
    log_processed: List[str] = field(default_factory=list)
    
    # [Policy: MUTABLE]
    balance: float = 0.0
    order_request: Optional[dict] = None


@dataclass
class TaskContext(BaseDomainContext):
    # [Policy: MUTABLE]
    active_tasks: Dict[str, Any] = field(default_factory=dict)
    sync_ops_count: int = 0
    async_job_result: Optional[str] = None
    log_outbox: List[Any] = field(default_factory=list)  # Restricted Outbox logs


@dataclass
class LegacyDomain(BaseDomainContext):
    """Fallback for shared/legacy state."""
    status: str = "IDLE"
    processed_count: int = 0
    parallel_consensus: float = 0.0


# --- 3. System (Root Container) ---
class DemoSystemContext(BaseSystemContext):
    global_ctx = Namespace(DemoGlobal)
    domain = Namespace(LegacyDomain)
    
    # RFC-002 Namespaces
    ecommerce = Namespace(EcommerceContext)
    tasks = Namespace(TaskContext)
