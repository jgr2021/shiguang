"""Allowlisted record snapshots and three-way merge; no credentials or settings."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from diary import date_field, digest, encode, now, require
from localization import tr

FILE_LIMIT = 10 * 1024 * 1024
MANIFEST_LIMIT = 16 * 1024 * 1024
FIELDS = {
    "task": ("planner_tasks", "id", "id day title at_time priority notes done created_at updated_at".split()),
    "note": ("planner_notes", "day", "day body updated_at".split()),
    "entry": ("entries", "id", "id entry_date raw_text fingerprint created_at analysis revision".split()),
    "document": ("documents", "id", "id kind payload fingerprint revision created_at updated_at".split()),
    "file": ("planner_files", "sha256", "sha256 title original_name size notes tags cloud_url as_of extracted_text extraction_status created_at updated_at".split()),
}
HISTORY = {"entry": ("revisions", "entry_id", "entry_id revision analysis reason created_at".split()),
           "document": ("document_revisions", "document_id", "document_id revision payload fingerprint created_at".split())}


def initialize(store):
    store.db.executescript("""
        CREATE TABLE IF NOT EXISTS github_sync_base (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS github_conflicts (
            id TEXT PRIMARY KEY, key TEXT NOT NULL, local TEXT NOT NULL, remote TEXT NOT NULL,
            choice TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
    """)


def snapshot(store):
    records, skipped = {}, 0
    for kind, (table, primary, columns) in FIELDS.items():
        for row in store.db.execute("SELECT * FROM " + table):
            item = {column: row[column] for column in columns}
            if kind == "file":
                if item["size"] > FILE_LIMIT:
                    skipped += 1
                    continue
                item["suffix"] = Path(row["relative_path"]).suffix
                item["dates"] = [list(r) for r in store.db.execute(
                    "SELECT start_day,end_day FROM planner_file_dates WHERE file_id=? ORDER BY start_day,end_day", (row["id"],))]
            if kind in HISTORY:
                hist, foreign, fields = HISTORY[kind]
                item["history"] = [{c: r[c] for c in fields} for r in store.db.execute(
                    "SELECT * FROM " + hist + " WHERE " + foreign + "=? ORDER BY revision", (row[primary],))]
            records[kind + "/" + str(row[primary])] = item
    return records, skipped


def validate(records):
    require(isinstance(records, dict) and len(records) <= 50000, "Invalid sync records")
    for key, item in records.items():
        require(isinstance(key, str) and "/" in key, "Invalid record key")
        kind, identifier = key.split("/", 1)
        require(kind in FIELDS, "Unsupported record kind")
        if kind == "note":
            date_field(identifier)
        elif kind == "file":
            require(re.fullmatch(r"[0-9a-f]{64}", identifier), "Invalid file digest")
        else:
            require(re.fullmatch(r"[A-Za-z0-9_-]{1,120}", identifier), "Invalid record ID")
        if item is None:
            continue  # Explicit tombstone; a missing HTTP object is never a deletion.
        _, primary, columns = FIELDS[kind]
        extra = {"history"} if kind in HISTORY else {"suffix", "dates"} if kind == "file" else set()
        require(isinstance(item, dict) and set(item) == set(columns) | extra and item[primary] == identifier,
                "Invalid record fields")
        for column in columns:
            numeric = column in {"priority", "done", "size", "revision"}
            require(type(item[column]) is (int if numeric else str), "Invalid record value")
            if not numeric:
                require(len(item[column]) <= 1000000, "Oversized record value")
        if kind == "task":
            from planner_store import PlannerStore
            PlannerStore.validate_task(item)
        elif kind == "note":
            date_field(item["day"])
        elif kind == "entry":
            date_field(item["entry_date"])
            fingerprint = digest([item["entry_date"], item["raw_text"]])
            require(item["fingerprint"] == fingerprint and identifier == "D" + item["entry_date"].replace("-", "") + "-" + fingerprint[:12],
                    "Invalid original diary fingerprint")
            require(isinstance(json.loads(item["analysis"]), dict), "Invalid analysis")
        elif kind == "document":
            require(item["kind"] in {"review", "update"} and isinstance(json.loads(item["payload"]), dict), "Invalid document")
            payload = json.loads(item["payload"])
            require(digest(payload) == item["fingerprint"] and isinstance(payload.get("title"), str), "Invalid document fingerprint")
            require(isinstance(payload.get("source_entry_ids"), list) and all(isinstance(x, str) for x in payload["source_entry_ids"]), "Invalid document sources")
            if item["kind"] == "review":
                start, end = date_field(payload.get("period_start")), date_field(payload.get("period_end"))
                require(start <= end and identifier == "R" + start + "_" + end and isinstance(payload.get("body"), str), "Invalid review")
            else:
                require(all(isinstance(payload.get(c), str) for c in ("topic_id", "claim", "implication")), "Invalid update")
                require(isinstance(payload.get("sources"), list) and 0 < len(payload["sources"]) <= 3, "Invalid external sources")
                for source in payload["sources"]:
                    require(isinstance(source, dict) and all(isinstance(source.get(c), str) for c in ("title", "url", "retrieved_at")), "Invalid external source")
                    parsed = urlparse(source["url"])
                    require(parsed.scheme in {"http", "https"} and parsed.hostname, "Invalid source URL")
                    for c in ("published_at", "event_date"):
                        if source.get(c) is not None:
                            date_field(source[c])
                require(identifier == "U" + digest([payload["topic_id"], payload["claim"], sorted(s["url"] for s in payload["sources"])])[:16], "Invalid update ID")
        elif kind == "file":
            require(0 <= item["size"] <= FILE_LIMIT and re.fullmatch(r"\.[a-z0-9]{1,12}", item["suffix"]), "Invalid attachment")
            require(item['title'].strip() and len(item['title']) <= 240, "Invalid attachment title")
            if item['as_of']:
                date_field(item['as_of'])
            if item['cloud_url']:
                parsed = urlparse(item['cloud_url'])
                require(parsed.scheme == 'https' and parsed.hostname and not parsed.username, "Invalid cloud URL")
            require(isinstance(item["dates"], list) and 0 < len(item["dates"]) <= 10000, "Invalid file dates")
            for span in item["dates"]:
                require(isinstance(span, list) and len(span) == 2 and date_field(span[0]) <= date_field(span[1]), "Invalid date span")
            require(len({tuple(x) for x in item["dates"]}) == len(item["dates"]), "Duplicate date spans")
        if kind in HISTORY:
            _, foreign, fields = HISTORY[kind]
            require(isinstance(item["history"], list) and 0 < len(item["history"]) <= 10000, "Invalid revision history")
            require(1 <= item["revision"] <= 10000, "Invalid revision count")
            revisions = []
            for row in item["history"]:
                require(isinstance(row, dict) and set(row) == set(fields) and row[foreign] == identifier, "Invalid revision")
                require(type(row["revision"]) is int and row["revision"] > 0, "Invalid revision number")
                require(all(isinstance(row[c], str) for c in fields if c != "revision"), "Invalid revision fields")
                revisions.append(row["revision"])
            require(revisions == list(range(1, item["revision"] + 1)), "Incomplete revision history")
            latest = item["history"][-1]
            current_fields = ("analysis",) if kind == "entry" else ("payload", "fingerprint")
            require(all(latest[c] == item[c] for c in current_fields), "Revision differs from current record")


def merge(store, local, remote, base):
    merged, conflicts = {}, []
    for key in sorted(set(base) | set(local) | set(remote)):
        l, r, b = local.get(key), remote.get(key), base.get(key)
        if l == r:
            merged[key] = l
        elif l == b:
            merged[key] = r
        elif r == b:
            merged[key] = l
        else:
            identifier = digest([key, l, r])
            old = store.db.execute("SELECT choice FROM github_conflicts WHERE id=?", (identifier,)).fetchone()
            if old and old[0] in {"local", "remote"}:
                merged[key] = l if old[0] == "local" else r
            else:
                conflicts.append((identifier, key, encode(l), encode(r)))
    if conflicts:
        with store.db:
            store.db.execute("UPDATE github_conflicts SET active=0")
            for row in conflicts:
                store.db.execute("INSERT INTO github_conflicts(id,key,local,remote,created_at) VALUES(?,?,?,?,?) "
                                 "ON CONFLICT(id) DO UPDATE SET active=1", (*row, now()))
        raise ValueError(tr('有 {0} 条记录在两台设备上都被修改，请先处理冲突。', len(conflicts)))
    return merged


def apply_records(store, before, merged):
    """Caller holds BEGIN IMMEDIATE. Version increments invalidate open editors."""
    deleted = []
    for key, value in merged.items():
        if before.get(key) == value:
            continue
        kind, identifier = key.split("/", 1)
        table, primary, columns = FIELDS[kind]
        if value is None:
            if kind in HISTORY:
                hist, foreign, _ = HISTORY[kind]
                store.db.execute("DELETE FROM " + hist + " WHERE " + foreign + "=?", (identifier,))
            if kind == "entry":
                store.db.execute("DELETE FROM planner_inbox WHERE entry_id=?", (identifier,))
            if kind == "file":
                store.db.execute("DELETE FROM planner_file_dates WHERE file_id IN (SELECT id FROM planner_files WHERE sha256=?)", (identifier,))
            store.db.execute("DELETE FROM " + table + " WHERE " + primary + "=?", (identifier,))
            deleted.append((kind, identifier))
            continue
        values = {c: value[c] for c in columns}
        if kind == "file":
            previous = store.db.execute("SELECT id FROM planner_files WHERE sha256=?", (identifier,)).fetchone()
            values["id"] = previous[0] if previous else "F" + identifier[:20]
            values["relative_path"] = "vault/attachments/" + identifier + value["suffix"]
        names = list(values)
        versioned = kind in {"task", "note", "file"}
        sql = "INSERT INTO " + table + " (" + ",".join(names) + ") VALUES(" + ",".join("?" for _ in names) + ") "
        sql += "ON CONFLICT(" + primary + ") DO UPDATE SET " + ",".join(c + "=excluded." + c for c in names if c != primary)
        if versioned:
            sql += ",version=" + table + ".version+1"
        store.db.execute(sql, tuple(values.values()))
        if kind == "file":
            store.db.execute("DELETE FROM planner_file_dates WHERE file_id=?", (values["id"],))
            store.db.executemany("INSERT INTO planner_file_dates VALUES(?,?,?)", [(values["id"], a, b) for a, b in value["dates"]])
        if kind in HISTORY:
            hist, foreign, fields = HISTORY[kind]
            store.db.execute("DELETE FROM " + hist + " WHERE " + foreign + "=?", (identifier,))
            store.db.executemany("INSERT INTO " + hist + " (" + ",".join(fields) + ") VALUES(" + ",".join("?" for _ in fields) + ")",
                                 [tuple(r[c] for c in fields) for r in value["history"]])
    # Validate original analysis links only after all referenced entries exist.
    for key, value in merged.items():
        if not value:
            continue
        if key.startswith("entry/"):
            store.diary.analysis(json.loads(value["analysis"]), value["raw_text"], value["id"])
        elif key.startswith("document/"):
            store.diary.sources(json.loads(value["payload"]).get("source_entry_ids", []))
    return deleted


def asset_path(store, item):
    folder = (store.root / "vault" / "attachments").resolve()
    path = (folder / (item["sha256"] + item["suffix"])).resolve()
    require(path.parent == folder, "Invalid asset destination")
    return path


def checked_bytes(path, item):
    require(path.is_file() and path.stat().st_size == item["size"], tr('同步附件缺失或大小不符，请检查本机文件。'))
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == item["sha256"], tr('附件校验失败，本次同步已停止。'))
    return data
