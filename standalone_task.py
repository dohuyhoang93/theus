
def standalone_add(x, y):
    """
    A purely standalone function with NO dependencies on 'theus'.
    """
    import os
    import threading
    return {
        "result": x + y,
        "pid": os.getpid(),
        "tid": threading.get_ident(),
        "context": "standalone"
    }
