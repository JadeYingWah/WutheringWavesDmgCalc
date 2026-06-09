# -*- coding: utf-8 -*-
"""
外部错误日志报告程序
==================
由主程序闪退时自动启动，或手动双击运行。
展示最近一条 CRITICAL 错误 + 完整错误日志列表。
"""

import sys
import os
import json

def _find_log_file():
    """定位 error_log.json：开发时在 ../config/，打包后在 ../WWDmgCalc/config/"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "config", "error_log.json")
    if os.path.exists(path):
        return path
    # 打包后 ErrorViewer.exe 与 WWDmgCalc 同级
    alt = os.path.join(os.path.dirname(base), "WWDmgCalc", "config", "error_log.json")
    if os.path.exists(alt):
        return alt
    return path  # fallback

LOG_FILE = _find_log_file()


def _load_entries():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("entries", [])


def _latest_critical():
    for e in reversed(_load_entries()):
        if e["level"] == "CRITICAL":
            return e
    return None


def _show_detail(entry):
    """显示单条错误详情。"""
    try:
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                                      QTextEdit, QHBoxLayout, QGroupBox, QScrollArea,
                                      QWidget)
        from PyQt6.QtCore import Qt

        dlg = QDialog()
        dlg.setWindowTitle("错误详情")
        dlg.setMinimumSize(480, 340)
        dlg.resize(560, 420)

        root = QVBoxLayout(dlg)
        root.setSpacing(6)
        root.setContentsMargins(12, 10, 12, 10)

        lc = "#ff4444" if entry["level"] == "CRITICAL" else ("#e94560" if entry["level"] == "ERROR" else "#ffb74d")
        hdr = QLabel(f'[{entry["level"]}]  {entry["time"]}')
        hdr.setStyleSheet(f"color:{lc}; font-size:11px; font-weight:700;")
        root.addWidget(hdr)

        first_line = entry["summary"].split("\n")[0]
        title = QLabel(first_line)
        title.setWordWrap(True)
        title.setStyleSheet("font-size:14px; font-weight:700;")
        root.addWidget(title)

        dg_box = QGroupBox("错误信息")
        dl = QVBoxLayout(dg_box)
        dl.setContentsMargins(6, 4, 6, 4)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(entry.get("detail", entry["summary"]))
        te.setStyleSheet("font-family:'Consolas',monospace; font-size:12px;")
        dl.addWidget(te)
        root.addWidget(dg_box, stretch=1)

        br = QHBoxLayout()
        br.addStretch()
        cb = QPushButton("关闭")
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.clicked.connect(dlg.accept)
        br.addWidget(cb)
        root.addLayout(br)

        dlg.exec()
    except Exception:
        pass


def _show_log_list(entries):
    """显示完整错误日志列表（和主程序 ErrorReportDialog 互通）。"""
    try:
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                                      QListWidget, QListWidgetItem, QHBoxLayout,
                                      QWidget, QApplication)
        from PyQt6.QtCore import Qt

        dlg = QDialog()
        dlg.setWindowTitle("错误日志")
        dlg.setMinimumSize(680, 460)
        dlg.resize(720, 520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        title = QLabel("错误日志")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        hint = QLabel(f"共 {len(entries)} 条记录。")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(hint)

        lst = QListWidget()
        lst.setStyleSheet("QListWidget { font-size: 12px; }")
        for entry in reversed(entries):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 2, 4, 2)
            rl.setSpacing(8)

            level_color = "#ff4444" if entry["level"] == "CRITICAL" else ("#e94560" if entry["level"] == "ERROR" else "#ffb74d")
            text = f'[{entry["level"]}] {entry["time"]}  {entry["summary"].split(chr(10))[0]}'
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {level_color}; font-size: 12px;")
            lbl.setWordWrap(True)
            rl.addWidget(lbl, stretch=1)

            view_btn = QPushButton("查看")
            view_btn.setFixedWidth(50)
            view_btn.setStyleSheet(
                "QPushButton { font-size: 11px; padding: 2px 8px; border: 1px solid #555; "
                "border-radius: 3px; background: transparent; color: #aaa; }"
                "QPushButton:hover { border-color: #e94560; color: #e94560; }"
            )
            view_btn.clicked.connect(lambda checked, e=entry: _show_detail(e))
            rl.addWidget(view_btn)

            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            lst.addItem(item)
            lst.setItemWidget(item, row)
        layout.addWidget(lst, stretch=1)

        br = QHBoxLayout()
        br.addStretch()
        cb = QPushButton("关闭")
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.clicked.connect(dlg.accept)
        br.addWidget(cb)
        layout.addLayout(br)

        dlg.exec()
    except Exception:
        pass


def main():
    # 优先 PyQt6，失败则 Tkinter 降级
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication(sys.argv)
    except Exception:
        app = None

    entries = _load_entries()
    if not entries:
        if app:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(None, "错误日志", "没有错误记录。")
        return

    # --crash 标志：由主程序闪退后启动，先弹崩溃详情提醒用户
    show_crash_first = "--crash" in sys.argv

    if show_crash_first:
        critical = _latest_critical()
        if critical:
            _show_detail(critical)       # 先展示崩溃详情
    _show_log_list(entries)              # 关闭后展示完整日志列表


if __name__ == "__main__":
    main()
