# -*- coding: utf-8 -*-
"""Git 代理管理工具 —— 检测可用代理端口，一键配给 git。"""

import sys
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QTextEdit, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal


def scan_proxy_ports():
    """扫描本地常见代理端口，返回 (ip, port, 是否socks5) 列表。"""
    import socket
    candidates = []
    for port in [15715, 7890, 7891, 10808, 10809, 8888, 8080, 2080, 1080, 3128]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.15)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            candidates.append(port)
        s.close()
    return candidates


def test_proxy(ip, port, proto="http"):
    """测试代理是否可用。"""
    import urllib.request
    try:
        proxy_url = f"{proto}://{ip}:{port}"
        handler = urllib.request.ProxyHandler({proto: proxy_url})
        opener = urllib.request.build_opener(handler, urllib.request.ProxyHandler({}))
        req = urllib.request.Request("https://github.com")
        with opener.open(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_git_proxy():
    try:
        r = subprocess.run(["git", "config", "--global", "--get", "http.proxy"], capture_output=True, text=True, timeout=5)
        http = r.stdout.strip() if r.returncode == 0 else "\uff08\u672a\u8bbe\u7f6e\uff09"
        r = subprocess.run(["git", "config", "--global", "--get", "https.proxy"], capture_output=True, text=True, timeout=5)
        https = r.stdout.strip() if r.returncode == 0 else "\uff08\u672a\u8bbe\u7f6e\uff09"
        return http, https
    except Exception:
        return "\uff08\u8bfb\u53d6\u5931\u8d25\uff09", "\uff08\u8bfb\u53d6\u5931\u8d25\uff09"


def set_git_proxy(proxy_url):
    subprocess.run(["git", "config", "--global", "http.proxy", proxy_url], check=True)
    subprocess.run(["git", "config", "--global", "https.proxy", proxy_url], check=True)


def unset_git_proxy():
    subprocess.run(["git", "config", "--global", "--unset", "http.proxy"], capture_output=True)
    subprocess.run(["git", "config", "--global", "--unset", "https.proxy"], capture_output=True)


class _TestThread(QThread):
    """后台测试代理连通性，不阻塞 UI。"""
    result = pyqtSignal(str, str)

    def __init__(self, proto, port, proxy_url):
        super().__init__()
        self._proto = proto
        self._port = port
        self._proxy_url = proxy_url

    def run(self):
        import urllib.request
        try:
            if self._proto == "socks5":
                handler = urllib.request.ProxyHandler({})
            else:
                handler = urllib.request.ProxyHandler({"http": self._proxy_url, "https": self._proxy_url})
            opener = urllib.request.build_opener(handler)
            req = urllib.request.Request("https://github.com")
            with opener.open(req, timeout=8) as resp:
                if resp.status == 200:
                    self.result.emit("✅ 测试成功，可以访问 GitHub", "green")
                else:
                    self.result.emit(f"❌ 访问失败 (HTTP {resp.status})", "red")
        except Exception as e:
            if self._proto == "socks5" and "socks" not in str(e).lower():
                try:
                    import socket
                    socks = __import__("socks")
                    socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", self._port)
                    socket.socket = socks.socksocket
                    req = urllib.request.Request("https://github.com")
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        if resp.status == 200:
                            self.result.emit("✅ 测试成功，可以访问 GitHub", "green")
                        else:
                            self.result.emit(f"❌ 访问失败 (HTTP {resp.status})", "red")
                        return
                except Exception:
                    pass
            msg = str(e)
            if "timed out" in msg or "Connection refused" in msg:
                self.result.emit("❌ 连接超时，代理不可用", "red")
            else:
                self.result.emit(f"❌ 测试失败：{msg[:50]}", "red")


class GitProxyManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Git \u4ee3\u7406\u7ba1\u7406")
        self.setFixedSize(640, 500)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("\ud83d\udd0c Git \u4ee3\u7406\u7ba1\u7406\u5de5\u5177")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # \u72b6\u6001
        gb1 = QGroupBox("\u72b6\u6001\u4fe1\u606f")
        gb1_layout = QVBoxLayout(gb1)
        self._status_label = QLabel("\u6b63\u5728\u68c0\u6d4b...")
        self._status_label.setWordWrap(True)
        gb1_layout.addWidget(self._status_label)
        layout.addWidget(gb1)

        # \u53ef\u7528\u4ee3\u7406
        gb2 = QGroupBox("\u68c0\u6d4b\u5230\u7684\u4ee3\u7406\u7aef\u53e3")
        gb2_layout = QVBoxLayout(gb2)
        self._proxy_combo = QComboBox()
        self._proxy_combo.setMinimumHeight(30)
        gb2_layout.addWidget(self._proxy_combo)

        # \u6d4b\u8bd5
        test_row = QHBoxLayout()
        test_btn = QPushButton("\ud83d\udd0d \u6d4b\u8bd5\u8fde\u63a5")
        test_btn.setStyleSheet("QPushButton{background:#2196F3;color:white;padding:8px 16px;font-size:13px;border-radius:5px;}QPushButton:hover{background:#1976D2;}")
        test_btn.clicked.connect(self._test_proxy_selected)
        test_row.addWidget(test_btn)
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        test_row.addWidget(self._test_result, 1)
        gb2_layout.addLayout(test_row)
        layout.addWidget(gb2)
        btn_layout = QHBoxLayout()
        self._apply_btn = QPushButton("\u2705 \u5e94\u7528\u5230 Git")
        self._apply_btn.setStyleSheet("QPushButton{background:#4CAF50;color:white;padding:10px;font-size:14px;border-radius:6px;}QPushButton:hover{background:#45a049;}QPushButton:disabled{background:#ccc;}")
        self._apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._apply_btn)

        self._clear_btn = QPushButton("\u2716 \u6e05\u9664 Git \u4ee3\u7406")
        self._clear_btn.setStyleSheet("QPushButton{background:#f44336;color:white;padding:10px;font-size:14px;border-radius:6px;}QPushButton:hover{background:#d32f2f;}QPushButton:disabled{background:#ccc;}")
        self._clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self._clear_btn)
        layout.addLayout(btn_layout)

        # Git \u5f53\u524d\u8bbe\u7f6e
        gb3 = QGroupBox("Git \u5f53\u524d\u4ee3\u7406\u8bbe\u7f6e")
        gb3_layout = QVBoxLayout(gb3)
        self._git_label = QLabel("\u6b63\u5728\u68c0\u6d4b...")
        self._git_label.setWordWrap(True)
        gb3_layout.addWidget(self._git_label)
        layout.addWidget(gb3)

        # \u64cd\u4f5c\u65e5\u5fd7
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(70)
        layout.addWidget(self._log)

        QTimer.singleShot(100, self._refresh)

    def _refresh(self):
        self._status_label.setText("\u6b63\u5728\u68c0\u6d4b...")
        self._proxy_combo.clear()
        self._apply_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)
        QApplication.processEvents()
        QTimer.singleShot(50, self._do_refresh)

    def _do_refresh(self):
        # \u626b\u63cf\u7aef\u53e3
        ports = scan_proxy_ports()
        if ports:
            self._status_label.setText(f"\u2705 \u68c0\u6d4b\u5230 {len(ports)} \u4e2a\u53ef\u7528\u4ee3\u7406\u7aef\u53e3\uff0c\u5df2\u5217\u5728\u4e0b\u62c9\u83dc\u5355",)
        else:
            self._status_label.setText("\u274c \u672a\u68c0\u6d4b\u5230\u4efb\u4f55\u4ee3\u7406\u7aef\u53e3\uff0c\u8bf7\u786e\u8ba4 VPN \u5df2\u6253\u5f00")
            # \u4ecd\u8981\u663e\u793a git \u4ee3\u7406\u72b6\u6001\uff0c\u4e0d\u80fd\u63d0\u524d return
            http, https = get_git_proxy()
            self._git_label.setText(f"HTTP: {http}\nHTTPS: {https}")
            self._clear_btn.setEnabled(http != "\uff08\u672a\u8bbe\u7f6e\uff09")
            return

        self._proxy_combo.clear()
        for p in ports:
            self._proxy_combo.addItem(f"HTTP  http://127.0.0.1:{p}",    ("http",  p))
            self._proxy_combo.addItem(f"SOCKS5  socks5://127.0.0.1:{p}", ("socks5", p))

        # \u81ea\u52a8\u9009\u4e2d\u7b2c\u4e00\u4e2a
        self._proxy_combo.setCurrentIndex(0)

    def _test_proxy_selected(self):
        """\u6d4b\u8bd5\u5f53\u524d\u9009\u4e2d\u7684\u4ee3\u7406\u80fd\u5426\u8bbf\u95ee GitHub\uff08\u5f02\u6b65\uff0c\u4e0d\u5361 UI\uff09"""
        if self._proxy_combo.count() == 0:
            return
        proto, port = self._proxy_combo.currentData()
        proxy_url = f"{proto}://127.0.0.1:{port}"
        self._test_result.setText("\u6d4b\u8bd5\u4e2d...\uff08\u7f51\u7edc\u8bf7\u6c42\u4e0d\u4f1a\u5361\u754c\u9762\uff09")
        self._test_result.setStyleSheet("color: #888;")

        # \u7528 QTimer.singleShot \u6a21\u62df\u5f02\u6b65\uff0c\u4e0d\u5360\u7528\u4e3b\u7ebf\u7a0b
        from PyQt6.QtCore import QThread, pyqtSignal
        class TestThread(QThread):
            result = pyqtSignal(str, str)
            def run(self):
                import urllib.request
                try:
                    if proto == "socks5":
                        handler = urllib.request.ProxyHandler({})
                    else:
                        handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
                    opener = urllib.request.build_opener(handler)
                    req = urllib.request.Request("https://github.com")
                    with opener.open(req, timeout=8) as resp:
                        if resp.status == 200:
                            self.result.emit("\u2705 \u6d4b\u8bd5\u6210\u529f\uff0c\u53ef\u4ee5\u8bbf\u95ee GitHub", "green")
                        else:
                            self.result.emit(f"\u274c \u8bbf\u95ee\u5931\u8d25 (HTTP {resp.status})", "red")
                except Exception as e:
                    if proto == "socks5" and "socks" not in str(e).lower():
                        try:
                            import socket
                            socks = __import__("socks")
                            socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", port)
                            socket.socket = socks.socksocket
                            req = urllib.request.Request("https://github.com")
                            with urllib.request.urlopen(req, timeout=8) as resp:
                                if resp.status == 200:
                                    self.result.emit("\u2705 \u6d4b\u8bd5\u6210\u529f\uff0c\u53ef\u4ee5\u8bbf\u95ee GitHub", "green")
                                else:
                                    self.result.emit(f"\u274c \u8bbf\u95ee\u5931\u8d25 (HTTP {resp.status})", "red")
                                return
                        except Exception:
                            pass
                    msg = str(e)
                    if "timed out" in msg or "Connection refused" in msg:
                        self.result.emit("\u274c \u8fde\u63a5\u8d85\u65f6\uff0c\u4ee3\u7406\u4e0d\u53ef\u7528", "red")
                    else:
                        self.result.emit(f"\u274c \u6d4b\u8bd5\u5931\u8d25\uff1a{msg[:50]}", "red")

        self._test_thread = TestThread()
        self._test_thread.result.connect(lambda text, color: self._on_test_done(text, color))
        self._test_thread.start()

    def _on_test_done(self, text, color):
        self._test_result.setText(text)
        self._test_result.setStyleSheet(f"color: {color}; font-weight: bold;")
        self._test_thread = None

        # Git \u5f53\u524d\u8bbe\u7f6e
        http, https = get_git_proxy()
        self._git_label.setText(f"HTTP: {http}\nHTTPS: {https}")

        self._apply_btn.setEnabled(True)
        self._clear_btn.setEnabled(http != "\uff08\u672a\u8bbe\u7f6e\uff09")

    def _update_git_status(self):
        """\u4e13\u95e8\u66f4\u65b0 git \u4ee3\u7406\u72b6\u6001\u533a\uff08\u4e0d\u91cd\u7f6e\u5176\u4ed6\u5143\u7d20\uff09"""
        http, https = get_git_proxy()
        self._git_label.setText(f"HTTP: {http}\nHTTPS: {https}")
        self._clear_btn.setEnabled(http != "\uff08\u672a\u8bbe\u7f6e\uff09")
        self._apply_btn.setEnabled(self._proxy_combo.count() > 0)
        QApplication.processEvents()

    def _on_apply(self):
        if self._proxy_combo.count() == 0:
            QMessageBox.warning(self, "\u63d0\u793a", "\u6ca1\u6709\u53ef\u7528\u7684\u4ee3\u7406\u7aef\u53e3")
            return
        proto, port = self._proxy_combo.currentData()
        proxy_url = f"{proto}://127.0.0.1:{port}"
        try:
            set_git_proxy(proxy_url)
            self._log.append(f"\u2705 \u5df2\u8bbe\u7f6e Git \u4ee3\u7406 \u2192 {proxy_url}")
            self._update_git_status()
        except Exception as e:
            QMessageBox.critical(self, "\u9519\u8bef", f"\u8bbe\u7f6e\u5931\u8d25:\n{e}")

    def _on_clear(self):
        try:
            unset_git_proxy()
            self._log.append("\u2705 \u5df2\u6e05\u9664 Git \u4ee3\u7406")
            self._update_git_status()
        except Exception as e:
            QMessageBox.critical(self, "\u9519\u8bef", f"\u6e05\u9664\u5931\u8d25:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = GitProxyManager()
    w.show()
    sys.exit(app.exec())
