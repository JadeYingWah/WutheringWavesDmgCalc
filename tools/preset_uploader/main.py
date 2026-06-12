# -*- coding: utf-8 -*-
"""预设上传工具 - GUI 版"""

import os, sys, json, base64, urllib.request, urllib.error
from urllib.parse import quote
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QTextEdit, QLineEdit,
    QCheckBox, QProgressBar, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

OWNER = "JadeYingWah"
REPO = "WutheringWavesDmgCalc"
BRANCH = "main"
CATEGORIES = {"character":"角色","weapon":"武器","echo_set":"声骸套装","character_buff":"角色增益"}
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".upload_token")


class UploadThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    done_signal = pyqtSignal(int, int)

    def __init__(self, token, file_list):
        super().__init__()
        self.token = token
        self.file_list = file_list

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
            msg = {403:"Token权限不足", 404:"路径不存在", 422:"路径格式错误"}.get(e.code, f"HTTP {e.code}")
            self.log_signal.emit(f"  x {msg}")
            return None

    def run(self):
        try:
            self._do_upload()
        except Exception as e:
            self.log_signal.emit(f"\n  !! 上传过程异常: {e}")
            self.done_signal.emit(0, len(self.file_list))

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
        manifest = {}
        for cat in CATEGORIES:
            manifest[cat] = sorted(fname for cat2, fname, _ in self.file_list if cat2 == cat)
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


class PresetUploader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("官方预设上传工具")
        self.setFixedSize(680, 560)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("官方预设上传工具")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        gb_token = QGroupBox("GitHub Token")
        gb_token_layout = QVBoxLayout(gb_token)
        token_row = QHBoxLayout()
        self._token_input = QLineEdit()
        self._token_input.setPlaceholderText("输入 github_pat_xxx 或 ghp_xxx ...")
        self._token_input.setEchoMode(QLineEdit.EchoMode.Password)
        token_row.addWidget(self._token_input, 1)
        # 不保存 Token，每次手动输入
        cb = QCheckBox("显示")
        cb.toggled.connect(lambda c: self._token_input.setEchoMode(
            QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password))
        token_row.addWidget(cb)
        gb_token_layout.addLayout(token_row)
        layout.addWidget(gb_token)

        gb_list = QGroupBox("本地官方预设文件")
        gb_list_layout = QVBoxLayout(gb_list)
        self._file_list = QListWidget()
        gb_list_layout.addWidget(self._file_list)
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.clicked.connect(self._refresh)
        gb_list_layout.addWidget(refresh_btn)
        layout.addWidget(gb_list)

        upload_row = QHBoxLayout()
        self._upload_btn = QPushButton("上传到 GitHub")
        self._upload_btn.setStyleSheet(
            "QPushButton{background:#2196F3;color:white;padding:10px;font-size:15px;border-radius:5px;}"
            "QPushButton:disabled{background:#ccc;}")
        self._upload_btn.clicked.connect(self._start_upload)
        upload_row.addWidget(self._upload_btn)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        upload_row.addWidget(self._progress, 1)
        layout.addLayout(upload_row)

        gb_log = QGroupBox("上传日志")
        gb_log_layout = QVBoxLayout(gb_log)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        gb_log_layout.addWidget(self._log)
        layout.addWidget(gb_log)

        self._refresh()



    def _refresh(self):
        self._file_list.clear()
        base = os.path.join(ROOT, "presets", "official")
        total = 0
        if os.path.exists(base):
            for cat, label in CATEGORIES.items():
                d = os.path.join(base, cat)
                if os.path.isdir(d):
                    files = sorted(f for f in os.listdir(d) if f.endswith(".json"))
                    item = QListWidgetItem(f"  {label} ({len(files)}个)")
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    self._file_list.addItem(item)
                    for f in files:
                        self._file_list.addItem(f"      {f}")
                    total += len(files)
        self._log.setText(f"共 {total} 个预设文件\n")
        self._update_btn()

    def _update_btn(self):
        self._upload_btn.setEnabled(bool(self._token_input.text().strip()))

    def _on_token_change(self):
        self._update_btn()

    def _start_upload(self):
        token = self._token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "请输入 Token")
            return
        files = []
        base = os.path.join(ROOT, "presets", "official")
        for cat in CATEGORIES:
            d = os.path.join(base, cat)
            if os.path.isdir(d):
                for fname in sorted(os.listdir(d)):
                    if not fname.endswith(".json"):
                        continue
                    with open(os.path.join(d, fname), "r", encoding="utf-8") as f:
                        files.append((cat, fname, f.read()))
        if not files:
            QMessageBox.information(self, "提示", "没有预设文件")
            return

        self._upload_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._log.clear()
        self._log.append(f"开始上传 {len(files)} 个预设...\n")

        self._thread = UploadThread(token, files)
        self._thread.log_signal.connect(self._log.append)
        self._thread.progress_signal.connect(lambda c, t: (self._progress.setMaximum(t), self._progress.setValue(c)))
        self._thread.done_signal.connect(self._on_done)
        self._thread.start()

    def _on_done(self, success, failed):
        self._progress.setVisible(False)
        self._upload_btn.setEnabled(True)
        self._log.append("\n" + "="*30 + f"\n 上传完成: 成功 {success}, 失败 {failed}")
        QMessageBox.information(self, "上传完成", f"成功: {success}\n失败: {failed}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PresetUploader()
    w.show()
    sys.exit(app.exec())
