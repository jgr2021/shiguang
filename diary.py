"""Durable diary storage for the Shiguang Codex agent. Python 3.9+, stdlib only."""
from localization import tr
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

TZ = timezone(timedelta(hours=8))
CATEGORIES = {"产出", "想法", "学习", "生活", "情绪", "关系", "决策"}
KINDS = {"reported_fact", "idea", "feeling", "decision", "question"}
STATUSES = {"suggested", "planned", "done", "dropped"}


def now():
    return datetime.now(TZ).isoformat(timespec="seconds")


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text_field(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + tr(' 不能为空'))
    return value


def date_field(value):
    require(isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)), tr('日期格式应为 YYYY-MM-DD'))
    date.fromisoformat(value)
    return value


def string_list(value, label):
    require(isinstance(value, list), label + tr(' 必须为列表'))
    require(all(isinstance(v, str) and v.strip() for v in value), label + tr(' 必须为非空字符串列表'))
    return list(dict.fromkeys(value))


def read_json(path):
    with open(path, encoding="utf-8-sig") as handle:
        result = json.load(handle)
    require(isinstance(result, dict), tr('输入必须为 JSON 对象'))
    return result


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=str(path.parent), delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


class Diary:
    def __init__(self, root):
        self.root = Path(root).resolve()
        (self.root / "vault").mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.root / "vault" / "diary.sqlite3"), timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY, entry_date TEXT NOT NULL, raw_text TEXT NOT NULL,
                fingerprint TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL,
                analysis TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS revisions (
                entry_id TEXT NOT NULL REFERENCES entries(id), revision INTEGER NOT NULL,
                analysis TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(entry_id, revision));
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
                fingerprint TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS document_revisions (
                document_id TEXT NOT NULL REFERENCES documents(id), revision INTEGER NOT NULL,
                payload TEXT NOT NULL, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(document_id, revision));
            CREATE INDEX IF NOT EXISTS entries_date ON entries(entry_date);
        """)

    def close(self):
        self.db.close()

    def get(self, entry_id):
        row = self.db.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
        require(row is not None, tr('找不到记录：') + entry_id)
        item = dict(row)
        item["analysis"] = json.loads(item["analysis"])
        return item

    def all_entries(self):
        return [self.get(row[0]) for row in self.db.execute("SELECT id FROM entries ORDER BY entry_date, created_at, id").fetchall()]

    def sources(self, identifiers):
        return [self.get(key) for key in string_list(identifiers, "source_entry_ids")]

    def analysis(self, value, raw, own_id=None):
        require(isinstance(value, dict), tr('analysis 必须为对象'))
        result = {"title": text_field(value.get("title"), "title"), "summary": text_field(value.get("summary"), "summary")}
        for key in ("categories", "tags", "projects", "questions"):
            result[key] = string_list(value.get(key, []), key)
        require(set(result["categories"]) <= CATEGORIES, tr('分类不在当前词表中'))
        require(len(result["categories"]) <= 3 and len(result["tags"]) <= 5 and len(result["questions"]) <= 1, tr('分类最多3个、标签最多5个、问题最多1个'))
        result["observations"], result["actions"], result["links"] = [], [], []
        for key in ("observations", "actions", "links"):
            require(isinstance(value.get(key, []), list), key + tr(' 必须为列表'))
            require(all(isinstance(v, dict) for v in value.get(key, [])), key + tr(' 的元素必须为对象'))
        for item in value.get("observations", []):
            require(item.get("kind") in KINDS, tr('无效的 observation.kind'))
            evidence = text_field(item.get("evidence"), "evidence")
            require(evidence in raw, tr('observation.evidence 必须是原文精确片段'))
            result["observations"].append({"kind": item["kind"], "text": text_field(item.get("text"), "observation.text"), "evidence": evidence})
        for item in value.get("actions", []):
            require(item.get("status") in STATUSES, tr('无效的 action.status'))
            due = item.get("due_date")
            if due is not None:
                date_field(due)
            evidence = item.get("evidence")
            if evidence is not None:
                require(isinstance(evidence, str) and bool(evidence.strip()) and evidence in raw, tr('action.evidence 必须是原文精确片段'))
            require(item["status"] == "suggested" or evidence is not None, tr('用户承诺、完成或取消的行动需要原文依据'))
            result["actions"].append({"text": text_field(item.get("text"), "action.text"), "status": item["status"], "due_date": due, "evidence": evidence})
        for item in value.get("links", []):
            entry_id = text_field(item.get("entry_id"), "link.entry_id")
            require(entry_id != own_id, tr('记录不能关联自身'))
            self.get(entry_id)
            result["links"].append({"entry_id": entry_id, "relation": text_field(item.get("relation"), "relation"), "reason": text_field(item.get("reason"), "reason")})
        return result

    def add(self, payload):
        entry_date = date_field(payload.get("entry_date"))
        raw = text_field(payload.get("raw_text"), "raw_text")
        fingerprint = digest([entry_date, raw])
        identifier = "D" + entry_date.replace("-", "") + "-" + fingerprint[:12]
        with self.db:
            existing = self.db.execute("SELECT id, revision FROM entries WHERE fingerprint=?", (fingerprint,)).fetchone()
            if existing:
                return {"status": "duplicate", "id": existing["id"], "revision": existing["revision"]}
            analysis = self.analysis(payload.get("analysis"), raw, identifier)
            timestamp = now()
            self.db.execute("INSERT INTO entries VALUES(?,?,?,?,?,?,1)", (identifier, entry_date, raw, fingerprint, timestamp, encode(analysis)))
            self.db.execute("INSERT INTO revisions VALUES(?,1,?,?,?)", (identifier, encode(analysis), "首次归档", timestamp))
        return {"status": "saved", "id": identifier, "revision": 1}

    def revise(self, identifier, payload):
        reason = text_field(payload.get("reason"), "reason")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            entry = self.get(identifier)
            analysis = self.analysis(payload.get("analysis"), entry["raw_text"], identifier)
            if analysis == entry["analysis"]:
                return {"status": "unchanged", "id": identifier, "revision": entry["revision"]}
            revision = entry["revision"] + 1
            self.db.execute("UPDATE entries SET analysis=?, revision=? WHERE id=?", (encode(analysis), revision, identifier))
            self.db.execute("INSERT INTO revisions VALUES(?,?,?,?,?)", (identifier, revision, encode(analysis), reason, now()))
        return {"status": "revised", "id": identifier, "revision": revision}

    def save_document(self, kind, payload):
        rows = self.sources(payload.get("source_entry_ids", []))
        normalized = dict(payload)
        normalized["source_entry_ids"] = [row["id"] for row in rows]
        text_field(payload.get("title"), "title")
        if kind == "review":
            start, end = date_field(payload.get("period_start")), date_field(payload.get("period_end"))
            require(start <= end, tr('复盘起始日期不能晚于结束日期'))
            require(rows and all(start <= row["entry_date"] <= end for row in rows), tr('复盘必须引用范围内的真实记录'))
            text_field(payload.get("body"), "body")
            normalized["source_fingerprint"] = digest([[r["id"], r["revision"], r["fingerprint"]] for r in sorted(rows, key=lambda r: r["id"])])
            identifier = "R" + start + "_" + end
        else:
            text_field(payload.get("topic_id"), "topic_id")
            text_field(payload.get("claim"), "claim")
            text_field(payload.get("implication"), "implication")
            sources = payload.get("sources")
            require(isinstance(sources, list) and 1 <= len(sources) <= 3, tr('每条动态需要1–3个来源'))
            for source in sources:
                require(isinstance(source, dict), tr('source 必须为对象'))
                text_field(source.get("title"), "source.title")
                parsed = urlparse(text_field(source.get("url"), "source.url"))
                require(parsed.scheme in {"http", "https"} and bool(parsed.hostname), tr('source.url 必须为 HTTP(S) 地址'))
                moment = datetime.fromisoformat(text_field(source.get("retrieved_at"), "retrieved_at").replace("Z", "+00:00"))
                require(moment.tzinfo is not None, tr('retrieved_at 必须包含时区'))
                for key in ("published_at", "event_date"):
                    if source.get(key) is not None:
                        date_field(source[key])
            identifier = "U" + digest([payload["topic_id"], payload["claim"], sorted(s["url"] for s in sources)])[:16]
        fingerprint = digest(normalized)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute("SELECT * FROM documents WHERE id=?", (identifier,)).fetchone()
            if old and (kind == "update" or old["fingerprint"] == fingerprint):
                return {"status": "duplicate", "id": identifier, "revision": old["revision"]}
            revision, timestamp = (old["revision"] + 1 if old else 1), now()
            self.db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, fingerprint=excluded.fingerprint, revision=excluded.revision, updated_at=excluded.updated_at", (identifier, kind, encode(normalized), fingerprint, revision, timestamp, timestamp))
            self.db.execute("INSERT INTO document_revisions VALUES(?,?,?,?,?)", (identifier, revision, encode(normalized), fingerprint, timestamp))
        return {"status": "saved", "id": identifier, "revision": revision}

    def documents(self):
        results = []
        for row in self.db.execute("SELECT * FROM documents ORDER BY created_at, id"):
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            results.append(item)
        return results

    def context(self):
        rows = self.all_entries()
        today = datetime.now(TZ).date()
        monday = today - timedelta(days=today.weekday())
        start, end = (monday - timedelta(days=7)).isoformat(), (monday - timedelta(days=1)).isoformat()
        weekly = [r for r in rows if start <= r["entry_date"] <= end]
        source_hash = digest([[r["id"], r["revision"], r["fingerprint"]] for r in sorted(weekly, key=lambda r: r["id"])])
        existing = self.db.execute("SELECT payload FROM documents WHERE id=?", ("R" + start + "_" + end,)).fetchone()
        previous_hash = json.loads(existing["payload"]).get("source_fingerprint") if existing else None
        planner = self.planner_data(include_assets=False)
        pending = [row["entry_id"] for row in planner.get("planner_inbox", []) if row["processed_at"] is None]
        return {"today": today.isoformat(), "timezone": "Asia/Shanghai", "entry_count": len(rows), "desktop_pending_entry_ids": pending, "planner_open_tasks": [row for row in planner.get("planner_tasks", []) if not row["done"]], "recent_entries": [{"id": r["id"], "date": r["entry_date"], "title": r["analysis"]["title"], "summary": r["analysis"]["summary"], "categories": r["analysis"]["categories"], "tags": r["analysis"]["tags"], "revision": r["revision"]} for r in rows[-50:]], "previous_week": {"period_start": start, "period_end": end, "source_entry_ids": [r["id"] for r in weekly], "needs_review": bool(weekly) and source_hash != previous_hash}, "recent_documents": [{"id": d["id"], "kind": d["kind"], "title": d["payload"]["title"], "updated_at": d["updated_at"]} for d in self.documents()[-10:]]}

    def planner_data(self, include_assets=True):
        available = {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        results = {}
        for name in ("planner_tasks", "planner_notes", "planner_inbox", "planner_files", "planner_file_dates", "planner_settings", "planner_chat"):
            if not include_assets and name not in {"planner_tasks", "planner_notes", "planner_inbox"}:
                continue
            if name in available:
                results[name] = [dict(row) for row in self.db.execute("SELECT * FROM " + name)]
        return results

    def export(self):
        entries, documents = self.all_entries(), self.documents()
        revisions = [dict(row) for row in self.db.execute("SELECT * FROM revisions ORDER BY entry_id, revision")]
        doc_revisions = [dict(row) for row in self.db.execute("SELECT * FROM document_revisions ORDER BY document_id, revision")]
        for row in revisions:
            row["analysis"] = json.loads(row["analysis"])
        for row in doc_revisions:
            row["payload"] = json.loads(row["payload"])
        archive = {"schema_version": 3, "exported_at": now(), "entries": entries, "revisions": revisions, "documents": documents, "document_revisions": doc_revisions, "planner": self.planner_data()}
        atomic_write(self.root / "archive.json", json.dumps(archive, ensure_ascii=False, indent=2) + "\n")
        index = ["# 拾光 · 档案索引", "", "记录：" + str(len(entries)) + " 条", "", "## 日记", ""]
        if not entries:
            index.append("还没有日记。直接在本聊天发送第一条记录即可。")
        status_names = {"suggested": "建议", "planned": "已计划", "done": "已完成", "dropped": "已取消"}
        kind_names = {"reported_fact": "用户陈述", "idea": "想法", "feeling": "感受", "decision": "决定", "question": "疑问"}
        for row in reversed(entries):
            analysis = row["analysis"]
            title = analysis["title"].replace("\n", " ")
            index.append("- " + row["entry_date"] + " · [" + title.replace("[", "［").replace("]", "］") + "](entries/" + row["id"] + ".md) · " + " / ".join(analysis["categories"]))
            lines = ["# " + title, "", "记录 ID：" + row["id"], "日期：" + row["entry_date"], "归档：" + row["created_at"], "分析版本：" + str(row["revision"]), "", "## 原文", ""]
            lines.extend("> " + line for line in row["raw_text"].split("\n"))
            lines += ["", "## 整理", "", analysis["summary"], "", "分类：" + " / ".join(analysis["categories"]), "标签：" + "、".join(analysis["tags"])]
            if analysis["projects"]:
                lines += ["项目：" + "、".join(analysis["projects"])]
            if analysis["observations"]:
                lines += ["", "## 提炼与依据", ""]
                for item in analysis["observations"]:
                    lines += ["- " + kind_names[item["kind"]] + "：" + item["text"], "  - 原文依据：" + item["evidence"].replace("\n", " / ")]
            if analysis["actions"]:
                lines += ["", "## 行动", ""]
                lines += ["- 【" + status_names[a["status"]] + "】" + a["text"] + ("；日期：" + a["due_date"] if a["due_date"] else "") for a in analysis["actions"]]
            if analysis["links"]:
                lines += ["", "## 相关记录", ""]
                lines += ["- [" + link["entry_id"] + "](" + link["entry_id"] + ".md) · " + link["relation"] + "：" + link["reason"] for link in analysis["links"]]
            if analysis["questions"]:
                lines += ["", "## 留待思考", ""] + analysis["questions"]
            history = [r for r in revisions if r["entry_id"] == row["id"]]
            lines += ["", "## 修订记录", ""] + ["- v" + str(r["revision"]) + " · " + r["created_at"] + " · " + r["reason"] for r in history]
            atomic_write(self.root / "entries" / (row["id"] + ".md"), "\n".join(lines) + "\n")
        index += ["", "## 复盘与动态", ""]
        if not documents:
            index.append("暂无。")
        for item in documents:
            payload = item["payload"]
            folder = "reviews" if item["kind"] == "review" else "updates"
            lines = ["# " + payload["title"], "", "更新：" + item["updated_at"], "版本：" + str(item["revision"]), ""]
            if item["kind"] == "review":
                lines += ["范围：" + payload["period_start"] + " 至 " + payload["period_end"], "", payload["body"]]
            else:
                lines += [payload["claim"], "", "## 与你的关联", "", payload["implication"], "", "## 来源", ""]
                for source in payload["sources"]:
                    lines += ["- [" + source["title"] + "](" + source["url"] + ")", "  - 发布：" + (source.get("published_at") or "未知") + "；事件：" + (source.get("event_date") or "未知") + "；检索：" + source["retrieved_at"]]
            lines += ["", "## 依据的日记", ""] + ["- [" + key + "](../entries/" + key + ".md)" for key in payload["source_entry_ids"]]
            atomic_write(self.root / folder / (item["id"] + ".md"), "\n".join(lines) + "\n")
            index.append("- [" + payload["title"].replace("[", "［").replace("]", "］") + "](" + folder + "/" + item["id"] + ".md)")
        atomic_write(self.root / "index.md", "\n".join(index) + "\n")
        return {"status": "exported", "entries": len(entries), "documents": len(documents), "root": str(self.root)}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="拾光日记存储：Codex负责理解，本工具负责可靠保存。")
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parent), help="独立数据目录，测试时必须指定 work/ 下目录")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "context", "export"):
        commands.add_parser(name)
    for name in ("add", "report", "update"):
        commands.add_parser(name).add_argument("--file", required=True)
    change = commands.add_parser("revise")
    change.add_argument("--id", required=True)
    change.add_argument("--file", required=True)
    commands.add_parser("show").add_argument("--id", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("--query", default="")
    listing.add_argument("--start")
    listing.add_argument("--end")
    listing.add_argument("--offset", type=int, default=0)
    listing.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    diary = None
    try:
        diary = Diary(args.data_dir)
        if args.command in {"init", "export"}:
            result = diary.export()
        elif args.command == "context":
            result = diary.context()
        elif args.command == "show":
            result = diary.get(args.id)
        elif args.command == "list":
            if args.start:
                date_field(args.start)
            if args.end:
                date_field(args.end)
            require(args.offset >= 0 and 1 <= args.limit <= 1000, tr('offset>=0，limit范围1–1000'))
            rows = [r for r in reversed(diary.all_entries()) if (not args.start or r["entry_date"] >= args.start) and (not args.end or r["entry_date"] <= args.end) and args.query.casefold() in encode(r).casefold()]
            result = {"total": len(rows), "offset": args.offset, "entries": rows[args.offset:args.offset + args.limit]}
        else:
            payload = read_json(args.file)
            if args.command == "add":
                result = diary.add(payload)
            elif args.command == "revise":
                result = diary.revise(args.id, payload)
            else:
                result = diary.save_document("review" if args.command == "report" else "update", payload)
            try:
                diary.export()
                result["export_status"] = "saved"
                folder = "entries" if args.command in {"add", "revise"} else "reviews" if args.command == "report" else "updates"
                result["path"] = str(diary.root / folder / (result["id"] + ".md"))
            except OSError as error:
                result["export_status"] = "failed"
                result["export_error"] = str(error)
                result["recovery"] = "主档案已提交，请运行 export 重建阅读副本。"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if diary is not None:
            diary.close()


if __name__ == "__main__":
    raise SystemExit(main())
