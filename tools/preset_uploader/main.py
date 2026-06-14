# -*- coding: utf-8 -*-
"""预设上传工具 - GUI 版
用户选择 JSON 预设文件，输入自己的 GitHub 用户名，提交 PR 等待审核。
"""

import os, sys, json, base64, time, urllib.request, urllib.error
from urllib.parse import quote
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QTextEdit, QLineEdit,
    QCheckBox, QProgressBar, QFileDialog,
    QListWidget, QListWidgetItem, QFrame,
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

OWNER = "JadeYingWah"
REPO = "WutheringWavesDmgCalc"
CATEGORIES = {"character": "角色", "weapon": "武器", "echo_set": "声骸套装", "character_buff": "角色增益"}
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".upload_token")

# ═════════════ 统一样式表 ═════════════
STYLE = """
QWidget {
    background: #1e1e2e;
    color: #cdd6f4;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}
QGroupBox {
    font-weight: bold;
    font-size: 13px;
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 14px;
    background: #2a2a3c;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #cdd6f4;
}
QLineEdit {
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 7px 10px;
    background: #313244;
    color: #cdd6f4;
}
QLineEdit:focus {
    border-color: #89b4fa;
}
QPushButton {
    border-radius: 4px;
    padding: 7px 16px;
    font-size: 13px;
}
QListWidget {
    border: 1px solid #45475a;
    border-radius: 4px;
    background: #313244;
    color: #cdd6f4;
}
QListWidget::item {
    padding: 4px 8px;
}
QListWidget::item:selected {
    background: #45475a;
    color: #cdd6f4;
}
QTextEdit {
    border: 1px solid #45475a;
    border-radius: 4px;
    background: #313244;
    color: #cdd6f4;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}
QProgressBar {
    border: 1px solid #45475a;
    border-radius: 4px;
    background: #313244;
    height: 8px;
    text-align: center;
    font-size: 11px;
    color: #cdd6f4;
}
QProgressBar::chunk {
    background: #89b4fa;
    border-radius: 3px;
}
QCheckBox {
    spacing: 6px;
    color: #cdd6f4;
}
QScrollBar:vertical {
    background: #1e1e2e;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


# ═══════════════════════════════════════════════
# 上传线程：创建 PR 分支 → 上传文件 → 创建 PR
# ═══════════════════════════════════════════════

class UploadThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    done_signal = pyqtSignal(int, str)

    def __init__(self, token, contributor, file_list):
        super().__init__()
        self.token = token
        self.contributor = contributor
        self.file_list = file_list
        self.branch = f"preset-{contributor}-{int(time.time())}"

    def _api(self, method, url, data=None):
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("User-Agent", "WWDmgCalc/1.0")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                c = resp.read().decode("utf-8")
                return json.loads(c) if c else None
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            msg = {403: "Token 权限不足", 404: "路径不存在", 422: "已存在或格式错误"}.get(
                e.code, f"HTTP {e.code}")
            self.log_signal.emit(f"  ✗ {msg}: {err[:80]}")
            return None

    def run(self):
        try:
            self._do_upload()
        except Exception as e:
            self.log_signal.emit(f"\n  !! 上传过程异常: {e}")
            self.done_signal.emit(0, "")

    def _do_upload(self):
        self.log_signal.emit("▶ 获取 main 分支状态...")
        main_ref = self._api("GET",
            f"https://api.github.com/repos/{OWNER}/{REPO}/git/ref/heads/main")
        if not main_ref or "object" not in main_ref:
            self.log_signal.emit("  ✗ 无法获取 main 分支，请检查 Token 权限")
            self.done_signal.emit(0, "")
            return
        main_sha = main_ref["object"]["sha"]
        self.log_signal.emit(f"  ✓ main: {main_sha[:7]}")

        self.log_signal.emit(f"▶ 创建分支: {self.branch}")
        new_ref = self._api("POST",
            f"https://api.github.com/repos/{OWNER}/{REPO}/git/refs",
            {"ref": f"refs/heads/{self.branch}", "sha": main_sha})
        if not new_ref:
            self.log_signal.emit("  ✗ 创建分支失败")
            self.done_signal.emit(0, "")
            return
        self.log_signal.emit("  ✓ 分支已创建")

        # ── 将投稿人 GitHub 用户名写入预设 JSON author 字段 ──
        for idx, (cat_name, fname_name, content_val) in enumerate(self.file_list):
            try:
                d = json.loads(content_val)
                d["author"] = self.contributor
                self.file_list[idx] = (cat_name, fname_name, json.dumps(d, ensure_ascii=False, indent=2))
            except Exception:
                pass

        success = failed = 0
        total = len(self.file_list)
        for i, (cat, fname, content) in enumerate(self.file_list):
            path = f"presets/official/{cat}/{fname}"
            url = (f"https://api.github.com/repos/{OWNER}/{REPO}/contents/"
                   f"{quote(path, safe='/')}")
            self.log_signal.emit(f"[{i+1}/{total}] {cat}/{fname}")

            existing = self._api("GET", f"{url}?ref=main")
            data = {
                "message": f"投稿 ({self.contributor}): {cat}/{fname}",
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": self.branch,
            }
            if existing and "sha" in existing:
                data["sha"] = existing["sha"]
            if self._api("PUT", url, data):
                success += 1
            else:
                failed += 1
            self.progress_signal.emit(i + 1, total + 3)

        if failed > 0:
            self.log_signal.emit(f"\n  {success} 成功, {failed} 失败")
            self.done_signal.emit(success, "")
            return

        # ── 更新 CONTRIBUTORS.md ──
        self.log_signal.emit(f"[{total+1}/{total+3}] 更新 CONTRIBUTORS.md...")
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        contrib_path_gh = "CONTRIBUTORS.md"
        contrib_url_gh = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{quote(contrib_path_gh, safe='/')}"
        try:
            ce = self._api("GET", f"{contrib_url_gh}?ref=main")
            if ce and "content" in ce:
                old_md = base64.b64decode(ce["content"]).decode("utf-8")
                # 解析已有作者→文件列表
                existing = {}  # {name: {file1, file2, ...}}
                for line in old_md.split(chr(10)):
                    line = line.strip()
                    if not line.startswith("|"): continue
                    if line.startswith("|-"): continue
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 3 and parts[0] not in ("贡献者",) and parts[0] != "*(虚位以待)*":
                        existing.setdefault(parts[0], set())
                        for f in parts[1].replace("<br>", chr(10)).split(chr(10)):
                            f = f.strip()
                            if f: existing[parts[0]].add(f)
                # 合并本次投稿
                if self.contributor not in existing:
                    existing[self.contributor] = set()
                for cat, fn, ct in self.file_list:
                    existing[self.contributor].add(f"{cat}/{fn}")
                # 重建表格
                header_end = 0
                lines = old_md.split(chr(10))
                for i, line in enumerate(lines):
                    if line.strip().startswith("|---"): header_end = i + 1; break
                footer_start = len(lines)
                for i in range(header_end, len(lines)):
                    if not lines[i].strip().startswith("|") and not lines[i].strip().startswith("---"):
                        footer_start = i; break
                new_lines = lines[:header_end]
                for name in sorted(existing.keys()):
                    file_str = "<br>".join(sorted(existing[name]))
                    new_lines.append(f"| {name} | {file_str} | {today} |")
                new_lines += lines[footer_start:]
                new_md = chr(10).join(new_lines)
                data = {
                    "message": f"投稿 ({self.contributor}): 更新 CONTRIBUTORS.md",
                    "content": base64.b64encode(new_md.encode("utf-8")).decode("ascii"),
                    "branch": self.branch,
                    "sha": ce["sha"],
                }
                self._api("PUT", contrib_url_gh, data)
                self.log_signal.emit("  ✓ CONTRIBUTORS.md 已更新")
        except Exception as e:
            self.log_signal.emit(f"  ⚠ CONTRIBUTORS.md: {e}")

        # ── 更新 manifest.json ──
        self.log_signal.emit(f"[{total+2}/{total+3}] 更新 manifest.json...")
        try:
            man_path = "presets/official/manifest.json"
            man_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{quote(man_path, safe='/')}"
            man_exist = self._api("GET", f"{man_url}?ref=main")
            old_man = {}
            man_sha = None
            if man_exist and "content" in man_exist:
                old_man = json.loads(base64.b64decode(man_exist["content"]).decode("utf-8"))
                man_sha = man_exist.get("sha")
            for cat in CATEGORIES:
                if cat not in old_man:
                    old_man[cat] = []
            for cat, fn, ct in self.file_list:
                if fn not in old_man.get(cat, []):
                    old_man.setdefault(cat, []).append(fn)
            new_man = json.dumps(old_man, ensure_ascii=False, indent=2)
            man_data = {
                "message": f"投稿 ({self.contributor}): 更新 manifest.json",
                "content": base64.b64encode(new_man.encode("utf-8")).decode("ascii"),
                "branch": self.branch,
            }
            if man_sha:
                man_data["sha"] = man_sha
            if self._api("PUT", man_url, man_data):
                self.log_signal.emit("  ✓ manifest.json 已更新")
        except Exception as e:
            self.log_signal.emit(f"  ⚠ manifest.json: {e}")

        self.log_signal.emit(f"[{total+3}/{total+3}] 创建 Pull Request...")
        authors = set()
        file_lines = []
        for cat, fname, content in self.file_list:
            file_lines.append(f"- `presets/official/{cat}/{fname}`")
            try:
                d = json.loads(content)
                a = d.get("author", "").strip()
                if a:
                    authors.add(a)
            except Exception:
                pass

        pr_body = f"## 投稿人：{self.contributor}\n\n"
        if authors:
            pr_body += f"**预设作者**：{', '.join(sorted(authors))}\n\n"
        pr_body += "### 包含文件\n" + "\n".join(file_lines)
        pr_body += (
            "\n\n---\n"
            "> 此 PR 由预设上传工具自动创建。\n"
            f"> 投稿人 GitHub：@{self.contributor}\n"
        )

        pr_resp = self._api("POST",
            f"https://api.github.com/repos/{OWNER}/{REPO}/pulls",
            {"title": f"📦 预设投稿 by {self.contributor}（{len(self.file_list)} 个文件）",
             "head": self.branch, "base": "main", "body": pr_body})
        if pr_resp and "html_url" in pr_resp:
            pr_url = pr_resp["html_url"]
            self.log_signal.emit(f"  ✓ PR 已创建: {pr_url}")
            self.progress_signal.emit(total + 2, total + 3)
            self.done_signal.emit(success, pr_url)
        else:
            self.log_signal.emit("  ✗ PR 创建失败")
            self.done_signal.emit(success, "")


# ═══════════════════════════════════════════════
# 主界面
# ═══════════════════════════════════════════════

class PresetUploader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("官方预设上传工具")
        self.setFixedSize(620, 560)
        self._pending_files = []  # [(cat, fname, content), ...]
        self._user_verified = False
        self._author_token = self._load_token()

        self._build_ui()
        self._update_state()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        # ── 标题 ──
        title = QLabel("📦 官方预设上传")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #cdd6f4; background: transparent;")
        layout.addWidget(title)

        # ── 工具状态：一行状态条 ──
        status_frame = QFrame()
        status_frame.setStyleSheet(
            "QFrame{background:#2a2a3c;border:1px solid #45475a;border-radius:6px;padding:8px 12px;}")
        status_row = QHBoxLayout(status_frame)
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(6)

        has = bool(self._author_token)
        self._status_label = QLabel("● 已配置" if has else "● 未配置")
        self._status_label.setStyleSheet(
            f"color:{'#a6e3a1' if has else '#f38ba8'};font-size:12px;font-weight:bold;background:transparent;")
        status_row.addWidget(self._status_label)

        self._cfg_input = QLineEdit()
        self._cfg_input.setPlaceholderText("粘贴 Token (ghp_xxx)...")
        self._cfg_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._cfg_input.setMaximumWidth(280)
        self._cfg_input.setStyleSheet(
            "QLineEdit{font-size:11px;padding:4px 8px;border:1px solid #45475a;border-radius:4px;background:#313244;color:#cdd6f4;}")
        if self._author_token:
            self._cfg_input.setText(self._author_token)
        status_row.addWidget(self._cfg_input)

        show_cb = QCheckBox("显示")
        show_cb.setStyleSheet("font-size:11px;background:transparent;color:#cdd6f4;")
        show_cb.toggled.connect(
            lambda c: self._cfg_input.setEchoMode(
                QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password))
        status_row.addWidget(show_cb)

        self._save_btn = QPushButton("保存")
        self._save_btn.setStyleSheet(
            "QPushButton{background:#89b4fa;color:#1e1e2e;border:0;padding:4px 14px;font-size:11px;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#74c7ec;}")
        self._save_btn.clicked.connect(self._save_token)
        status_row.addWidget(self._save_btn)

        status_row.addStretch()
        layout.addWidget(status_frame)
        self._token_hint = QLabel("作者专用。普通投稿无需 Token，请在下方「你的信息」栏填写您的 GitHub 名称。")
        self._token_hint.setStyleSheet("color:#6c7086;font-size:10px;background:transparent;")
        self._token_hint.setWordWrap(True)
        layout.addWidget(self._token_hint)

        # ── 你的信息 ──
        gb_user = QGroupBox("你的信息")
        gb_user_layout = QVBoxLayout(gb_user)
        gb_user_layout.setSpacing(8)
        user_row = QHBoxLayout()
        lbl = QLabel("GitHub 用户名：")
        lbl.setStyleSheet("background:transparent;color:#cdd6f4;font-size:13px;padding-top:2px;")
        user_row.addWidget(lbl)
        self._user_input = QLineEdit()
        self._user_input.setMinimumHeight(30)
        self._user_input.setPlaceholderText("输入你的 GitHub 用户名（如 JadeBrookYuyanxi）")
        self._user_input.setStyleSheet("QLineEdit{padding:6px 10px;background:#313244;color:#cdd6f4;border:1px solid #45475a;border-radius:4px;}")
        self._user_input.textChanged.connect(self._on_user_changed)
        user_row.addWidget(self._user_input, 1)
        gb_user_layout.addLayout(user_row)
        self._hint_label = QLabel("  只需填写你的 GitHub 用户名，无需 Token")
        hint = self._hint_label
        self._hint_label.setStyleSheet("color:#6c7086;font-size:11px;background:transparent;")
        gb_user_layout.addWidget(self._hint_label)
        self._user_status = QLabel()
        self._user_status.setStyleSheet("color:#6c7086;font-size:11px;background:transparent;padding-left:2px;")
        gb_user_layout.addWidget(self._user_status)
        layout.addWidget(gb_user)

        # ── 文件列表 ──
        gb_file = QGroupBox("预设文件")
        gb_file_layout = QVBoxLayout(gb_file)
        gb_file_layout.setSpacing(6)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("选择文件 ＋")
        add_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#89b4fa;border:1px solid #89b4fa;padding:6px 14px;font-size:13px;border-radius:4px;}"
            "QPushButton:hover{background:#313244;color:#b4befe;}")
        add_btn.clicked.connect(self._pick_file)
        btn_row.addWidget(add_btn)
        clear_btn = QPushButton("清空")
        clear_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#a6adc8;border:1px solid #45475a;padding:6px 14px;font-size:13px;border-radius:4px;}"
            "QPushButton:hover{background:#313244;color:#b4befe;}")
        clear_btn.clicked.connect(self._clear_files)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        gb_file_layout.addLayout(btn_row)

        self._pending_list = QListWidget()
        self._pending_list.setMaximumHeight(260)
        self._pending_list.setAlternatingRowColors(True)
        gb_file_layout.addWidget(self._pending_list)

        self._pending_label = QLabel("尚未添加文件")
        self._pending_label.setStyleSheet("color:#6c7086;font-size:11px;background:transparent;")
        gb_file_layout.addWidget(self._pending_label)

        layout.addWidget(gb_file)

        # ── 提交 ──
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self._upload_btn = QPushButton("提交投稿")
        self._upload_btn.setStyleSheet(
            "QPushButton{background:#cba6f7;color:#1e1e2e;border:0;padding:10px 28px;font-size:14px;font-weight:bold;border-radius:6px;}"
            "QPushButton:hover{background:#b4befe;}"
            "QPushButton:disabled{background:#45475a;color:#6c7086;}")
        self._upload_btn.clicked.connect(self._start_upload)
        self._upload_btn.setEnabled(False)
        action_row.addWidget(self._upload_btn)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setFixedHeight(8)
        action_row.addWidget(self._progress, 1)
        layout.addLayout(action_row)

        # ── 日志 ──
        gb_log = QGroupBox("上传日志")
        gb_log_layout = QVBoxLayout(gb_log)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(130)
        gb_log_layout.addWidget(self._log)
        layout.addWidget(gb_log)

    # ═════════════ Token ═════════════

    def _load_token(self):
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r", encoding="utf-8-sig") as f:
                    t = f.read().strip()
                    if t:
                        return t
            except Exception:
                pass
        return ""

    def _save_token(self):
        t = self._cfg_input.text().strip()
        if not t:
            QMessageBox.warning(self, "提示", "Token 不能为空")
            return

        reply = QMessageBox.question(
            self, "确认更改",
            "确认更新 Token？\n\n这将会覆盖当前已保存的 Token。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(t)
            self._author_token = t
            self._status_label.setText("● 已配置")
            self._status_label.setStyleSheet(
                "color:#a6e3a1;font-size:12px;font-weight:bold;background:transparent;")
            self._save_btn.setText("✓ 已保存")
            self._save_btn.setStyleSheet(
                "QPushButton{background:#a6e3a1;color:#1e1e2e;border:0;padding:4px 14px;font-size:11px;font-weight:bold;border-radius:4px;}"
                "QPushButton:hover{background:#a6e3a1;}")
            QTimer.singleShot(2000, self._restore_save_btn)
            self._update_state()
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def _restore_save_btn(self):
        self._save_btn.setText("保存")
        self._save_btn.setStyleSheet(
            "QPushButton{background:#89b4fa;color:#1e1e2e;border:0;padding:4px 14px;font-size:11px;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#74c7ec;}")

    # ═════════════ 文件选择 ═════════════

    def _pick_file(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "选择预设 JSON 文件", "", "JSON 文件 (*.json);;所有文件 (*.*)")
        if not fpath:
            return
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"无法解析 JSON 文件：\n{e}")
            return

        category = data.get("category", "")
        author = data.get("author", "")
        fname = os.path.basename(fpath)

        if category not in CATEGORIES:
            QMessageBox.warning(
                self, "分类未知",
                f"预设类别「{category}」不在支持范围内。\n"
                f"支持的分类：{', '.join(CATEGORIES.keys())}\n\n"
                f"请确认 JSON 中 category 字段是否为其中之一。")
            return

        cat_label = CATEGORIES[category]
        display = f"[{cat_label}]  {fname}"
        if author:
            display += f"  — 作者：{author}"

        for i in range(self._pending_list.count()):
            if self._pending_list.item(i).text() == display:
                QMessageBox.information(self, "已存在", "该文件已在待上传列表中。")
                return

        self._pending_list.addItem(display)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        self._pending_files.append((category, fname, content))
        self._update_state()

    def _clear_files(self):
        self._pending_files.clear()
        self._pending_list.clear()
        self._update_state()

    def _on_user_changed(self):
        self._update_state()
        if hasattr(self, "_user_timer"):
            self._user_timer.stop()
        self._user_timer = QTimer()
        self._user_timer.setSingleShot(True)
        self._user_timer.timeout.connect(self._verify_user)
        self._user_timer.start(600)

    def _verify_user(self):
        username = self._user_input.text().strip()
        if not username:
            self._user_verified = False
            self._user_status.setText("")
            self._hint_label.setText("只需填写你的 GitHub 用户名，无需 Token")
            return
        try:
            check_req = urllib.request.Request(f"https://github.com/{username}")
            check_req.add_header("User-Agent", "WWDmgCalc/1.0")
            urllib.request.urlopen(check_req, timeout=10)
            self._user_verified = True
            self._user_status.setText("✓ 用户存在")
            self._hint_label.setText("只需填写你的 GitHub 用户名，无需 Token — 投稿后将在您的名下记录贡献。")
            self._user_status.setStyleSheet("color:#a6e3a1;font-size:11px;background:transparent;padding-left:2px;")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                self._user_verified = False
                self._user_status.setText("✗ GitHub 上找不到该用户")
                self._hint_label.setText("✗ 该地址在 GitHub 上不存在，请确认您的用户名大小写是否合适。")
                self._user_status.setStyleSheet("color:#f38ba8;font-size:11px;background:transparent;padding-left:2px;")
            else:
                self._user_status.setText("")
        except Exception:
            self._user_verified = False
            self._user_status.setText("⚠ 无法验证，请稍后重试")
            self._user_status.setStyleSheet("color:#f9e2af;font-size:11px;background:transparent;padding-left:2px;")
            self._hint_label.setText("网络连接失败，无法验证。您仍可继续投稿。")

    def _update_state(self):
        n = len(self._pending_files)
        if n == 0:
            self._pending_label.setText("尚未添加文件")
            self._pending_label.setStyleSheet("color:#6c7086;font-size:11px;background:transparent;")
        else:
            self._pending_label.setText(f"共 {n} 个文件待上传")
            self._pending_label.setStyleSheet("color:#cdd6f4;font-weight:bold;font-size:11px;background:transparent;")
        has_user = bool(self._user_input.text().strip()) and self._user_verified
        ready = has_user and n > 0 and bool(self._author_token)
        self._upload_btn.setEnabled(ready)

    # ═════════════ 提交 ═════════════

    def _start_upload(self):
        if not self._author_token:
            QMessageBox.warning(self, "未配置", "工具未配置 Token，无法上传。")
            return
        contributor = self._user_input.text().strip()
        if not contributor:
            QMessageBox.warning(self, "提示", "请输入你的 GitHub 用户名")
            return
        if not self._user_verified:
            QMessageBox.warning(self, "用户未验证", f"GitHub 用户名「{contributor}」未通过验证。\n请检查输入框下方的提示。\n\n确认输入正确后重试。")
            return
        if not self._pending_files:
            QMessageBox.information(self, "提示", "没有待上传的文件")
            return


        reply = QMessageBox.question(
            self, "确认投稿",
            f"以 @{contributor} 的身份提交 {len(self._pending_files)} 个预设文件。\n\n"
            "提交后将创建 Pull Request，等待审核合并后生效。\n\n确认提交？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._upload_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._log.clear()
        self._log.append(f"投稿人: @{contributor}")
        self._log.append(f"文件数: {len(self._pending_files)}\n")

        self._thread = UploadThread(self._author_token, contributor, list(self._pending_files))
        self._thread.log_signal.connect(self._log.append)
        self._thread.progress_signal.connect(
            lambda c, t: (self._progress.setMaximum(t), self._progress.setValue(c)))
        self._thread.done_signal.connect(self._on_done)
        self._thread.start()

    def _on_done(self, success, pr_url):
        self._progress.setVisible(False)
        self._update_state()
        if pr_url:
            self._log.append(f"\n{'─'*40}\nPR: {pr_url}")
            QMessageBox.information(
                self, "提交成功",
                f"已创建 Pull Request！\n\n等待审核合并即可。\n\n{pr_url}")
        else:
            self._log.append(f"\n{'─'*40}\n完成: 成功 {success}")
            QMessageBox.information(self, "提交完成", f"成功 {success} 个文件，请检查日志。")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    w = PresetUploader()
    w.show()
    sys.exit(app.exec())
