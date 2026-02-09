from dataclasses import dataclass, field
from typing import Dict, List, Optional
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

@dataclass
class ServiceDomain(BaseDomainContext):
    # Data Zone
    orders: Dict[str, dict] = field(default_factory=dict)
    inventory: Dict[str, int] = field(default_factory=dict)
    
    # Init some values
    def __post_init__(self):
        if not self.inventory:
            self.inventory["item_123"] = 100
            self.inventory["item_456"] = 0

@dataclass
class ServiceGlobal(BaseGlobalContext):
    api_version: str = "v1"

@dataclass
class ServiceContext(BaseSystemContext):
    pass
