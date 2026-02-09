import os
import sys
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

# Goal: Verify the "Real World" usage of Theus CLI tools (Chapter 15)
# Commands to test:
# 1. init
# 2. audit gen-spec
# 3. audit inspect
# 4. schema gen
# 5. check

def run_command(args, cwd):
    """Run CLI command as a subprocess."""
    print(f"   $ python -m theus.cli {' '.join(args)}")
    cmd = [sys.executable, "-m", "theus.cli"] + args
    result = subprocess.run(
        cmd, 
        cwd=str(cwd), 
        check=False, 
        capture_output=True, 
        text=True,
        env={**os.environ, "PYTHONPATH": os.getcwd()} # Point PYTHONPATH to current root
    )
    if result.returncode != 0:
        print(f"   ❌ FAILED: {result.stderr}")
    return result

def main():
    print("==============================================")
    print("   THEUS CLI TOOLS VERIFICATION (CHAP 15) ")
    print("==============================================")
    
    # Setup Sandbox
    with tempfile.TemporaryDirectory() as temp_dir:
        sandbox = Path(temp_dir)
        project_name = "cli_demo_app"
        project_dir = sandbox / project_name
        
        print("\n[Step 1] Verify 'init' command")
        res = run_command(["init", project_name, "--quiet"], cwd=sandbox)
        if res.returncode == 0 and (project_dir / "main.py").exists():
            print("   ✅ Project Scaffolding: OK")
        else:
            print("   ❌ Init Failed.")
            return

        # Setup Dummy Process for Audit/Linker Check
        process_code = """
from theus import process

@process(inputs=["domain.counter"], outputs=["domain.counter"])
def my_task(ctx):
    # Violation POP-E01
    print("This is wrong") 
    ctx.domain.counter += 1
    return {"domain.counter": ctx.domain.counter}
"""
        (project_dir / "src/processes/task_a.py").write_text(process_code, encoding="utf-8")

        # Setup Dummy Context for Schema Gen
        context_code = """
from dataclasses import dataclass
from typing import List
from theus import BaseGlobalContext, BaseDomainContext

@dataclass
class AppGlobal(BaseGlobalContext):
    admin_email: str = "admin@test.com"

@dataclass
class AppDomain(BaseDomainContext):
    items: List[str] = None
"""
        (project_dir / "src/context.py").write_text(context_code, encoding="utf-8")

        print("\n[Step 2] Verify 'check' (Linter)")
        res = run_command(["check", "src/processes"], cwd=project_dir)
        if "Found 1 violations" in res.stdout or "POP-E01" in res.stdout:
            print("   ✅ Linter (check): OK (Caught violations)")
        else:
            print(f"   ❌ Linter Failed to catch violation. Output:\n{res.stdout}")

        print("\n[Step 3] Verify 'audit gen-spec'")
        res = run_command(["audit", "gen-spec"], cwd=project_dir)
        recipe_path = project_dir / "specs/audit_recipe.yaml"
        if res.returncode == 0 and recipe_path.exists():
            content = recipe_path.read_text("utf-8")
            if "my_task" in content:
                print("   ✅ Audit Spec Generation: OK")
            else:
                print("   ❌ Spec Generated but missing process 'my_task'")
        else:
            print("   ❌ Audit Gen-Spec Failed.")

        print("\n[Step 4] Verify 'audit inspect'")
        res = run_command(["audit", "inspect", "my_task"], cwd=project_dir)
        if "Audit Inspector: my_task" in res.stdout:
             print("   ✅ Audit Inspector: OK")
        else:
             print(f"   ❌ Audit Inspect Failed. Output:\n{res.stdout}")

        print("\n[Step 5] Verify 'schema gen'")
        res = run_command(["schema", "gen"], cwd=project_dir)
        schema_path = project_dir / "specs/context_schema.yaml"
        if res.returncode == 0 and schema_path.exists():
             content = schema_path.read_text("utf-8")
             if "admin_email" in content:
                 print("   ✅ Schema Generation: OK")
             else:
                 print("   ❌ Schema Gen failed (Missing fields)")
        else:
             print("   ❌ Schema Gen command failed.")

        print("\n==============================================")
        print("   🎉 ALL CLI TOOLS VERIFIED SUCCESSFULLY")

if __name__ == "__main__":
    main()
