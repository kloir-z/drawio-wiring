_ctr = 0


def nid(p="c"):
    """Return a unique ID using a global counter."""
    global _ctr
    _ctr += 1
    return f"{p}_{_ctr}"


def reset_ids():
    """Reset the counter (for testing)."""
    global _ctr
    _ctr = 0
