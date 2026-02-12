from theus.engine import TheusEngine
from pydantic import BaseModel

print("Verifying Proxy to_dict with Pydantic v2...")

class MyModel(BaseModel):
    x: int = 1

try:
    engine = TheusEngine(context={"domain": MyModel()})
    # Engine creates proxy
    proxy = engine.state.domain
    print(f"Proxy type: {type(proxy)}")
    
    # Check to_dict
    d = proxy.to_dict()
    print(f"Result: {d}")
    
    if d == {'x': 1}:
        print("SUCCESS: to_dict returned correct dict")
    else:   
        print(f"FAILURE: to_dict returned unexpected value: {d}")

except Exception as e:
    print(f"FAILURE: to_dict raised exception: {e}")
    import traceback
    traceback.print_exc()
