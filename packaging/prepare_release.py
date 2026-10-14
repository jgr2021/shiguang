"""Assemble a clean, allowlisted program payload; never copy the owner's archive."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary-dir", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--link-runtime", action="store_true", help="Hard-link build files into staging on the same drive")
    parser.add_argument("--no-zip", action="store_true", help="Only assemble the clean staging directory")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent
    binary = Path(args.binary_dir).resolve()
    stage = Path(args.stage).resolve()
    release = Path(args.release).resolve()
    if stage.exists():
        raise SystemExit("Use a new empty staging directory for each release.")
    stage.mkdir(parents=True)
    release.mkdir(parents=True, exist_ok=True)
    copy_program = os.link if args.link_runtime else shutil.copy2
    copy_program(binary / "Shiguang.exe", stage / "Shiguang.exe")
    def ignore(folder, names):
        return [n for n in names if n in {"direct_url.json", "RECORD", "INSTALLER", "REQUESTED"}]
    shutil.copytree(binary / "_internal", stage / "_internal", ignore=ignore, copy_function=copy_program)
    shutil.copy2(source / "shiguang.ico", stage / "shiguang.ico")
    # Inno 6 requires a BOM for unambiguous Unicode text.
    for name in ("开始使用.txt", "開始使用.txt", "Getting-Started.txt"):
        (stage / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8-sig")
    shutil.copy2(source / 'AI连接指南.md', stage / 'AI连接指南.md')
    shutil.copy2(source / 'GitHub同步说明.md', stage / 'GitHub同步说明.md')
    app_registration = source / 'github-app.json'
    if app_registration.exists():
        registration = json.loads(app_registration.read_text(encoding='utf-8-sig'))
        if set(registration) != {'client_id', 'slug'} or not all(isinstance(x, str) for x in registration.values()):
            raise SystemExit('github-app.json must contain only the public client_id and slug.')
        (stage / 'github-app.json').write_text(json.dumps(registration, indent=2), encoding='utf-8')
    licenses = stage / "licenses"
    licenses.mkdir()
    distributions = ["pypdf", "cryptography", "cffi", "pycparser", "Pillow", "brotlicffi", "typing_extensions", "packaging", "setuptools", "importlib_metadata", "zipp", "more-itertools", "jaraco.functools", "jaraco.context", "jaraco.text", "backports.tarfile", "platformdirs", "pyreadline3", "colorama", "pyinstaller", "altgraph", "pefile", "pywin32-ctypes"]
    notices = []
    for name in distributions:
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        notices.append(name + " " + dist.version)
        for relative in dist.files or []:
            if any(part.lower().startswith(("license", "copying", "notice", "authors")) for part in relative.parts):
                original = Path(dist.locate_file(relative))
                if original.is_file() and original.suffix.lower() not in {".py", ".pyc"}:
                    destination = licenses / name / str(relative).replace("..", "_").replace(":", "_")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, destination)
    python_root = Path(sys.base_prefix)
    for candidate in [python_root / "LICENSE.txt", python_root / "Lib" / "LICENSE.txt", python_root / "tcl" / "tcl8.6" / "license.terms", python_root / "tcl" / "tk8.6" / "license.terms"]:
        if candidate.is_file():
            shutil.copy2(candidate, licenses / (candidate.parent.name + "-" + candidate.name))
    (stage / "THIRD-PARTY-NOTICES.txt").write_text("拾光使用 Python、Tcl/Tk、SQLite、PyInstaller 及下列第三方组件。许可证见 licenses/ 和运行库内的许可文件。\n\n" + "\n".join(notices), encoding="utf-8-sig")
    forbidden = {"vault", "generated", "entries", "reviews", "updates", "credentials.dpapi", "auth.json", "config.json", "archive.json", "memory.md", "AGENT.md", "desktop-error.log", "accounts", "accounts.json", "github-token.dpapi", "github-binding.json"}
    paths = list(stage.rglob("*"))
    for path in paths:
        if any(part in forbidden for part in path.relative_to(stage).parts) or path.suffix.lower() in {".sqlite3", ".db", ".log"}:
            raise SystemExit("Private-data path found in release payload: " + path.name)
    manifest = [{"path": p.relative_to(stage).as_posix(), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths if p.is_file()]
    (stage / "release-manifest.json").write_text(json.dumps({"version": "1.9.2", "languages": ["zh-CN", "zh-TW", "en"], "payload": "program-only", "personal_data_included": False, "files": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    portable = release / "Shiguang-1.9.2-Windows-x64.zip"
    if not args.no_zip:
        with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.write(path, "Shiguang/" + path.relative_to(stage).as_posix())
    for name in ("开始使用.txt", "開始使用.txt", "Getting-Started.txt"):
        shutil.copy2(stage / name, release / name)
    print(json.dumps({"stage": str(stage), "files": len(manifest), "personal_data_included": False, "portable": str(portable) if not args.no_zip else None, "zip_bytes": portable.stat().st_size if not args.no_zip else 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
