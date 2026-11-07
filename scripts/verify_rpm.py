#!/usr/bin/env python3
"""Validate architecture, required resources, and the packaged GLIBC baseline."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from plan import package_name


def command(*args):
    return subprocess.check_output(args, text=True)


def verify(source, version, arch, sha, destination):
    candidates = list(Path(source).glob("*.rpm"))
    if len(candidates) != 1:
        raise ValueError(f"Expected one RPM, found {len(candidates)}")
    artifact = candidates[0].resolve()
    identity = command("rpm", "-qp", "--queryformat", "%{NAME}\n%{VERSION}\n%{RELEASE}\n%{ARCH}\n", str(artifact)).splitlines()
    if identity != ["dsh-tauri", version, "1.github", arch]:
        raise ValueError(f"Unexpected RPM identity: {identity}")
    files = command("rpm", "-qlp", str(artifact)).splitlines()
    required = ["/usr/bin/deepseek-harness-desktop", "/usr/lib/DSH Tauri/licenses/upstream/LICENSE", "/usr/lib/DSH Tauri/licenses/upstream/LICENSE.details"]
    if not all(name in files for name in required):
        raise ValueError("RPM is missing its executable or upstream license notices")
    if not any("/runtime/" in name and name.endswith("/chrome-sandbox") for name in files):
        raise ValueError("RPM is missing the Electron sandbox helper")
    if not any(name.startswith("/usr/share/applications/") and name.endswith(".desktop") for name in files):
        raise ValueError("RPM has no desktop launcher")
    highest = (0, 0)
    elf_count = 0
    with tempfile.TemporaryDirectory(prefix="rpm-verify-") as temp:
        unpack = subprocess.Popen(["rpm2cpio", str(artifact)], stdout=subprocess.PIPE)
        try:
            result = subprocess.run(["cpio", "-idm", "--quiet", "--no-absolute-filenames"], cwd=temp, stdin=unpack.stdout, capture_output=True)
            unpack.stdout.close()
            if unpack.wait() or result.returncode:
                raise ValueError("Could not extract RPM payload")
        finally:
            if unpack.poll() is None:
                unpack.kill()
                unpack.wait()
        for file in Path(temp).rglob("*"):
            if not file.is_file() or file.is_symlink():
                continue
            with file.open("rb") as stream:
                if stream.read(4) != b"\x7fELF":
                    continue
            elf_count += 1
            output = command("readelf", "--version-info", "--wide", str(file))
            needs = False
            for line in output.splitlines():
                if "Version needs section" in line:
                    needs = True
                elif re.match(r"Version (definition|symbols) section", line):
                    needs = False
                if needs:
                    for match in re.finditer(r"Name: GLIBC_(\d+(?:\.\d+)+)\b", line):
                        requirement = tuple(map(int, match.group(1).split(".")))
                        highest = max(highest, requirement)
                        if requirement > (2, 35):
                            raise ValueError(f"{file.relative_to(temp)} needs GLIBC_{match.group(1)} > 2.35")
        if not elf_count or highest == (0, 0):
            raise ValueError("No versioned ELF files were inspected")
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    filename = package_name(version, arch)
    shutil.copyfile(artifact, dest / filename)
    metadata = {"architecture": arch, "filename": filename, "version": version, "upstream_sha": sha,
                "elf_files_checked": elf_count, "highest_glibc": ".".join(map(str, highest))}
    (dest / f"build-{arch}.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    verify(*sys.argv[1:])
