"""Local attachments, date associations and offline content search."""
from localization import tr
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
import uuid
import zipfile
from urllib.parse import urlparse
from xml.etree import ElementTree

from diary import date_field, now, require, atomic_write
from planner_store import PlannerStore, ConflictError

TEXT_LIMIT = 300000
ALIASES = [
    ("简历", "履历", "簡歷", "履歷", "resume", "résumé", "curriculum vitae", "cv", "求职", "求職"),
    ("论文", "論文", "文章", "paper", "研究成果", "发表", "發表"),
    ("开会", "開會", "会议", "會議", "meeting", "讨论", "討論", "纪要", "紀要"),
    ("报告", "報告", "汇报", "彙報", "总结", "總結", "report", "复盘", "復盤", "回顧"),
    ("学习", "學習", "课程", "課程", "笔记", "筆記", "读书", "讀書", "培训", "培訓", "study", "course", "learning"),
    ("项目", "項目", "專案", "工程", "project", "开发", "開發", "作品"),
    ("实验", "實驗", "测试", "測試", "experiment", "test", "验证", "驗證"),
]


def normalize(text):
    return unicodedata.normalize("NFKC", text).casefold()


def parse_dates(start, end, extra=""):
    start, end = date_field(start), date_field(end or start)
    require(start <= end, tr('开始日期不能晚于结束日期。'))
    spans = {(start, end)}
    for item in re.split(r"[,，;；\s]+", extra.strip()):
        if item:
            parts = re.split(r"[~～]", item)
            require(len(parts) in (1, 2), tr('额外日期范围请写为 开始日期~结束日期。'))
            a, b = date_field(parts[0]), date_field(parts[-1])
            require(a <= b, tr('额外范围的开始日期不能晚于结束日期。'))
            spans.add((a, b))
    return sorted(spans)


def extract_text(path):
    suffix = path.suffix.lower()
    try:
        if suffix in {".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".log", ".tex", ".rst"}:
            with path.open('rb') as handle:
                raw = handle.read(TEXT_LIMIT * 4)
            for encoding in ("utf-8-sig", "gb18030", "utf-16"):
                try:
                    content = raw.decode(encoding)
                    break
                except UnicodeError:
                    continue
            else:
                content = raw.decode("utf-8", errors="replace")
        elif suffix in {".docx", ".pptx", ".xlsx"}:
            chunks = []
            with zipfile.ZipFile(path) as archive:
                names = [n for n in archive.namelist() if
                         (suffix == ".docx" and re.fullmatch(r"word/(document|header\d+|footer\d+)\.xml", n)) or
                         (suffix == ".pptx" and re.fullmatch(r"ppt/slides/slide\d+\.xml", n)) or
                         (suffix == ".xlsx" and re.fullmatch(r"xl/(sharedStrings|worksheets/sheet\d+)\.xml", n))]
                size = 0
                for name in sorted(names):
                    info = archive.getinfo(name)
                    require(info.file_size <= 25000000, tr('文档内容过大，仅保留原文件。'))
                    size += info.file_size
                    require(size <= 50000000, tr('文档内容过大，仅保留原文件。'))
                    root = ElementTree.fromstring(archive.read(name))
                    chunks.extend(node.text for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"t", "v"} and node.text)
            content = "\n".join(chunks)
        elif suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            chunks, total = [], 0
            for page in reader.pages[:300]:
                value = page.extract_text() or ""
                chunks.append(value)
                total += len(value)
                if total >= TEXT_LIMIT:
                    break
            content = "\n".join(chunks)
            if len(reader.pages) > 300:
                return content[:TEXT_LIMIT], "已提取前300页；可在备注补充后续内容"
        else:
            return "", "按文件名、标签和备注检索；此格式未提取正文"
        if not content.strip():
            return "", "未提取到正文（图片或扫描件可在备注补充文字）"
        return content[:TEXT_LIMIT], "正文已提取" + ("（前30万字）" if len(content) > TEXT_LIMIT else "")
    except Exception as error:
        return "", "原文件已保存，正文提取失败：" + str(error)[:180]


class FileStore(PlannerStore):
    def __init__(self, root):
        super().__init__(root)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS planner_files (
                id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
                original_name TEXT NOT NULL, relative_path TEXT NOT NULL, size INTEGER NOT NULL,
                notes TEXT NOT NULL, tags TEXT NOT NULL, cloud_url TEXT NOT NULL,
                as_of TEXT NOT NULL, extracted_text TEXT NOT NULL, extraction_status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS planner_file_dates (
                file_id TEXT NOT NULL REFERENCES planner_files(id), start_day TEXT NOT NULL,
                end_day TEXT NOT NULL, PRIMARY KEY(file_id,start_day,end_day));
            CREATE INDEX IF NOT EXISTS file_date_span ON planner_file_dates(start_day,end_day);
            CREATE TABLE IF NOT EXISTS planner_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS planner_chat (
                id TEXT PRIMARY KEY, role TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
        """)

    def setting(self, key, default=""):
        row = self.db.execute("SELECT value FROM planner_settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        with self.db:
            self.db.execute("INSERT INTO planner_settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def file(self, identifier, content=True):
        row = self.db.execute("SELECT * FROM planner_files WHERE id=?", (identifier,)).fetchone()
        require(row is not None, tr('找不到这个附件。'))
        result = dict(row)
        if not content:
            result.pop("extracted_text", None)
        result["dates"] = [list(r) for r in self.db.execute("SELECT start_day,end_day FROM planner_file_dates WHERE file_id=? ORDER BY start_day,end_day", (identifier,))]
        return result

    def files_for_day(self, day):
        date_field(day)
        return [dict(r) for r in self.db.execute("SELECT DISTINCT f.id,f.title,f.original_name,f.size,f.tags,f.extraction_status,f.version FROM planner_files f JOIN planner_file_dates d ON f.id=d.file_id WHERE d.start_day<=? AND d.end_day>=? ORDER BY f.created_at DESC", (day, day))]

    def attachment_page(self, query="", offset=0, limit=50):
        """Bounded metadata pages for browsing files independently of their dates."""
        query = query.strip().lower()
        condition = " WHERE instr(lower(title || ' ' || original_name || ' ' || tags), ?) > 0" if query else ""
        args = (query,) if query else ()
        total = self.db.execute("SELECT count(*) FROM planner_files" + condition, args).fetchone()[0]
        rows = [dict(row) for row in self.db.execute(
            "SELECT id,title,original_name,size,tags,version,created_at FROM planner_files" + condition +
            " ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", args + (limit, offset))]
        by_id = {row['id']: row for row in rows}
        for row in rows:
            row['dates'] = []
        if by_id:
            placeholders = ','.join('?' for _ in by_id)
            for identifier, start, end in self.db.execute(
                    "SELECT file_id,start_day,end_day FROM planner_file_dates WHERE file_id IN (" + placeholders + ") ORDER BY start_day,end_day", tuple(by_id)):
                by_id[identifier]['dates'].append([start, end])
        return rows, total

    def file_dates(self, start, end):
        counts = {}
        spans = list(self.db.execute("SELECT file_id,start_day,end_day FROM planner_file_dates WHERE start_day<=? AND end_day>=?", (end, start)))
        for day in (date.fromisoformat(start) + timedelta(days=n) for n in range((date.fromisoformat(end) - date.fromisoformat(start)).days + 1)):
            value = day.isoformat()
            counts[value] = len({r[0] for r in spans if r[1] <= value <= r[2]})
        return counts

    def calendar_files(self, start, end):
        """One metadata query for the visible month; deduplicate overlapping spans."""
        first, last = date.fromisoformat(date_field(start)), date.fromisoformat(date_field(end))
        rows = self.db.execute(
            "SELECT f.id,f.title,f.original_name,d.start_day,d.end_day "
            "FROM planner_files f JOIN planner_file_dates d ON f.id=d.file_id "
            "WHERE d.start_day<=? AND d.end_day>=? ORDER BY f.created_at DESC,f.id",
            (end, start))
        result = {}
        for row in rows:
            item = dict(row)
            left, right = max(first, date.fromisoformat(item['start_day'])), min(last, date.fromisoformat(item['end_day']))
            for offset in range((right - left).days + 1):
                day = (left + timedelta(days=offset)).isoformat()
                result.setdefault(day, {})[item['id']] = item
        return {day: list(items.values()) for day, items in result.items()}

    def validate_metadata(self, data):
        title = data.get("title", "").strip()
        require(bool(title) and len(title) <= 240, tr('请填写240字以内的附件标题。'))
        cloud = data.get("cloud_url", "").strip()
        if cloud:
            parsed = urlparse(cloud)
            require(parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username, tr('云端链接需要是有效的 HTTPS 地址。'))
        as_of = data.get("as_of", "").strip()
        if as_of:
            date_field(as_of)
        return title, data.get("notes", ""), data.get("tags", ""), cloud, as_of

    def import_file(self, source, data, spans):
        meta = self.validate_metadata(data)
        require(bool(spans), tr('请至少关联一天。'))
        for start, end in spans:
            require(date_field(start) <= date_field(end), tr('日期范围无效。'))
        source = Path(source)
        require(source.is_file(), tr('请选择一个文件。'))
        require(source.stat().st_size <= 512 * 1024 * 1024, tr('单个附件暂支持512MB以内。'))
        folder = self.root / "vault" / "attachments"
        folder.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="import-", suffix=".pending", dir=str(folder))
        pending = Path(name)
        digest = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as target, source.open("rb") as original:
                size = 0
                for block in iter(lambda: original.read(1024 * 1024), b""):
                    size += len(block)
                    require(size <= 512 * 1024 * 1024, tr('单个附件暂支持512MB以内。'))
                    digest.update(block)
                    target.write(block)
            sha = digest.hexdigest()
            existing = self.db.execute("SELECT id FROM planner_files WHERE sha256=?", (sha,)).fetchone()
            if existing:
                with self.db:
                    self.db.executemany("INSERT OR IGNORE INTO planner_file_dates VALUES(?,?,?)", [(existing[0], a, b) for a, b in spans])
                    self.db.execute("UPDATE planner_files SET version=version+1,updated_at=? WHERE id=?", (now(), existing[0]))
                return {"status": "linked", "file": self.file(existing[0], False)}
            suffix = source.suffix.lower()
            if not re.fullmatch(r"\.[a-z0-9]{1,12}", suffix):
                suffix = ".bin"
            destination = folder / (sha + suffix)
            pending.replace(destination)
            text, status = extract_text(destination)
            identifier = "F" + uuid.uuid4().hex[:20]
            with self.db:
                self.db.execute("INSERT INTO planner_files VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                                (identifier, sha, meta[0], source.name, destination.relative_to(self.root).as_posix(), size,
                                 *meta[1:], text, status, now(), now()))
                self.db.executemany("INSERT INTO planner_file_dates VALUES(?,?,?)", [(identifier, a, b) for a, b in spans])
            return {"status": "imported", "file": self.file(identifier, False)}
        finally:
            if pending.exists():
                pending.unlink()

    def update_file(self, identifier, version, data, spans):
        meta = self.validate_metadata(data)
        require(bool(spans), tr('请至少关联一天。'))
        for a, b in spans:
            require(date_field(a) <= date_field(b), tr('日期范围无效。'))
        with self.db:
            cursor = self.db.execute("UPDATE planner_files SET title=?,notes=?,tags=?,cloud_url=?,as_of=?,updated_at=?,version=version+1 WHERE id=? AND version=?", (*meta, now(), identifier, version))
            if cursor.rowcount != 1:
                raise ConflictError(tr('附件已在其他位置更新，请重新打开。'))
            self.db.execute("DELETE FROM planner_file_dates WHERE file_id=?", (identifier,))
            self.db.executemany("INSERT INTO planner_file_dates VALUES(?,?,?)", [(identifier, a, b) for a, b in spans])
        return self.file(identifier, False)

    def path_for(self, item):
        path = (self.root / item["relative_path"]).resolve()
        require(self.root / "vault" / "attachments" in path.parents, tr('附件路径无效。'))
        return path

    def records(self):
        for row in self.db.execute("SELECT * FROM planner_files ORDER BY created_at DESC"):
            item = dict(row)
            spans = [list(r) for r in self.db.execute("SELECT start_day,end_day FROM planner_file_dates WHERE file_id=? ORDER BY start_day", (item["id"],))]
            yield {"kind": "附件", "id": item["id"], "day": spans[0][0] if spans else "", "title": item["title"], "body": item["notes"] + "\n" + item["extracted_text"], "tags": item["tags"] + " " + item["original_name"], "dates": spans, "as_of": item["as_of"], "extraction_status": item["extraction_status"]}
        for row in self.db.execute("SELECT * FROM planner_tasks ORDER BY day DESC"):
            item = dict(row)
            yield {"kind": "待办", "id": item["id"], "day": item["day"], "at_time": item['at_time'], "priority": item['priority'], "title": item["title"], "body": item["notes"], "tags": "已完成" if item["done"] else "未完成计划", "done": bool(item["done"])}
        for row in self.db.execute("SELECT * FROM planner_notes WHERE trim(body)!='' ORDER BY day DESC"):
            item = dict(row)
            yield {"kind": "草稿", "id": "N" + item["day"], "day": item["day"], "title": item["body"].splitlines()[0][:80], "body": item["body"], "tags": "随记草稿（未归档）"}
        for row in self.db.execute("SELECT * FROM entries ORDER BY entry_date DESC"):
            item = dict(row)
            analysis = json.loads(item["analysis"])
            yield {"kind": "归档", "id": item["id"], "day": item["entry_date"], "title": analysis["title"], "body": item["raw_text"], "tags": " ".join(analysis["tags"] + analysis["categories"]), "analysis": analysis}

    def search(self, query, limit=100):
        query = normalize(query.strip())
        require(bool(query), tr('请输入想查找的内容。'))
        terms = set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", query))
        for prefix in ("帮我找", "帮我", "查找", "搜索", "关于", "之前的", "以前的", "那个", "的文件", "一下"):
            query = query.replace(prefix, " ")
        terms.update(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", query))
        expanded = set(terms)
        for group in ALIASES:
            if any(alias in query for alias in group):
                expanded.update(group)
        grams = {word[i:i + 2] for word in terms if len(word) > 2 for i in range(len(word) - 1)}
        results = []
        for item in self.records():
            heading = normalize(item["title"] + " " + item["tags"])
            body = normalize(item["body"])
            score = sum((9 if term in terms else 6) for term in expanded if term and term in heading)
            score += sum((4 if term in terms else 2) for term in expanded if term and term in body)
            if grams:
                overlap = sum(g in heading for g in grams) / len(grams)
                score += overlap * 5 if overlap >= .25 else 0
                body_overlap = sum(g in body for g in grams) / len(grams)
                score += body_overlap * 2 if body_overlap >= .4 else 0
            if score > 0:
                hit = next((body.find(term) for term in expanded if term in body), 0)
                item["snippet"] = item["body"][max(0, hit - 40):max(0, hit - 40) + 180].replace("\n", " ")
                item["score"] = score
                item.pop("body", None)
                item.pop("analysis", None)
                results.append(item)
        return sorted(results, key=lambda item: (item["score"], item["day"]), reverse=True)[:limit]

    def sync_files(self):
        value = self.setting("sync_folder")
        require(bool(value), tr('请先选择网盘客户端的本机同步文件夹。'))
        base = Path(value).resolve()
        require(base.is_dir(), tr('同步文件夹不可用，请检查网盘客户端或重新选择。'))
        destination = base / "拾光附件"
        require(destination != self.root and self.root not in destination.parents, tr('同步目录请选在应用文件夹之外。'))
        destination.mkdir(exist_ok=True)
        manifest = []
        for row in self.db.execute("SELECT id FROM planner_files"):
            item = self.file(row[0], False)
            source = self.path_for(item)
            target = destination / source.name
            if not target.exists() or target.stat().st_size != source.stat().st_size:
                temp = target.with_suffix(target.suffix + ".pending")
                shutil.copyfile(source, temp)
                temp.replace(target)
            item["filename"] = source.name
            manifest.append(item)
        atomic_write(destination / "日期关联.json", json.dumps({"updated_at": now(), "files": manifest}, ensure_ascii=False, indent=2))
        return str(destination), len(manifest)

    def add_chat(self, role, body):
        with self.db:
            self.db.execute("INSERT INTO planner_chat VALUES(?,?,?,?)", (uuid.uuid4().hex, role, body, now()))

    def chat_history(self, limit=60):
        rows = self.db.execute("SELECT role,body,created_at FROM planner_chat ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in reversed(rows)]


def main():
    import argparse
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="拾光附件与检索工具")
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parent))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("show").add_argument("--id", required=True)
    sub.add_parser("search").add_argument("--query", required=True)
    add = sub.add_parser("import")
    add.add_argument("--path", required=True)
    add.add_argument("--day", required=True)
    add.add_argument("--end")
    add.add_argument("--extra", default="")
    add.add_argument("--title")
    add.add_argument("--as-of", default="")
    args = parser.parse_args()
    store = FileStore(args.data_dir)
    try:
        if args.command == "list":
            result = [store.file(r[0], False) for r in store.db.execute("SELECT id FROM planner_files ORDER BY created_at DESC")]
        elif args.command == "show":
            result = store.file(args.id)
        elif args.command == "search":
            result = store.search(args.query)
        else:
            result = store.import_file(args.path, {"title": args.title or Path(args.path).name, "as_of": args.as_of}, parse_dates(args.day, args.end or args.day, args.extra))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
