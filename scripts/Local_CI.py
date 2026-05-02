import subprocess
import sys
import os
import platform
import time

def get_env():
    """Configure environment variables for reliable builds."""
    env = os.environ.copy()
    
    # [CRITICAL] Fix Stale Binary & Build Failure on Python 3.14
    env["PYO3_USE_ABI3_FORWARD_COMPATIBILITY"] = "1"
    
    # [CRITICAL] Fix 'no Python 3.x interpreter found' on Windows
    env["PYO3_PYTHON"] = sys.executable
    
    # [VENV Detection] Help maturin find the right venv
    if "VIRTUAL_ENV" not in env:
        python_dir = os.path.dirname(sys.executable)
        venv_root = os.path.dirname(python_dir)
        if os.path.exists(os.path.join(venv_root, "pyvenv.cfg")):
            env["VIRTUAL_ENV"] = venv_root
            env["PATH"] = python_dir + os.pathsep + env.get("PATH", "")
            print(f"🔧 Auto-detected VIRTUAL_ENV: {venv_root}")
            
    return env

def get_project_root():
    """Get the absolute path to the project root (parent of scripts/)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)

def run_step(cmd, env, title):
    """Run a command with visible logging and correct CWD."""
    project_root = get_project_root()
    print("\n==================================================")
    print(f"🚀 [STEP] {title}")
    print(f"   Exec: {' '.join(cmd)}")
    print(f"   CWD:  {project_root}")
    print("==================================================")
    
    start_time = time.time()
    try:
        # shell=True required for Windows scripts/shims resolution
        use_shell = (platform.system() == "Windows")
        # [CRITICAL] Always run from project root to find pyproject.toml
        subprocess.check_call(cmd, env=env, shell=use_shell, cwd=project_root)
        
        duration = time.time() - start_time
        print(f"✅ [SUCCESS] {title} ({duration:.2f}s)")
    except subprocess.CalledProcessError as e:
        print(f"❌ [FAILED] {title} (Exit Code: {e.returncode})")
        sys.exit(e.returncode)

def step_build_install(env):
    """Build Rust Core and Install into current environment."""
    # Try maturin develop first (faster, editable-ish)
    try:
        run_step(["maturin", "develop", "--release"], env, "Compiling Rust Core (Maturin)")
    except SystemExit:
        print("⚠️ 'maturin develop' failed. Fallback to pip install...")
        run_step([sys.executable, "-m", "pip", "install", "."], env, "Installing via Pip")

def step_gen_stubs(env):
    """Generate Python Type Stubs (.pyi)."""
    # PYTHON PATH must point to project root for imports to work
    env["PYTHONPATH"] = get_project_root()
    run_step([sys.executable, "scripts/gen_stubs.py"], env, "Generating Type Stubs")

def step_test_automated(env):
    """Run Pytest Suite."""
    env["PYTHONPATH"] = get_project_root()
    run_step([sys.executable, "-m", "pytest", "tests/"], env, "Running Automated Tests (Pytest)")

def step_test_manual(env):
    """Run Manual Integration Suite."""
    env["PYTHONPATH"] = get_project_root()
    run_step([sys.executable, "tests/manual/run_suite.py"], env, "Running Manual Integration Suite")

def step_clippy(env):
    """Run Cargo Clippy with strict lint levels (pedantic minimum)."""
    run_step(
        [
            "cargo",
            "clippy",
            "--all-targets",
            "--all-features",
            "--",
            "-D",
            "warnings",
            "-W",
            "clippy::pedantic",
            "-A",
            "clippy::needless_pass_by_value",
            "-A",
            "clippy::unnecessary_wraps",
            "-A",
            "clippy::unused_self",
            "-A",
            "clippy::missing_errors_doc",
            "-A",
            "clippy::missing_panics_doc",
            "-A",
            "clippy::manual_let_else",
            "-A",
            "clippy::used_underscore_items",
            "-A",
            "clippy::used_underscore_binding",
            "-A",
            "clippy::doc_link_with_quotes",
            "-A",
            "clippy::match_same_arms",
            "-A",
            "clippy::cast_possible_truncation",
            "-A",
            "clippy::cast_sign_loss",
            "-A",
            "clippy::cast_precision_loss",
            "-A",
            "clippy::items_after_statements",
            "-A",
            "clippy::unreadable_literal",
            "-A",
            "clippy::needless_continue",
            "-A",
            "clippy::only_used_in_recursion",
        ],
        env,
        "Running Cargo Clippy (Strict + Pedantic)",
    )

def step_pyright(env):
    """Run Pyright static type checking."""
    env["PYTHONPATH"] = get_project_root()
    run_step([sys.executable, "-m", "pyright"], env, "Running Pyright")

def step_ruff(env):
    """Run Ruff Python linter/formatter."""
    env["PYTHONPATH"] = get_project_root()
    run_step([sys.executable, "-m", "ruff", "check", "."], env, "Running Ruff")

def step_rust_test(env):
    """Run Rust unit tests."""
    run_step(["cargo", "test"], env, "Running Rust Tests")

def step_verify_parity(env):
    """Run API Parity Verification."""
    env["PYTHONPATH"] = get_project_root()
    run_step([sys.executable, "tests/verify_api_parity.py"], env, "Verifying API Parity")

def main():
    print("🛡️  Theus Local CI Automation Tool")
    print(f"   Python: {sys.version.split()[0]}")
    print(f"   Platform: {platform.system()}")
    
    args = sys.argv[1:]
    
    # Handle Help
    if not args or args[0] in ["--help", "-h", "help"]:
        print("\nUsage: python scripts/Local_CI.py <command>")
        print("Commands:")
        print("  full   : Build -> Stubs -> Clippy -> Pyright -> Ruff -> Rust Test -> Pytest -> Manual Test")
        print("  build  : Build -> Install")
        print("  verify : Build -> Clippy -> Pyright -> Ruff -> Rust Test -> Verify API Parity")
        print("  help   : Show this help message")
        sys.exit(0)
        
    command = args[0].lower()
    env = get_env()
    
    if command == "full":
        step_build_install(env)
        step_gen_stubs(env)
        step_clippy(env)
        step_pyright(env)
        step_ruff(env)
        step_rust_test(env)
        step_test_automated(env)
        step_test_manual(env)
    elif command == "build":
        step_build_install(env)
    elif command == "verify":
        step_build_install(env)
        step_clippy(env)
        step_pyright(env)
        step_ruff(env)
        step_rust_test(env)
        step_verify_parity(env)
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)
        
    print("\n🎉 LOCAL CI COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
