# -*- coding: utf-8 -*-
"""预设上传工具 - GUI 版
用户选择任意 JSON 预设文件，自动识别分类，上传到 GitHub 官方预设库。
"""

import os, sys, json, base64, urllib.request, urllib.error
from urllib.parse import quote
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QTextEdit, QLineEdit,
    QCheckBox, QProgressBar, QFileDialog, QFrame,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

OWNER = "JadeYingWah"
REPO = "WutheringWavesDmgCalc"
BRANCH = "main"
CATEGORIES = {"character": "角色", "weapon": "武器", "echo_set": "声骸套装", "character_buff": "角色增益"}


class UploadThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    done_signal = pyqtSignal(int, int)

    def __init__(self, token, file_list):
        super().__init__()
        self.token = token
        self.file_list = file_list  # [(cat, fname, content), ...]

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
            msg = {403: "Token权限不足", 404: "路径不存在", 422: "路径格式错误"}.get(e.code, f"HTTP {e.code}")
            self.log_signal.emit(f"  x {msg}")
            return None

    def _do_upload(self):
        success = failed = 0
        total = len(self.file_list) + 1
        for i, (cat, fname, content) in enumerate(self.file_list):
            path = f"presets/official/{cat}/{fname}"
            url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{quote(path, safe='/')}"
            self.log_signal.emit(f"[{i+1}/{total-1}] 上传: {cat}/{fname}")
            existing = self._api("GET", url)
            data = {"message": f"更新预设: {cat}/{fname}",
                    "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    "branch": BRANCH}
            if existing and "sha" in existing:
                data["sha"] = existing["sha"]
            if self._api("PUT", url, data):
                self.log_signal.emit("  v 成功")
                success += 1
            else:
                failed += 1
            self.progress_signal.emit(i + 1, total)
        # 更新 manifest
        manifest = {}
        for cat in CATEGORIES:
            cat_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/presets/official/{cat}?ref={BRANCH}"
            cat_list = self._api("GET", cat_url)
            filenames = []
            if isinstance(cat_list, list):
                for item in cat_list:
                    if item.get("name", "").endswith(".json") and item["name"] != "manifest.json":
                        filenames.append(item["name"])
            manifest[cat] = sorted(set(filenames + [fname for cat2, fname, _ in self.file_list if cat2 == cat]))
        mjson = json.dumps(manifest, ensure_ascii=False, indent=2)
        path = "presets/official/manifest.json"
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{quote(path, safe='/')}"
        existing = self._api("GET", url)
        data = {"message": "更新 manifest.json",
                "content": base64.b64encode(mjson.encode("utf-8")).decode("ascii"),
                "branch": BRANCH}
        if existing and "sha" in existing:
            data["sha"] = existing["sha"]
        if self._api("PUT", url, data):
            self.log_signal.emit(f"[{total}/{total}] 上传: manifest.json ... v 成功")
        self.progress_signal.emit(total, total)
        self.done_signal.emit(success, failed)

    def run(self):
        try:
            self._do_upload()
        except Exception as e:
            self.log_signal.emit(f"\n  !! 上传过程异常: {e}")
            self.done_signal.emit(0, len(self.file_list))


class PresetUploader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("官方预设上传工具")
        self.setFixedSize(680, 600)
        self._pending_files = []  # [(cat, fname, content), ...]
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("官方预设上传工具")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # ── Token ──
        gb_token = QGroupBox("GitHub Token")
        gb_token_layout = QVBoxLayout(gb_token)
        token_row = QHBoxLayout()
        self._token_input = QLineEdit()
        self._token_input.setPlaceholderText("输入 github_pat_xxx 或 ghp_xxx ...")
        self._token_input.setEchoMode(QLineEdit.EchoMode.Password)
        token_row.addWidget(self._token_input, 1)
        cb = QCheckBox("显示")
        cb.toggled.connect(lambda c: self._token_input.setEchoMode(
            QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password))
        token_row.addWidget(cb)
        gb_token_layout.addLayout(token_row)
        layout.addWidget(gb_token)

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

        # 待上传文件列表
        self._pending_label = QLabel("待上传文件（为空，请点击「选择文件」添加）")
        self._pending_label.setStyleSheet("color:#888;padding:4px 0;")
        gb_file_layout.addWidget(self._pending_label)

        self._pending_list = QListWidget()
        self._pending_list.setMaximumHeight(140)
        gb_file_layout.addWidget(self._pending_list)

        layout.addWidget(gb_file)

        # ── 上传按钮 ──
        upload_row = QHBoxLayout()
        self._upload_btn = QPushButton("上传到 GitHub")
        self._upload_btn.setStyleSheet(
            "QPushButton{background:#2196F3;color:white;padding:10px;font-size:15px;border-radius:5px;}"
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
        preset_name = data.get("name", os.path.splitext(os.path.basename(fpath))[0])
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

        # 检查重复
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
        has_token = bool(self._token_input.text().strip())
        self._upload_btn.setEnabled(has_token and n > 0)
        self._clear_btn.setEnabled(n > 0)

    # ── 上传 ──

    def _start_upload(self):
        token = self._token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "请输入 Token")
            return
        if not self._pending_files:
            QMessageBox.information(self, "提示", "没有待上传的文件")
            return

        self._upload_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._log.clear()
        self._log.append(f"开始上传 {len(self._pending_files)} 个预设...\n")

        self._thread = UploadThread(token, list(self._pending_files))
        self._thread.log_signal.connect(self._log.append)
        self._thread.progress_signal.connect(
            lambda c, t: (self._progress.setMaximum(t), self._progress.setValue(c)))
        self._thread.done_signal.connect(self._on_done)
        self._thread.start()

    def _on_done(self, success, failed):
        self._progress.setVisible(False)
        self._update_state()
        self._log.append("\n" + "="*30 + f"\n 上传完成: 成功 {success}, 失败 {failed}")
        QMessageBox.information(self, "上传完成", f"成功: {success}\n失败: {failed}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PresetUploader()
    w.show()
    sys.exit(app.exec())
