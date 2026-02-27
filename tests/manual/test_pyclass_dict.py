"""Minimal test: Does SupervisorProxy have __dict__ after removing subclass?"""
import theus_core
from theus_core import SupervisorProxy

# Check type-level dict for __dict__ descriptor
type_dict = type.__getattribute__(SupervisorProxy, '__dict__')
has_dict_descr = '__dict__' in type_dict
print(f"SupervisorProxy type has __dict__ descriptor: {has_dict_descr}")

# Check if the type supports __dict__ via tp_dictoffset
# If no subclass, vars() should raise TypeError
try:
    v = vars(SupervisorProxy)
    print(f"vars(SupervisorProxy) = type {type(v)}, keys: {list(v.keys())[:5]}...")
except TypeError as e:
    print(f"vars(SupervisorProxy) TypeError: {e}")

print(f"\nSupervisorProxy.__flags__: {SupervisorProxy.__flags__}")
print(f"SupervisorProxy.__basicsize__: {SupervisorProxy.__basicsize__}")

# Check if mro has __dict__
for cls in SupervisorProxy.__mro__:
    cls_dict = type.__getattribute__(cls, '__dict__')
    if '__dict__' in cls_dict:
        print(f"\n__dict__ descriptor found on: {cls}")
        descr = cls_dict['__dict__']
        print(f"  descriptor type: {type(descr)}")
