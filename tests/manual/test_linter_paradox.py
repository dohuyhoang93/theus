from typing import Annotated
from theus.context import BaseDomainContext, Mutable

# Goal: Verify POP-E07 (Paradox Check)
# This class contains intentional semantic contradictions.

class MyParadoxContext(BaseDomainContext):
    # 1. Paradox: Log prefix vs Mutable tag
    log_v1: Annotated[list, Mutable] = []
    
    # 2. Paradox: Audit prefix vs Mutable tag
    audit_events: Annotated[dict, Mutable] = {}
    
    # 3. Paradox: Signal prefix vs Mutable tag
    sig_control: Annotated[int, Mutable] = 0
    
    # 4. Paradox: Meta prefix vs Mutable tag
    meta_config: Annotated[str, Mutable] = "safe"
    
    # 5. OK: Standard data prefix with Mutable
    data_user: Annotated[dict, Mutable] = {}
    
    # 6. OK: Log prefix without Mutable
    log_history: list = []

def some_process():
    # Placeholder for linter to scan
    pass
