"""Offline planner data model sharing the diary's SQLite database."""
from localization import tr
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import uuid
import zipfile

from diary import Diary, date_field, now, require, text_field


class ConflictError(ValueError):
    pass


class PlannerStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.diary = Diary(self.root)
        self.db = self.diary.db
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS planner_tasks (
                id TEXT PRIMARY KEY, day TEXT NOT NULL, title TEXT NOT NULL,
                at_time TEXT NOT NULL DEFAULT '', priority INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '', done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
            CREATE INDEX IF NOT EXISTS planner_day ON planner_tasks(day);
            CREATE TABLE IF NOT EXISTS planner_notes (
                day TEXT PRIMARY KEY, body TEXT NOT NULL, updated_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS planner_inbox (
                entry_id TEXT PRIMARY KEY REFERENCES entries(id), queued_at TEXT NOT NULL,
                processed_at TEXT);
        """)

    def close(self):
        self.diary.close()

    def task(self, identifier):
        row = self.db.execute("SELECT * FROM planner_tasks WHERE id=?", (identifier,)).fetchone()
        require(row is not None, tr('这条待办已被删除，请刷新后再试。'))
        return dict(row)

    def tasks(self, start=None, end=None, only_open=False):
        conditions, parameters = [], []
        if start:
            conditions.append("day>=?")
            parameters.append(date_field(start))
        if end:
            conditions.append("day<=?")
            parameters.append(date_field(end))
        if only_open:
            conditions.append("done=0")
        query = "SELECT * FROM planner_tasks"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY day,done,priority DESC,CASE WHEN at_time='' THEN 1 ELSE 0 END,at_time,created_at,id"
        return [dict(row) for row in self.db.execute(query, parameters)]

    def save_task(self, data, identifier=None, expected_version=None):
        day = date_field(data.get("day"))
        title = text_field(data.get("title"), "待办内容").strip()
        require(len(title) <= 240, tr('待办标题请控制在240字以内。'))
        at_time = data.get("at_time", "").strip()
        require(not at_time or re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", at_time), tr('时间格式为 HH:MM，例如 09:30；全天事项可以留空。'))
        priority = data.get("priority", 0)
        require(priority in (0, 1), tr('优先级无效。'))
        notes = data.get("notes", "")
        require(isinstance(notes, str) and len(notes) <= 100000, tr('备注最长100000字。'))
        done = data.get("done", 0)
        require(done in (0, 1, False, True), tr('完成状态无效。'))
        timestamp = now()
        with self.db:
            if identifier:
                require(isinstance(expected_version, int), tr('修改待办需要读取当前版本。'))
                cursor = self.db.execute("UPDATE planner_tasks SET day=?,title=?,at_time=?,priority=?,notes=?,done=?,updated_at=?,version=version+1 WHERE id=? AND version=?", (day, title, at_time, priority, notes, int(done), timestamp, identifier, expected_version))
                if cursor.rowcount != 1:
                    raise ConflictError(tr('这条待办刚刚被更新，请重新打开后编辑。'))
            else:
                identifier = "T" + uuid.uuid4().hex[:20]
                self.db.execute("INSERT INTO planner_tasks VALUES(?,?,?,?,?,?,?,?,?,1)", (identifier, day, title, at_time, priority, notes, int(done), timestamp, timestamp))
        return self.task(identifier)

    def toggle(self, identifier, expected_version):
        row = self.task(identifier)
        row["done"] = 0 if row["done"] else 1
        return self.save_task(row, identifier, expected_version)

    def delete_task(self, identifier, expected_version):
        with self.db:
            cursor = self.db.execute("DELETE FROM planner_tasks WHERE id=? AND version=?", (identifier, expected_version))
            if cursor.rowcount != 1:
                raise ConflictError(tr('这条待办刚刚被更新，请重新打开后操作。'))

    def note(self, day):
        date_field(day)
        row = self.db.execute("SELECT * FROM planner_notes WHERE day=?", (day,)).fetchone()
        return dict(row) if row else {"day": day, "body": "", "updated_at": None, "version": 0}

    def save_note(self, day, body, expected_version):
        date_field(day)
        require(isinstance(body, str) and len(body) <= 1000000, tr('日记长度超出限制。'))
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            previous = self.note(day)
            if previous["version"] != expected_version:
                raise ConflictError(tr('这一天的日记在其他位置有更新。当前文字仍在编辑框内，请先复制保留，再重新打开应用。'))
            if previous["body"] == body:
                return previous
            self.db.execute("INSERT INTO planner_notes VALUES(?,?,?,1) ON CONFLICT(day) DO UPDATE SET body=excluded.body,updated_at=excluded.updated_at,version=planner_notes.version+1", (day, body, now()))
        return self.note(day)

    def note_dates(self, start, end):
        return {row[0] for row in self.db.execute("SELECT day FROM planner_notes WHERE day>=? AND day<=? AND trim(body)!=''", (date_field(start), date_field(end)))}

    def archive_note(self, day):
        note = self.note(day)
        require(bool(note["body"].strip()), tr('先写下一点内容再归档。'))
        body = note["body"]
        first_line = next(line.strip() for line in body.splitlines() if line.strip())
        result = self.diary.add({"entry_date": day, "raw_text": body, "analysis": {"title": first_line[:36], "summary": "离线保存的日记原文，等待 Agent 整理。", "categories": [], "tags": [], "projects": [], "observations": [], "actions": [], "links": [], "questions": []}})
        if result["status"] == "saved":
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO planner_inbox VALUES(?,?,NULL)", (result["id"], now()))
        self.diary.export()
        return result

    def archived_for_day(self, day):
        date_field(day)
        return [dict(row) for row in self.db.execute("SELECT e.id,e.raw_text,e.created_at,i.processed_at,CASE WHEN i.entry_id IS NULL THEN 0 ELSE 1 END as desktop FROM entries e LEFT JOIN planner_inbox i ON e.id=i.entry_id WHERE e.entry_date=? ORDER BY e.created_at DESC", (day,))]

    def pending(self):
        return [dict(row) for row in self.db.execute("SELECT i.entry_id,i.queued_at,e.entry_date,e.raw_text,e.revision FROM planner_inbox i JOIN entries e ON e.id=i.entry_id WHERE i.processed_at IS NULL ORDER BY i.queued_at")]

    def acknowledge(self, identifier):
        self.diary.get(identifier)
        with self.db:
            self.db.execute("UPDATE planner_inbox SET processed_at=? WHERE entry_id=? AND processed_at IS NULL", (now(), identifier))
        self.diary.export()

    def backup(self, destination):
        destination = Path(destination)
        require(destination.suffix.lower() == ".zip", tr('备份文件使用 .zip 后缀。'))
        with tempfile.TemporaryDirectory(prefix="shiguang-backup-") as temporary:
            snapshot = Path(temporary) / "diary.sqlite3"
            target = sqlite3.connect(str(snapshot))
            try:
                self.db.backup(target)
                tables = {r[0] for r in target.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                files = list(target.execute("SELECT relative_path FROM planner_files")) if "planner_files" in tables else []
            finally:
                target.close()
            temporary_zip = destination.with_name(destination.name + ".pending")
            with zipfile.ZipFile(str(temporary_zip), "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(str(snapshot), "vault/diary.sqlite3")
                for name in ("config.json", "memory.md", "AGENT.md"):
                    source = self.root / name
                    if source.exists():
                        archive.write(str(source), name)
                for (relative,) in files:
                    source = (self.root / relative).resolve()
                    require(self.root / "vault" / "attachments" in source.parents, tr('备份遇到无效的附件路径。'))
                    require(source.is_file(), tr('附件缺失，备份未完成：') + relative)
                    archive.write(str(source), relative)
                generated = self.root / "generated"
                if generated.exists():
                    for source in generated.iterdir():
                        if source.is_file() and source.suffix.lower() in {".md", ".docx", ".json"}:
                            archive.write(str(source), source.relative_to(self.root).as_posix())
                archive.writestr("backup-info.json", json.dumps({"app": "拾光日历", "version": "1.2.0", "created_at": now(), "includes": "日记、待办、随记草稿、修订记录、复盘与动态、Agent待整理队列、附件与日期关联、对话记录与生成文档"}, ensure_ascii=False, indent=2))
            temporary_zip.replace(destination)
        return str(destination)


def main():
    parser = argparse.ArgumentParser(description="拾光离线日历数据工具")
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parent))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pending")
    sub.add_parser("tasks")
    sub.add_parser("ack").add_argument("--id", required=True)
    add = sub.add_parser("task")
    add.add_argument("--file", required=True)
    add.add_argument("--id")
    add.add_argument("--version", type=int)
    args = parser.parse_args()
    store = PlannerStore(args.data_dir)
    try:
        if args.command == "pending":
            result = store.pending()
        elif args.command == "tasks":
            result = store.tasks()
        elif args.command == "ack":
            store.acknowledge(args.id)
            result = {"status": "acknowledged", "id": args.id}
        else:
            with open(args.file, encoding="utf-8-sig") as handle:
                data = json.load(handle)
            result = store.save_task(data, args.id, args.version)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
