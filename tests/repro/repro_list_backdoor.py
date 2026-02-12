from theus import TheusEngine
import os

def repro():
    print("--- REPRO: LIST MUTATION BACKDOOR ---")
    
    # 1. Setup engine with a list
    data = {"domain": {"my_list": [1, 2, 3], "my_dict": {"a": 1}}}
    engine = TheusEngine(context=data)
    
    print(f"Initial State: {engine.state.domain['my_list']}")
    
    # 2. Access via domain_proxy (Default read_only=True)
    proxy = engine.state.domain_proxy()
    print(f"Proxy Type: {type(proxy)}")
    
    # 3. Test DICT protection (Should fail with my fix)
    print("\nTesting Dict Protection...")
    try:
        proxy.my_dict['b'] = 2
        print("❌ FAILURE: Dict mutation SUCCEEDED outside transaction!")
    except Exception as e:
        print(f"✅ Dict mutation BLOCKED: {e}")

    # 4. Test LIST protection (Passive Inference Gap?)
    print("\nTesting List Protection...")
    list_from_proxy = proxy.my_list
    print(f"List object from proxy: {list_from_proxy} (Type: {type(list_from_proxy)})")
    
    try:
        list_from_proxy.append(999)
        print("⚠️  List mutation call SUCCEEDED in Python.")
    except Exception as e:
        print(f"✅ List mutation BLOCKED in Python: {e}")

    # 5. Check if state was compromised
    final_list = engine.state.domain['my_list']
    print(f"\nFinal State List: {final_list}")
    
    if 999 in final_list:
        print("❌ CRITICAL: Global State was COMPROMISED via List Backdoor!")
    else:
        print("✅ SUCCESS: Global State remains intact.")

if __name__ == "__main__":
    repro()
