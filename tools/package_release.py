"""Package committed source and the built Windows addon; never include local state."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    if git("status", "--porcelain").strip():
        raise SystemExit("Commit source changes before packaging a release")
    version = (ROOT / "VERSION").read_text().strip()
    commit = git("rev-parse", "HEAD").decode().strip()
    files = {}
    with tarfile.open(fileobj=io.BytesIO(git("archive", "HEAD"))) as archive:
        for member in archive.getmembers():
            if member.isfile():
                files[member.name] = archive.extractfile(member).read()
    for name in ("@ArmaDevBridge/addons/bridge.pbo", "@ArmaDevBridge/arma3_mcp_bridge.dll"):
        files[name] = (ROOT / name).read_bytes()
    files["BUILDINFO.json"] = (json.dumps({
        "version": version, "source_commit": commit,
        "repository": "https://github.com/GearUnclear/eden-mcp-bridge",
        "platform": "windows-x64", "unsigned": True,
        "artifact_sha256": {n: hashlib.sha256(b).hexdigest()
                            for n, b in files.items() if n.startswith("@ArmaDevBridge/")},
    }, indent=2) + "\n").encode()
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    target = out / f"eden-mcp-bridge-{version}-windows-x64.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo("eden-mcp-bridge/" + name, date_time=(2026, 10, 13, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files)
        for name, data in files.items():
            assert archive.read("eden-mcp-bridge/" + name) == data
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (out / "SHA256SUMS.txt").write_text(f"{digest}  {target.name}\n", encoding="ascii")
    print(f"Verified {len(files)} archive members: {target.name} ({target.stat().st_size} bytes)")
    print(f"SHA256 {digest}")


if __name__ == "__main__":
    main()
