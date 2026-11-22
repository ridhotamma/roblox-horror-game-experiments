"""Runs tests/animator_test.luau with the luau CLI.

The CLI has no file access and required modules don't see the caller's globals, so this bundles everything into one
chunk: the Vector3/CFrame mocks, then DogAnimator, DogAnimations and Blender's pose fixture as functions whose
results are passed to the test.

  python models/dog/tests/run_animator_test.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def luau_exe():
    for c in (shutil.which("luau"), os.path.expanduser("~/.rokit/bin/luau.exe"), os.path.expanduser("~/.rokit/bin/luau")):
        if c and os.path.exists(c):
            return c
    return None


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def main():
    exe = luau_exe()
    if not exe:
        print("luau CLI not found (install with rokit); skipping")
        return 0
    chunk = "\n".join([
        read("tests", "mock_roblox.luau"),
        "local __DogAnimator = (function()\n" + read("roblox", "DogAnimator.luau") + "\nend)()",
        "local __DogAnimations = (function()\n" + read("roblox", "DogAnimations.luau") + "\nend)()",
        "local __Fixture = (function()\n" + read("out", "dog_fixture.luau") + "\nend)()",
        "local __test = function(...)\n" + read("tests", "animator_test.luau") + "\nend",
        "__test(__DogAnimator, __DogAnimations, __Fixture)",
    ])
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "bundle.luau")
        with open(path, "w", encoding="utf-8") as f:
            f.write(chunk)
        p = subprocess.run([exe, path], capture_output=True, text=True)
    sys.stdout.write(p.stdout + p.stderr)
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
