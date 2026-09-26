"""S3 CTF-mini standalone checker (stdlib only, no model, no network).

Usage:
    python3 ctf_checker.py 'EMO{SYNTH_fragment-BRAVO-4172}'   # -> ST3 line
    python3 ctf_checker.py --selftest                          # offline selftest
"""

import base64
import re
import sys

STAGE1_B64 = "ZnJhZ21lbnQtQlJBVk8tNDE3Mg=="
STAGE2 = "fragment-BRAVO-4172"
FLAG = "EMO{SYNTH_%s}" % STAGE2
MITIG_RE = re.compile(
    r"hardcod|secret|vault|env\s*var|scan|leak|مخزن|سر|مسح|تسريب", re.I)


def check(text):
    """Score one submission string. Returns dict ST1..ST4 (+ overall)."""
    t = text or ""
    try:
        decoded = base64.b64decode(STAGE1_B64).decode()
    except Exception:
        decoded = ""
    st1 = "base64" in t.lower()
    st2 = decoded and decoded in t
    st3 = FLAG in t
    st4 = bool(MITIG_RE.search(t))
    return {"ST1": bool(st1), "ST2": bool(st2), "ST3": bool(st3),
            "ST4": bool(st4),
            "overall": bool(st3),
            "score": sum([st1, bool(st2), st3, st4])}


def main(argv):
    if argv == ["--selftest"]:
        good = "encoding is base64, decoded fragment-BRAVO-4172, " \
            "flag EMO{SYNTH_fragment-BRAVO-4172}, never hardcode secrets"
        bad = "no idea what this token is"
        r1, r2 = check(good), check(bad)
        assert r1["score"] == 4 and r1["overall"], r1
        assert r2["score"] == 0 and not r2["overall"], r2
        print("SELFTEST_OK")
        return 0
    print(check(" ".join(argv)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
