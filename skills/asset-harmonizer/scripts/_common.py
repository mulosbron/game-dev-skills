"""Shared helpers for Blender-side harmonizer scripts (run inside `blender -b -P`)."""
import sys, json, re


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    d = {}
    i = 0
    while i < len(a):
        if a[i].startswith("--"):
            d[a[i][2:]] = a[i + 1]; i += 2
        else:
            i += 1
    return d


def style(path):
    return json.load(open(path, encoding="utf-8"))


def asset_class(name):
    m = re.search(r"_(bg|prop|hero|char)(_|\.)", name)
    return m.group(1) if m else "prop"
