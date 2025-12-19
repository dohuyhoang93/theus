
try:
    from pydantic import BaseModel, ConfigDict, ValidationError
    HAS_PYDANTIC = True
    VERSION = 2
except ImportError:
    try:
        from pydantic import BaseModel, ValidationError
        HAS_PYDANTIC = True
        VERSION = 1
    except ImportError:
        HAS_PYDANTIC = False

if not HAS_PYDANTIC:
    print("SKIP: Pydantic not installed.")
    exit(0)

print(f"Running Pydantic Demo (Version {VERSION})...")

# --- Level 3 Implementation ---
class UserContext(BaseModel):
    name: str
    age: int

    # STRICT MODE ON
    if VERSION == 2:
        model_config = ConfigDict(validate_assignment=True)
    else:
        class Config:
            validate_assignment = True

def run_demo():
    # 1. Correct Init
    print("\n1. Init User(name='Nam', age=20)")
    u = UserContext(name="Nam", age=20)
    print(f"   -> Success: {u}")

    # 2. Strict Assignment Check
    print("\n2. Trying: u.age = 'InvalidString'")
    try:
        u.age = "InvalidString"
        print("   -> FAIL: Assignment accepted (Should not happen)")
    except ValidationError as e:
        print("   -> CAUGHT EXPECTED ERROR:")
        print(f"      {e}")
        print("   -> ✅ Strict Type Enforcement verified!")

# --- Added for Schema Gen Test ---
class SystemContext(BaseModel):
    # This matches the structure expected by schema_gen
    # Assuming standard POP structure: global, domain, local
    # But for this test, we just embed StrictUser as 'domain'
    domain: UserContext
    if VERSION == 2:
        model_config = ConfigDict(arbitrary_types_allowed=True)

if __name__ == "__main__":
    run_demo()
