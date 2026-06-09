# -*- coding: utf-8 -*-
# 错误处理与日志系统（从 WWDmgCalc.py 拆分）
# 所有以下划线开头的名字通过 __all__ 显式导出供主程序 import * 使用

__all__ = [
    # === 模块级变量 ===
    "_log_entries", "_new_error_count", "_on_new_error_cb", "_logger",
    "_ERROR_LOG_DIR", "_ERROR_LOG_FILE", "_MAX_PERSIST_ENTRIES",
    # === 函数 ===
    "_center_window", "_show_toast", "_set_new_error_callback",
    "_add_log_entry", "_init_logger", "_load_persist_log", "_save_persist_log",
    "_make_entry_key",
    # === 类 ===
    "ErrorDetailDialog", "ErrorReportDialog",
]

import sys
import os
import json
import logging
import logging.handlers
import hashlib
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QListWidget, QListWidgetItem, QGroupBox,
    QScrollArea, QWidget, QFrame, QApplication,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QSequentialAnimationGroup

# 项目根目录（error_system.py 在 error_handler/ 子目录下）
_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ERROR_LOG_DIR = os.path.join(_PROJ_DIR, "config")
_ERROR_LOG_FILE = os.path.join(_ERROR_LOG_DIR, "error_log.json")
_MAX_PERSIST_ENTRIES = 500

_log_entries = []  # [{time, level, summary, detail, key}, ...]  内存中的日志条目
_new_error_count = [0]  # 未读错误计数（用 list 包装：跨模块 import * 时 int 不可变会丢失更新）
_on_new_error_cb = None  # 新错误回调，由 MainScreen 设置


def _center_window(win):
    """将窗口居中到当前屏幕（延迟执行确保布局已完成）。"""
    def _do_center():
        sg = QApplication.primaryScreen().availableGeometry()
        ww = win.width() or win.sizeHint().width()
        wh = win.height() or win.sizeHint().height()
        win.move((sg.width() - ww) // 2,
                 (sg.height() - wh) // 2)
    QTimer.singleShot(0, _do_center)


def _show_toast(parent, text, duration=2000):
    """在父窗口底部中央显示一个带淡入淡出动画的悬浮提示标签。"""
    if parent is None:
        parent = QApplication.instance().activeWindow()
    if parent is None:
        return

    toast = QLabel(text, parent)
    toast.setStyleSheet(
        "QLabel { background: rgba(30,30,50,0.92); color: #e0e0e0;"
        "font-size: 13px; padding: 10px 24px; border-radius: 8px;"
        "border: 1px solid rgba(255,255,255,0.1); }"
    )
    toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
    toast.adjustSize()
    pw, ph = parent.width(), parent.height()
    toast.move((pw - toast.width()) // 2, ph - 80)
    toast.raise_()

    effect = QGraphicsOpacityEffect(toast)
    effect.setOpacity(0)
    toast.setGraphicsEffect(effect)
    toast.show()

    fade_in = QPropertyAnimation(effect, b"opacity")
    fade_in.setDuration(300)
    fade_in.setStartValue(0)
    fade_in.setEndValue(1)

    fade_out = QPropertyAnimation(effect, b"opacity")
    fade_out.setDuration(400)
    fade_out.setStartValue(1)
    fade_out.setEndValue(0)

    seq = QSequentialAnimationGroup()
    seq.addAnimation(fade_in)
    seq.addPause(duration)
    seq.addAnimation(fade_out)
    seq.finished.connect(toast.deleteLater)
    seq.start()
    toast._anim = seq


def _set_new_error_callback(cb):
    global _on_new_error_cb
    _on_new_error_cb = cb


def _make_entry_key(time_str, summary):
    """为日志条目生成简短唯一 key，用于去重。"""
    raw = f"{time_str}:{summary[:80]}"
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def _load_persist_log():
    """从 config/error_log.json 加载历史日志。"""
    global _log_entries
    try:
        if os.path.exists(_ERROR_LOG_FILE):
            with open(_ERROR_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _log_entries = data.get("entries", [])[-_MAX_PERSIST_ENTRIES:]
    except Exception:
        _log_entries = []


def _save_persist_log():
    """将当前日志持久化到 config/error_log.json。"""
    try:
        os.makedirs(_ERROR_LOG_DIR, exist_ok=True)
        with open(_ERROR_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump({"entries": _log_entries[-_MAX_PERSIST_ENTRIES:]},
                      f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass  # 磁盘写入失败不阻塞程序


def _add_log_entry(level, summary, detail=""):
    """添加一条日志到内存并持久化。返回 (is_new, entry)。"""
    global _log_entries
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    key = _make_entry_key(now, summary)
    for e in reversed(_log_entries[-10:]):
        if e["key"] == key:
            return False, e
    if not detail:
        detail = summary
        summary = summary.split("\n")[0][:120]
    entry = {"time": now, "level": level, "summary": summary,
             "detail": detail, "key": key}
    _log_entries.append(entry)
    _new_error_count[0] += 1
    _save_persist_log()
    if _on_new_error_cb:
        try:
            _on_new_error_cb()
        except Exception:
            pass
    return True, entry


def _init_logger():
    """初始化模块级 logger + 加载持久化日志。"""
    os.makedirs(_ERROR_LOG_DIR, exist_ok=True)

    logger = logging.getLogger("WWDmgCalc")
    logger.setLevel(logging.WARNING)
    if logger.handlers:
        return logger

    # 持久化 handler：每次 log 调用时同步写入 error_log.json
    class PersistHandler(logging.Handler):
        def emit(self, record):
            try:
                _add_log_entry(record.levelname, self.format(record))
            except Exception:
                pass
    ph = PersistHandler()
    ph.setLevel(logging.WARNING)
    ph.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ph)

    _load_persist_log()
    return logger


_logger = _init_logger()


class ErrorDetailDialog(QDialog):
    """单条错误详情弹窗 — 展示完整W信息、分析、评估、建议。"""

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.setWindowTitle("错误详情")
        self.setMinimumSize(550,750)   #最小宽高 拖拽下限
        self.resize(550,750)           #默认宽高 大局时的大小
        self.setWindowOpacity(0.95)    #窗口透明度
        _center_window(self)           #居中屏幕
        # ── 主题检测 ──
        is_light = False
        try:
            w = QApplication.instance().activeWindow()
            while w is not None:
                if hasattr(w, "current_theme"):
                    is_light = w.current_theme == "light"
                    break
                w = w.parent() if hasattr(w, "parent") and callable(w.parent) else None
        except Exception:
            pass
        te_bg = "#f0f4fa" if is_light else "#1a2738"
        te_fg = "#1b2035" if is_light else "#e3e5ea"

        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(12, 10, 12, 10)

        # ── 级别 + 时间 ──
        lc = ("#ff4444" if entry["level"] == "CRITICAL" else
              "#e94560" if entry["level"] == "ERROR" else "#ffb74d")
        hdr = QLabel(f'[{entry["level"]}]  {entry["time"]}')
        hdr.setStyleSheet(f"color:{lc}; font-size:11px; font-weight:700;")
        root.addWidget(hdr)

        # ── 标题 ──
        title_lbl = QLabel(entry.get("summary", ""))
        title_lbl.setWordWrap(True)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet("font-size:14px; font-weight:700;")
        root.addWidget(title_lbl)

        # ── 原始错误信息 ──
        dg = QGroupBox("原始错误信息")
        dl = QVBoxLayout(dg)
        dl.setContentsMargins(6, 4, 6, 4)
        dt = QTextEdit()
        dt.setReadOnly(True)
        dt.setPlainText(entry.get("detail", entry.get("summary", "")))
        dt.setStyleSheet(
            f"font-family:'Consolas','Courier New',monospace; font-size:12px;"
            f"background:{te_bg}; color:{te_fg};"
            f"border:1px solid {'#bfcadb' if is_light else '#263248'}; border-radius:4px;"
        )
        dl.addWidget(dt)
        root.addWidget(dg, stretch=3)

        # ── 分析与建议 ──
        ag = QGroupBox("分析与建议")
        al = QVBoxLayout(ag)
        al.setContentsMargins(6, 4, 6, 4)
        asc = QScrollArea()
        asc.setWidgetResizable(True)
        asc.setFrameShape(QFrame.Shape.NoFrame)
        aw = QWidget()
        awl = QVBoxLayout(aw)
        awl.setContentsMargins(0, 0, 0, 0)
        for p in _analyze_error(entry):
            lb = QLabel(p)
            lb.setWordWrap(True)
            lb.setStyleSheet("font-size:12px; padding:1px 0;")
            awl.addWidget(lb)
        awl.addStretch()
        asc.setWidget(aw)
        al.addWidget(asc)
        root.addWidget(ag, stretch=2)

        # ── 关闭 ──
        br = QHBoxLayout()
        br.addStretch()
        cb = QPushButton("关闭")
        cb.setObjectName("backButton")
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.clicked.connect(self.accept)
        br.addWidget(cb)
        root.addLayout(br)


def _analyze_error(entry):
    """根据错误内容生成分析、评估、建议，返回字符串列表。"""
    summary = entry.get("summary", "")
    detail = entry.get("detail", "")
    combined = (summary + " " + detail).lower()
    parts = ["【分析】"]

    if "ocr" in combined:
        if "识别失败" in combined or "未能识别" in combined:
            parts.append("• OCR 引擎未能从图片中提取有效文字。")
            parts.append("• 可能原因：图片分辨率过低、文字模糊、UI 缩放异常。")
            parts.append("• 可能原因：截图区域不包含目标面板（声骸卡片/技能描述）。")
        elif "污染" in combined or "垃圾" in combined or "无效" in combined:
            parts.append("• OCR 成功读取文字但内容包含大量 UI 噪音（污染）。")
            parts.append("• 建议使用局部截图（裁剪到目标面板）代替全屏截图。")
        elif "解析" in combined:
            parts.append("• OCR 成功读取文字但解析器未能匹配到有效数据。")
            parts.append("• 可能原因：游戏版本更新导致 UI 文字格式变化。")
        elif "name '" in combined or "not defined" in combined:
            parts.append("• OCR 模块中引用了未定义的变量或函数。")
            parts.append("• 常见原因：代码重构后遗漏的导入或全局变量。")
        else:
            parts.append("• OCR 流程中发生异常，详情见上方原始信息。")
    elif "importerror" in combined or "modulenotfound" in combined:
        parts.append("• 缺少必要的 Python 依赖包。")
        parts.append("• 请在终端执行: pip install -r requirements.txt")
    elif "filenotfound" in combined or "不存在" in combined:
        parts.append("• 程序尝试访问的文件或目录不存在。")
        parts.append("• 检查 config/ 和 save/ 目录是否完整。")
    elif "json" in combined:
        parts.append("• 存档或配置文件 JSON 格式损坏。")
        parts.append("• 建议检查对应文件或删除后重新生成。")
    elif "name '" in combined or "not defined" in combined:
        parts.append("• Python 变量/函数未定义，通常由代码重构遗漏导致。")
        parts.append("• 如果反复出现，将日志反馈给开发者。")
    elif "keyboardinterrupt" in combined:
        parts.append("• 用户手动中断程序（Ctrl+C），非错误。")
    elif "线程" in combined or "thread" in combined:
        parts.append("• 后台线程（OCR 或其他）发生异常。")
        parts.append("• 主程序可继续运行，但该线程功能已中止。")
    else:
        parts.append("• 发生未分类的运行时错误，详情见上方原始信息。")

    parts.append("")
    parts.append("【评估】")
    if entry.get("level") == "CRITICAL":
        parts.append("⛔ 致命：程序崩溃或异常退出。")
    elif entry.get("level") == "ERROR":
        parts.append("⚠ 错误：功能受阻但程序可继续运行。")
    elif "失败" in combined:
        parts.append("⚠ 功能请求未能完成（如识别/解析失败）。")
    else:
        parts.append("ℹ 警告：不影响正常使用，建议关注。")

    parts.append("")
    parts.append("【建议】")
    if "ocr" in combined:
        parts.append("• 优先使用局部截图（裁剪到目标面板）而非全屏截图。")
        parts.append("• 确保游戏 UI 缩放为 100%，截图分辨率 ≥ 1920×1080。")
        parts.append("• 如反复出现，可手动输入数据代替 OCR。")
    elif "import" in combined.lower() or "modulenotfound" in combined:
        parts.append("• 运行 pip install -r requirements.txt 安装依赖。")
    elif "json" in combined:
        parts.append("• 备份后删除损坏文件，重启程序自动重建。")
    elif "name '" in combined or "not defined" in combined:
        parts.append("• 检查对应模块的 import 语句和全局变量定义。")
        parts.append("• 通常为代码重构遗漏，反馈给开发者即可。")
    elif "线程" in combined or "thread" in combined:
        parts.append("• 重启程序可恢复该功能。")
    else:
        parts.append("• 如问题反复出现，请将上方原始信息复制后反馈给开发者。")
    return parts


class ErrorReportDialog(QDialog):
    """错误日志查看弹窗 — 摘要列表 + 查看详情按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("错误日志")
        self.setMinimumSize(680, 460)
        self.resize(720, 520)
        self.setWindowOpacity(0.97)
        _center_window(self)


        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("错误日志")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        hint = QLabel(f"共 {len(_log_entries)} 条记录（最多保留 {_MAX_PERSIST_ENTRIES} 条）。")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.setStyleSheet("QListWidget { font-size: 12px; }")
        layout.addWidget(self._list, stretch=1)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("复制全部到剪贴板")
        copy_btn.setObjectName("backButton")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_all)
        btn_row.addWidget(copy_btn)

        clear_btn = QPushButton("清除日志")
        clear_btn.setObjectName("backButton")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_logs)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("backButton")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._refresh()

    def _refresh(self):
        self._list.clear()
        if not _log_entries:
            self._list.addItem("（暂无错误记录）")
            return
        for entry in reversed(_log_entries):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            row_layout.setSpacing(8)

            level_color = (
                "#ff4444" if entry["level"] == "CRITICAL" else
                "#e94560" if entry["level"] == "ERROR" else
                "#ffb74d"
            )
            text = f'[{entry["level"]}] {entry["time"]}  {entry["summary"].split(chr(10))[0]}'
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {level_color}; font-size: 12px;")
            lbl.setWordWrap(True)
            row_layout.addWidget(lbl, stretch=1)

            view_btn = QPushButton("查看")
            view_btn.setFixedWidth(50)
            view_btn.setStyleSheet(
                "QPushButton { font-size: 11px; padding: 2px 8px; border: 1px solid #555; "
                "border-radius: 3px; background: transparent; color: #aaa; }"
                "QPushButton:hover { border-color: #e94560; color: #e94560; }"
            )
            view_btn.clicked.connect(lambda checked, e=entry: ErrorDetailDialog(e, self).exec())
            row_layout.addWidget(view_btn)

            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

    def _copy_all(self):
        texts = []
        for entry in _log_entries:
            texts.append(f'[{entry["level"]}] {entry["time"]}  {entry["summary"]}')
        QApplication.clipboard().setText("\n".join(texts))

    def _clear_logs(self):
        global _log_entries
        _log_entries.clear()
        _new_error_count[0] = 0
        _save_persist_log()
        self._refresh()
