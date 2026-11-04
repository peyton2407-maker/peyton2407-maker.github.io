#!/usr/bin/env python3
"""Keep index.html's version stamp for each separately loaded script (js/*.js) in step with the
file, so a browser never runs new page code with an old cached script. Run after editing a file
in js/; --check only reports (the change check uses it).

Usage: python3 scripts/stamp_assets.py [--check]
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "index.html"


def main():
    check = "--check" in sys.argv
    html = PAGE.read_text(encoding="utf-8")
    bad = []

    def fix(m):
        name, old = m.group(1), m.group(2)
        f = ROOT / "js" / name
        if not f.exists():
            bad.append(f"js/{name} is missing")
            return m.group(0)
        ver = hashlib.sha1(f.read_bytes()).hexdigest()[:10]
        if ver != old:
            bad.append(f"js/{name}: stamp {old}, file is {ver}")
        return f'"/js/{name}?v={ver}"'

    new = re.sub(r'"/js/([\w.-]+\.js)\?v=([0-9a-f]+)"', fix, html)
    if check:
        for b in bad:
            print(b)
        return 1 if bad else 0
    if new != html:
        PAGE.write_text(new, encoding="utf-8")
        print("stamped:", "; ".join(bad))
    else:
        print("stamps are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
