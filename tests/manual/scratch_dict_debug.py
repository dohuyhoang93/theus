"""Diagnostic: How is __dict__ being resolved on SupervisorProxy?"""
import theus_core
from theus_core import SupervisorProxy

# 1. Check type-level __dict__ descriptor
sp_type = type.__getattribute__(SupervisorProxy, '__dict__')
print(f"1. SupervisorProxy type dict: {type(sp_type)}")
print(f"   Has __dict__ descriptor: {'__dict__' in sp_type}")

# 2. Check tp_flags for subclass/dict support
print(f"2. SupervisorProxy.__flags__: {getattr(SupervisorProxy, '__flags__', 'N/A')}")
print(f"   Has __slots__: {hasattr(SupervisorProxy, '__slots__')}")
print(f"   __basicsize__: {getattr(SupervisorProxy, '__basicsize__', 'N/A')}")

# 3. Try to create an instance and check __dict__
# We need TheusEngine to create a proper SupervisorProxy
import asyncio
from theus.engine import TheusEngine
from theus.contracts import process

@process(inputs=["domain"], outputs=["domain.status"])
async def p_debug(ctx):
    domain = ctx.domain
    print(f"\n3. ctx.domain type: {type(domain)}")
    
    # Check if __dict__ descriptor exists on the TYPE of domain
    domain_type = type(domain)
    has_dict_descr = '__dict__' in type.__getattribute__(domain_type, '__dict__')
    print(f"   __dict__ in type's __dict__: {has_dict_descr}")
    
    # Try type.__getattribute__ directly (bypasses __getattr__)
    try:
        d = type.__getattribute__(domain, '__dict__')
        print(f"   type.__getattribute__(domain, '__dict__'): type={type(d)}, keys={list(d.keys()) if isinstance(d, dict) else 'N/A'}")
    except AttributeError as e:
        print(f"   type.__getattribute__ -> AttributeError: {e}")
    except PermissionError as e:
        print(f"   type.__getattribute__ -> PermissionError: {e}")
    
    # Try object.__getattribute__ directly
    try:
        d = object.__getattribute__(domain, '__dict__')
        print(f"   object.__getattribute__(domain, '__dict__'): type={type(d)}")
    except AttributeError as e:
        print(f"   object.__getattribute__ -> AttributeError: {e}")
    except PermissionError as e:
        print(f"   object.__getattribute__ -> PermissionError: {e}")
    
    # Try getattr (goes through __getattr__)
    try:
        d = getattr(domain, '__dict__')
        print(f"   getattr(domain, '__dict__'): type={type(d)}")
    except PermissionError as e:
        print(f"   getattr -> PermissionError: {e} ✅ BLOCKED")
    except AttributeError as e:
        print(f"   getattr -> AttributeError: {e}")
    
    ctx.domain.status = "done"
    return None

engine = TheusEngine(context={"domain": {"status": "", "data": "test"}})
asyncio.run(engine.execute(p_debug))
