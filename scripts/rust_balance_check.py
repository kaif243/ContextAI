"""Cheap static check: balance of {}, () and [] in Rust source files.
Strips strings and comments before counting so quoted braces don't trip us up.
"""
import os
import re


def check(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # Strip line comments.
    cleaned = re.sub(r"//.*", "", text)
    # Strip block comments (non-greedy, no nesting in Rust but this is fine).
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.S)
    # Replace string literals with empty quoted markers so braces inside them don't count.
    cleaned = re.sub(r'"(?:\\.|[^"\\])*"', '""', cleaned)
    counts = {c: cleaned.count(c) for c in "{}()[]"}
    ok = (
        counts["{"] == counts["}"]
        and counts["("] == counts[")"]
        and counts["["] == counts["]"]
    )
    print(
        f"{os.path.relpath(path):60s}  "
        f"{{={counts['{']}/}}={counts['}']}  "
        f"(={counts['(']}/)={counts[')']}  "
        f"[={counts['[']}/]={counts[']']}  "
        f"{'OK' if ok else 'MISMATCH'}"
    )


for root, _, files in os.walk("src/tauri/src"):
    for fn in files:
        if fn.endswith(".rs"):
            check(os.path.join(root, fn))
