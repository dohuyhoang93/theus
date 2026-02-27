from typing import Annotated, get_type_hints
from theus.context import Mutable, BaseDomainContext, BaseSystemContext

class OverrideDomain(BaseDomainContext):
    const_data: Annotated[dict, Mutable]

class OverrideSystem(BaseSystemContext):
    domain: OverrideDomain

print("Testing OverrideDomain instantiation...")
obj = OverrideDomain()
print(f"obj: {obj}")

print("\n--- Method 1: __annotations__ ---")
ann = getattr(type(obj), '__annotations__', {})
print('ann:', ann)
if 'const_data' in ann:
    print('metadata:', getattr(ann['const_data'], '__metadata__', None))

print("\n--- Method 2: get_type_hints(include_extras=True) ---")
try:
    hints = get_type_hints(type(obj), include_extras=True)
    print("hints:", hints)
    if 'const_data' in hints:
        print('metadata:', getattr(hints['const_data'], '__metadata__', None))
except Exception as e:
    print("get_type_hints failed:", e)

print("\n--- Method 3: Pydantic model_fields ---")
fields = getattr(obj, "model_fields", getattr(obj, "__fields__", None))
print("fields:", list(fields.keys()) if fields else None)
if fields and 'const_data' in fields:
    field_info = fields['const_data']
    try:
        # Pydantic v2
        ann = field_info.annotation
        print("annotation:", ann)
        print("metadata:", getattr(ann, '__metadata__', None))
    except AttributeError:
        # Pydantic v1
        print("type_:", field_info.type_)
        print("metadata:", getattr(field_info.type_, '__metadata__', None))
