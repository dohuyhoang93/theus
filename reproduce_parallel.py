
try:
    from theus.parallel import InterpreterPool
    print("Import successful (unexpected on < 3.14)")
except ImportError as e:
    print(f"Caught expected ImportError: {e}")
except Exception as e:
    print(f"Caught unexpected error: {type(e).__name__}: {e}")
