"""Patch basicsr's removed torchvision import (known incompat: torchvision.transforms.functional_tensor)."""
import importlib.util, pathlib, sys
spec = importlib.util.find_spec("basicsr")
if not spec: sys.exit("basicsr not installed")
f = pathlib.Path(spec.origin).parent / "data" / "degradations.py"
t = f.read_text(encoding="utf-8")
new = t.replace("from torchvision.transforms.functional_tensor import rgb_to_grayscale",
                "from torchvision.transforms.functional import rgb_to_grayscale")
if new != t: f.write_text(new, encoding="utf-8"); print("patched", f)
else: print("nothing to patch")
