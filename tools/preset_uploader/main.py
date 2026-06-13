# -*- coding: utf-8 -*-
"""预设上传工具 - GUI 版
用户选择 JSON 预设文件，输入自己的 GitHub 用户名，提交 PR 等待审核。
"""

import os, sys, json, base64, time, urllib.request, urllib.error
from urllib.parse import quote
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QTextEdit, QLineEdit,
    QProgressBar, QFileDialog,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

OWNER = "JadeYingWah"
REPO = "WutheringWavesDmgCalc"
CATEGORIES = {"character": "角色", "weapon": "武器", "echo_set": "声骸套装", "character_buff": "角色增益"}

# 工具目录下的 token 文件（由项目作者维护）
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".upload_token")


# ═══════════════════════════════════════════════
# 上传线程：创建 PR 分支 → 上传文件 → 创建 PR
# ═══════════════════════════════════════════════

class UploadThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    done_signal = pyqtSignal(int, str)  # success, pr_url

    def __init__(self, token, contributor, file_list):
        super().__init__()
        self.token = token
        self.contributor = contributor  # 投稿人 GitHub 用户名
        self.file_list = file_list       # [(cat, fname, content), ...]
        self.branch = f"preset-{contributor}-{int(time.time())}"

    def _api(self, method, url, data=None):
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
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
            self.log_signal.emit(f"  x {msg}: {err[:80]}")
            return None

    def run(self):
        try:
            self._do_upload()
        except Exception as e:
            self.log_signal.emit(f"\n  !! 上传过程异常: {e}")
            self.done_signal.emit(0, "")

    def _do_upload(self):
        # ── 1. 获取 main 最新 SHA ──
        self.log_signal.emit("获取仓库最新状态...")
        main_ref = self._api("GET",
            f"https://api.github.com/repos/{OWNER}/{REPO}/git/ref/heads/main")
        if not main_ref or "object" not in main_ref:
            self.log_signal.emit("  x 无法获取 main 分支，请检查 Token 权限")
            self.done_signal.emit(0, "")
            return
        main_sha = main_ref["object"]["sha"]
        self.log_signal.emit(f"  v main 分支: {main_sha[:7]}")

        # ── 2. 创建新分支 ──
        self.log_signal.emit(f"创建分支: {self.branch}")
        new_ref = self._api("POST",
            f"https://api.github.com/repos/{OWNER}/{REPO}/git/refs",
            {"ref": f"refs/heads/{self.branch}", "sha": main_sha})
        if not new_ref:
            self.log_signal.emit("  x 创建分支失败")
            self.done_signal.emit(0, "")
            return
        self.log_signal.emit(f"  v 分支已创建")

        # ── 3. 上传预设文件到分支 ──
        success = failed = 0
        total = len(self.file_list)
        for i, (cat, fname, content) in enumerate(self.file_list):
            path = f"presets/official/{cat}/{fname}"
            url = (f"https://api.github.com/repos/{OWNER}/{REPO}/contents/"
                   f"{quote(path, safe='/')}")
            self.log_signal.emit(f"[{i+1}/{total}] {cat}/{fname}")

            # 检查 main 上是否已有同名文件
            existing = self._api("GET", f"{url}?ref=main")
            data = {
                "message": f"投稿 ({self.contributor}): {cat}/{fname}",
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": self.branch,
            }
            if existing and "sha" in existing:
                data["sha"] = existing["sha"]
                self.log_signal.emit(f"    （覆盖已有文件）")

            if self._api("PUT", url, data):
                success += 1
            else:
                failed += 1
            self.progress_signal.emit(i + 1, total + 1)

        if failed > 0:
            self.log_signal.emit(f"\n  {success} 成功, {failed} 失败")
            self.done_signal.emit(success, "")
            return

        # ── 4. 创建 Pull Request ──
        self.log_signal.emit(f"[{total+1}/{total+1}] 创建 Pull Request...")
        # 收集作者信息
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

        pr_data = {
            "title": f"📦 预设投稿 by {self.contributor}（{len(self.file_list)} 个文件）",
            "head": self.branch,
            "base": "main",
            "body": pr_body,
        }
        pr_resp = self._api("POST",
            f"https://api.github.com/repos/{OWNER}/{REPO}/pulls", pr_data)
        if pr_resp and "html_url" in pr_resp:
            pr_url = pr_resp["html_url"]
            self.log_signal.emit(f"  v PR 已创建: {pr_url}")
            self.progress_signal.emit(total + 1, total + 1)
            self.done_signal.emit(success, pr_url)
        else:
            self.log_signal.emit("  x PR 创建失败")
            self.done_signal.emit(success, "")


# ═══════════════════════════════════════════════
# 主界面
# ═══════════════════════════════════════════════

class PresetUploader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("官方预设上传工具")
        self.setFixedSize(680, 580)
        self._pending_files = []  # [(cat, fname, content), ...]

        # 读取作者 Token
        self._author_token = self._load_token()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("官方预设上传工具")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # ── Token 状态 ──
        gb_token = QGroupBox("工具状态")
        gb_token_layout = QVBoxLayout(gb_token)
        if self._author_token:
            self._token_status = QLabel("✅ 工具已配置，可直接使用")
            self._token_status.setStyleSheet("color:#2e7d32;font-size:12px;")
        else:
            self._token_status = QLabel(
                "⚠️ 未配置 Token。请在工具目录创建 .upload_token 文件，"
                "写入 JadeYingWah 的 GitHub Token（仅作者使用）")
            self._token_status.setWordWrap(True)
            self._token_status.setStyleSheet("color:#c62828;font-size:12px;")
        gb_token_layout.addWidget(self._token_status)
        layout.addWidget(gb_token)

        # ── 你的 GitHub 用户名 ──
        gb_user = QGroupBox("你的信息")
        gb_user_layout = QVBoxLayout(gb_user)
        user_row = QHBoxLayout()
        user_row.addWidget(QLabel("GitHub 用户名:"))
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("输入你的 GitHub 用户名（如 JadeYingWah）")
        self._user_input.textChanged.connect(self._update_state)
        user_row.addWidget(self._user_input, 1)
        gb_user_layout.addLayout(user_row)
        hint = QLabel("💡 无需 Token，只需填写你的 GitHub 用户名即可投稿")
        hint.setStyleSheet("color:#888;font-size:11px;")
        gb_user_layout.addWidget(hint)
        layout.addWidget(gb_user)

        # ── 选择文件 ──
        gb_file = QGroupBox("选择预设文件")
        gb_file_layout = QVBoxLayout(gb_file)

        pick_row = QHBoxLayout()
        pick_btn = QPushButton("选择文件")
        pick_btn.setStyleSheet("QPushButton{padding:8px 16px;font-size:14px;}")
        pick_btn.clicked.connect(self._pick_file)
        pick_row.addWidget(pick_btn)
        self._clear_btn = QPushButton("清空列表")
        self._clear_btn.clicked.connect(self._clear_files)
        pick_row.addWidget(self._clear_btn)
        pick_row.addStretch()
        gb_file_layout.addLayout(pick_row)

        self._pending_label = QLabel("待上传文件（为空，请点击「选择文件」添加）")
        self._pending_label.setStyleSheet("color:#888;padding:4px 0;")
        gb_file_layout.addWidget(self._pending_label)

        self._pending_list = QListWidget()
        self._pending_list.setMaximumHeight(140)
        gb_file_layout.addWidget(self._pending_list)

        layout.addWidget(gb_file)

        # ── 提交按钮 ──
        upload_row = QHBoxLayout()
        self._upload_btn = QPushButton("提交投稿")
        self._upload_btn.setStyleSheet(
            "QPushButton{background:#2196F3;color:white;padding:8px 20px;font-size:14px;border-radius:5px;}"
            "QPushButton:disabled{background:#ccc;}")
        self._upload_btn.clicked.connect(self._start_upload)
        self._upload_btn.setEnabled(False)
        upload_row.addWidget(self._upload_btn)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        upload_row.addWidget(self._progress, 1)
        layout.addLayout(upload_row)

        # ── 日志 ──
        gb_log = QGroupBox("上传日志")
        gb_log_layout = QVBoxLayout(gb_log)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        gb_log_layout.addWidget(self._log)
        layout.addWidget(gb_log)

        self._update_state()

    # ── Token ──

    def _load_token(self):
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                    t = f.read().strip()
                    if t:
                        return t
            except Exception:
                pass
        return ""

    # ── 选择文件 ──

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
            display += f"  （作者：{author}）"

        for i in range(self._pending_list.count()):
            if self._pending_list.item(i).text() == display:
                QMessageBox.information(self, "已存在", f"该文件已在待上传列表中。")
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

    def _update_state(self):
        n = len(self._pending_files)
        if n == 0:
            self._pending_label.setText("待上传文件（为空，请点击「选择文件」添加）")
            self._pending_label.setStyleSheet("color:#888;padding:4px 0;")
        else:
            self._pending_label.setText(f"待上传文件（{n} 个）")
            self._pending_label.setStyleSheet("color:#333;font-weight:bold;padding:4px 0;")
        has_user = bool(self._user_input.text().strip())
        ready = has_user and n > 0 and bool(self._author_token)
        self._upload_btn.setEnabled(ready)
        self._clear_btn.setEnabled(n > 0)

    # ── 提交 ──

    def _start_upload(self):
        if not self._author_token:
            QMessageBox.warning(self, "未配置", "工具未配置作者 Token，无法上传。")
            return
        contributor = self._user_input.text().strip()
        if not contributor:
            QMessageBox.warning(self, "提示", "请输入你的 GitHub 用户名")
            return
        if not self._pending_files:
            QMessageBox.information(self, "提示", "没有待上传的文件")
            return

        # 确认弹窗
        reply = QMessageBox.question(
            self, "确认投稿",
            f"将用 @{contributor} 的身份提交 {len(self._pending_files)} 个预设文件。\n\n"
            f"提交后将在 GitHub 创建一个 Pull Request，\n"
            f"等待作者审核合并后即可生效。\n\n确认提交？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._upload_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._log.clear()
        self._log.append(f"投稿人: @{contributor}")
        self._log.append(f"待上传: {len(self._pending_files)} 个文件\n")

        self._thread = UploadThread(
            self._author_token, contributor, list(self._pending_files))
        self._thread.log_signal.connect(self._log.append)
        self._thread.progress_signal.connect(
            lambda c, t: (self._progress.setMaximum(t),
                          self._progress.setValue(c)))
        self._thread.done_signal.connect(self._on_done)
        self._thread.start()

    def _on_done(self, success, pr_url):
        self._progress.setVisible(False)
        self._update_state()
        if pr_url:
            self._log.append(f"\n{'='*40}\n PR 链接: {pr_url}")
            QMessageBox.information(
                self, "提交成功",
                f"已创建 Pull Request！\n\n"
                f"等待作者审核合并即可。\n\n"
                f"PR 链接：\n{pr_url}")
        else:
            self._log.append("\n" + "="*40 + f"\n 上传完成: 成功 {success}")
            QMessageBox.information(
                self, "提交完成",
                f"成功 {success} 个文件\n\n请检查日志了解详情。")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PresetUploader()
    w.show()
    sys.exit(app.exec())
