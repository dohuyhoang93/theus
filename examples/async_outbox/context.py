
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class DemoDomainContext:
    # Runtime-only (Not persisted to DB, but kept in Memory)
    active_tasks: Dict[str, Any] = field(default_factory=dict)
    
    # Transaction Buffer (Accumulates events before Flush)
    outbox_buffer: List[Dict] = field(default_factory=list)
    
    # Ops Counter for verification
    sync_ops_count: int = 0
    async_job_result: str = ""

@dataclass
class DemoSystemContext:
    domain: DemoDomainContext
    
    # Aliases for v2/v3 compatibility helper if used
    @property
    def domain_ctx(self):
        return self.domain
