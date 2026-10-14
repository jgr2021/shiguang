"""Local account routing. Existing owner data stays at its original path."""
import base64
import json
import re
import time
from pathlib import Path

from app_config import protect, program_dir
from diary import atomic_write, require
from localization import tr


def read_json(path, default):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def app_registration():
    value = read_json(program_dir() / "github-app.json", {})
    return {"client_id": value.get("client_id", ""), "slug": value.get("slug", "")}


def save_registration(client_id, slug):
    require(re.fullmatch(r"[A-Za-z0-9_.-]{6,100}", client_id or "") and
            re.fullmatch(r"[a-z0-9-]{1,100}", slug or ""), tr('请填写正确的 Client ID 和 App 名称。'))
    write_json(program_dir() / "github-app.json", {"client_id": client_id, "slug": slug})


def binding(root):
    return read_json(Path(root) / "vault" / "github-binding.json", {})


def save_binding(root, value):
    previous = binding(root)
    require(not previous or (previous["user_id"], previous["repo_id"]) ==
            (value["user_id"], value["repo_id"]), tr('此资料空间已绑定其他账号或仓库。请使用独立空间。'))
    write_json(Path(root) / "vault" / "github-binding.json", value)


def save_token(root, user):
    # This file is deliberately outside the SQLite database and backup allowlist.
    path = Path(root) / "vault" / "github-token.dpapi"
    path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = protect(json.dumps({"user_id": user["id"], "token": user["token"],
                                    "expires_at": user["expires_at"]}).encode())
    atomic_write(path, base64.b64encode(encrypted).decode("ascii"))


def token_for(root, user_id):
    path = Path(root) / "vault" / "github-token.dpapi"
    require(path.exists(), tr('请先用 GitHub 登录。'))
    value = json.loads(protect(base64.b64decode(path.read_bytes()), True))
    require(value.get("user_id") == user_id, tr('登录账号与此资料空间不一致，已停止同步。'))
    require(not value.get("expires_at") or value["expires_at"] > time.time() + 30,
            tr('GitHub 登录已过期，请重新登录。'))
    return value["token"]


def forget_token(root):
    path = Path(root) / "vault" / "github-token.dpapi"
    if path.exists():
        path.unlink()


class Accounts:
    def __init__(self, home):
        self.home = Path(home).resolve()
        self.path = self.home / "accounts.json"
        self.state = read_json(self.path, {"active": ".", "users": {}})

    def resolve(self, relative):
        require(relative == "." or re.fullmatch(r"offline(?:-[1-9][0-9]*)?", relative or "") or
                re.fullmatch(r"accounts/github-[1-9][0-9]*", relative or ""), "Invalid account directory")
        path = (self.home / relative).resolve()
        require(path == self.home or self.home in path.parents, "Account directory escaped data root")
        return path

    def current(self):
        return self.resolve(self.state.get("active", "."))

    def destination(self, user_id, current, include_current=False):
        require(type(user_id) is int and user_id > 0, "Invalid account ID")
        known = self.state["users"].get(str(user_id))
        if known:
            return self.resolve(known)
        current = Path(current).resolve()
        old = binding(current)
        if include_current:
            require(not old or old["user_id"] == user_id,
                    tr('此资料空间已绑定其他账号或仓库。请使用独立空间。'))
            require(current == self.home or self.home in current.parents, "Invalid current profile")
            return current
        return self.resolve("accounts/github-" + str(user_id))

    def remember(self, user_id, root):
        relative = Path(root).resolve().relative_to(self.home).as_posix()
        self.resolve(relative)
        self.state["users"][str(user_id)] = relative
        write_json(self.path, self.state)

    def activate(self, root):
        relative = Path(root).resolve().relative_to(self.home).as_posix()
        self.resolve(relative)
        self.state["active"] = relative
        write_json(self.path, self.state)

    def offline(self):
        # A previously bound owner's records must not appear as a new guest's data.
        if not binding(self.home):
            return self.home
        index = 0
        while True:
            root = self.resolve("offline" if index == 0 else "offline-" + str(index))
            if not binding(root):
                return root
            index += 1
