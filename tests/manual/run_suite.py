import glob
import subprocess
import sys
import os
import time

def main():
    # Find all verify_*.py scripts in the same directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    scripts = glob.glob("verify_*.py")
    scripts.sort()

    print(f"Found {len(scripts)} verification scripts.")
    print("="*60)

    results = []
    start_global = time.time()

    for script in scripts:
        print(f"\n>> RUNNING: {script}")
        print("-" * 30)
        
        t0 = time.time()
        # flush=True to ensure we see output
        try:
            # Run with python -u (unbuffered) to see output in real-time if we were piping, 
            # but here we let it inherit stdout/stderr so it prints directly to console.
            res = subprocess.run([sys.executable, "-u", script], check=False)
            dt = time.time() - t0
            
            status = "✅ PASS" if res.returncode == 0 else "❌ FAIL"
            results.append((script, status, dt))
            
            if res.returncode != 0:
                print(f"\n[!] {script} returned exit code {res.returncode}")

        except Exception as e:
            print(f"EXECUTION ERROR: {e}")
            results.append((script, "💥 ERROR", 0))

    print("\n" + "="*60)
    print("MANUAL SUITE SUMMARY")
    print("="*60)
    
    failures = 0
    for name, status, dt in results:
        print(f"{status} | {name:<35} | {dt:.2f}s")
        if "PASS" not in status:
            failures += 1
            
    total_time = time.time() - start_global
    print("-" * 60)
    print(f"Total Time: {total_time:.2f}s")
    print(f"Passed: {len(scripts) - failures}/{len(scripts)}")
    
    if failures > 0:
        print(f"FAILED: {failures} scripts.")
        sys.exit(1)
    else:
        print("ALL GREEN.")
        sys.exit(0)

if __name__ == "__main__":
    main()
