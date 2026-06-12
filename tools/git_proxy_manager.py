# -*- coding: utf-8 -*-
"""Git 代理管理工具 —— 查看系统代理设置，一键配给 git。"""

import sys
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer


def get_system_proxy():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\Internet Settings")
        enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        return bool(enable), server
    except Exception:
        return False, ""


def get_git_proxy():
    try:
        r = subprocess.run(["git", "config", "--global", "--get", "http.proxy"], capture_output=True, text=True, timeout=5)
        http = r.stdout.strip() if r.returncode == 0 else "(\u672a\u8bbe\u7f6e)"
        r = subprocess.run(["git", "config", "--global", "--get", "https.proxy"], capture_output=True, text=True, timeout=5)
        https = r.stdout.strip() if r.returncode == 0 else "(\u672a\u8bbe\u7f6e)"
        return http, https
    except Exception:
        return "(\u8bfb\u53d6\u5931\u8d25)", "(\u8bfb\u53d6\u5931\u8d25)"


def set_git_proxy(server):
    subprocess.run(["git", "config", "--global", "http.proxy", f"http://{server}"], check=True)
    subprocess.run(["git", "config", "--global", "https.proxy", f"http://{server}"], check=True)


def unset_git_proxy():
    subprocess.run(["git", "config", "--global", "--unset", "http.proxy"], capture_output=True)
    subprocess.run(["git", "config", "--global", "--unset", "https.proxy"], capture_output=True)


class GitProxyManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Git \u4ee3\u7406\u7ba1\u7406")
        self.setFixedSize(500, 380)
        self._system_server = ""
        layout = QVBoxLayout(self)

        title = QLabel("\ud83d\udd0c Git \u4ee3\u7406\u7ba1\u7406\u5de5\u5177")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        gb1 = QGroupBox("\u7cfb\u7edf\u4ee3\u7406\u8bbe\u7f6e")
        gb1_layout = QVBoxLayout(gb1)
        self._sys_status = QLabel("\u6b63\u5728\u68c0\u6d4b...")
        self._sys_status.setWordWrap(True)
        gb1_layout.addWidget(self._sys_status)
        layout.addWidget(gb1)

        gb2 = QGroupBox("Git \u4ee3\u7406\u8bbe\u7f6e")
        gb2_layout = QVBoxLayout(gb2)
        self._git_status = QLabel("\u6b63\u5728\u68c0\u6d4b...")
        self._git_status.setWordWrap(True)
        gb2_layout.addWidget(self._git_status)
        layout.addWidget(gb2)

        btn_layout = QHBoxLayout()
        self._apply_btn = QPushButton("\u2b07 \u5e94\u7528\u7cfb\u7edf\u4ee3\u7406\u5230 Git")
        self._apply_btn.setStyleSheet("QPushButton{background:#4CAF50;color:white;padding:10px;font-size:14px;border-radius:6px;}QPushButton:hover{background:#45a049;}QPushButton:disabled{background:#ccc;}")
        self._apply_btn.clicked.connect(self._on_apply)
        self._apply_btn.setEnabled(False)
        btn_layout.addWidget(self._apply_btn)

        self._clear_btn = QPushButton("\u2716 \u6e05\u9664 Git \u4ee3\u7406")
        self._clear_btn.setStyleSheet("QPushButton{background:#f44336;color:white;padding:10px;font-size:14px;border-radius:6px;}QPushButton:hover{background:#d32f2f;}QPushButton:disabled{background:#ccc;}")
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setEnabled(False)
        btn_layout.addWidget(self._clear_btn)
        layout.addLayout(btn_layout)

        refresh_btn = QPushButton("\ud83d\udd04 \u5237\u65b0")
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(80)
        layout.addWidget(self._log)

        QTimer.singleShot(100, self._refresh)

    def _refresh(self):
        self._sys_status.setText("\u6b63\u5728\u68c0\u6d4b...")
        self._git_status.setText("\u6b63\u5728\u68c0\u6d4b...")
        self._apply_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)
        QApplication.processEvents()
        QTimer.singleShot(50, self._do_refresh)

    def _do_refresh(self):
        enable, server = get_system_proxy()
        if enable and server:
            self._sys_status.setText(f"\u2705 \u7cfb\u7edf\u4ee3\u7406\u5df2\u542f\u7528\n   \u5730\u5740: {server}\n   \u6ce8\uff1agit \u4e0d\u4f1a\u81ea\u52a8\u4f7f\u7528\u7cfb\u7edf\u4ee3\u7406\uff0c\u9700\u8981\u624b\u52a8\u914d\u7f6e")
            self._system_server = server
            self._apply_btn.setEnabled(True)
        else:
            self._sys_status.setText("\u274c \u7cfb\u7edf\u4ee3\u7406\u672a\u542f\u7528")
            self._system_server = ""
            self._apply_btn.setEnabled(False)

        http, https = get_git_proxy()
        self._git_status.setText(f"HTTP \u4ee3\u7406: {http}\nHTTPS\u4ee3\u7406: {https}")
        self._clear_btn.setEnabled(http != "(\u672a\u8bbe\u7f6e)")

    def _on_apply(self):
        if not self._system_server:
            QMessageBox.warning(self, "\u63d0\u793a", "\u672a\u68c0\u6d4b\u5230\u7cfb\u7edf\u4ee3\u7406")
            return
        try:
            set_git_proxy(self._system_server)
            self._log.append(f"\u2705 \u5df2\u8bbe\u7f6e Git \u4ee3\u7406 \u2192 {self._system_server}")
            self._refresh()
        except Exception as e:
            QMessageBox.critical(self, "\u9519\u8bef", f"\u8bbe\u7f6e\u5931\u8d25:\n{e}")

    def _on_clear(self):
        try:
            unset_git_proxy()
            self._log.append("\u2705 \u5df2\u6e05\u9664 Git \u4ee3\u7406")
            self._refresh()
        except Exception as e:
            QMessageBox.critical(self, "\u9519\u8bef", f"\u6e05\u9664\u5931\u8d25:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = GitProxyManager()
    w.show()
    sys.exit(app.exec())
