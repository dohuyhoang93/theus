import inspect
import theus_core
import os

def generate_stub_block(obj, name):
    lines = []
    
    # Class Handling
    if inspect.isclass(obj):
        lines.append(f"class {name}:")
        doc = inspect.getdoc(obj)
        if doc:
            lines.append(f'    """{doc}"""')
        
        # Methods
        for member_name, member in inspect.getmembers(obj):
            if member_name.startswith("__"): continue # Skip dunder for now unless essential
            
            sig = None
            try:
                sig = inspect.signature(member)
            except ValueError:
                pass
            
            if sig:
                 lines.append(f"    def {member_name}{sig}: ...")
    
    lines.append("")
    return "\n".join(lines)

def main():
    print("Generating stubs for theus_core...")
    
    content = ["from typing import Any, Optional, List, Dict", "", ""]
    
    # Introspect TheusEngine
    # Logic: inspect.signature works for pyo3 classes if annotated!
    
    for name, obj in inspect.getmembers(theus_core):
        if inspect.isclass(obj):
            # Special handling for TheusEngine method signatures
            print(f"Processing Class: {name}")
            content.append(f"class {name}:")
            
            for m_name, m_obj in inspect.getmembers(obj):
                # Filter useful methods
                if m_name.startswith("__") and m_name not in ["__init__", "__enter__", "__exit__"]: 
                    continue
                
                # Check if it's a method/function (routine)
                if not (inspect.isroutine(m_obj) or inspect.isfunction(m_obj) or inspect.ismethod(m_obj)):
                    continue

                try:
                    sig = inspect.signature(m_obj)
                    # Pyo3 signatures usually clean.
                    content.append(f"    def {m_name}{sig}: ...")
                except (ValueError, TypeError):
                    # Fallback for things like built-in methods without signatures
                    content.append(f"    def {m_name}(self, *args, **kwargs): ...")
            
            content.append("")

    output_path = "theus/theus_core.pyi"
    os.makedirs("theus", exist_ok=True)
    
    with open(output_path, "w") as f:
        f.write("\n".join(content))
        
    print(f"✅ Generated {output_path}")

if __name__ == "__main__":
    main()
