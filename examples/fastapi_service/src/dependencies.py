import os
from functools import lru_cache
from typing import Generator

from theus import TheusEngine
from theus.config import ConfigFactory
from theus.audit import AuditRecipe, AuditLevel

from .context import ServiceContext, ServiceDomain, ServiceGlobal
from . import processes

# Singleton Instance
_engine_instance: TheusEngine | None = None

class Settings:
    # Simulating loading from env
    AUDIT_STRICT: bool = True
    THEUS_HEAP_SIZE: int = 512

@lru_cache
def get_settings() -> Settings:
    return Settings()

def get_engine() -> TheusEngine:
    """
    Dependency Provider for TheusEngine.
    Follows Singleton pattern for the Engine instance.
    """
    global _engine_instance
    
    if _engine_instance is None:
        print("[System] Initializing Theus Engine...")
        
        # 1. Init Context
        domain = ServiceDomain()
        global_ctx = ServiceGlobal()
        ctx = ServiceContext(global_ctx=global_ctx, domain=domain)
        
        # 2. Audit Config (Code-First or File-Based)
        # Here we define a simple rule: Block if thresholds exceeded
        audit_recipe = AuditRecipe(
            threshold_max=5,
            level=AuditLevel.Block,
            reset_on_success=True
        )
        
        # 3. Create Engine
        _engine_instance = TheusEngine(
            context=ctx,
            strict_guards=True,
            strict_cas=False, # Use Smart CAS
            audit_recipe=audit_recipe
        )
        
        # 4. Register Processes 
        # (Explicit registration is better for compiled binaries/PyInstaller)
        _engine_instance.register(processes.create_order)
        _engine_instance.register(processes.cancel_order)
        
        print(f"[System] Engine Ready. Version: {_engine_instance.state.version}")

    return _engine_instance
