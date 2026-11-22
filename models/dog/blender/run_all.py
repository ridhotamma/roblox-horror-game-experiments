"""Rebuilds the Dog end to end with headless Blender: mesh -> rig -> animations -> exports -> Luau animator test.

  python models/dog/blender/run_all.py [--preview] [--blender "C:/Program Files/Blender Foundation/Blender 5.3/blender.exe"]

--preview also renders out/mesh-*.png and the out/anim-*.png contact sheets.
"""
import os
import sys
import json
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"


def blender_exe():
    if "--blender" in sys.argv:
        return sys.argv[sys.argv.index("--blender") + 1]
    return os.environ.get("BLENDER_PATH") or shutil.which("blender") or DEFAULT_BLENDER


def stage(label, blend, script, *args):
    cmd = [blender_exe(), "-b"]
    cmd += [blend] if blend else ["--factory-startup"]
    cmd += ["--python", os.path.join(HERE, script), "--", *args]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    result = None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT "):
            result = json.loads(line[7:])
    if p.returncode != 0 or result is None or "Traceback" in p.stderr + p.stdout:
        sys.stdout.write(p.stdout[-4000:] + p.stderr[-4000:])
        raise SystemExit(f"{label} failed")
    print(f"== {label}: {json.dumps(result)[:900]}")
    return result


def main():
    preview = ["--preview"] if "--preview" in sys.argv else []
    stage("mesh", None, "build_dog.py", *preview)
    stage("rig", os.path.join(HERE, "Dog_mesh.blend"), "rig_dog.py")
    stage("animate", os.path.join(HERE, "Dog_rig.blend"), "animate_dog.py", *preview)
    stage("export", os.path.join(HERE, "Dog.blend"), "export_roblox.py")
    test = os.path.join(ROOT, "tests", "run_animator_test.py")
    if subprocess.run([sys.executable, test]).returncode != 0:
        raise SystemExit("animator test failed")

if __name__ == "__main__":
    main()
