"""GitHub App device authorization and bounded, authenticated API calls."""
import base64
import json
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

from diary import require
from localization import tr


class GitHubError(ValueError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class NoRedirect(HTTPRedirectHandler):
    # Never forward an Authorization header to a redirect destination.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, token=""):
        self.token = token
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, data=None, login=False):
        require(path.startswith("/") and not path.startswith("//"), "Invalid GitHub API path")
        host = "https://github.com" if login else "https://api.github.com"
        headers = {"Accept": "application/json" if login else "application/vnd.github+json",
                   "User-Agent": "Shiguang-Sync", "Content-Type": "application/json"}
        if not login:
            headers["X-GitHub-Api-Version"] = "2022-11-28"
            if self.token:
                headers["Authorization"] = "Bearer " + self.token
        payload = json.dumps(data).encode() if data is not None else None
        try:
            with self.opener.open(Request(host + path, payload, headers, method=method), timeout=20) as response:
                raw = response.read(24 * 1024 * 1024 + 1)
                require(len(raw) <= 24 * 1024 * 1024, tr('同步数据过大，请减少附件或记录后重试。'))
                return json.loads(raw) if raw else {}
        except HTTPError as error:
            # Do not include the server response, URL or tokens in logs/UI.
            messages = {401: tr('GitHub 登录已过期，请重新登录。'),
                        403: tr('GitHub 权限不足或请求受限。请检查仓库授权，稍后重试。'),
                        404: tr('找不到已授权的仓库或记录，请检查 GitHub App 的仓库权限。'),
                        409: tr('另一台设备刚更新了记录，请重新同步。'),
                        422: tr('GitHub 拒绝了此次更新，请检查仓库状态后重试。')}
            raise GitHubError(error.code, messages.get(error.code, tr('GitHub 请求失败（{0}），本机记录仍然保留。', error.code))) from None
        except (URLError, TimeoutError, socket.timeout):
            raise GitHubError(0, tr('暂时无法连接 GitHub；记录已留在本机，联网后可重试。')) from None

    def begin_login(self, client_id):
        require(re.fullmatch(r"[A-Za-z0-9_.-]{6,100}", client_id or ""), tr('请先配置拾光的 GitHub App Client ID。'))
        value = self.request("POST", "/login/device/code", {"client_id": client_id}, login=True)
        require(value.get("device_code") and value.get("user_code"), tr('GitHub 设备登录未启用，请检查应用配置。'))
        return value

    def finish_login(self, client_id, code, cancel):
        interval = max(5, int(code.get("interval", 5)))
        deadline = time.monotonic() + min(900, int(code.get("expires_in", 900)))
        while time.monotonic() < deadline:
            if cancel.wait(interval):
                raise ValueError(tr('已取消登录。'))
            value = self.request("POST", "/login/oauth/access_token", {
                "client_id": client_id, "device_code": code["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, login=True)
            if value.get("access_token"):
                require(value["access_token"].startswith("ghu_"), tr('请使用 GitHub App，不能使用传统 OAuth App。'))
                user = GitHub(value["access_token"]).request("GET", "/user")
                require(type(user.get("id")) is int and user["id"] > 0, "Invalid GitHub identity")
                return {"id": user["id"], "login": user["login"], "token": value["access_token"],
                        "expires_at": time.time() + int(value["expires_in"]) if value.get("expires_in") else 0}
            error = value.get("error")
            if error == "slow_down":
                interval += 5
            elif error != "authorization_pending":
                raise ValueError(tr('GitHub 授权未完成或已取消，请重新登录。'))
        raise ValueError(tr('登录验证码已过期，请重新登录。'))

    def repositories(self, owner_id):
        result = []
        for page in range(1, 11):
            rows = self.request("GET", "/user/repos?visibility=private&affiliation=owner&per_page=100&page=" + str(page))
            for row in rows:
                if row.get("private") and row["owner"]["id"] == owner_id and not row.get("archived"):
                    result.append({"id": row["id"], "name": row["full_name"], "branch": row["default_branch"]})
            if len(rows) < 100:
                break
        return result

    def check_repo(self, binding):
        user = self.request("GET", "/user")
        require(user.get("id") == binding["user_id"], tr('登录账号与此资料空间不一致，已停止同步。'))
        require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", binding["repo"]), "Invalid repository")
        repo = self.request("GET", "/repos/" + binding["repo"])
        require(repo.get("private") is True and repo["id"] == binding["repo_id"] and
                repo["owner"]["id"] == binding["user_id"] and not repo.get("archived"),
                tr('同步仓库必须仍为当前账号拥有的私有仓库。'))
        return repo

    def blob(self, repo, sha):
        require(re.fullmatch(r"[0-9a-f]{40}", sha or ""), "Invalid Git blob")
        value = self.request("GET", "/repos/" + repo + "/git/blobs/" + sha)
        require(value.get("encoding") == "base64", "Unsupported Git blob encoding")
        return base64.b64decode(value["content"], validate=False)

    def put_blob(self, repo, content):
        value = self.request("POST", "/repos/" + repo + "/git/blobs", {
            "encoding": "base64", "content": base64.b64encode(content).decode("ascii")})
        return value["sha"]

    def read_head(self, binding):
        prefix = "/repos/" + binding["repo"]
        ref = self.request("GET", prefix + "/git/ref/heads/" + quote(binding["branch"], safe=""))
        commit = self.request("GET", prefix + "/git/commits/" + ref["object"]["sha"])
        # Walk only the dedicated subtree; never enumerate unrelated repository content.
        root = self.request("GET", prefix + "/git/trees/" + commit["tree"]["sha"])
        folder = next((x for x in root["tree"] if x["path"] == "shiguang-sync"), None)
        require(not root.get("truncated"), "Truncated Git tree")
        files = {}
        if folder:
            require(folder["type"] == "tree", "Invalid sync folder")
            tree = self.request("GET", prefix + "/git/trees/" + folder["sha"] + "?recursive=1")
            require(not tree.get("truncated"), "Truncated sync tree")
            files = {x["path"]: x["sha"] for x in tree["tree"] if x["type"] == "blob"}
        return ref["object"]["sha"], commit["tree"]["sha"], files

    def publish(self, binding, head, tree, changes):
        self.check_repo(binding)
        prefix = "/repos/" + binding["repo"]
        created = self.request("POST", prefix + "/git/trees", {"base_tree": tree, "tree": changes})
        commit = self.request("POST", prefix + "/git/commits", {
            "message": "Sync Shiguang records", "tree": created["sha"], "parents": [head]})
        self.request("PATCH", prefix + "/git/refs/heads/" + quote(binding["branch"], safe=""),
                     {"sha": commit["sha"], "force": False})
        return commit["sha"]
