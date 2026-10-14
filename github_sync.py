"""Private-repository sync using immutable blobs and non-forced commits."""
import copy
import hashlib
import json
import os
import sqlite3
import tempfile
from types import SimpleNamespace

from diary import encode, now, require
from github_accounts import binding, token_for
from github_client import GitHub
from github_records import (MANIFEST_LIMIT, initialize, snapshot, validate, merge,
                            apply_records, asset_path, checked_bytes)
from localization import tr


def sync(store, progress=lambda message: None):
    initialize(store)
    account = binding(store.root)
    require(account, tr('请先关联 GitHub 私有仓库并启用同步。'))
    owner = encode([account['user_id'], account['repo_id']])
    previous_owner = store.setting('github_sync_owner')
    require(not previous_owner or previous_owner == owner,
            tr('此同步档案属于其他账号或仓库，请使用独立资料空间。'))
    client = GitHub(token_for(store.root, account["user_id"]))
    progress(tr('正在连接 GitHub…'))
    client.check_repo(account)
    head, tree, files = client.read_head(account)
    base = {r[0]: json.loads(r[1]) for r in store.db.execute("SELECT key,payload FROM github_sync_base")}
    remote = {}
    if "records.json" in files:
        data = client.blob(account["repo"], files["records.json"])
        require(len(data) <= MANIFEST_LIMIT, tr('同步数据过大，请减少附件或记录后重试。'))
        manifest = json.loads(data)
        require(manifest.get("format") == "shiguang-sync" and manifest.get("schema") == 1 and
                manifest.get("owner_id") == account["user_id"], tr('远端资料格式或所属账号不符，已停止同步。'))
        remote = manifest["records"]
        validate(remote)
    else:
        require(not files and not base and not store.setting("github_last_sync"),
                tr('远端同步文件缺失，已停止同步以保护本机记录。'))
    require(set(base).issubset(remote) or not base, tr('远端历史不完整，已停止同步以保护本机记录。'))
    with store.db:
        store.db.execute("BEGIN")
        local, skipped = snapshot(store)
    validate(local)
    merged = merge(store, local, remote, base)
    validate(merged)
    content = encode({"format": "shiguang-sync", "schema": 1, "owner_id": account["user_id"], "records": merged}).encode("utf-8")
    require(len(content) <= MANIFEST_LIMIT, tr('同步数据过大，请减少附件或记录后重试。'))

    # Check all referential constraints on an in-memory snapshot before publishing.
    staged_db = sqlite3.connect(":memory:")
    staged_db.row_factory = sqlite3.Row
    try:
        store.db.backup(staged_db)
        staged_db.execute("PRAGMA foreign_keys=ON")
        diary = copy.copy(store.diary)
        diary.db = staged_db
        staged = SimpleNamespace(db=staged_db, diary=diary)
        with staged_db:
            apply_records(staged, local, merged)
    finally:
        staged_db.close()

    assets = [v for k, v in merged.items() if k.startswith("file/") and v is not None]
    require(sum(v["size"] for v in assets) <= 100 * 1024 * 1024 and len(assets) <= 1000,
            tr('轻量同步暂支持总计100 MiB、最多1000个小附件。'))
    changes, needed = [], set()
    for index, item in enumerate(assets):
        progress(tr('正在同步附件 {0}/{1}…', index + 1, len(assets)))
        remote_path = "files/" + item["sha256"]
        needed.add(remote_path)
        path = asset_path(store, item)
        if path.exists():
            data = checked_bytes(path, item)
        else:
            require(remote_path in files, tr('同步附件缺失或大小不符，请检查本机文件。'))
            data = client.blob(account["repo"], files[remote_path])
            require(len(data) == item["size"] and hashlib.sha256(data).hexdigest() == item["sha256"],
                    tr('附件校验失败，本次同步已停止。'))
            path.parent.mkdir(parents=True, exist_ok=True)
            handle, name = tempfile.mkstemp(prefix="sync-", suffix=".pending", dir=str(path.parent))
            try:
                with os.fdopen(handle, "wb") as target:
                    target.write(data)
                os.replace(name, path)
            finally:
                if os.path.isfile(name):
                    os.remove(name)
        expected_git_sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if remote_path in files:
            require(files[remote_path] == expected_git_sha, tr('附件校验失败，本次同步已停止。'))
        else:
            sha = client.put_blob(account["repo"], data)
            changes.append({"path": "shiguang-sync/" + remote_path, "mode": "100644", "type": "blob", "sha": sha})
    for path in files:
        if path.startswith("files/") and path not in needed:
            changes.append({"path": "shiguang-sync/" + path, "mode": "100644", "type": "blob", "sha": None})
    if merged != remote or "records.json" not in files or changes:
        progress(tr('正在保存到私有仓库…'))
        # Verify privacy again before sending private record bytes.
        client.check_repo(account)
        sha = client.put_blob(account["repo"], content)
        changes.append({"path": "shiguang-sync/records.json", "mode": "100644", "type": "blob", "sha": sha})
        head = client.publish(account, head, tree, changes)

    progress(tr('正在更新本机记录…'))
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        current, _ = snapshot(store)
        require(current == local, tr('同步期间本机有新编辑，已保留新内容，请再同步一次。'))
        deleted = apply_records(store, local, merged)
        store.db.execute("DELETE FROM github_sync_base")
        store.db.executemany("INSERT INTO github_sync_base VALUES(?,?)", [(key, encode(value)) for key, value in merged.items()])
        store.db.execute("UPDATE github_conflicts SET active=0")
        store.db.execute("INSERT INTO planner_settings VALUES('github_sync_owner',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (owner,))
        store.db.execute("INSERT INTO planner_settings VALUES('github_last_sync',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (now(),))
    # Export only after the transaction succeeds; external paths come from fixed IDs.
    store.diary.export()
    for kind, identifier in deleted:
        if kind == 'file' and local.get('file/' + identifier) is not None:
            path = asset_path(store, local['file/' + identifier])
            if path.is_file():
                path.unlink()
        folders = {"entry": ("entries",), "document": ("reviews", "updates")}.get(kind, ())
        for folder in folders:
            parent = (store.root / folder).resolve()
            path = (parent / (identifier + ".md")).resolve()
            if path.parent == parent and path.is_file():
                path.unlink()
    return {"records": sum(v is not None for v in merged.values()), "skipped": skipped,
            "head": head, "at": store.setting("github_last_sync")}
