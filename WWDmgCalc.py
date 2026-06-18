# -*- coding: utf-8 -*-
from shared_state import HIDDEN_ITEMS, LOCKED_SUMMARY_ITEMS, HIDDEN_ECHO_IDS
#
# 鸣潮伤害计算器 (Wuthering Waves Damage Calculator)
# ====================================================
# 基于 PyQt6 的图形化伤害计算工具, 支持:
#   - 角色基础属性与武器配置
#   - 多声骸 (1c/3c/4c) 管理, 含主词条、副词条
#   - 武器谐振 / 合鸣效果 / 技能效果 (常驻+触发) 的词条录入
#   - 独立乘区自定义分组计算
#   - 按元素/技能/效应筛选, 组合所有来源数据完成伤害计算
#   - 结果列表: 保存多条计算结果, 支持锁定、批量操作
#   - 存档管理: 保存/加载/快速存档/预设存档
#   - 内置使用手册, 可自行编辑图文内容
#   - 黑夜/白天双主题切换
#
# 架构说明:
#   左侧导航树 -> 右侧 QStackedWidget 页面切换.
#   数据流: 来源页 (角色&武器, 声骸, 谐振, 合鸣, 技能)
#          -> 四个数值总结页 (基础数值, 加成乘区, 加深乘区, 暴击乘区)
#          -> 计算结果页 (筛选 + 倍率 -> 最终伤害).
#   每层变更通过回调 (_on_change_cb) 向下传播.
#
# 导入系统模块
import sys
import json
import os
import subprocess
from datetime import datetime
import re
import math
import copy

# 导入独立的计算引擎（纯数学函数，零 GUI 依赖，供主程序和测试共用）
import damage_calc

# 导入 PyQt6 GUI 所需的所有组件
from PyQt6.QtWidgets import (
    QApplication, QGraphicsOpacityEffect, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLayout, QPushButton, QStackedWidget, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox, QLineEdit,
    QListWidget, QListWidgetItem, QSizePolicy, QScrollArea,
    QTableWidget, QTabWidget, QHeaderView, QStyle, QStyleOptionComboBox, QFrame, QTableWidgetItem,
    QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QMenu, QMessageBox, QTextEdit, QToolTip
)

# 导入 Qt 核心枚举与动画支持
from PyQt6.QtCore import Qt, QEvent, QObject, QPoint, QPropertyAnimation, QEasingCurve, QTimer, QUrl, QThread, QRect, QRectF, QSize, QSequentialAnimationGroup, pyqtSignal

# 导入字体与绘图相关功能
from PyQt6.QtGui import (
    QFont, QFontMetrics, QGuiApplication, QIcon, QPainter, QPalette, QPen, QPixmap,
    QColor, QBrush, QCursor, QDesktopServices, QShortcut,
    QTextDocument, QTextCursor, QTextCharFormat,
    QImage, QPainterPath,
)

# ==================== 游戏数据常量 ====================

# 固定属性集合 —— 这些属性不参与百分比加成计算
CONSTANT_ATTRS = {"固定攻击", "固定生命", "固定防御"}

# 声骸主词条类型（按费用 cost 分组）
ECHO_MAIN_STATS = {
    4: ["暴击率", "暴击伤害", "攻击力", "治疗效果加成", "生命值", "防御力"],
    3: ["冷凝伤害加成", "热熔伤害加成", "气动伤害加成", "导电伤害加成",
        "衍射伤害加成", "湮灭伤害加成", "共鸣效率", "攻击力", "生命值", "防御力"],
    1: ["攻击力", "生命值", "防御力"],
}

# 声骸主词条默认数值（按费用 cost 分组，百分比值已是百分数形式）
ECHO_MAIN_VALUES = {
    4: {"暴击率": 22.0, "暴击伤害": 44.0, "攻击力": 33.0,
        "治疗效果加成": 26.4, "生命值": 33.0, "防御力": 41.8},
    3: {"冷凝伤害加成": 30.0, "热熔伤害加成": 30.0, "气动伤害加成": 30.0,
        "导电伤害加成": 30.0, "衍射伤害加成": 30.0, "湮灭伤害加成": 30.0,
        "共鸣效率": 32.0, "攻击力": 30.0, "生命值": 30.0, "防御力": 38.0},
    1: {"攻击力": 18.0, "生命值": 22.8, "防御力": 18.0},
}

# 每种费用声骸的固定词条（名称, 数值）
ECHO_FIXED_MAIN = {
    4: ("固定攻击", 150.0),
    3: ("固定攻击", 100.0),
    1: ("固定生命", 2280.0),
}

# 声骸副词条可选列表（每个声骸最多选 5 个）
ECHO_SUB_STATS = [
    "暴击率", "暴击伤害",
    "攻击力", "生命值", "防御力",
    "普攻伤害加成", "重击伤害加成", "共鸣技能伤害加成", "共鸣解放伤害加成",
    "共鸣效率",
    "固定生命", "固定攻击", "固定防御",
]

# 武器谐振可选属性（涵盖加成、加深、无视防御、抗性等全部词条）
WEAPON_RESONANCE_ATTRS = [
    "攻击力加成", "防御力加成", "生命值加成",
    "全属性伤害加成", "冷凝伤害加成", "热熔伤害加成", "气动伤害加成",
    "导电伤害加成", "衍射伤害加成", "湮灭伤害加成",
    "全属性伤害加深", "冷凝伤害加深", "热熔伤害加深", "气动伤害加深",
    "导电伤害加深", "衍射伤害加深", "湮灭伤害加深",
    "共鸣解放伤害加成", "共鸣技能伤害加成", "重击伤害加成", "普攻伤害加成",
    "暴击伤害加成", "暴击率加成",
    "共鸣解放伤害加深", "共鸣技能伤害加深", "重击伤害加深", "普攻伤害加深",
    "无视防御", "忽视防御", "减少防御",
    "共鸣解放无视防御", "共鸣技能无视防御",
    "重击无视防御", "普攻无视防御",
    "变奏技能无视防御", "声骸技能无视防御",
    "全属性抗性减少", "伤害加深", "伤害加成", "伤害提升",
    "冷凝抗性无视", "热熔抗性无视", "气动抗性无视",
    "导电抗性无视", "衍射抗性无视", "湮灭抗性无视",
    "冷凝抗性减少", "热熔抗性减少", "气动抗性减少",
    "导电抗性减少", "衍射抗性减少", "湮灭抗性减少",
    "治疗效果加成", "共鸣效率加成",
    "声骸技能伤害加成", "声骸技能伤害加深",
    "光噪加深", "风蚀加深", "虚湮加深", "聚爆加深", "霜渐加深", "电磁加深",
    "倍率增加", "倍率提升",

]

# 用于特定增益表格下拉框（仅倍率词条）
MULTIPLIER_ONLY_ATTRS = [a for a in WEAPON_RESONANCE_ATTRS if "倍率" in a]

# 武器附加属性类型（角色与武器页使用）
WEAPON_BONUS_TYPES = ["生命值", "攻击力", "防御力", "暴击率", "暴击伤害", "共鸣效率"]


def _place_highlight_overlay(parent, rect, style="background: #ffeb3b;"):
    """在 parent 上放置黄色叠层，两轮渐入渐出（共 2s），结束后自动删除。"""
    overlay = QWidget(parent)
    overlay.setGeometry(rect)
    overlay.setStyleSheet(style)
    overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    overlay.show()
    effect = QGraphicsOpacityEffect(overlay)
    effect.setOpacity(0.0)
    overlay.setGraphicsEffect(effect)
    TOTAL = 2000
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(TOTAL)
    anim.setEasingCurve(QEasingCurve.Type.Linear)
    def kf(ms): return ms / TOTAL
    anim.setKeyValueAt(kf(0),    0.0)
    anim.setKeyValueAt(kf(270),  0.55)
    anim.setKeyValueAt(kf(650),  0.55)
    anim.setKeyValueAt(kf(920),  0.0)
    anim.setKeyValueAt(kf(1070), 0.0)
    anim.setKeyValueAt(kf(1340), 0.55)
    anim.setKeyValueAt(kf(1720), 0.55)
    anim.setKeyValueAt(kf(2000), 0.0)
    anim.finished.connect(overlay.deleteLater)
    overlay._anim = anim
    anim.start()


def _auto_keywords(label):
    """从标题按 _ 分割生成默认关键词（名称_技能_伤害_倍率）。
    每段最多 30 字符；少于 3 段则认为格式不匹配，返回空列表。"""
    parts = [p.strip()[:30] for p in label.split("_") if p.strip()]
    if len(parts) < 3:
        return []
    return parts

# 项目根目录定位
#   _APP_DIR:    可写用户数据（存档/预设/配置）所在目录
#   _DATA_DIR:   只读资源（使用手册/错误处理）所在目录
if getattr(sys, 'frozen', False):
    # 打包后结构: 主文件夹/WWDmgCalc/WWDmgCalc.exe
    # 用户数据在主文件夹下（exe 的上两级）
    _APP_DIR = os.path.dirname(os.path.dirname(sys.executable))
    # PyInstaller 打包后只读数据在 _internal/ 目录
    _DATA_DIR = getattr(sys, '_MEIPASS', _APP_DIR)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
    _DATA_DIR = _APP_DIR

from error_handler.error_system import (
    _logger, _center_window, _show_toast, _set_new_error_callback,
    _add_log_entry, _log_entries, _new_error_count, ErrorReportDialog,
)


from theme_system import THEMES, build_stylesheet
# ==================== 存档系统常量 ====================

SAVE_DIR = os.path.join(_APP_DIR, "save")
SAVE_FILE_VERSION = 1

# ==================== 自定义导航树（带动画） ====================

class NavTree(QTreeWidget):
    """左侧导航树. 分区配色, 展开/折叠箭头, 点击切换右侧页面."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QTreeWidget.ScrollMode.ScrollPerPixel)
        self._scroll_anim = QPropertyAnimation(self.verticalScrollBar(), b"value")
        self._scroll_anim.setDuration(250)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.itemExpanded.connect(self._scroll_to_last_child)

    def _scroll_to_last_child(self, item):
        last = self._find_last_visible_descendant(item)
        if last:
            self.scrollToItem(last, self.ScrollHint.PositionAtBottom)

    def _find_last_visible_descendant(self, item):
        if item.childCount() == 0 or not item.isExpanded():
            return item
        return self._find_last_visible_descendant(item.child(item.childCount() - 1))

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        current = self.verticalScrollBar().value()
        target = max(
            self.verticalScrollBar().minimum(),
            min(self.verticalScrollBar().maximum(), current - delta)
        )
        self._scroll_anim.stop()
        self._scroll_anim.setStartValue(current)
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.start()
        event.accept()

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if item and item.childCount() > 0:
            rect = self.visualItemRect(item)
            if event.pos().x() - rect.left() < 50:
                self.setCurrentItem(item)
                item.setExpanded(not item.isExpanded())
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item and item.childCount() > 0:
            item.setExpanded(not item.isExpanded())
            return
        super().mouseDoubleClickEvent(event)

# ==================== 欢迎界面 ====================

class WelcomeScreen(QWidget):
    """欢迎启动页. 标题 + 简介 + 开始计算按钮."""
    def __init__(self, on_start):
        super().__init__()
        self.setObjectName("WelcomeScreen")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        layout.addStretch(2)

        title = QLabel("鸣潮伤害计算器")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Wuthering Waves Damage Calculator")
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(30)

        start_btn = QPushButton("开始计算")
        start_btn.setObjectName("startButton")
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.clicked.connect(on_start)
        layout.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(12)

        contrib_btn = QPushButton("🎖️ 贡献者名单")
        contrib_btn.setObjectName("contribButton")
        contrib_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        contrib_btn.clicked.connect(self._show_contributors)
        layout.addWidget(contrib_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(3)

    def _show_contributors(self):
        """弹出贡献者名单窗口"""
        try:
            import preset_manager
            from preset_manager import PresetManager
        except ImportError:
            return
        presets = PresetManager.list_presets()
        # 按作者分组：{author: [(name, category), ...]}
        author_map = {}
        for p in presets:
            if p.get("source") != "official":
                continue
            a = p.get("author", "").strip()
            if a:
                if a not in author_map:
                    author_map[a] = []
                cat_label = {"character":"角色","weapon":"武器","echo_set":"套装","character_buff":"增益"}.get(p["category"], p["category"])
                author_map[a].append(f"[{cat_label}] {p['name']}")
        if not author_map:
            QMessageBox.information(self, "贡献者名单", "暂无贡献者记录。\n欢迎你成为第一位贡献者！")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("🎖️ 贡献者名单")
        dlg.resize(456, 462)
        dlg.setMinimumSize(360, 264)
        dlg.setStyleSheet("QDialog{background:#1e1e2e;}")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        title = QLabel("感谢以下贡献者")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:16px;font-weight:bold;color:#cdd6f4;background:transparent;")
        lay.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:0;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setSpacing(10)
        for name in sorted(author_map.keys()):
            name_label = QLabel(f"✦  {name}")
            name_label.setStyleSheet("font-size:14px;font-weight:bold;color:#f5c2e7;background:transparent;padding:2px 8px;")
            inner_lay.addWidget(name_label)
            for item in author_map[name]:
                item_label = QLabel(f"     {item}")
                item_label.setWordWrap(True)
                item_label.setStyleSheet("font-size:12px;color:#a6adc8;background:transparent;padding:1px 16px;")
                inner_lay.addWidget(item_label)
        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll)
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("QPushButton{background:#45475a;color:#cdd6f4;border:0;padding:6px 20px;border-radius:4px;}QPushButton:hover{background:#585b70;}")
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        dlg.exec()

# ==================== 带搜索功能的下拉框 ====================

class SearchCombo(QComboBox):
    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMinimumWidth(160)

        self._valid_items = list(items or [])
        self._all_items = list(self._valid_items)
        self._updating = False
        self._popup_open = False
        self._arrow_hover = False
        self._arrow_rect = None

        for item in self._all_items:
            self.addItem(item)

        le = self.lineEdit()
        le.setPlaceholderText("输入搜索...")

        le.textChanged.connect(self._on_text_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_margins()

    def _update_margins(self):
        rect = self._arrow_rect_via_style()
        self.lineEdit().setTextMargins(0, 0, rect.width() + 4, 0)

    def _arrow_rect_via_style(self):
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        return self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            opt,
            QStyle.SubControl.SC_ComboBoxArrow,
            self
        )

    def _arrow_rect_abs(self):
        return self._arrow_rect_via_style()

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt6.QtGui import QPainter, QColor, QPolygon
        from PyQt6.QtCore import QPoint

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self._arrow_rect_via_style()
        self._arrow_rect = rect

        # 箭头按钮背景色与箭头色: 根据当前主题适配
        is_light = False
        try:
            w = self.window()
            if w and hasattr(w, "current_theme"):
                is_light = w.current_theme == "light"
        except Exception as e:
            _logger.debug("SearchCombo 主题检测失败: %s", e)
        if is_light:
            arrow_bg = QColor(80, 112, 232, 25 if self._arrow_hover else 12)
            arrow_color = QColor("#5c6a80")
        else:
            arrow_bg = QColor(255, 255, 255, 20 if self._arrow_hover else 12)
            arrow_color = QColor("#e6e6e6")
        p.setBrush(arrow_bg)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(rect)

        # 箭头三角形
        p.setBrush(arrow_color)
        cx = rect.center().x()
        cy = rect.center().y()
        if self._popup_open:
            # ▲ 向上三角，表示点一下可收起
            pts = [QPoint(cx - 5, cy + 3), QPoint(cx + 5, cy + 3), QPoint(cx, cy - 4)]
        else:
            # ▼ 向下三角，表示点一下可展开
            pts = [QPoint(cx - 5, cy - 3), QPoint(cx + 5, cy - 3), QPoint(cx, cy + 4)]
        p.drawPolygon(QPolygon(pts))
        p.end()

    def mousePressEvent(self, event):
        if self._arrow_rect_abs().contains(event.pos()):
            self._toggle_popup()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        old = self._arrow_hover
        self._arrow_hover = self._arrow_rect_abs().contains(event.pos())
        if old != self._arrow_hover:
            self.update()
        super().mouseMoveEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._arrow_hover:
            self._arrow_hover = False
            self.update()
        super().leaveEvent(event)

    def _toggle_popup(self):
        if self._popup_open:
            self.hidePopup()
        else:
            self._updating = True
            self.clear()
            self.addItems(self._all_items)
            self.lineEdit().clear()
            self._updating = False
            self.showPopup()

    def _on_text_changed(self, text):
        if self._updating:
            return
        self._updating = True
        current = text.strip()
        popup_visible = self.view().isVisible()
        self.clear()
        if current and current not in self._all_items:
            filtered = [i for i in self._all_items if current.lower() in i.lower()]
            self.addItems(filtered if filtered else self._all_items)
        elif current and current in self._all_items:
            pass  # 已是完整词条名，不重置列表（否则补全触发二次 textChanged 会把全部词条加回来）
        else:
            self.addItems(self._all_items)
        self.lineEdit().setText(current)
        if popup_visible and self.count() > 0:
            self.showPopup()
        self._updating = False

    def showPopup(self):
        self._updating = True
        self.clear()
        self.addItems(self._all_items)
        self._updating = False
        self._popup_open = True
        self.update()
        super().showPopup()

    def hidePopup(self):
        super().hidePopup()
        self._popup_open = False
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return

        popup_open = self.view().isVisible()
        if popup_open:
            self._updating = True
            self.clear()
            self.addItems(self._all_items)
            self._updating = False
            super().wheelEvent(event)
            return

        text = self.currentText().strip()
        if not self._valid_items:
            return
        if text in self._valid_items:
            idx = self._valid_items.index(text)
        else:
            idx = -1
        if delta > 0:
            idx = (idx + 1) % len(self._valid_items)
        else:
            idx = (idx - 1) % len(self._valid_items)
        self.lineEdit().setText(self._valid_items[idx])

    def currentText(self):
        return self.lineEdit().text().strip()

    def isValidSelection(self):
        return self.lineEdit().text().strip() in self._valid_items

    def update_items(self, new_items):
        self._valid_items = list(new_items)
        self._all_items = list(new_items)
        self._updating = True
        self.clear()
        self.addItems(self._all_items)
        self._updating = False

# ==================== 属性列表项（可编辑、锁定、删除） ====================

class AttrListItem(QWidget):
    """属性列表单项组件. 名称可编辑, 数值可调, 支持锁定/删除."""
    def __init__(self, name, value, parent=None):
        super().__init__(parent)
        self.name = name
        self.locked = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(0)

        self.name_edit = QLineEdit(name)
        self.name_edit.setObjectName("nameEdit")
        self.name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.name_edit.textChanged.connect(self._on_name_changed)

        fm = QFontMetrics(self.name_edit.font())
        w = fm.horizontalAdvance(name) + 40
        self.name_edit.setFixedWidth(max(100, w))

        name_space = QWidget()
        name_space_layout = QHBoxLayout(name_space)
        name_space_layout.setContentsMargins(0, 0, 0, 0)
        name_space_layout.addWidget(self.name_edit)
        name_space_layout.addStretch()
        layout.addWidget(name_space, stretch=1)

        self.value_spin = QDoubleSpinBox()
        self.value_spin.setObjectName("itemValueSpin")
        self.value_spin.setRange(0, 9999)
        self.value_spin.setDecimals(4)
        self.value_spin.setFixedWidth(90)
        self.value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_spin.setValue(value)
        layout.addWidget(self.value_spin)

        unit_text = "常数" if name in CONSTANT_ATTRS else "百分比"
        self.unit_label = QLabel(unit_text)
        self.unit_label.setObjectName("unitLabel")
        self.unit_label.setFixedWidth(50)
        self.unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.unit_label)

        ops_widget = QWidget()
        ops_layout = QHBoxLayout(ops_widget)
        ops_layout.setContentsMargins(0, 0, 0, 0)
        ops_layout.setSpacing(6)

        self.lock_btn = QPushButton("锁定")
        self.lock_btn.setObjectName("itemLockBtn")
        self.lock_btn.setFixedSize(50, 28)
        self.lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_btn.clicked.connect(self._toggle_lock)
        ops_layout.addWidget(self.lock_btn)

        self.view_summary_btn = QPushButton("查看总结")
        self.view_summary_btn.setObjectName("itemLockBtn")
        self.view_summary_btn.setFixedSize(58, 28)
        self.view_summary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_summary_btn.clicked.connect(self._on_view_summary)
        ops_layout.addWidget(self.view_summary_btn)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setObjectName("itemDeleteBtn")
        self.delete_btn.setFixedSize(50, 28)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self._request_delete)
        ops_layout.addWidget(self.delete_btn)

        layout.addWidget(ops_widget)

        self._delete_callback = None
        self._view_summary_callback = None

    def _on_name_changed(self, text):
        fm = QFontMetrics(self.name_edit.font())
        w = fm.horizontalAdvance(text) + 40
        self.name_edit.setFixedWidth(max(100, w))

    def _toggle_lock(self):
        self.locked = not self.locked
        self.lock_btn.setText("解锁" if self.locked else "锁定")
        self.delete_btn.setEnabled(not self.locked)
        self.value_spin.setEnabled(not self.locked)
        self.name_edit.setReadOnly(self.locked)

    def set_delete_callback(self, callback):
        self._delete_callback = callback

    def set_view_summary_callback(self, callback):
        self._view_summary_callback = callback

    def _on_view_summary(self):
        if self._view_summary_callback:
            self._view_summary_callback(self.name_edit.text().strip())

    def _request_delete(self):
        if not self.locked and self._delete_callback:
            self._delete_callback(self)

# ==================== 通用表格属性页（基类） ====================

class BaseTableAttrPage(QWidget):
    """通用的基于表格的属性添加页面基类（支持锁定/删除）"""
    def __init__(self, title_text, desc_text="搜索选择属性后点击添加", attr_list=None):
        super().__init__()
        self._counter = 0
        self._rows = []          # 存储每行的数据字典
        self._attr_list = attr_list or WEAPON_RESONANCE_ATTRS
        self._on_change_cb = None  # 变更回调，通知外部

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel(title_text)
        title.setObjectName("sectionTitle")
        self._title_label = title
        layout.addWidget(title)

        self._desc_label = QLabel(desc_text)
        self._desc_label.setObjectName("labelSecondary")
        self._desc_label.setWordWrap(True)
        layout.addWidget(self._desc_label)

        # 输入行
        input_row = QHBoxLayout()
        self.combo = SearchCombo(self._attr_list)
        self.combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo.currentTextChanged.connect(self._on_combo_changed)
        self.combo.lineEdit().returnPressed.connect(self._on_combo_return)
        input_row.addWidget(self.combo, stretch=3)

        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(0, 9999)
        self.value_spin.setDecimals(4)
        self.value_spin.setFixedWidth(120)
        self.value_spin.installEventFilter(self)
        input_row.addWidget(self.value_spin)

        self.input_unit_label = QLabel("百分比")
        self.input_unit_label.setObjectName("unitLabel")
        self.input_unit_label.setFixedWidth(60)
        input_row.addWidget(self.input_unit_label)

        self._add_btn = QPushButton("添加")
        self._add_btn.setObjectName("addButton")
        self._add_btn.setFixedWidth(50)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.clicked.connect(self._add)
        input_row.addWidget(self._add_btn)

        self._input_row_widget = QWidget()
        self._input_row_widget.setLayout(input_row)
        layout.addWidget(self._input_row_widget)

        # 表格
        self.table = QTableWidget()
        self.table.setObjectName("attrTable")
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["名称", "序列号", "数值", "取值", "操作"])
        self.table.verticalHeader().setVisible(False)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        hdr = self.table.horizontalHeader()
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 5):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(1, 70)
        hdr.resizeSection(2, 190)
        hdr.resizeSection(3, 85)
        hdr.resizeSection(4, 90)

        layout.addWidget(self.table, stretch=1)

    def _on_combo_changed(self, text):
        self.input_unit_label.setText("常数" if text in CONSTANT_ATTRS else "百分比")

    def eventFilter(self, obj, event):
        if obj == self.value_spin and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._add()
                return True
        return super().eventFilter(obj, event)

    def _on_combo_return(self):
        """回车快捷键：如果当前文字不在词条列表中，先补全不添加"""
        if not self.combo.isValidSelection():
            self.combo.lineEdit().end(False)
        else:
            self._add()

    def _add(self):
        name = self.combo.currentText().strip()
        if not name or not self.combo.isValidSelection():
            return
        value = self.value_spin.value()
        self._counter += 1
        self._add_row(name, value, self._counter)
        if self._on_change_cb:
            self._on_change_cb()
        self.combo.lineEdit().clear()
        self.input_unit_label.setText("百分比")

    def _add_row(self, name, value, seq_num):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, 42)

        name_edit = QLineEdit(name)
        name_edit.setReadOnly(True)
        name_edit.setObjectName("nameEdit")
        name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 0, name_edit)

        type_label = "常驻" if self.page_key == "combined_perm" else "触发"
        seq_label = QLabel(f"{type_label}{seq_num}")
        seq_label.setObjectName("seqLabel")
        seq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 1, seq_label)

        value_spin = QDoubleSpinBox()
        value_spin.setObjectName("itemValueSpin")
        value_spin.setRange(0, 9999)
        value_spin.setFixedWidth(180)
        value_spin.setDecimals(4)
        value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_spin.setValue(value)
        value_spin.valueChanged.connect(self._on_item_value_changed)
        self.table.setCellWidget(row, 2, value_spin)

        unit_text = "常数" if name in CONSTANT_ATTRS else "百分比"
        unit_label = QLabel(unit_text)
        unit_label.setObjectName("unitLabel")
        unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 3, unit_label)

        row_data = {
            'name_edit': name_edit,
            'seq_label': seq_label,
            'value_spin': value_spin,
            'unit_label': unit_label,
            'locked': False,
        }

        ops_widget = QWidget()
        ops_layout = QHBoxLayout(ops_widget)
        ops_layout.setContentsMargins(0, 0, 0, 0)
        ops_layout.setSpacing(6)

        lock_btn = QPushButton("锁定")
        lock_btn.setObjectName("itemLockBtn")
        lock_btn.setFixedSize(48, 28)
        lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        lock_btn.clicked.connect(lambda _, rd=row_data: self._toggle_lock(rd))
        ops_layout.addWidget(lock_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("itemDeleteBtn")
        delete_btn.setFixedSize(48, 28)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(lambda _, rd=row_data: self._delete_row(rd))
        ops_layout.addWidget(delete_btn)

        self.table.setCellWidget(row, 4, ops_widget)

        row_data['lock_btn'] = lock_btn
        row_data['delete_btn'] = delete_btn
        self._rows.append(row_data)

    def _toggle_lock(self, rd):
        rd['locked'] = not rd['locked']
        rd['lock_btn'].setText("解锁" if rd['locked'] else "锁定")
        rd['delete_btn'].setEnabled(not rd['locked'])
        rd['value_spin'].setEnabled(not rd['locked'])
        rd['name_edit'].setReadOnly(rd['locked'])

    def _delete_row(self, rd):
        if rd['locked']:
            return
        try:
            idx = self._rows.index(rd)
        except ValueError:
            return
        self._rows.pop(idx)
        self.table.removeRow(idx)
        self._resequence()
        if self._on_change_cb:
            self._on_change_cb()

    def _on_item_value_changed(self, *_):
        if self._on_change_cb:
            self._on_change_cb()

    def _resequence(self):
        for i, rd in enumerate(self._rows):
            tp = "常驻" if self.page_key == "combined_perm" else "触发"
            rd['seq_label'].setText(f"{tp}{i + 1}")
        self._counter = len(self._rows)  # 同步计数器：预设/删除后编号不留缺口

    def collect_data(self):
        return [(rd['name_edit'].text(), rd['value_spin'].value(), rd['locked']) for rd in self._rows]

# ==================== 综合填写页 ====================

class CombinedEntryPage(BaseTableAttrPage):
    """综合填写页 —— 在一个页面中统一添加属性，并通过「来源」下拉框
    自动分发到对应的子页面（武器谐振/合鸣效果/技能效果/角色效果/其他效果/共鸣链效果/首位声骸效果）。

    表格列: 名称 | 副名称 | 序列号 | 数值 | 取值 | 来源 | 操作
    输入行: SearchCombo(属性名) + QDoubleSpinBox(数值) + QLabel(单位) + QComboBox(来源) + 添加按钮
    """
    SOURCES = ["武器谐振", "合鸣效果", "技能效果", "角色效果", "其他效果", "共鸣链效果", "关联效果", "首位声骸效果"]

    def _resequence(self):
        super()._resequence()
        fix_table_height(self.table)

    def __init__(self, title_text, desc_text="搜索选择属性后点击添加\n请选择词条来源（武器谐振/合鸣效果/技能效果/角色效果/其他效果/共鸣链效果/首位声骸效果）"):
        super().__init__(title_text, desc_text)
        self.page_key = ""  # 由 MainScreen 设置为 "combined_perm" 或 "combined_trigger"

        # —— 重新配置表格为 7 列 ——
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(1, 210)   # 副名称（加宽30px）
        hdr.resizeSection(2, 80)   # 序列号
        hdr.resizeSection(3, 180)  # 数值
        hdr.resizeSection(4, 80)   # 取值
        hdr.resizeSection(5, 85)   # 来源
        hdr.resizeSection(6, 60)   # 操作（收窄30%）

        # —— 在输入行中添加来源选择（SearchCombo 右侧自带 ▼/▲ 展开/收起箭头） ——
        self.source_combo = SearchCombo(self.SOURCES)
        self.source_combo.setMinimumWidth(100)
        self.source_combo.setCurrentIndex(0)

        # 找到输入行布局，在单位 label 和添加按钮之间插入来源选择
        input_layout = self._input_row_widget.layout()
        # 输入行改为: [combo(属性)] [value_spin] [unit_label] [source_combo] [add_btn]
        input_layout.insertWidget(3, self.source_combo)

        # 表格高度自适应行数
        self.table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)

    def _add(self):
        """重写添加逻辑：验证输入后将数据写入综合表。"""
        name = self.combo.currentText().strip()
        if not name or not self.combo.isValidSelection():
            return
        value = self.value_spin.value()
        source = self.source_combo.currentText()
        self._counter += 1
        self._add_row_with_source(name, value, self._counter, source)
        fix_table_height(self.table)
        self.table.updateGeometry()
        self.updateGeometry()
        self.combo.lineEdit().clear()
        self.input_unit_label.setText("百分比")
        if self._on_change_cb:
            self._on_change_cb()

    def _add_row_with_source(self, name, value, seq_num, source, chain_num=None):
        """与父类 _add_row 类似，但多一列「来源」。chain_num 用于共鸣链关闭时精确移除。"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, 42)

        name_edit = QLineEdit(name)
        name_edit.setObjectName("nameEdit")
        name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 0, name_edit)

        # 副名称（用户自定义备注，如"守岸人延奏buff"）
        sub_name_edit = QLineEdit()
        sub_name_edit.setObjectName("subNameEdit")
        sub_name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_name_edit.setReadOnly(True)
        sub_name_edit.setPlaceholderText("（备注）")
        sub_name_edit.editingFinished.connect(self._on_item_value_changed)
        self.table.setCellWidget(row, 1, _make_sub_name_cell(sub_name_edit, lambda: name))

        type_label = "常驻" if self.page_key == "combined_perm" else "触发"
        seq_label = QLabel(f"{type_label}{seq_num}")
        seq_label.setObjectName("seqLabel")
        seq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 2, seq_label)

        value_spin = QDoubleSpinBox()
        value_spin.setObjectName("itemValueSpin")
        value_spin.setRange(0, 9999)
        value_spin.setFixedWidth(180)
        value_spin.setDecimals(4)
        value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_spin.setValue(value)
        value_spin.valueChanged.connect(self._on_item_value_changed)
        self.table.setCellWidget(row, 3, value_spin)

        unit_text = "常数" if name in CONSTANT_ATTRS else "百分比"
        unit_label = QLabel(unit_text)
        unit_label.setObjectName("unitLabel")
        unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 4, unit_label)

        # 来源列
        source_label = QLabel(source)
        source_label.setObjectName("seqLabel")
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 5, source_label)

        row_data = {
            'name_edit': name_edit,
            'sub_name_edit': sub_name_edit,
            'seq_label': seq_label,
            'value_spin': value_spin,
            'unit_label': unit_label,
            'source': source,
            'source_label': source_label,
            'locked': False,
            'chain_num': chain_num,
        }
        ops_widget = QWidget()
        ops_layout = QHBoxLayout(ops_widget)
        ops_layout.setContentsMargins(2, 0, 2, 0)
        ops_layout.setSpacing(3)

        # 查看总结按钮（跳转到对应数值总结页面并高亮）
        view_btn = QPushButton("查看总结")
        view_btn.setObjectName("itemLockBtn")
        view_btn.setFixedSize(60, 28)
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.clicked.connect(
            lambda _, n=name, s=source, nk=self.page_key, rd=row_data:
            self._navigate_to_summary(n, s, nk, rd['seq_label'].text()))
        ops_layout.addWidget(view_btn)

        # 删除按钮
        del_btn = QPushButton("删除")
        del_btn.setObjectName("itemDeleteBtn")
        del_btn.setFixedSize(48, 28)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(
            lambda _, n=name, s=source, rd=row_data:
            self._delete_combined_row(n, s, rd, rd['seq_label'].text()))
        ops_layout.addWidget(del_btn)

        self.table.setCellWidget(row, 6, ops_widget)

        row_data['delete_btn'] = del_btn
        self._rows.append(row_data)


    def _delete_combined_row(self, name, source, rd, seq_num=0):
        """删除行，同时清除隐藏和锁定状态。"""
        type_label = "常驻" if self.page_key == "combined_perm" else "触发"
        actual_seq = seq_num
        for ri, rdx in enumerate(self._rows):
            if rdx is rd:
                actual_seq = ri + 1
                break
        key = (name, self.page_key, f"{type_label}{actual_seq}")
        HIDDEN_ITEMS.discard(key)
        LOCKED_SUMMARY_ITEMS.discard(key)
        rd['locked'] = False
        self._delete_row(rd)

    def remove_effects_by_source_and_names(self, source, names, chain_num=None):
        """移除指定来源且名称匹配的所有行（用于共鸣链关闭时清理）。
        chain_num 用于精确匹配特定共鸣链的行。names 为空时移除该 chain_num 的所有行。"""
        rows_to_remove = []
        for i, rd in enumerate(self._rows):
            if rd.get('source') != source:
                continue
            if chain_num is not None and rd.get('chain_num') != chain_num:
                continue
            if names and rd['name_edit'].text().strip() not in names:
                continue
            rows_to_remove.append(i)
        for i in reversed(rows_to_remove):
            rd = self._rows[i]
            name = rd['name_edit'].text().strip()
            seq_label = rd['seq_label']
            seq_num = int(seq_label.text()) if seq_label and hasattr(seq_label, 'text') and seq_label.text().isdigit() else 0
            self._delete_combined_row(name, source, rd, seq_num)
        return len(rows_to_remove)

    def _highlight_row(self, row, scroll=None):
        """在指定表格行上平滑滚动到靠近顶部，再放置黄色叠层"""
        idx = self.table.model().index(row, 0)
        # 找外层 QScrollArea（可从外部传入以跳过查找）
        if scroll is None:
            p = self.table.parent()
            while p:
                if isinstance(p, QScrollArea):
                    scroll = p; break
                p = p.parent()
        if scroll:
            QApplication.processEvents()
            # 计算目标行在 scroll 内容中的 Y 坐标
            row_y = sum(self.table.rowHeight(i) for i in range(row))
            hdr_h = self.table.horizontalHeader().height() if self.table.horizontalHeader().isVisible() else 0
            table_origin = self.table.mapTo(scroll.widget(), QPoint(0, 0))
            target_y = table_origin.y() + hdr_h + row_y
            vp_h = scroll.viewport().height()
            desired = max(0, target_y - vp_h // 5)
            sb = scroll.verticalScrollBar()
            old_pos = sb.value()
            if abs(desired - old_pos) < 2:
                QTimer.singleShot(80, lambda: self._show_row_highlight(self.table, row))
                return
            anim = QPropertyAnimation(sb, b"value")
            anim.setDuration(450)
            anim.setStartValue(old_pos)
            anim.setEndValue(min(desired, sb.maximum()))
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            anim.finished.connect(lambda tb=self.table, r=row:
                QTimer.singleShot(80, lambda:
                    self._show_row_highlight(tb, r)))
            scroll._scroll_anim = anim
            anim.start()
        else:
            self.table.scrollTo(idx)
            QTimer.singleShot(200, lambda: self._show_row_highlight(self.table, row))

    def _show_row_highlight(self, table, row):
        QApplication.processEvents()
        idx = table.model().index(row, 0)
        rect = table.visualRect(idx)
        rect.setWidth(table.viewport().width())
        _place_highlight_overlay(table.viewport(), rect)

    def _navigate_to_summary(self, name, source, nav_key, seq_label=""):
        """跳转到对应的总结/减伤页面并高亮当前词条。"""
        summary_key = "summary_base"
        if any(kw in name for kw in CRIT_DMG_KEYWORDS) or any(kw in name for kw in CRIT_RATE_KEYWORDS):
            summary_key = "summary_crit"
        elif DEEPEN_SUFFIX in name:
            summary_key = "summary_deepen"
        elif any(s in name for s in BONUS_SUFFIX):
            summary_key = "summary_bonus"
        elif damage_calc.is_defense_item(name):
            summary_key = "enemy_defense"
        elif damage_calc.is_resistance_item(name):
            summary_key = "enemy_resistance"

        navigate_fn = getattr(self, '_navigate_summary', None)
        summary_pages = getattr(self, '_summary_pages', {})
        target_page = summary_pages.get(summary_key)

        if navigate_fn:
            navigate_fn(summary_key)
            if target_page:
                # 防御/抗性页面用序列号匹配，总结页面用名称匹配
                # 总结页用真实名称做二次验证（seq_label 在 highlight_item 列 2 匹配后还需名称列一致）
                QTimer.singleShot(200, lambda n=name, s=source, nk=nav_key, sq=seq_label:
                                  target_page.highlight_item(n, s, nk, sq)
                                  if hasattr(target_page, 'highlight_item') else None)

    def collect_data(self):
        """返回 6 元组 (name,val,locked,source,seq,sub)，seq 已带 常驻N/触发N 前缀"""
        prefix = "常驻" if self.page_key == "combined_perm" else "触发"
        return [(rd['name_edit'].text(), rd['value_spin'].value(),
                 rd['locked'], rd.get('source', ''), f"{prefix}{i + 1}",
                 rd.get('sub_name_edit', QLineEdit()).text()) for i, rd in enumerate(self._rows)]


# ==================== 关键词关联页面 ====================

class KeywordAssociationPage(QWidget):
    """关键词关联页面 —— 管理共鸣链效果的关键词关联

    表格列: 名称 | 副名称 | 序列号 | 数值 | 取值 | 来源 | 关键词关联 | 操作
    """

    def __init__(self):
        super().__init__()
        self._counter = 0          # 手动添加计数器
        self._chain_counter = 0    # 共鸣链添加计数器
        self._rows = []
        self._on_change_cb = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("关键词关联")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        desc = QLabel("管理共鸣链效果的关键词关联，用于计算时筛选特定卡片")
        desc.setObjectName("labelSecondary")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 输入行
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        kw_attr_list = MULTIPLIER_ONLY_ATTRS
        self._name_combo = SearchCombo(kw_attr_list)
        self._name_combo.lineEdit().setPlaceholderText("输入搜索...")
        input_row.addWidget(self._name_combo, stretch=3)

        self._value_spin = QDoubleSpinBox()
        self._value_spin.setRange(0, 9999)
        self._value_spin.setDecimals(4)
        self._value_spin.setFixedWidth(100)
        input_row.addWidget(self._value_spin)

        input_row.addWidget(QLabel("%"))

        self._type_combo = QComboBox()
        self._type_combo.addItems(EFFECT_TYPES)
        self._type_combo.setFixedWidth(60)
        input_row.addWidget(self._type_combo)

        self._source_combo = SearchCombo(CombinedEntryPage.SOURCES)
        self._source_combo.setMinimumWidth(100)
        self._source_combo.setCurrentIndex(6)  # 默认"关联效果"
        input_row.addWidget(self._source_combo)

        add_btn = QPushButton("添加")
        add_btn.setObjectName("addButton")
        add_btn.setFixedWidth(50)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_row)
        input_row.addWidget(add_btn)

        layout.addLayout(input_row)

        self._name_combo.lineEdit().returnPressed.connect(self._add_row)

        # 表格
        self._table = QTableWidget()
        self._table.setObjectName("attrTable")
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels(
            ["名称", "副名称", "序列号", "数值", "取值", "来源", "关键词关联", "操作"])
        self._table.verticalHeader().setVisible(False)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # 名称弹性填充
        for i in range(1, 8):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(1, 180)   # 副名称（+50）
        hdr.resizeSection(2, 140)   # 序列号（+30）
        hdr.resizeSection(3, 180)   # 数值（+30）
        hdr.resizeSection(4, 80)    # 取值（+10）
        hdr.resizeSection(5, 100)   # 来源（+10）
        hdr.resizeSection(6, 140)   # 关键词关联（+20）
        hdr.resizeSection(7, 90)    # 操作（+10）

        layout.addWidget(self._table, stretch=1)

    def _add_row(self):
        name = self._name_combo.currentText().strip()
        if not name:
            return

        value = self._value_spin.value()
        eff_type = self._type_combo.currentText()
        source = self._source_combo.currentText()

        self._counter += 1
        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)
        self._table.setRowHeight(row_idx, 50)

        # 名称
        name_edit = QLineEdit(name)
        name_edit.setObjectName("nameEdit")
        name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 0, name_edit)

        # 副名称
        sub_name_edit = QLineEdit()
        sub_name_edit.setObjectName("nameEdit")
        sub_name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_name_edit.setReadOnly(True)
        sub_name_edit.setPlaceholderText("（备注）")
        self._table.setCellWidget(row_idx, 1, _make_sub_name_cell(sub_name_edit, lambda: name))

        # 序列号
        seq_label = QLabel(f"关联{self._counter}")
        seq_label.setObjectName("seqLabel")
        seq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 2, seq_label)

        # 数值
        value_spin = QDoubleSpinBox()
        value_spin.setObjectName("itemValueSpin")
        value_spin.setRange(0, 9999)
        value_spin.setDecimals(4)
        value_spin.setValue(value)
        value_spin.valueChanged.connect(lambda cb=self._on_change_cb: cb and cb())
        value_spin.setFixedWidth(100)
        value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 3, value_spin)

        # 取值
        unit_label = QLabel("百分比")
        unit_label.setObjectName("unitLabel")
        unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 4, unit_label)

        # 来源
        source_label = QLabel(source)
        source_label.setObjectName("seqLabel")
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 5, source_label)

        # 关键词关联（按钮，点击编辑）
        kw_btn = QPushButton("点击编辑")
        kw_btn.setObjectName("itemLockBtn")
        kw_btn.setFixedSize(110, 35)
        kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        kw_btn.clicked.connect(lambda _, b=kw_btn: self._edit_keywords_for_btn(b))
        self._table.setCellWidget(row_idx, 6, kw_btn)

        # 操作（删除）
        ops = QWidget()
        ops_layout = QHBoxLayout(ops)
        ops_layout.setContentsMargins(2, 0, 2, 0)
        ops_layout.setSpacing(3)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("itemDeleteBtn")
        del_btn.setFixedSize(55, 28)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self._remove_row(row_idx))
        ops_layout.addWidget(del_btn)

        self._table.setCellWidget(row_idx, 7, ops)

        self._name_combo.lineEdit().clear()
        self._value_spin.setValue(0)

        if self._on_change_cb:
            self._on_change_cb()

    def _remove_row(self, row_idx):
        # 动态查找行：闭包捕获的 row_idx 可能因中间删行而失效
        sender = self.sender()
        if sender:
            for r in range(self._table.rowCount()):
                ops = self._table.cellWidget(r, 7)
                if ops and sender in ops.findChildren(QPushButton):
                    row_idx = r
                    break
        if 0 <= row_idx < self._table.rowCount():
            self._table.removeRow(row_idx)
            if self._on_change_cb:
                self._on_change_cb()

    def _edit_keywords_for_btn(self, btn):
        """通过按钮对象查找所在行，避免 removeRow 后 row_idx 失效。"""
        for row in range(self._table.rowCount()):
            if self._table.cellWidget(row, 6) is btn:
                self._edit_keywords(row)
                return

    def _edit_keywords(self, row_idx):
        """编辑关键词关联"""
        kw_btn = self._table.cellWidget(row_idx, 6)
        if not kw_btn:
            return
        current_kw = kw_btn.text() if kw_btn.text() != "点击编辑" else ""
        current_list = [k.strip() for k in current_kw.split(",") if k.strip()] if current_kw else []

        dlg = QDialog(self)
        dlg.setWindowTitle("编辑关键词")
        dlg.setMinimumSize(400, 350)
        dlg.resize(450, 400)

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(12, 12, 12, 12)

        kw_title = QLabel("关键词关联")
        kw_title.setObjectName("sectionTitle")
        dlg_layout.addWidget(kw_title)

        kw_desc = QLabel("输入关键词后点击添加，留空则增益全部卡片")
        kw_desc.setObjectName("labelSecondary")
        kw_desc.setWordWrap(True)
        dlg_layout.addWidget(kw_desc)

        input_row = QHBoxLayout()
        kw_input = QLineEdit()
        kw_input.setPlaceholderText("输入关键词...")
        kw_input.setObjectName("nameEdit")
        input_row.addWidget(kw_input, stretch=1)

        add_kw_btn = QPushButton("添加")
        add_kw_btn.setObjectName("addButton")
        add_kw_btn.setFixedWidth(50)
        add_kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        input_row.addWidget(add_kw_btn)
        dlg_layout.addLayout(input_row)

        kw_list = QListWidget()
        kw_list.setObjectName("attrList")
        for kw in current_list:
            kw_list.addItem(kw)
        dlg_layout.addWidget(kw_list, stretch=1)

        del_kw_btn = QPushButton("删除选中")
        del_kw_btn.setObjectName("itemDeleteBtn")
        del_kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dlg_layout.addWidget(del_kw_btn)

        def add_keyword():
            text = kw_input.text().strip()
            if text and text not in [kw_list.item(i).text() for i in range(kw_list.count())]:
                kw_list.addItem(text)
                kw_input.clear()

        add_kw_btn.clicked.connect(add_keyword)
        kw_input.returnPressed.connect(add_keyword)

        def del_keyword():
            for item in reversed(kw_list.selectedItems()):
                kw_list.takeItem(kw_list.row(item))

        del_kw_btn.clicked.connect(del_keyword)

        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("backButton")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(dlg.reject)
        bottom.addWidget(cancel_btn)
        ok_btn = QPushButton("确认")
        ok_btn.setFixedSize(80, 32)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(lambda: self._confirm_keywords(dlg, kw_btn, kw_list))
        bottom.addWidget(ok_btn)
        dlg_layout.addLayout(bottom)

        dlg.exec()

    def _confirm_keywords(self, dlg, kw_btn, kw_list):
        keywords = [kw_list.item(i).text() for i in range(kw_list.count())]
        kw_btn.setText(", ".join(keywords) if keywords else "点击编辑")
        dlg.accept()
        if self._on_change_cb:
            self._on_change_cb()

    def add_effect(self, name, value, eff_type, source, sub_name="", keywords="", chain_prefix=""):
        """从外部添加效果（如共鸣链弹窗保存时调用）"""
        # 根据来源使用不同计数器
        if chain_prefix:
            self._chain_counter += 1
            seq_text = f"{chain_prefix}关联{self._chain_counter}"
        else:
            self._counter += 1
            seq_text = f"关联{self._counter}"

        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)
        self._table.setRowHeight(row_idx, 50)

        name_edit = QLineEdit(name)
        name_edit.setObjectName("nameEdit")
        name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 0, name_edit)

        sub_name_edit = QLineEdit(sub_name)
        sub_name_edit.setObjectName("nameEdit")
        sub_name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_name_edit.setReadOnly(True)
        sub_name_edit.setPlaceholderText("（备注）")
        self._table.setCellWidget(row_idx, 1, _make_sub_name_cell(sub_name_edit, lambda: name))

        seq_label = QLabel(seq_text)
        seq_label.setObjectName("seqLabel")
        seq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 2, seq_label)

        value_spin = QDoubleSpinBox()
        value_spin.setObjectName("itemValueSpin")
        value_spin.setRange(0, 9999)
        value_spin.setDecimals(4)
        value_spin.setValue(value)
        value_spin.setFixedWidth(100)
        value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_spin.valueChanged.connect(lambda cb=self._on_change_cb: cb and cb())
        self._table.setCellWidget(row_idx, 3, value_spin)

        unit_label = QLabel("百分比")
        unit_label.setObjectName("unitLabel")
        unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 4, unit_label)

        source_label = QLabel(source)
        source_label.setObjectName("seqLabel")
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 5, source_label)

        kw_btn = QPushButton(keywords if keywords else "点击编辑")
        kw_btn.setObjectName("itemLockBtn")
        kw_btn.setFixedSize(110, 35)
        kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        kw_btn.clicked.connect(lambda _, b=kw_btn: self._edit_keywords_for_btn(b))
        self._table.setCellWidget(row_idx, 6, kw_btn)

        ops = QWidget()
        ops_layout = QHBoxLayout(ops)
        ops_layout.setContentsMargins(2, 0, 2, 0)
        ops_layout.setSpacing(3)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("itemDeleteBtn")
        del_btn.setFixedSize(55, 28)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self._remove_row(row_idx))
        ops_layout.addWidget(del_btn)

        self._table.setCellWidget(row_idx, 7, ops)

        if self._on_change_cb:
            self._on_change_cb()

    def add_effect_with_seq(self, name, value, eff_type, source, sub_name="", keywords="", seq_text=""):
        """从外部添加效果，使用指定的序列号（用于共鸣链同步，避免计数器递增）"""
        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)
        self._table.setRowHeight(row_idx, 50)

        name_edit = QLineEdit(name)
        name_edit.setObjectName("nameEdit")
        name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 0, name_edit)

        sub_name_edit = QLineEdit(sub_name)
        sub_name_edit.setObjectName("nameEdit")
        sub_name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_name_edit.setReadOnly(True)
        sub_name_edit.setPlaceholderText("（备注）")
        self._table.setCellWidget(row_idx, 1, _make_sub_name_cell(sub_name_edit, lambda: name))

        seq_label = QLabel(seq_text)
        seq_label.setObjectName("seqLabel")
        seq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 2, seq_label)

        value_spin = QDoubleSpinBox()
        value_spin.setObjectName("itemValueSpin")
        value_spin.setRange(0, 9999)
        value_spin.setDecimals(4)
        value_spin.setValue(value)
        value_spin.valueChanged.connect(lambda cb=self._on_change_cb: cb and cb())
        value_spin.setFixedWidth(100)
        value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 3, value_spin)

        unit_label = QLabel("百分比")
        unit_label.setObjectName("unitLabel")
        unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 4, unit_label)

        source_label = QLabel(source)
        source_label.setObjectName("seqLabel")
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 5, source_label)

        kw_btn = QPushButton(keywords if keywords else "点击编辑")
        kw_btn.setObjectName("itemLockBtn")
        kw_btn.setFixedSize(110, 35)
        kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        kw_btn.clicked.connect(lambda _, b=kw_btn: self._edit_keywords_for_btn(b))
        self._table.setCellWidget(row_idx, 6, kw_btn)

        ops = QWidget()
        ops_layout = QHBoxLayout(ops)
        ops_layout.setContentsMargins(2, 0, 2, 0)
        ops_layout.setSpacing(3)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("itemDeleteBtn")
        del_btn.setFixedSize(55, 28)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self._remove_row(row_idx))
        ops_layout.addWidget(del_btn)

        self._table.setCellWidget(row_idx, 7, ops)

        if self._on_change_cb:
            self._on_change_cb()

    def get_items(self):
        """返回所有条目"""
        items = []
        for row in range(self._table.rowCount()):
            name_edit = self._table.cellWidget(row, 0)
            sub_name_edit = self._table.cellWidget(row, 1)
            seq_label = self._table.cellWidget(row, 2)
            value_spin = self._table.cellWidget(row, 3)
            unit_label = self._table.cellWidget(row, 4)
            source_label = self._table.cellWidget(row, 5)
            kw_btn = self._table.cellWidget(row, 6)
            if name_edit and value_spin:
                kw_text = kw_btn.text() if kw_btn and kw_btn.text() != "点击编辑" else ""
                eff_type = unit_label.text() if unit_label else "百分比"
                sub_name = _get_sub_name_text(sub_name_edit)
                seq = seq_label.text() if seq_label and hasattr(seq_label, 'text') else ""
                items.append({
                    "name": name_edit.text().strip(),
                    "value": value_spin.value(),
                    "eff_type": eff_type,
                    "source": source_label.text() if source_label else "共鸣链效果",
                    "sub_name": sub_name,
                    "keywords": kw_text,
                    "seq": seq,
                })
        return items

    def remove_effects_by_chain(self, chain_num):
        """移除指定共鸣链的所有关联行（根据序列号「共鸣链X关联Y」匹配）"""
        prefix = f"共鸣链{chain_num}关联"
        rows_to_remove = []
        for row in range(self._table.rowCount()):
            seq_widget = self._table.cellWidget(row, 2)
            if seq_widget and hasattr(seq_widget, 'text'):
                if seq_widget.text().startswith(prefix):
                    rows_to_remove.append(row)
        # 从后往前删避免索引错位
        for row in reversed(rows_to_remove):
            self._table.removeRow(row)
        # 递减共鸣链计数器
        self._chain_counter = max(0, self._chain_counter - len(rows_to_remove))
        return len(rows_to_remove)


# ==================== 声骸列表项（用于计数页） ====================

class EchoCounterItem(QWidget):
    """声骸计数列表中的单项. 显示序号 + 费用 + 隐藏 + 删除按钮."""
    def __init__(self, cost, echo_id, change_cb=None, parent=None):
        super().__init__(parent)
        self.cost = cost
        self.echo_id = echo_id
        self._change_cb = change_cb

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        layout.addWidget(QLabel(f"{cost}费声骸"))
        layout.addStretch()

        is_hidden = echo_id in HIDDEN_ECHO_IDS
        self.hide_btn = QPushButton("隐藏中" if is_hidden else "隐藏")
        self.hide_btn.setObjectName("itemDeleteBtn" if is_hidden else "itemLockBtn")
        self.hide_btn.setFixedSize(52, 28)
        self.hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_btn.clicked.connect(self._toggle_hide)
        layout.addWidget(self.hide_btn)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setObjectName("itemDeleteBtn")
        self.delete_btn.setFixedSize(50, 28)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.delete_btn)

    def _toggle_hide(self):
        if self.echo_id in HIDDEN_ECHO_IDS:
            HIDDEN_ECHO_IDS.discard(self.echo_id)
            self.hide_btn.setText("隐藏")
            self.hide_btn.setObjectName("itemLockBtn")
        else:
            HIDDEN_ECHO_IDS.add(self.echo_id)
            self.hide_btn.setText("隐藏中")
            self.hide_btn.setObjectName("itemDeleteBtn")
        self.hide_btn.style().unpolish(self.hide_btn)
        self.hide_btn.style().polish(self.hide_btn)
        if self._change_cb:
            self._change_cb()


from ocr_engine import _ALL_STAT_NAMES, OCRWorker, _parse_dmg_mult_ocr_results

class LoadingOverlay(QWidget):
    """半透明遮罩 + 旋转加载动画 + 取消按钮，覆盖在父窗口中央"""
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._progress_label = QLabel(self)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setStyleSheet("color:#fff;font-size:14px;font-weight:bold;")
        self._progress_label.hide()
        self._cancel_btn = QPushButton("取消", self)
        self._cancel_btn.setObjectName("itemDeleteBtn")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setFixedSize(70, 32)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        self._cancel_btn.hide()
        self.hide()

    def _on_cancel_clicked(self):
        """取消按钮点击：即时反馈 + 发出中断信号"""
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("取消中…")
        self._cancel_btn.repaint()
        self.cancel_requested.emit()

    def _rotate(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def show_overlay(self, text=""):
        if self.parent():
            self.setGeometry(self.parent().rect())
        self._angle = 0
        self._timer.start(50)
        self.show()
        self.raise_()
        self.set_progress(text)
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.setText("取消")
        self._cancel_btn.show()
        self._cancel_btn.raise_()

    def hide_overlay(self):
        self._timer.stop()
        self.hide()
        self._progress_label.hide()
        self._cancel_btn.hide()

    def set_progress(self, text):
        if text:
            self._progress_label.setText(text)
            cx = self.width() // 2
            cy = self.height() // 2
            self._progress_label.setGeometry(cx - 100, cy + 50, 200, 28)
            self._progress_label.show()
            self._progress_label.raise_()
            self._progress_label.update()
        else:
            self._progress_label.hide()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 半透明背景
        p.fillRect(self.rect(), QColor(0, 0, 0, 80))
        # 转圈
        cx = self.width() // 2
        cy = self.height() // 2
        r = 32
        p.translate(cx, cy)
        pen = QPen(QColor(100, 180, 255), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for i in range(12):
            a = self._angle + i * 30
            alpha = 30 + i * 18
            if alpha > 255:
                alpha = 255
            c = QColor(100, 180, 255, alpha)
            pen.setColor(c)
            p.setPen(pen)
            x1 = int(r * 0.45 * math.cos(math.radians(a)))
            y1 = int(r * 0.45 * math.sin(math.radians(a)))
            x2 = int(r * 0.85 * math.cos(math.radians(a)))
            y2 = int(r * 0.85 * math.sin(math.radians(a)))
            p.drawLine(x1, y1, x2, y2)
        p.end()

    def resizeEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().rect())
        cx = self.width() // 2
        cy = self.height() // 2
        self._progress_label.setGeometry(cx - 100, cy + 50, 200, 28)
        self._cancel_btn.move(cx - 35, cy + 80)
        super().resizeEvent(event)


class OCRConfirmDialog(QDialog):
    """OCR 识别结果确认对话框（支持多图片 Tab 切换）"""

    COST_OPTIONS = ["1费", "3费", "4费"]

    def __init__(self, data_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OCR 识别结果确认")
        self.setMinimumWidth(820)

        self._current_tab = 0

        # 将原始 data 转为可编辑的 tab 数据
        self._tab_data = []
        for d in data_list:
            tab = {
                "cost": d.get("cost"),
                "main_name": d["main_stat"]["name"] if d.get("main_stat") else "",
                "main_value": d["main_stat"]["value"] if d.get("main_stat") else 0.0,
                "sub_stats": [{"name": s["name"], "value": s["value"], "is_percent": s.get("is_percent", False)}
                              for s in d.get("sub_stats", [])],
                "raw_lines": d.get("raw_lines", []),
            }
            self._tab_data.append(tab)
        _center_window(self)


        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # —— Tab 切换栏 ——
        self._tab_btns = []
        if len(self._tab_data) > 1:
            tab_row = QHBoxLayout()
            tab_row.setSpacing(4)
            tab_row.addStretch()
            for i in range(len(self._tab_data)):
                btn = QPushButton(f"图片{i + 1}")
                btn.setCheckable(True)
                btn.setFixedWidth(60)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, idx=i: self._load_tab(idx))
                btn.setStyleSheet("""
                    QPushButton { padding:7px 12px; border:1px solid #555; border-radius:3px;
                                  background:#2a2a2a; color:#aaa; font-size:12px; }
                    QPushButton:checked { background:#3a6a9a; color:#fff; border-color:#5a9aca; }
                """)
                tab_row.addWidget(btn)
                self._tab_btns.append(btn)
            tab_row.addStretch()
            layout.addLayout(tab_row)

        # —— 主体：左右两栏 ——
        body = QHBoxLayout()
        body.setSpacing(16)

        # 左侧：编辑区域
        left = QVBoxLayout()
        left.setSpacing(12)

        # —— 费用（可选择） ——
        cost_row = QHBoxLayout()
        cost_row.addWidget(QLabel("声骸费用:"))
        self.cost_combo = SearchCombo(self.COST_OPTIONS)
        self.cost_combo.setMinimumWidth(80)
        self.cost_combo.currentTextChanged.connect(self._on_cost_changed)
        cost_row.addWidget(self.cost_combo)
        cost_row.addStretch()
        left.addLayout(cost_row)

        # —— 主词条（全为百分比，无常数） ——
        main_group = QGroupBox("主词条")
        main_form = QFormLayout(main_group)
        self.main_name_combo = SearchCombo()
        main_form.addRow("名称:", self.main_name_combo)

        main_val_row = QHBoxLayout()
        self.main_value_spin = QDoubleSpinBox()
        self.main_value_spin.setRange(0, 9999)
        self.main_value_spin.setDecimals(4)
        main_val_row.addWidget(self.main_value_spin, stretch=1)
        main_unit = QLabel("%")
        main_unit.setFixedWidth(20)
        main_unit.setStyleSheet("font-weight:bold;color:#aaa;")
        main_val_row.addWidget(main_unit)
        main_form.addRow("数值:", main_val_row)
        left.addWidget(main_group)

        # —— 固定词条（根据费用自动确定，无需手动选择） ——
        fixed_group = QGroupBox("固定词条")
        fixed_form = QFormLayout(fixed_group)
        self.fixed_label = QLabel("—")
        self.fixed_label.setStyleSheet("font-weight:bold;font-size:14px;")
        fixed_form.addRow("词条:", self.fixed_label)
        left.addWidget(fixed_group)

        # —— 副词条 ——
        sub_group = QGroupBox("副词条")
        self.sub_layout = QVBoxLayout(sub_group)
        self.sub_widgets = []
        # "+" 添加按钮
        add_row = QHBoxLayout()
        add_row.addStretch()
        self.add_sub_btn = QPushButton("＋ 添加副词条")
        self.add_sub_btn.setObjectName("itemAddBtn")
        self.add_sub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_sub_btn.clicked.connect(self._on_add_sub)
        add_row.addWidget(self.add_sub_btn)
        self.sub_layout.addLayout(add_row)
        self._update_add_btn()
        left.addWidget(sub_group)
        left.addStretch()

        body.addLayout(left, stretch=7)

        # 右侧：原始识别文本（可滚动）
        raw_group = QGroupBox("原始识别文本")
        raw_layout = QVBoxLayout(raw_group)
        self.raw_scroll = QScrollArea()
        self.raw_scroll.setWidgetResizable(True)
        self.raw_label = QLabel("(无)")
        self.raw_label.setWordWrap(True)
        self.raw_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.raw_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.raw_label.setStyleSheet("font-size:11px;color:#888;")
        self.raw_scroll.setWidget(self.raw_label)
        raw_layout.addWidget(self.raw_scroll)
        body.addWidget(raw_group, stretch=3)

        layout.addLayout(body)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        n = len(self._tab_data)
        confirm_btn = QPushButton(f"确认添加（共{n}个）" if n > 1 else "确认添加")
        confirm_btn.setObjectName("addButton")
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

        # 加载第一个 tab（跳过初始保存，避免覆盖已解析的数据）
        self._initial_load = True
        self._load_tab(0)
        self.resize(820, 600)

    # ——— Tab 切换 ———
    def _save_current_tab(self):
        """将当前界面值保存到 _tab_data[_current_tab]"""
        if self._current_tab < len(self._tab_data):
            tab = self._tab_data[self._current_tab]
            tab["cost"] = self._current_cost()
            tab["main_name"] = self.main_name_combo.currentText()
            tab["main_value"] = self.main_value_spin.value()
            tab["sub_stats"] = [
                {"name": nc.currentText(), "value": vs.value(), "is_percent": ip}
                for nc, vs, ip, _ul, _rw in self.sub_widgets
            ]

    def _load_tab(self, index):
        """保存当前 tab，然后加载指定 tab 的数据到界面"""
        if index >= len(self._tab_data):
            return
        if getattr(self, '_initial_load', False):
            self._initial_load = False
        else:
            self._save_current_tab()
        self._current_tab = index

        tab = self._tab_data[index]

        # 费用
        cost_str = f"{tab['cost']}费" if tab["cost"] else None
        if cost_str and cost_str in self.COST_OPTIONS:
            self.cost_combo.setCurrentText(cost_str)
        else:
            self.cost_combo.setCurrentText("")

        # 主词条
        self._populate_main_combo()
        if tab["main_name"]:
            self.main_name_combo.setCurrentText(tab["main_name"])
        self.main_value_spin.setValue(tab["main_value"])

        # 固定词条
        self._update_fixed_defaults()

        # 副词条：先清空再重建
        for _nc, _vs, _ip, _ul, rw in list(self.sub_widgets):
            self.sub_layout.removeWidget(rw)
            rw.deleteLater()
        self.sub_widgets.clear()
        for sub in tab["sub_stats"]:
            self._add_sub_row(sub)
        self._update_add_btn()

        # 原始文本
        raw = tab.get("raw_lines", [])
        # 全屏截图原始行数多，取前 30 行 + 尾部调试信息（解析结果/词条）
        if not raw:
            self.raw_label.setText("(无)")
        elif len(raw) <= 50:
            self.raw_label.setText("\n".join(raw))
        else:
            # 找到 "--- 逐行解析结果 ---" 的分割位置
            split_at = next((i for i, s in enumerate(raw) if "逐行解析结果" in s), -1)
            if split_at > 0:
                head = raw[:30]
                tail = raw[split_at:]
                self.raw_label.setText("\n".join(head + ["... (省略中间行) ..."] + tail))
            else:
                self.raw_label.setText("\n".join(raw[:50]))

        # Tab 按钮高亮
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i == index)

        # 标题
        n = len(self._tab_data)
        self.setWindowTitle(f"OCR 识别结果确认 — 图片{index + 1}/{n}" if n > 1 else "OCR 识别结果确认")

    # ——— 费用联动 ———
    def _current_cost(self):
        text = self.cost_combo.currentText()
        return int(text[0]) if text and text[0].isdigit() else None

    def _on_cost_changed(self):
        self._populate_main_combo()
        self._update_fixed_defaults()

    def _populate_main_combo(self):
        cost = self._current_cost()
        if cost and cost in ECHO_MAIN_STATS:
            items = ECHO_MAIN_STATS[cost]
        else:
            items = list(_ALL_STAT_NAMES)
        self.main_name_combo._all_items = list(items)
        self.main_name_combo._valid_items = list(items)
        self.main_name_combo.clear()
        for item in items:
            self.main_name_combo.addItem(item)
        self.main_name_combo.lineEdit().clear()

    def _update_fixed_defaults(self):
        cost = self._current_cost()
        if cost and cost in ECHO_FIXED_MAIN:
            name, val = ECHO_FIXED_MAIN[cost]
            self.fixed_label.setText(f"{name}  +{val:.0f}")
        else:
            self.fixed_label.setText("—")

    # ——— 副词条增删 ———
    def _add_sub_row(self, sub=None):
        if sub is None:
            sub = {"name": "", "value": 0.0, "is_percent": False}
        row_widget = QWidget()
        row_widget.setMinimumHeight(60)
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)

        name_combo = SearchCombo(ECHO_SUB_STATS)
        name_combo.setMinimumWidth(84)
        name_combo.setMinimumHeight(40)
        if sub.get("name"):
            name_combo.setCurrentText(sub["name"])
        row.addWidget(name_combo, stretch=3)

        value_spin = QDoubleSpinBox()
        value_spin.setRange(0, 9999)
        value_spin.setDecimals(4)
        value_spin.setValue(sub.get("value", 0.0))
        value_spin.setMinimumHeight(40)
        row.addWidget(value_spin, stretch=1)

        is_pct = sub.get("is_percent", False)
        unit_label = QLabel("百分比" if is_pct else "常数")
        unit_label.setFixedWidth(52)
        unit_label.setMinimumHeight(40)
        unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unit_label.setStyleSheet("font-weight:bold;color:#888;font-size:11px;")
        row.addWidget(unit_label)

        del_btn = QPushButton("删除")
        del_btn.setFixedWidth(75)
        del_btn.setMinimumHeight(40)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("color:#e55;font-weight:bold;")
        row.addWidget(del_btn)

        idx = len(self.sub_widgets)
        del_btn.clicked.connect(lambda: self._on_remove_sub(idx))
        self.sub_widgets.append((name_combo, value_spin, is_pct, unit_label, row_widget))

        # 插入到添加按钮之前（倒数第二个位置是 add_sub_btn 所在行）
        insert_pos = self.sub_layout.count() - 1  # 最后一行是 add 按钮
        self.sub_layout.insertWidget(insert_pos, row_widget)
        self._update_add_btn()

    def _on_add_sub(self):
        if len(self.sub_widgets) >= 5:
            return
        name, ok = QInputDialog.getItem(
            self, "添加副词条", "选择词条名称:",
            ECHO_SUB_STATS, 0, False
        )
        if not ok or not name:
            return
        self._add_sub_row({"name": name, "value": 0.0, "is_percent": name in CONSTANT_ATTRS})

    def _on_remove_sub(self, idx):
        if idx >= len(self.sub_widgets):
            return
        _, _, _, _, row_widget = self.sub_widgets[idx]
        self.sub_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self.sub_widgets.pop(idx)
        # 修正后续删除按钮的 idx 绑定
        for i in range(idx, len(self.sub_widgets)):
            name_combo, value_spin, is_pct, unit_label, rw = self.sub_widgets[i]
            # 断开旧连接并重新绑定
            for btn in rw.findChildren(QPushButton):
                try:
                    btn.clicked.disconnect()
                except TypeError:
                    pass
                btn.clicked.connect(lambda checked, idx2=i: self._on_remove_sub(idx2))
        self._update_add_btn()

    def _update_add_btn(self):
        if hasattr(self, "add_sub_btn"):
            self.add_sub_btn.setEnabled(len(self.sub_widgets) < 5)

    def get_confirmed_data(self):
        """返回所有 tab 的用户确认数据"""
        self._save_current_tab()
        result = []
        for tab in self._tab_data:
            cost = tab.get("cost")
            if cost and cost in ECHO_FIXED_MAIN:
                fixed_name, fixed_val = ECHO_FIXED_MAIN[cost]
            else:
                fixed_name, fixed_val = "", 0.0
            result.append({
                "cost": cost if cost is not None else 1,
                "main_stat": {
                    "name": tab["main_name"],
                    "value": tab["main_value"],
                    "is_percent": True,
                },
                "fixed_stat": {
                    "name": fixed_name,
                    "value": fixed_val,
                },
                "sub_stats": tab["sub_stats"],
            })
        return result


# ==================== 窄宽度控件（突破 QComboBox 内部最小宽度限制） ====================

class NarrowComboBox(QComboBox):
    """QComboBox 子类，覆写 minimumSizeHint 以允许列宽级别的窄宽度。"""
    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


class NarrowDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox 子类，覆写 minimumSizeHint 以允许列宽级别的窄宽度。"""
    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


# ==================== 伤害倍率确认对话框 ====================

class DamageMultConfirmDialog(QDialog):
    """伤害倍率 OCR 识别结果确认对话框"""

    def __init__(self, data_list, parent=None, raw_text=""):
        super().__init__(parent)
        self.setWindowTitle("伤害倍率识别结果确认")
        self.setMinimumWidth(1250)
        self.setMinimumHeight(650)
        self.setObjectName("dmgMultDialog")

        # 检测主题
        is_light = self._is_light_theme()
        if is_light:
            c = {
                "bg": "#dce3f0", "header_bg": "#dfe6f2",
                "text": "#1b2035", "accent": "#5070e8",
                "input_bg": "#f0f4fa", "input_border": "#b8c4d6", "input_focus": "#5070e8",
                "border": "#bfcadb",
                "dropdown_bg": "#f0f4fa", "dropdown_sel": "#cbd8ed",
            }
        else:
            c = {
                "bg": "#1b2030", "header_bg": "#1b2132",
                "text": "#dde0e6", "accent": "#e94560",
                "input_bg": "#252d42", "input_border": "#2e3448", "input_focus": "#e94560",
                "border": "#2a3045",
                "dropdown_bg": "#252d42", "dropdown_sel": "#1e2840",
            }
        _center_window(self)


        outer = QVBoxLayout(self)
        outer.setSpacing(14)
        outer.setContentsMargins(20, 18, 20, 18)

        title = QLabel(f"识别到 {len(data_list)} 条伤害倍率")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {c['text']};")
        outer.addWidget(title)

        hint = QLabel("请确认或修改每条数据，完成后点击下方按钮添加到结果列表：")
        hint.setObjectName("labelSecondary")
        outer.addWidget(hint)

        # 左右分栏
        body = QHBoxLayout()
        body.setSpacing(16)

        # === 左侧：QTableWidget + 比例列宽 ===
        # 列: 名称 | 分类 | 基础数值 | 基础倍率(%) | 技能类型 | 元素 | 效应
        COL_W = [260, 100, 100, 110, 110, 90, 100]
        headers = ["名称", "分类", "基础数值", "基础倍率(%)", "技能类型", "元素", "效应"]
        COL_RATIOS = [3.5, 1.2, 1.0, 1.2, 1.3, 1.0, 1.2]

        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.verticalHeader().setDefaultSectionSize(38)
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        def _apply_ratios():
            total_w = table.viewport().width()
            if total_w <= 0:
                return
            ratio_sum = sum(COL_RATIOS)
            for ci, r in enumerate(COL_RATIOS):
                w = int(total_w * r / ratio_sum)
                table.setColumnWidth(ci, w)
                # 同步更新每行控件的宽度
                for row in range(table.rowCount()):
                    wgt = table.cellWidget(row, ci)
                    if wgt:
                        wgt.setFixedWidth(w)

        table._apply_ratios = _apply_ratios
        orig_resize = table.resizeEvent
        def _on_resize(e):
            orig_resize(e)
            _apply_ratios()
        table.resizeEvent = _on_resize

        table.setStyleSheet(
            f"QTableWidget {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 6px; }}"
            f"QHeaderView::section {{"
            f"  background: {c['header_bg']}; color: {c['accent']}; font-weight: 600;"
            f"  font-size: 13px; border: none; padding: 4px 6px;"
            f"}}"
        )

        # 样式：名称列（宽列）
        wide_style = (
            f"background: {c['input_bg']}; color: {c['text']};"
            f"border: 1px solid {c['input_border']}; border-radius: 4px;"
            f"padding: 4px 6px; font-size: 13px;"
        )
        # 样式：窄列（基础数值/倍率/技能/元素/效应）
        narrow_style = (
            f"background: {c['input_bg']}; color: {c['text']};"
            f"border: 1px solid {c['input_border']}; border-radius: 3px;"
            f"padding: 4px 6px; font-size: 12px;"
        )
        widget_focus = f"border-color: {c['input_focus']};"
        dropdown_style = (
            f"background: {c['dropdown_bg']}; color: {c['text']};"
            f"border: 1px solid {c['input_border']}; border-radius: 4px;"
            f"selection-background-color: {c['dropdown_sel']};"
        )

        table.setRowCount(len(data_list))
        self._row_widgets = []
        self._data = []

        for row, d in enumerate(data_list):
            self._data.append(dict(d))
            widgets = []

            # 名称（宽列，用 wide_style）
            le = QLineEdit(d.get("label", ""))
            le.setAlignment(Qt.AlignmentFlag.AlignCenter)
            le.setStyleSheet(f"QLineEdit {{ {wide_style} }} QLineEdit:focus {{ {widget_focus} }}")
            table.setCellWidget(row, 0, le)
            widgets.append(le)

            # 分类
            cat_cb = NarrowComboBox()
            cat_cb.addItems(DAMAGE_CATEGORIES)
            cat_val = d.get("category", "")
            if cat_val and cat_val in DAMAGE_CATEGORIES:
                cat_cb.setCurrentText(cat_val)
            cat_cb.setFixedWidth(COL_W[1])
            cat_cb.setStyleSheet(
                f"QComboBox {{ {narrow_style} }} QComboBox:focus {{ {widget_focus} }}"
                "QComboBox::drop-down { border: none; width: 10px; }"
                f"QComboBox QAbstractItemView {{ {dropdown_style} }}"
            )
            cat_cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            table.setCellWidget(row, 1, cat_cb)
            widgets.append(cat_cb)

            # 基础数值
            cb1 = NarrowComboBox()
            cb1.addItems(["攻击力", "生命值", "防御力"])
            cb1.setCurrentText(d.get("basis", "攻击力"))
            cb1.setFixedWidth(COL_W[2])
            cb1.setStyleSheet(
                f"QComboBox {{ {narrow_style} }} QComboBox:focus {{ {widget_focus} }}"
                "QComboBox::drop-down { border: none; width: 10px; }"
                f"QComboBox QAbstractItemView {{ {dropdown_style} }}"
            )
            cb1.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            table.setCellWidget(row, 2, cb1)
            widgets.append(cb1)

            # 基础倍率
            sp = NarrowDoubleSpinBox()
            sp.setRange(0, 99999)
            sp.setDecimals(4)
            sp.setValue(d.get("base_mult", 0.0))
            sp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sp.setFixedWidth(COL_W[3])
            sp.setStyleSheet(
                f"QDoubleSpinBox {{ {narrow_style} }} QDoubleSpinBox:focus {{ {widget_focus} }}"
                "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button"
                " { width: 0; height: 0; border: none; background: transparent; }"
                "QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow"
                " { image: none; border: none; width: 0; height: 0; }"
            )
            table.setCellWidget(row, 3, sp)
            widgets.append(sp)

            # 技能类型
            cb3 = NarrowComboBox()
            cb3.addItems(SKILL_TYPES)
            sk = d.get("skill")
            if sk and sk in SKILL_TYPES:
                cb3.setCurrentText(sk)
            elif sk:
                cb3.setCurrentText("普攻")
            cb3.setFixedWidth(COL_W[4])
            cb3.setStyleSheet(
                f"QComboBox {{ {narrow_style} }} QComboBox:focus {{ {widget_focus} }}"
                "QComboBox::drop-down { border: none; width: 10px; }"
                f"QComboBox QAbstractItemView {{ {dropdown_style} }}"
            )
            cb3.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            table.setCellWidget(row, 4, cb3)
            widgets.append(cb3)

            # 元素
            cb4 = NarrowComboBox()
            cb4.addItems(ELEMENTS)
            el = d.get("element")
            if el and el in ELEMENTS:
                cb4.setCurrentText(el)
            cb4.setFixedWidth(COL_W[5])
            cb4.setStyleSheet(
                f"QComboBox {{ {narrow_style} }} QComboBox:focus {{ {widget_focus} }}"
                "QComboBox::drop-down { border: none; width: 10px; }"
                f"QComboBox QAbstractItemView {{ {dropdown_style} }}"
            )
            cb4.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            table.setCellWidget(row, 5, cb4)
            widgets.append(cb4)

            # 效应
            cb5 = NarrowComboBox()
            cb5.addItems(EFFECTS)
            ef = d.get("effect")
            if ef and ef in EFFECTS:
                cb5.setCurrentText(ef)
            cb5.setFixedWidth(COL_W[6])
            cb5.setStyleSheet(
                f"QComboBox {{ {narrow_style} }} QComboBox:focus {{ {widget_focus} }}"
                "QComboBox::drop-down { border: none; width: 10px; }"
                f"QComboBox QAbstractItemView {{ {dropdown_style} }}"
            )
            cb5.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            table.setCellWidget(row, 6, cb5)
            widgets.append(cb5)

            self._row_widgets.append(widgets)

        table._apply_ratios()  # 初始按比例分配列宽

        self._table = table
        body.addWidget(table, stretch=15)

        # === 右侧：原始识别文本 ===
        raw_group = QGroupBox("原始 OCR 识别文本")
        raw_layout = QVBoxLayout(raw_group)
        raw_layout.setContentsMargins(8, 8, 8, 8)
        raw_text_edit = QTextEdit()
        raw_text_edit.setReadOnly(True)
        raw_text_edit.setPlainText(raw_text)
        raw_text_edit.setStyleSheet(
            "font-size: 12px; font-family: 'Microsoft YaHei', sans-serif;"
            f"background: {c['input_bg']}; color: {c['text']};"
            f"border: 1px solid {c['input_border']}; border-radius: 4px;"
        )
        raw_layout.addWidget(raw_text_edit)
        body.addWidget(raw_group, stretch=5)

        outer.addLayout(body)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("backButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = QPushButton(f"确认添加（共{len(data_list)}条）")
        confirm_btn.setObjectName("itemAddBtn")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)

        outer.addLayout(btn_row)

    def _is_light_theme(self):
        try:
            w = self.parent()
            while w is not None:
                if hasattr(w, "current_theme"):
                    return w.current_theme == "light"
                w = w.parent()
        except Exception as e:
            _logger.debug("_is_light_theme 失败: %s", e)
        return False

    def get_confirmed_data(self):
        result = []
        for row, widgets in enumerate(self._row_widgets):
            item = dict(self._data[row])
            label_edit, cat_cb, basis_cb, mult_sp, skill_cb, elem_cb, effect_cb = widgets
            item["label"] = label_edit.text().strip() or item.get("label", "")
            item["category"] = cat_cb.currentText()
            item["basis"] = basis_cb.currentText()
            item["base_mult"] = mult_sp.value()
            item["skill"] = skill_cb.currentText()
            item["element"] = elem_cb.currentText()
            item["effect"] = effect_cb.currentText()
            result.append(item)
        return result


# ==================== 声骸计数页面 ====================

class EchoCounterPage(QWidget):
    """同费用声骸容器页. 管理多个 EchoPage, 支持新建/删除/翻页."""
    def __init__(self):
        super().__init__()
        self.echoes = []
        self.echo_id_counter = 0
        self._add_callback = None
        self._remove_callback = None
        self._change_callback = None
        self._ocr_callback = None
        self._ocr_loading_show = None
        self._ocr_loading_hide = None
        self._ocr_loading_progress = None
        self._pending_ocr_data = None
        self._build_ui()

    def set_callbacks(self, add_cb, remove_cb, change_cb=None):
        self._add_callback = add_cb
        self._remove_callback = remove_cb
        self._change_callback = change_cb

    def _notify_change(self):
        if self._change_callback:
            self._change_callback()

    def set_ocr_callback(self, cb):
        self._ocr_callback = cb

    def set_ocr_loading_callbacks(self, show_cb, hide_cb, progress_cb=None, cancel_cb=None):
        self._ocr_loading_show = show_cb
        self._ocr_loading_hide = hide_cb
        self._ocr_loading_progress = progress_cb
        self._ocr_cancel_cb = cancel_cb

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("声骸计数")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        desc = QLabel("选择费用类型后点击添加，总费用不能超过12，最多5个声骸")
        desc.setObjectName("labelSecondary")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        status_layout = QHBoxLayout()
        self.cost_label = QLabel("当前总费用: 0 / 12")
        self.cost_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.count_label = QLabel("声骸数量: 0 / 5")
        self.count_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        status_layout.addWidget(self.cost_label)
        status_layout.addWidget(self.count_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        select_layout = QHBoxLayout()
        self.cb_4 = QCheckBox("4费")
        self.cb_3 = QCheckBox("3费")
        self.cb_1 = QCheckBox("1费")
        select_layout.addWidget(self.cb_4)
        select_layout.addWidget(self.cb_3)
        select_layout.addWidget(self.cb_1)
        select_layout.addSpacing(20)

        self.add_btn = QPushButton("添加")
        self.add_btn.setObjectName("addButton")
        self.add_btn.setFixedWidth(80)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_echoes)
        select_layout.addWidget(self.add_btn)

        self.ocr_file_btn = QPushButton("导图识别")
        self.ocr_file_btn.setObjectName("itemAddBtn")
        self.ocr_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ocr_file_btn.clicked.connect(self._import_image_ocr)
        select_layout.addWidget(self.ocr_file_btn)

        self.ocr_clip_btn = QPushButton("截图识别")
        self.ocr_clip_btn.setObjectName("itemAddBtn")
        self.ocr_clip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ocr_clip_btn.clicked.connect(self._screenshot_ocr)
        select_layout.addWidget(self.ocr_clip_btn)
        select_layout.addStretch()

        layout.addLayout(select_layout)

        layout.addWidget(QLabel("已添加声骸:"))

        self.echo_list = QListWidget()
        self.echo_list.setObjectName("attrList")
        self.echo_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.echo_list, stretch=1)

        self._update_status()

    def _add_echoes(self):
        selected = []
        if self.cb_4.isChecked():
            selected.append(4)
        if self.cb_3.isChecked():
            selected.append(3)
        if self.cb_1.isChecked():
            selected.append(1)
        if not selected:
            return

        current_cost = sum(e[0] for e in self.echoes)
        current_count = len(self.echoes)
        new_costs = []
        temp_cost = current_cost
        temp_count = current_count

        for cost in selected:
            if temp_cost + cost <= 12 and temp_count < 5:
                temp_cost += cost
                temp_count += 1
                new_costs.append(cost)

        if not new_costs:
            return

        for cost in new_costs:
            self.echo_id_counter += 1
            eid = self.echo_id_counter
            self.echoes.append((cost, eid))
            if self._add_callback:
                self._add_callback(cost, eid)

        self._rebuild_echo_list()
        self._update_status()

        self.cb_4.setChecked(False)
        self.cb_3.setChecked(False)
        self.cb_1.setChecked(False)

    def _rebuild_echo_list(self):
        self.echo_list.clear()
        for cost, eid in sorted(self.echoes, key=lambda x: (-x[0], x[1])):
            item_widget = EchoCounterItem(cost, eid, change_cb=self._change_callback)
            item_widget.delete_btn.clicked.connect(
                lambda _, w=item_widget: self._remove_echo(w)
            )
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.echo_list.addItem(list_item)
            self.echo_list.setItemWidget(list_item, item_widget)

    def _remove_echo(self, widget):
        for i in range(self.echo_list.count()):
            if self.echo_list.itemWidget(self.echo_list.item(i)) is widget:
                eid = widget.echo_id
                self.echoes = [(c, e) for c, e in self.echoes if e != eid]
                self._rebuild_echo_list()
                if self._remove_callback:
                    self._remove_callback(eid)
                break
        self._update_status()

    def _update_status(self):
        cost = sum(e[0] for e in self.echoes)
        count = len(self.echoes)
        self.cost_label.setText(f"当前总费用: {cost} / 12")
        self.count_label.setText(f"声骸数量: {count} / 5")
        self.add_btn.setEnabled(cost < 12 and count < 5)

    # —— OCR 图文识别 ——

    def _set_ocr_buttons_enabled(self, enabled):
        self.ocr_file_btn.setEnabled(enabled)
        self.ocr_clip_btn.setEnabled(enabled)
        if enabled:
            self.ocr_file_btn.setText("导图识别")
            self.ocr_clip_btn.setText("截图识别")
        else:
            self.ocr_file_btn.setText("识别中...")
            self.ocr_clip_btn.setText("识别中...")

    def _on_ocr_finished(self, data_list):
        # ⚠️ 必须最先检查 sender，防止旧 worker 残留信号
        # 污染新 OCR 的 UI 状态（遮罩、按钮），导致卡死/闪退
        if self.sender() is not getattr(self, '_ocr_worker', None):
            return
        if self._ocr_loading_hide:
            self._ocr_loading_hide()
        self._set_ocr_buttons_enabled(True)

        # 如果被中断，跳过结果处理
        if getattr(self._ocr_worker, '_abort', False):
            return

        # 过滤失败项 + 有效内容检测（至少要有 cost 或 main_stat）
        valid = []
        for d in (data_list or []):
            if d is None:
                continue
            if d.get("cost") is not None or d.get("main_stat") is not None:
                valid.append(d)
            else:
                _logger.debug("声骸 OCR 结果无效（无 COST 无主词条），已丢弃: %s",
                             str(d.get("raw_lines", [])[:3] if d else "None"))

        if len(valid) < 1:
            _logger.warning("声骸 OCR 识别失败：%d 张图片均无有效内容",
                           len(data_list or []))
            self._update_error_log_btn_if_possible()
            QMessageBox.warning(self, "OCR 识别失败",
                              "未能识别出有效的声骸数据。\n"
                              "请确认截图中包含声骸面板（COST + 主词条 + 副词条）。\n\n"
                              "可点击侧边栏「错误日志」查看详情。")
            return

        self._confirm_and_add(valid)

    def _update_error_log_btn_if_possible(self):
        try:
            win = self.window()
            if win and hasattr(win, 'main_screen'):
                win.main_screen._update_error_log_btn()
        except Exception:
            pass

    def _on_ocr_error(self, msg):
        if self.sender() is not getattr(self, '_ocr_worker', None):
            return
        if self._ocr_loading_hide:
            self._ocr_loading_hide()
        self._set_ocr_buttons_enabled(True)
        _logger.warning("声骸 OCR 线程异常: %s", msg)
        self._update_error_log_btn_if_possible()
        QMessageBox.warning(self, "OCR 识别失败",
                          f"识别过程出错：\n{msg}\n\n可点击侧边栏「错误日志」查看详情。")

    def _on_ocr_progress(self, current, total):
        if self._ocr_loading_progress:
            self._ocr_loading_progress(f"识别中 {current}/{total}...")

    def abort_ocr(self):
        """中断当前 OCR 识别"""
        # 立即隐藏遮罩，不等线程 finished 信号（terminate 后信号可能延迟/丢失）
        if self._ocr_loading_hide:
            self._ocr_loading_hide()
        self._set_ocr_buttons_enabled(True)
        if hasattr(self, '_ocr_worker') and self._ocr_worker and self._ocr_worker.isRunning():
            self._ocr_worker.abort()

    def _start_ocr(self, sources):
        """sources: list[tuple[image_source, is_qimage]]"""
        # 断开旧 worker 信号，防止残留信号污染
        if hasattr(self, '_ocr_worker') and self._ocr_worker:
            try:
                self._ocr_worker.finished.disconnect(self._on_ocr_finished)
                self._ocr_worker.error.disconnect(self._on_ocr_error)
                self._ocr_worker.progress.disconnect(self._on_ocr_progress)
            except Exception:
                pass
        self._set_ocr_buttons_enabled(False)
        total = len(sources)
        if self._ocr_loading_show:
            self._ocr_loading_show(f"识别中...（上限5张）")
        self._ocr_worker = OCRWorker(sources)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_worker.progress.connect(self._on_ocr_progress)
        self._ocr_worker.start()

    def _import_image_ocr(self):
        """导图识别：选择图片文件进行 OCR（最多 5 张）"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择声骸截图（最多5张）", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*.*)"
        )
        if not file_paths:
            return
        sources = [(fp, False) for fp in file_paths[:5]]
        self._start_ocr(sources)

    def _screenshot_ocr(self):
        """截图识别：从剪贴板读取截图进行 OCR"""
        try:
            clipboard = QApplication.clipboard()
            # 先用轻量检查（避免 clipboard.image() 对非图片数据卡死）
            if not clipboard.mimeData().hasImage():
                QMessageBox.information(
                    self, "无截图",
                    "剪贴板中没有图片。\n"
                    "请先使用截图工具截图（如 Win+Shift+S），再点击此按钮。"
                )
                return
            qimage = clipboard.image()
            if qimage.isNull():
                QMessageBox.information(
                    self, "无截图",
                    "剪贴板中没有图片。\n"
                    "请先使用截图工具截图（如 Win+Shift+S），再点击此按钮。"
                )
                return
            self._start_ocr([(qimage, True)])
        except Exception as e:
            _logger.exception("截图识别失败: %s", e)
            QMessageBox.critical(self, "错误", f"截图识别失败:\n{e}")

    def _confirm_and_add(self, data_list):
        """弹出确认对话框，用户确认后创建声骸"""
        dlg = OCRConfirmDialog(data_list, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        confirmed_list = dlg.get_confirmed_data()
        # 暂停界面更新，避免逐条添加时反复重绘卡顿
        self.setUpdatesEnabled(False)
        try:
            added = 0
            for confirmed in confirmed_list:
                current_cost = sum(e[0] for e in self.echoes)
                current_count = len(self.echoes)
                cost = confirmed["cost"]
                if current_cost + cost > 12 or current_count >= 5:
                    QMessageBox.warning(self, "无法添加",
                        f"总费用超限或声骸数量已达上限（已添加 {added} 个，跳过剩余）。")
                    break

                self.echo_id_counter += 1
                eid = self.echo_id_counter
                self.echoes.append((cost, eid))
                if self._add_callback:
                    self._add_callback(cost, eid)

                if self._ocr_callback:
                    self._ocr_callback(eid, confirmed)

                added += 1
        finally:
            self.setUpdatesEnabled(True)

        self._rebuild_echo_list()
        self._update_status()

# ==================== 单个声骸详情页面 ====================

class _FitListWidget(QListWidget):
    """无内部滚动条、高度自适应内容的列表控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        s = super().sizeHint()
        h = sum(self.sizeHintForRow(i) for i in range(self.count()))
        h += self.frameWidth() * 2 + 4
        return QSize(s.width(), max(h, 40))

    def minimumSizeHint(self):
        return self.sizeHint()

    def rowsInserted(self, parent, start, end):
        super().rowsInserted(parent, start, end)
        self.updateGeometry()


class SubStatDialog(QDialog):
    """弹出选择副词条名称的对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加副词条")
        self.setMinimumWidth(360)
        _center_window(self)


        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("选择词条名称:"))

        self.name_combo = SearchCombo(ECHO_SUB_STATS)
        layout.addWidget(self.name_combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        confirm_btn = QPushButton("确认添加")
        confirm_btn.setObjectName("addButton")
        confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def _on_confirm(self):
        name = self.name_combo.currentText().strip()
        if not name or not self.name_combo.isValidSelection():
            QMessageBox.warning(self, "无效选择", "请从列表中选择一个有效的词条名称。")
            return
        self.accept()

    def get_name(self):
        return self.name_combo.currentText().strip()


class EchoPage(QWidget):
    """单个声骸配置页. 主词条 + 副词条 (最多5) + 固定词条."""
    def __init__(self, cost, echo_id):
        super().__init__()
        self.cost = cost
        self.echo_id = echo_id
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(f"{self.cost}费声骸")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        main_group = QGroupBox("主词条")
        main_group.setObjectName("main_group")
        main_layout = QVBoxLayout(main_group)

        main_row = QHBoxLayout()
        main_row.setSpacing(8)

        self.main_combo = SearchCombo(ECHO_MAIN_STATS[self.cost])
        self.main_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.main_combo.currentTextChanged.connect(self._on_main_stat_changed)
        main_row.addWidget(self.main_combo, stretch=3)

        self.main_value = QDoubleSpinBox()
        self.main_value.setObjectName("itemValueSpin")
        self.main_value.setRange(0, 9999)
        self.main_value.setDecimals(4)
        self.main_value.setFixedWidth(100)
        main_row.addWidget(self.main_value)

        self.main_unit = QLabel("百分比")
        self.main_unit.setObjectName("unitLabel")
        self.main_unit.setFixedWidth(60)
        main_row.addWidget(self.main_unit)

        self.main_lock_btn = QPushButton("锁定")
        self.main_lock_btn.setObjectName("itemLockBtn")
        self.main_lock_btn.setFixedSize(40, 24)
        self.main_lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.main_lock_btn.clicked.connect(self._toggle_main_lock)
        main_row.addWidget(self.main_lock_btn)

        # 隐藏此声骸
        self._echo_hide_btn = QPushButton(
            "取消隐藏" if self.echo_id in HIDDEN_ECHO_IDS else "隐藏"
        )
        self._echo_hide_btn.setObjectName(
            "itemDeleteBtn" if self.echo_id in HIDDEN_ECHO_IDS else "itemLockBtn"
        )
        self._echo_hide_btn.setFixedSize(48, 28)
        self._echo_hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._echo_hide_btn.clicked.connect(self._toggle_echo_hide)
        main_row.addWidget(self._echo_hide_btn)

        # 查看主词条总结
        view_main_btn = QPushButton("查看主词条总结")
        view_main_btn.setObjectName("itemLockBtn")
        view_main_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_main_btn.clicked.connect(lambda: self._nav_to_summary("main"))
        main_row.addWidget(view_main_btn)

        main_layout.addLayout(main_row)

        fixed_name, fixed_value = ECHO_FIXED_MAIN[self.cost]
        fixed_row = QHBoxLayout()
        fixed_row.setSpacing(8)
        fixed_row.addWidget(QLabel(f"{fixed_name}："))
        lbl = QLabel(f"{fixed_value:.1f}")
        lbl.setObjectName("fixedStatValue")
        lbl.setFixedWidth(100)
        fixed_row.addWidget(lbl)
        fixed_row.addWidget(QLabel("常数"))
        fixed_row.addStretch()
        # 查看固定词条总结
        view_fixed_btn = QPushButton("查看固定词条总结")
        view_fixed_btn.setObjectName("itemLockBtn")
        view_fixed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_fixed_btn.clicked.connect(lambda: self._nav_to_summary("fixed"))
        fixed_row.addWidget(view_fixed_btn)
        main_layout.addLayout(fixed_row)

        layout.addWidget(main_group)

        if ECHO_MAIN_STATS[self.cost]:
            self._on_main_stat_changed(ECHO_MAIN_STATS[self.cost][0])

        sub_group = QGroupBox("副词条（最多5个）")
        sub_layout = QVBoxLayout(sub_group)

        sub_row = QHBoxLayout()
        sub_row.addStretch()
        add_sub_btn = QPushButton("添加副词条")
        add_sub_btn.setObjectName("addButton")
        add_sub_btn.setFixedWidth(100)
        add_sub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_sub_btn.clicked.connect(self._add_sub_stat)
        sub_row.addWidget(add_sub_btn)

        sub_layout.addLayout(sub_row)

        self.sub_list = _FitListWidget()
        self.sub_list.setObjectName("attrList")
        sub_layout.addWidget(self.sub_list)

        layout.addWidget(sub_group)
        layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

        self._on_change_cb = None
        self.main_value.valueChanged.connect(self._notify_change)

    def _notify_change(self, *_):
        if self._on_change_cb:
            self._on_change_cb()

    def _on_main_stat_changed(self, text):
        if not self.main_combo.isValidSelection():
            return
        values = ECHO_MAIN_VALUES.get(self.cost, {})
        if text in values:
            self.main_value.setValue(values[text])
            self.main_unit.setText("常数" if text in CONSTANT_ATTRS else "百分比")

    def _highlight_main_area(self):
        """在主词条 QGroupBox 上放置黄色叠层，两轮渐入渐出（共 2s）。"""
        main_group = self.findChild(QGroupBox, "main_group")
        if main_group is None:
            return
        # 放在 QGroupBox 的父容器上，用 QGroupBox 的全局坐标
        parent = main_group.parent() or main_group
        g_rect = QRect(main_group.mapTo(parent, QPoint(0, 0)), main_group.size())
        _place_highlight_overlay(parent, g_rect,
                                 "background: #ffeb3b; border-radius: 8px;")

    def _highlight_sub_row(self, item_widget):
        """在副词条行上放置黄色叠层，两轮渐入渐出（共 2s）。"""
        # 找到 QListWidget 的 viewport，在其上定位叠层
        list_widget = self.sub_list
        for i in range(list_widget.count()):
            if list_widget.itemWidget(list_widget.item(i)) is item_widget:
                rect = list_widget.visualItemRect(list_widget.item(i))
                _place_highlight_overlay(list_widget.viewport(), rect,
                                         "background: #ffeb3b; border-radius: 4px;")
                return
        # fallback：直接在 item_widget 上放置
        _place_highlight_overlay(item_widget, item_widget.rect(),
                                 "background: #ffeb3b; border-radius: 4px;")

    def _toggle_echo_hide(self):
        if self.echo_id in HIDDEN_ECHO_IDS:
            HIDDEN_ECHO_IDS.discard(self.echo_id)
            self._echo_hide_btn.setText("隐藏")
            self._echo_hide_btn.setObjectName("itemLockBtn")
        else:
            HIDDEN_ECHO_IDS.add(self.echo_id)
            self._echo_hide_btn.setText("取消隐藏")
            self._echo_hide_btn.setObjectName("itemDeleteBtn")
            _show_toast(self, "已隐藏此声骸，所有词条将不计入计算")
        self._echo_hide_btn.style().unpolish(self._echo_hide_btn)
        self._echo_hide_btn.style().polish(self._echo_hide_btn)
        self._notify_change()

    def _nav_to_summary(self, stat_type):
        """跳转到数值总结页并高亮对应词条。"""
        nav_fn = getattr(self, '_navigate_summary', None)
        sp = getattr(self, '_summary_pages', {})
        # fallback: 通过主窗口获取
        if not nav_fn:
            try:
                win = self.window()
                ms = win.main_screen
                nav_fn = ms._navigate_to_key
                sp = {"summary_base": ms.page_summary_base,
                      "summary_bonus": ms.page_summary_bonus,
                      "summary_deepen": ms.page_summary_deepen,
                      "summary_crit": ms.page_summary_crit}
            except Exception:
                return
        nav_key = f"echo_{self.echo_id}"
        if stat_type == "main":
            name = self.main_combo.currentText()
            if any(kw in name for kw in CRIT_DMG_KEYWORDS | CRIT_RATE_KEYWORDS):
                sk = "summary_crit"
            elif any(s in name for s in BONUS_SUFFIX):
                sk = "summary_bonus"
            elif DEEPEN_SUFFIX in name:
                sk = "summary_deepen"
            else:
                sk = "summary_base"
            nav_fn(sk)
            target = sp.get(sk) if sp else None
            if target:
                hl_name = f"[声骸]主词条-{name}"
                QTimer.singleShot(200, lambda t=target, n=hl_name, nk=nav_key:
                                  t.highlight_item(n, "", nk))
        elif stat_type == "fixed":
            fn, fv = ECHO_FIXED_MAIN[self.cost]
            nav_fn("summary_base")
            target = sp.get("summary_base") if sp else None
            if target:
                hl_name = f"[声骸]固定词条-{fn}"
                QTimer.singleShot(200, lambda t=target, n=hl_name, nk=nav_key:
                                  t.highlight_item(n, "", nk))

    def _view_sub_summary(self, name):
        nav_fn = getattr(self, '_navigate_summary', None)
        sp = getattr(self, '_summary_pages', {})
        if not nav_fn:
            try:
                win = self.window()
                nav_fn = win.main_screen._navigate_to_key
                sp = {"summary_base": win.main_screen.page_summary_base,
                      "summary_bonus": win.main_screen.page_summary_bonus,
                      "summary_deepen": win.main_screen.page_summary_deepen,
                      "summary_crit": win.main_screen.page_summary_crit}
            except Exception:
                return
        nav_key = f"echo_{self.echo_id}"
        if any(kw in name for kw in CRIT_DMG_KEYWORDS | CRIT_RATE_KEYWORDS):
            sk = "summary_crit"
        elif any(s in name for s in BONUS_SUFFIX):
            sk = "summary_bonus"
        elif DEEPEN_SUFFIX in name:
            sk = "summary_deepen"
        else:
            sk = "summary_base"
        nav_fn(sk)
        target = sp.get(sk) if sp else None
        if target:
            hl_name = f"[声骸]副词条-{name}"
            QTimer.singleShot(200, lambda t=target, n=hl_name, nk=nav_key:
                              t.highlight_item(n, "", nk))

    def _toggle_main_lock(self):
        locked = self.main_lock_btn.text() == "锁定"
        self.main_lock_btn.setText("解锁" if locked else "锁定")
        self.main_combo.setEnabled(not locked)
        self.main_value.setEnabled(not locked)

    def _add_sub_stat_direct(self, name, value):
        """直接添加副词条（不弹窗），供 OCR 自动填充使用"""
        if self.sub_list.count() >= 5:
            return
        item_widget = AttrListItem(name, value)
        item_widget.set_delete_callback(self._remove_sub_stat)
        item_widget.set_view_summary_callback(self._view_sub_summary)
        item_widget.value_spin.valueChanged.connect(self._notify_change)
        item_widget.name_edit.textChanged.connect(self._notify_change)
        list_item = QListWidgetItem()
        list_item.setSizeHint(item_widget.sizeHint())
        self.sub_list.addItem(list_item)
        self.sub_list.setItemWidget(list_item, item_widget)
        self._notify_change()

    def _add_sub_stat(self):
        """点击按钮：弹窗选择词条名称后添加"""
        if self.sub_list.count() >= 5:
            return
        name, ok = QInputDialog.getItem(
            self, "添加副词条", "选择词条名称:",
            ECHO_SUB_STATS, 0, False
        )
        if not ok or not name:
            return
        self._add_sub_stat_direct(name, 0.0)

    def _remove_sub_stat(self, widget):
        for i in range(self.sub_list.count()):
            if self.sub_list.itemWidget(self.sub_list.item(i)) is widget:
                self.sub_list.takeItem(i)
                break
        self._notify_change()

    def collect_data(self):
        sub_stats = []
        for i in range(self.sub_list.count()):
            w = self.sub_list.itemWidget(self.sub_list.item(i))
            if w:
                sub_stats.append((w.name_edit.text(), w.value_spin.value(), w.locked))
        return {
            'main_stat': (self.main_combo.currentText(), self.main_value.value()),
            'fixed_stat': ECHO_FIXED_MAIN[self.cost],
            'sub_stats': sub_stats,
        }

# ==================== 敌人减伤页面 ====================

DEFENSE_ITEM_NAMES = {
    "无视防御", "忽视防御", "减少防御",
}

RESISTANCE_ITEM_NAMES = {
    "冷凝抗性无视", "热熔抗性无视", "气动抗性无视",
    "导电抗性无视", "衍射抗性无视", "湮灭抗性无视",
    "冷凝抗性减少", "热熔抗性减少", "气动抗性减少",
    "导电抗性减少", "衍射抗性减少", "湮灭抗性减少",
    "全属性抗性减少",
}

# 分类常量：用于数值总结和计算结果页面
ATK_PCT_NAMES = {"攻击力加成", "攻击力", "攻击"}
ATK_FLAT_NAMES = {"固定攻击"}
BONUS_SUFFIX = ["伤害加成", "伤害提升"]
DEEPEN_SUFFIX = "加深"
CRIT_RATE_KEYWORDS = {"暴击率"}

# 隐藏词条集合：key 为 (name, src_label)，隐藏后不参与计算

# 锁定词条集合：key 为 (name, src_label)，锁定后数值不可改、不可删除

# 隐藏声骸集合：echo_id 在其中的声骸不参与计算

CRIT_DMG_KEYWORDS = {"暴击伤害", "暴击伤害加成", "暴伤", "暴傷"}

def cell_center(table, row, col, widget):
    """Wrap widget in a container to center it in the table cell."""
    container = QWidget()
    cl = QHBoxLayout(container)
    cl.setContentsMargins(0, 0, 0, 0)
    cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cl.addWidget(widget)
    table.setCellWidget(row, col, container)


def fix_table_height(table):
    """Set minimum height on a table to fit all rows without scrolling."""
    h = table.horizontalHeader().height()
    for r in range(table.rowCount()):
        h += table.rowHeight(r)
    table.setMinimumHeight(h + 4)



class PropTable(QTableWidget):
    """QTableWidget with proportional column widths."""
    def __init__(self, proportions, parent=None):
        super().__init__(parent)
        self._proportions = proportions
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.viewport().width()
        if w > 0:
            total = sum(self._proportions)
            for i, p in enumerate(self._proportions):
                self.setColumnWidth(i, max(30, int(w * p / total)))

    def wheelEvent(self, event):
        # Forward wheel scrolling to the outermost scroll area (not table itself)
        p = self.parent()
        while p:
            if isinstance(p, QScrollArea):
                p.wheelEvent(event)
                return
            p = p.parent()
        super().wheelEvent(event)

# ==================== 防御减伤页面 ====================
#
# EnemyDefensePage: 通用 + 6 技能类型无视防御表格
# ───────────────────────────────────────────────
# 结构:
#   【技能视角切换】[无类别][普攻][重击][共鸣技能][共鸣解放][变奏技能][声骸技能]
#   【计算结果框】  总无视/减少防御 | 敌人最终防御值 | 防御乘区
#   【等级参数】    角色等级 | 敌人等级
#   【可滚动区域  QScrollArea → _tables_container】
#     ├── 通用无视/忽视/减少防御  表头: 启用/名称/副名称/序列号/数值/来源
#     ├── 普攻无视防御            表头同上 [全部|常驻|触发] 时效筛选
#     ├── 重击无视防御            ⋯
#     ├── 共鸣技能无视防御         ⋯
#     ├── 共鸣解放无视防御         ⋯
#     ├── 变奏技能无视防御         ⋯
#     └── 声骸技能无视防御          ⋯
#
# 计算分离:
#   def_multiplier            = 仅通用词条的防御乘区
#   _skill_zones["普攻"]      = 通用词条 + 普攻专用词条
#   get_defense_zone(skill)   → ResultPage / ResultListPage 按技能取
#
# 关键 API:
#   recalc()                   — 全量收集、分类、填充 7 表、计算各技能防御乘区
#   _on_timing_chip(key,val)   — 单表时效筛选（全部/常驻/触发）
#   _on_view_skill(skill)      — 技能视角切换，刷新结果标签
#   _on_def_item_toggled(key)  — 单行启用/关闭，控制 _disabled_items
#   get_defense_zone(skill)    — 供 ResultPage 获取对应技能的防御乘区
#   highlight_item(name,src,nk,sq) — 查看总结跳转：平滑滚动 + 黄色叠层
#
class EnemyDefensePage(BaseTableAttrPage):
    """敌人防御减伤页. 通用+6技能类型 无视防御表格，按技能分离计算."""
    navigate_requested = None

    _SKILL_NAMES = ["普攻", "重击", "共鸣技能", "共鸣解放", "变奏技能", "声骸技能"]

    def __init__(self):
        super().__init__(
            "防御减伤",
            "减防词条来自武器谐振、合鸣效果、技能效果",
            sorted(DEFENSE_ITEM_NAMES)
        )
        self._on_change_cb = None
        self._input_row_widget.setVisible(False)
        self.table.setVisible(False)

        self._desc_label.setVisible(False)
        old_title = self._title_label
        title_idx = self.layout().indexOf(old_title)
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        main = QLabel("防御减伤")
        main.setObjectName("sectionTitle")
        sub = QLabel("减防词条来自武器谐振、合鸣效果、技能效果")
        sub.setObjectName("labelSecondary")
        cl.addWidget(main)
        cl.addWidget(sub)
        self.layout().removeWidget(old_title)
        old_title.hide()
        old_title.deleteLater()
        self.layout().insertWidget(title_idx, container)
        self._title_label = main

        self._external_sources = []
        self._timing_filters = {}
        self._disabled_items = set()  # {(name, seq_label)}
        self._view_skill = None  # None=无类别, 否则普攻/重击/共鸣技能/…
        self._sub_name_timer = QTimer(self)
        self._sub_name_timer.setSingleShot(True)
        self._sub_name_timer.setInterval(500)
        self._sub_name_timer.timeout.connect(self.recalc)

        # ========== 技能视角切换 ==========
        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("防御乘区视角:"))
        view_skills = [("无类别", None)] + [(sk, sk) for sk in self._SKILL_NAMES]
        self._view_chips = []
        for label, sk_val in view_skills:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(72, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; color: #8b8fa3; border: 1px solid #4a4d5e;"
                " border-radius: 12px; font-size: 11px; padding: 1px 0px; }"
                "QPushButton:hover:!checked { background: rgba(255,255,255,0.05); color: #c0c4ce; }"
                "QPushButton:checked { background: #e94560; color: #ffffff; border-color: #e94560; font-weight: bold; }"
            )
            btn.clicked.connect(lambda _, sv=sk_val: self._on_view_skill(sv))
            self._view_chips.append(btn)
            view_row.addWidget(btn)
        if self._view_chips:
            self._view_chips[0].setChecked(True)
        view_row.addStretch()
        # ========== 计算结果 ==========
        result_group = QGroupBox("计算结果")
        result_layout = QFormLayout(result_group)
        self.total_ignore_label = QLabel("0.0%")
        self.total_ignore_label.setObjectName("resultValue")
        self.total_reduce_label = QLabel("0.0%")
        self.total_reduce_label.setObjectName("resultValue")
        self.enemy_def_label = QLabel("0.0")
        self.enemy_def_label.setObjectName("resultValue")
        self.def_multiplier_label = QLabel("0.0000")
        self.def_multiplier_label.setObjectName("resultValue")
        result_layout.addRow("无视防御:", self.total_ignore_label)
        result_layout.addRow("忽视/减少防御:", self.total_reduce_label)
        result_layout.addRow("敌人最终防御值:", self.enemy_def_label)
        result_layout.addRow("防御乘区:", self.def_multiplier_label)
        self.layout().insertWidget(2, result_group)

        self.layout().insertLayout(2, view_row)

        # ========== 等级参数 ==========
        level_group = QGroupBox("等级参数")
        level_layout = QFormLayout(level_group)
        self.char_level = QSpinBox()
        self.char_level.setRange(1, 90)
        self.char_level.setValue(90)
        self.enemy_level = QSpinBox()
        self.enemy_level.setRange(1, 120)
        self.enemy_level.setValue(100)
        level_layout.addRow("角色等级:", self.char_level)
        level_layout.addRow("敌人等级:", self.enemy_level)
        self.layout().insertWidget(3, level_group)

        # ========== 防御词条（可滚动）==========
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._tables_container = QWidget()
        self._tables_layout = QVBoxLayout(self._tables_container)
        self._tables_layout.setSpacing(12)
        self._tables_layout.setContentsMargins(0, 4, 0, 8)
        scroll.setWidget(self._tables_container)
        self._scroll = scroll
        self.layout().insertWidget(4, scroll)

        self._def_tables = {}
        for key in ["通用"] + self._SKILL_NAMES:
            self._build_def_table_block(key)
            self._timing_filters[key] = "全部"

        self._tables_layout.addStretch()

        self.char_level.valueChanged.connect(self.recalc)
        self.enemy_level.valueChanged.connect(self.recalc)
        self.recalc()

    def _build_def_table_block(self, key):
        label_text = "通用无视/忽视/减少防御" if key == "通用" else f"{key}无视防御"
        block = QWidget()
        bl = QVBoxLayout(block)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)

        hdr = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setObjectName("groupBoxTitle")
        hdr.addWidget(lbl)
        hdr.addStretch()

        timing_opts = ["全部", "常驻", "触发"]
        chip_group = QWidget()
        cg_layout = QHBoxLayout(chip_group)
        cg_layout.setContentsMargins(0, 0, 0, 0)
        cg_layout.setSpacing(0)
        chips = []
        for i, opt in enumerate(timing_opts):
            btn = QPushButton(opt)
            btn.setCheckable(True)
            btn.setFixedSize(56, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            base = (
                "QPushButton {"
                "  background: transparent;"
                "  color: #8b8fa3;"
                "  border: 1px solid #4a4d5e;"
                "  font-size: 11px;"
                "  padding: 1px 0px;"
            )
            if i == 0:
                base += "  border-top-left-radius: 12px;  border-bottom-left-radius: 12px;"
            elif i == len(timing_opts) - 1:
                base += "  border-top-right-radius: 12px;  border-bottom-right-radius: 12px;"
            else:
                base += "  border-radius: 0px;  border-left: 0px;"
            if i > 0:
                base += "  border-left: 0px;"
            base += "}"
            hover = (
                "QPushButton:hover:!checked {"
                "  background: rgba(255,255,255,0.05);"
                "  color: #c0c4ce;"
                "}"
            )
            checked = (
                "QPushButton:checked {"
                "  background: #e94560;"
                "  color: #ffffff;"
                "  border-color: #e94560;"
                "  font-weight: bold;"
                "}"
            )
            btn.setStyleSheet(base + hover + checked)
            if i == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda _, o=opt, c=chips, k=key: self._on_timing_chip(k, o, c))
            chips.append(btn)
            cg_layout.addWidget(btn)
        hdr.addWidget(chip_group)
        bl.addLayout(hdr)

        table = self._make_def_table(
            ["启用", "名称", "副名称", "序列号", "数值", "来源"],
            proportions=[0.08, 0.20, 0.12, 0.10, 0.18, 0.22]
        )
        table.setMinimumHeight(55 * 4 + 30)
        bl.addWidget(table)

        self._def_tables[key] = {"table": table, "items": [], "chips": chips, "timing_override": None}
        self._tables_layout.addWidget(block)

    def _on_def_item_toggled(self, item_key, checked):
        """启用/关闭单条无视防御词条"""
        if checked:
            self._disabled_items.discard(item_key)
        else:
            self._disabled_items.add(item_key)
        self.recalc()

    def _on_timing_chip(self, key, value, chips):
        if self._timing_filters.get(key) == value:
            return
        self._timing_filters[key] = value
        for c in chips:
            c.setChecked(False)
        for c in chips:
            if c.text() == value:
                c.setChecked(True)
                break
        self._refill_tables()

    def _matches_timing(self, eff_type, table_key):
        f = self._timing_filters.get(table_key, "全部")
        if f == "全部":
            return True
        if f == "常驻":
            return eff_type == "常驻"
        if f == "触发":
            return eff_type == "触发"
        return True

    def highlight_item(self, name, source, nav_key, seq_label):
        """从综合填写页"查看总结"跳转 —— 平滑滚动 + 黄色叠层高亮"""
        for key, d in self._def_tables.items():
            table = d["table"]
            for r in range(table.rowCount()):
                sq_item = table.item(r, 3)
                if sq_item and sq_item.text() == seq_label:
                    QApplication.processEvents()
                    row_y = table.rowViewportPosition(r)
                    table_y = table.mapTo(self._tables_container, table.pos()).y()
                    target = max(0, table_y + row_y - 80)
                    sb = self._scroll.verticalScrollBar()
                    if not sb:
                        return
                    cur = sb.value()
                    steps = 15
                    dlt = (target - cur) / steps

                    def _anim(s=1):
                        sb.setValue(int(cur + dlt * s))
                        if s < steps:
                            QTimer.singleShot(16, lambda ss=s+1: _anim(ss))
                        else:
                            QTimer.singleShot(60, lambda t=table, row=r: self._highlight_def_row(t, row))
                    _anim()
                    return

                    cur = sb.value()
                    steps = 15
                    dlt = (target - cur) / steps

                    def _anim(s=1):
                        sb.setValue(int(cur + dlt * s))
                        if s < steps:
                            QTimer.singleShot(16, lambda ss=s+1: _anim(ss))
                        else:
                            QTimer.singleShot(60, lambda: self._highlight_def_row(table, r))
                    _anim()
                    return



    # ========== 外部来源 ==========
    def set_external_sources(self, sources):
        self._external_sources = sources
        self.recalc()

    def _make_def_table(self, headers, proportions=None):
        if proportions is None:
            proportions = [1.0 / len(headers)] * len(headers)
        table = PropTable(proportions)
        table.setObjectName("defTable")
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        table.verticalHeader().setDefaultSectionSize(55)
        hdr = table.horizontalHeader()
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        return table

    def _on_source_clicked(self, nav_key, seq_label=""):
        if self.navigate_requested:
            self.navigate_requested(nav_key)
        if seq_label:
            QTimer.singleShot(350, lambda: self._do_highlight_in_source(nav_key, seq_label))

    def _do_highlight_in_source(self, nav_key, seq_label):
        ms = self.window().main_screen if self.window() else None
        if not ms:
            return
        QApplication.processEvents()
        if nav_key and nav_key in ms._scrolls:
            QApplication.processEvents()
        # 先尝试综合填写页高亮
        for key in ["combined_perm", "combined_trigger"]:
            scroll = ms._scrolls.get(key)
            if not scroll: continue
            pw = scroll.widget()
            if not isinstance(pw, CombinedEntryPage): continue
            for r in range(len(pw._rows)):
                try:
                    row_data = pw.collect_data()[r]
                    row_seq = row_data[4] if len(row_data) > 4 else ""
                    if row_seq == seq_label:
                        pw._highlight_row(r, scroll)
                        return
                except (IndexError, AttributeError):
                    continue
        # 失败则重试一次
        if seq_label:
            QTimer.singleShot(300, lambda: self._do_highlight_retry_def(seq_label))
        # 同时也高亮自己的表格
        QApplication.processEvents()
        for key, d in self._def_tables.items():
            table = d["table"]
            for r in range(table.rowCount()):
                sq_item = table.item(r, 3)
                if sq_item and sq_item.text() == seq_label:
                    self._highlight_def_row(table, r)
                    return

    def _do_highlight_retry_def(self, seq_label):
        ms = self.window().main_screen if self.window() else None
        if not ms:
            return
        QApplication.processEvents()
        for key in ["combined_perm", "combined_trigger"]:
            scroll = ms._scrolls.get(key)
            if not scroll: continue
            pw = scroll.widget()
            if not isinstance(pw, CombinedEntryPage): continue
            for r in range(len(pw._rows)):
                try:
                    row_data = pw.collect_data()[r]
                    if len(row_data) > 4 and row_data[4] == seq_label:
                        pw._highlight_row(r, scroll)
                        return
                except (IndexError, AttributeError):
                    continue

    def _highlight_def_row(self, table, row):
        """在防御减伤表格行上放置黄色叠层，双轮渐入渐出"""
        idx = table.model().index(row, 0)
        rect = table.visualRect(idx)
        rect.setWidth(table.viewport().width())
        _place_highlight_overlay(table.viewport(), rect)

    def collect_data(self):
        return {
            "char_level": self.char_level.value(),
            "enemy_level": self.enemy_level.value(),
            "timing_filters": dict(self._timing_filters),
            "disabled_items": [list(it) for it in self._disabled_items],
            "view_skill": self._view_skill,
        }

    def apply_data(self, data):
        if not data: return
        if "char_level" in data:
            self.char_level.setValue(data["char_level"])
        if "enemy_level" in data:
            self.enemy_level.setValue(data["enemy_level"])
        if "timing_filters" in data:
            self._timing_filters.update(data["timing_filters"])
        if "disabled_items" in data:
            self._disabled_items = {tuple(it) for it in data["disabled_items"]}
        if "view_skill" in data:
            self._view_skill = data["view_skill"]
            self._refresh_view_chips()
        self.recalc()

    def _toggle_lock(self, rd):
        super()._toggle_lock(rd)
        self.recalc()

    def _refresh_view_chips(self):
        """根据 _view_skill 刷新芯片选中状态"""
        for btn in self._view_chips:
            btn.setChecked(False)
        for btn in self._view_chips:
            if (btn.text() == "无类别" and self._view_skill is None) or btn.text() == self._view_skill:
                btn.setChecked(True)
                break

    def _on_view_skill(self, skill):
        if self._view_skill == skill:
            return
        self._view_skill = skill
        for btn in self._view_chips:
            btn.setChecked(False)
        for btn in self._view_chips:
            if (btn.text() == "无类别" and skill is None) or btn.text() == skill:
                btn.setChecked(True)
                break
        self._refresh_result_labels()

    def _refresh_result_labels(self):
        """根据 _view_skill 更新结果标签"""
        char_lv = float(self.char_level.value())
        enemy_lv = float(self.enemy_level.value())
        sk = self._view_skill

        def _is_ignore(n): return '无视防御' in n
        def _is_reduce(n): return '忽视防御' in n or '减少防御' in n

        if sk and hasattr(self, '_skill_zones') and sk in self._skill_zones:
            dz = self._skill_zones[sk]
            ignore = reduce = 0.0
            for it in self._all_active_generic:
                if (it[0], it[5]) not in self._disabled_items:
                    if _is_ignore(it[0]): ignore += it[1] / 100.0
                    elif _is_reduce(it[0]): reduce += it[1] / 100.0
            for it in self._all_skill_items.get(sk, []):
                if (it[0], it[5]) not in self._disabled_items:
                    if _is_ignore(it[0]): ignore += it[1] / 100.0
                    elif _is_reduce(it[0]): reduce += it[1] / 100.0
        else:
            dz = getattr(self, 'def_multiplier', 1.0)
            ignore = sum(it[1] / 100.0 for it in self._all_active_generic
                        if (it[0], it[5]) not in self._disabled_items and _is_ignore(it[0]))
            reduce = sum(it[1] / 100.0 for it in self._all_active_generic
                        if (it[0], it[5]) not in self._disabled_items and _is_reduce(it[0]))

        ignore = min(ignore, 1.0)
        reduce = min(reduce, 1.0)
        enemy_base = damage_calc.calc_enemy_base_def(enemy_lv)
        enemy_def = enemy_base * (1.0 - ignore) * (1.0 - reduce)
        self.total_ignore_label.setText(f"{ignore * 100:.1f}%")
        self.total_reduce_label.setText(f"{reduce * 100:.1f}%")
        self.enemy_def_label.setText(f"{enemy_def:.1f}")
        self.def_multiplier_label.setText(f"{dz:.10f}")

    def recalc(self):
        char_lv = float(self.char_level.value())
        enemy_lv = float(self.enemy_level.value())

        self._all_items = []
        for src_label, page, nav_key, category in self._external_sources:
            for item_data in page.collect_data():
                name = item_data[0]; value = item_data[1]
                if not damage_calc.is_defense_item(name):
                    continue
                eff_type = "常驻" if category == "常驻" else "触发"
                seq_label = item_data[4] if len(item_data) > 4 and item_data[4] else ""
                sub_name = item_data[5] if len(item_data) > 5 else ""
                self._all_items.append((name, value, eff_type, src_label, nav_key, seq_label, sub_name))

        # 分类：无视防御 vs 忽视/减少防御
        def _is_ignore(name):
            return '无视防御' in name
        def _is_reduce(name):
            return '忽视防御' in name or '减少防御' in name

        generic_items = []
        skill_items_map = {sk: [] for sk in self._SKILL_NAMES}
        for name, value, eff_type, src_label, nav_key, seq_label, sub_name in self._all_items:
            sk = damage_calc.get_def_pen_skill_type(name)
            if sk is not None:
                skill_items_map[sk].append((name, value, eff_type, src_label, nav_key, seq_label, sub_name))
            else:
                generic_items.append((name, value, eff_type, src_label, nav_key, seq_label, sub_name))

        self._fill_table("通用", generic_items)
        self._all_active_generic = generic_items
        self._all_skill_items = skill_items_map
        self._skill_zones = {}
        for sk in self._SKILL_NAMES:
            self._fill_table(sk, skill_items_map[sk])
            ignore = reduce = 0.0
            for it in generic_items:
                if (it[0], it[5]) not in self._disabled_items:
                    if _is_ignore(it[0]): ignore += it[1] / 100.0
                    elif _is_reduce(it[0]): reduce += it[1] / 100.0
            for it in skill_items_map[sk]:
                if (it[0], it[5]) not in self._disabled_items:
                    if _is_ignore(it[0]): ignore += it[1] / 100.0
                    elif _is_reduce(it[0]): reduce += it[1] / 100.0
            self._skill_zones[sk] = damage_calc.calc_defense_zone(char_lv, enemy_lv, ignore, reduce)

        generic_ignore = sum(it[1] / 100.0 for it in generic_items
                            if (it[0], it[5]) not in self._disabled_items and _is_ignore(it[0]))
        generic_reduce = sum(it[1] / 100.0 for it in generic_items
                            if (it[0], it[5]) not in self._disabled_items and _is_reduce(it[0]))
        self.def_multiplier = damage_calc.calc_defense_zone(char_lv, enemy_lv, generic_ignore, generic_reduce)

        self._refresh_result_labels()

        if self._on_change_cb:
            self._on_change_cb()

    def get_defense_zone(self, skill_type=None):
        if skill_type and hasattr(self, '_skill_zones') and skill_type in self._skill_zones:
            return self._skill_zones[skill_type]
        return getattr(self, 'def_multiplier', 1.0)

    def _fill_table(self, key, items):
        d = self._def_tables.get(key)
        if not d:
            return
        table = d["table"]
        d["items"] = items
        self._refill_one(table, items, key)

    def _refill_tables(self):
        for key, d in self._def_tables.items():
            self._refill_one(d["table"], d["items"], key)

    def _refill_one(self, table, all_items, key):
        def _centered(text):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            return item

        filtered = [it for it in all_items if self._matches_timing(it[2], key)]
        table.setRowCount(0)
        for name, value, eff_type, src_label, nav_key, seq_label, sub_name in filtered:
            r = table.rowCount()
            table.insertRow(r)
            cb = QCheckBox()
            item_key = (name, seq_label)
            cb.setChecked(item_key not in self._disabled_items)
            cb.setEnabled(True)
            cb.toggled.connect(lambda checked, ik=item_key: self._on_def_item_toggled(ik, checked))
            cell_center(table, r, 0, cb)
            table.setItem(r, 1, _centered(name))
            se = QLineEdit(sub_name)
            se.setObjectName("nameEdit")
            se.setAlignment(Qt.AlignmentFlag.AlignCenter)
            se.setReadOnly(True)
            se.setPlaceholderText("（备注）")
            cell_center(table, r, 2, _make_sub_name_cell(se))
            table.setItem(r, 3, _centered(seq_label))
            table.setItem(r, 4, _centered(f"{value:.1f}%"))
            src_btn = QPushButton(src_label)
            src_btn.setObjectName("backButton")
            src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            src_btn.clicked.connect(lambda _, nk=nav_key, sq=seq_label:
                                    self._on_source_clicked(nk, sq))
            cell_center(table, r, 5, src_btn)

        fix_table_height(table)

# ==================== 抗性页面 ====================

from enemy_res import EnemyResistancePage
from enemy_res import inject_deps as _inject_enemy_res
# ==================== 通用数据收集 ====================

def _collect_all_items(external_sources, echo_pages=None):
    """从所有来源页面收集数据，返回 [(name, value, source_label, nav_key, seq_label, sub_name), ...]"""
    items = []
    for src_label, page, nav_key in external_sources:
        data = page.collect_data()
        if isinstance(data, list):
            for entry in data:
                name, value = entry[0], entry[1]
                # 如果数据自带来源标签（如 CombinedEntryPage），优先使用
                item_src = entry[3] if len(entry) >= 4 else src_label
                # 序列号：CombinedEntryPage 条目含 seq_num，转为 "常驻N"/"触发N"
                seq_label = ""
                sub_name = ""
                if len(entry) >= 5 and nav_key in ("combined_perm", "combined_trigger"):
                    raw_seq = entry[4]
                    seq_label = str(raw_seq) if str(raw_seq).isdigit() else raw_seq
                if len(entry) >= 6:
                    sub_name = entry[5] or ""
                items.append((name, value, item_src, nav_key, seq_label, sub_name))
        elif isinstance(data, dict):
            if 'base_atk' in data:
                for n, v in [
                    ("角色基础攻击力", data['base_atk']),
                    ("武器基础攻击力", data['weapon_base_atk']),
                    ("角色基础生命值", data['base_hp']),
                    ("角色基础防御力", data['base_def']),
                ] + ([("武器附加" + data['weapon_bonus'][0], data['weapon_bonus'][1])]
                     if data.get('weapon_bonus') else []):
                    items.append((n, v, src_label, nav_key, "", ""))
            elif 'main_stat' in data:
                ms_name, ms_val = data['main_stat']
                fs_name, fs_val = data['fixed_stat']
                for n, v in [(f"[声骸]主词条-{ms_name}", ms_val),
                             (f"[声骸]固定词条-{fs_name}", fs_val)] + \
                             [(f"[声骸]副词条-{ss_name}", ss_val)
                              for ss_name, ss_val, *_ in data['sub_stats']]:
                    items.append((n, v, src_label, nav_key, "", ""))
    if echo_pages:
        for ei, (eid, scroll) in enumerate(echo_pages.items(), 1):
            if eid in HIDDEN_ECHO_IDS:
                continue
            ep = scroll.widget()
            data = ep.collect_data()
            src_label = f"声骸{ep.cost}费"
            nav_key = f"echo_{eid}"
            ms_name, ms_val = data['main_stat']
            items.append((f"[声骸]主词条-{ms_name}", ms_val, src_label, nav_key,
                          f"{ei}号声骸主词", ""))
            fs_name, fs_val = data['fixed_stat']
            items.append((f"[声骸]固定词条-{fs_name}", fs_val, src_label, nav_key,
                          f"{ei}号声骸固词", ""))
            for si, (ss_name, ss_val, *_) in enumerate(data['sub_stats'], 1):
                items.append((f"[声骸]副词条-{ss_name}", ss_val, src_label, nav_key,
                              f"{ei}号声骸副词{si}", ""))
    for _i, _it in enumerate(items):
        if len(_it) < 6:
            msg = f"_collect_all_items tuple too short (len={len(_it)} != 6): {_it}"
            try:
                from error_handler.error_system import _add_log_entry
                _add_log_entry("WARNING", msg, f"item {_i}: padded to 6-tuple")
            except Exception:
                pass
            # pad to 6-tuple instead of crashing
            items[_i] = (*_it, *([""] * (6 - len(_it))))
    return items


# ==================== 存档管理器 ====================

class SaveManager:
    """存档管理器. 收集/恢复全局状态, 序列化到 JSON. 含预设存档支持."""
    """集中管理应用状态的序列化与反序列化"""

    @staticmethod
    def ensure_save_dir():
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)

    @staticmethod
    def list_saves():
        """返回 ./save/ 中所有 .json 文件按修改时间降序排列"""
        SaveManager.ensure_save_dir()
        files = [f for f in os.listdir(SAVE_DIR) if f.endswith(".json")]
        paths = [os.path.join(SAVE_DIR, f) for f in files]
        paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return paths

    @staticmethod
    def collect_full_state(ms):
        """从 MainScreen 实例采集全部用户可编辑状态"""
        state = {
            "version": SAVE_FILE_VERSION,
            "app": "WWDmgCalc",
            "timestamp": datetime.now().isoformat(),
            "name": "",
            "theme": ms.window().current_theme if ms.window() else "dark",
            "pages": {}
        }
        pages = state["pages"]

        # CharBasePage
        cb = ms.page_char_base
        wb = None
        for cbox, spin, ul in cb.checkbox_group:
            if cbox.isChecked():
                wb = [cbox.text(), spin.value()]
                break
        pages["char_base"] = {
            "base_hp": cb.hp_spin.value(),
            "base_atk": cb.atk_spin.value(),
            "base_def": cb.def_spin.value(),
            "weapon_base_atk": cb.weapon_base_atk.value(),
            "weapon_bonus": wb,
        }

        # BaseTableAttrPage 子类（含 CombinedEntryPage、EnemyDefensePage）
        for key in ["combined_perm", "combined_trigger", "enemy_defense"]:
            pw = ms._scrolls[key].widget()
            rows = []
            for i, rd in enumerate(pw._rows):
                row_data = {
                    "name": rd["name_edit"].text(),
                    "value": rd["value_spin"].value(),
                    "locked": rd["locked"],
                    "seq": i + 1
                }
                # CombinedEntryPage 行自带来源标签和副名称
                src = rd.get("source", "")
                if src:
                    row_data["source"] = src
                sub = rd.get("sub_name_edit", None)
                if sub and sub.text().strip():
                    row_data["sub_name"] = sub.text().strip()
                rows.append(row_data)
            page_state = {"rows": rows, "counter": pw._counter}
            if key == "enemy_defense":
                page_state["disabled_items"] = [list(it) for it in pw._disabled_items]
                page_state["timing_filters"] = dict(pw._timing_filters)
                page_state["view_skill"] = pw._view_skill
                page_state["char_level"] = pw.char_level.value()
                page_state["enemy_level"] = pw.enemy_level.value()
            pages[key] = page_state

        # EnemyResistancePage
        er = ms.page_enemy_resistance
        spins = {}
        for (row, col), spin in er._spins.items():
            spins[f"{row},{col}"] = spin.value()
        boosts = {t: cb.isChecked() for t, cb in er._boost_checks.items()}
        pages["enemy_resistance"] = {
            "spins": spins,
            "boost_checks": boosts,
            "trigger_states": dict(er._trigger_states),
            "current_preset": er._current_preset,
        }

        # EchoCounterPage
        ec = ms.page_echo_counter
        pages["echo_counter"] = {
            "echoes": [list(e) for e in ec.echoes],
            "echo_id_counter": ec.echo_id_counter,
        }

        # EchoPages (动态)
        ep_state = {}
        for eid, scroll in ms.echo_pages.items():
            ep = scroll.widget()
            subs = []
            for i in range(ep.sub_list.count()):
                w = ep.sub_list.itemWidget(ep.sub_list.item(i))
                if w:
                    subs.append({
                        "name": w.name_edit.text(),
                        "value": w.value_spin.value(),
                        "locked": w.locked,
                    })
            ep_state[str(eid)] = {
                "cost": ep.cost,
                "echo_id": ep.echo_id,
                "main_stat": [ep.main_combo.currentText(), ep.main_value.value()],
                "main_locked": ep.main_lock_btn.text() == "解锁",
                "sub_stats": subs,
            }
        pages["echo_pages"] = ep_state

        # ResultPage 筛选状态
        rp = ms.page_result
        pages["result"] = {
            "base_mult": rp.base_mult.value(),
            "mult_increase": rp._gather_mult_data()[0] if hasattr(rp, '_gather_mult_data') else [],
            "mult_boosts": rp._gather_mult_data()[1] if hasattr(rp, '_gather_mult_data') else [],
            "filter_basis_idx": rp.filter_basis.currentIndex(),
            "filter_element_idx": rp.filter_element.currentIndex(),
            "filter_skill_idx": rp.filter_skill.currentIndex(),
            "filter_effect_idx": rp.filter_effect.currentIndex(),
            "auto_compute": rp._auto_compute,
        }

        # IndepZonePage
        pages["summary_indep"] = ms.page_indep_zone.collect_data()

        # ResonanceBuffPage
        pages["chain_buff"] = {
            "items": ms.page_resonance_buff.get_items(),
        }

        # KeywordAssociationPage
        pages["keyword_assoc"] = {
            "items": ms.page_keyword_assoc.get_items(),
            "counter": ms.page_keyword_assoc._counter,
            "chain_counter": ms.page_keyword_assoc._chain_counter,
        }

        # ResultListPage
        pages["result_list"] = {
            "items": ms.page_result_list.collect_data(),
            "auto_update": ms.page_result_list._auto_update,
        }

        # 持久化基础数值覆盖状态
        state["base_override_enabled"] = ms._base_override_enabled
        state["base_override_value"] = ms._base_override_value

        # 持久化隐藏/锁定状态（key 为 (name, src_label, nav_key) 三元组）
        _hidden_out = []
        for k in HIDDEN_ITEMS:
            if len(k) >= 3:
                _hidden_out.append([k[0], "" if len(k) < 4 else k[1], k[1] if len(k) == 3 else k[2], k[-1]])
        state["hidden_items"] = _hidden_out
        state["locked_items"] = []  # LOCKED_SUMMARY_ITEMS removed, keep compat
        state["hidden_echo_ids"] = list(HIDDEN_ECHO_IDS)

        return state

    @staticmethod
    def save_to_file(state, filepath):
        from preset_manager import _round_floats
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(_round_floats(state), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_from_file(filepath):
        if not os.path.exists(filepath):
            return None, f"文件不存在: {filepath}"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                state = json.load(f)
        except json.JSONDecodeError as e:
            return None, f"文件格式错误（非有效JSON）: {e}"
        except Exception as e:
            _logger.warning("存档读取失败 (%s): %s", filepath, e)
            return None, f"读取文件失败: {e}"
        if not isinstance(state, dict):
            return None, "存档根结构无效"
        if state.get("app") != "WWDmgCalc":
            return None, "并非鸣潮计算器存档文件"
        version = state.get("version", 0)
        if version > SAVE_FILE_VERSION:
            return None, f"存档版本 {version} 高于当前支持版本 {SAVE_FILE_VERSION}"
        if "pages" not in state:
            return None, "存档缺少 pages 字段"
        return state, None

    @staticmethod
    def apply_state(ms, state):
        """从状态字典恢复整个应用"""
        pages = state.get("pages", {})

        # 0. 恢复隐藏/锁定状态（兼容旧 2 元素和新 3 元素格式）
        HIDDEN_ITEMS.clear()
        for entry in state.get("hidden_items", []):
            if len(entry) >= 3:
                HIDDEN_ITEMS.add((entry[0], entry[2], entry[3]))  # 3元组: name, nav_key, seq
            elif len(entry) == 2:
                HIDDEN_ITEMS.add((entry[0], entry[1], ""))
        LOCKED_SUMMARY_ITEMS.clear()
        for entry in state.get("locked_items", []):
            if len(entry) >= 4:
                LOCKED_SUMMARY_ITEMS.add((entry[0], entry[1], entry[2], entry[3]))
            elif len(entry) == 3:
                LOCKED_SUMMARY_ITEMS.add((entry[0], entry[1], entry[2], ""))
            elif len(entry) == 2:
                LOCKED_SUMMARY_ITEMS.add((entry[0], entry[1], "", ""))
        HIDDEN_ECHO_IDS.clear()
        HIDDEN_ECHO_IDS.update(state.get("hidden_echo_ids", []))

        # 1. 清除现有声骸页
        for eid in list(ms.echo_pages.keys()):
            ms._remove_echo(eid)

        # 1. CharBasePage
        cb = pages.get("char_base", {})
        if cb:
            ms.page_char_base.hp_spin.setValue(cb.get("base_hp", 0))
            ms.page_char_base.atk_spin.setValue(cb.get("base_atk", 0))
            ms.page_char_base.def_spin.setValue(cb.get("base_def", 0))
            ms.page_char_base.weapon_base_atk.setValue(cb.get("weapon_base_atk", 0))
            wb = cb.get("weapon_bonus")
            if wb and len(wb) == 2:
                wb_type, wb_val = wb
                for cbox, spin, ul in ms.page_char_base.checkbox_group:
                    if cbox.text() == wb_type:
                        cbox.setChecked(True)
                        spin.setValue(wb_val)
                        break

        # 2. 恢复所有 BaseTableAttrPage 子类
        for key in ["combined_perm", "combined_trigger", "enemy_defense"]:
            pw = ms._scrolls[key].widget()
            SaveManager._restore_table_page(pw, pages.get(key, {}))
            if key == "enemy_defense":
                ed = pw
                ps = pages.get(key, {})
                ed.char_level.setValue(ps.get("char_level", 90))
                ed.enemy_level.setValue(ps.get("enemy_level", 100))
                ed._pending_disabled = ps.get("disabled_items", [])
                ed._pending_timing_filters = ps.get("timing_filters", {})
                ed._pending_view_skill = ps.get("view_skill", None)

        # 3. EnemyResistancePage
        er_data = pages.get("enemy_resistance", {})
        if er_data:
            erp = ms.page_enemy_resistance
            for key_str, val in er_data.get("spins", {}).items():
                r, c = key_str.split(",")
                row, col = int(r), int(c)
                if (row, col) in erp._spins:
                    erp._spins[(row, col)].setValue(val)
            for t, checked in er_data.get("boost_checks", {}).items():
                if t in erp._boost_checks:
                    erp._boost_checks[t].setChecked(checked)
            erp._pending_trigger_states = er_data.get("trigger_states", {})
            erp._current_preset = er_data.get("current_preset")

        # 4. EchoCounterPage — 先恢复计数器，再创建声骸页
        ec = pages.get("echo_counter", {})
        if ec:
            ms.page_echo_counter.echo_id_counter = ec.get("echo_id_counter", 0)

        # 5. 创建 EchoPages
        ep_data = pages.get("echo_pages", {})
        for eid_str, eps in sorted(ep_data.items(), key=lambda x: int(x[0])):
            SaveManager._create_echo_page(ms, eps["cost"], eps["echo_id"], eps)

        # 6. EchoCounterPage echoes 列表
        if ec:
            ms.page_echo_counter.echoes = [tuple(e) for e in ec.get("echoes", [])]
            ms.page_echo_counter._rebuild_echo_list()
            ms.page_echo_counter._update_status()

        # 7. ResultPage 筛选状态
        rp_data = pages.get("result", {})
        if rp_data:
            rp = ms.page_result
            rp.base_mult.setValue(rp_data.get("base_mult", 100.0))
            # 倍率值由关键词关联驱动，加载后 _sync_mult_entries() 自动从关键词关联填充表格
            rp.filter_basis.setCurrentIndex(rp_data.get("filter_basis_idx", 0))
            rp.filter_element.setCurrentIndex(rp_data.get("filter_element_idx", 0))
            rp.filter_skill.setCurrentIndex(rp_data.get("filter_skill_idx", 0))
            rp.filter_effect.setCurrentIndex(rp_data.get("filter_effect_idx", 0))

        # 8. IndepZonePage
        indep_data = pages.get("summary_indep", [])
        if indep_data:
            ms.page_indep_zone.apply_data(indep_data)

        # 9. ResultListPage（兼容旧版列表格式和新版字典格式）
        rl_data = pages.get("result_list", {})
        if isinstance(rl_data, list):
            ms.page_result_list.apply_data(rl_data)
        elif isinstance(rl_data, dict) and rl_data.get("items") is not None:
            ms.page_result_list.apply_data(rl_data["items"])
            ms.page_result_list._auto_update = rl_data.get("auto_update", False)
            ms.page_result_list._apply_auto_update_button_style()
        elif rl_data:
            ms.page_result_list.apply_data(rl_data)

        # 9b. 恢复关键词关联页面
        kw_data = pages.get("keyword_assoc", {})
        if kw_data:
            items = kw_data.get("items", [])
            # 只统计无 seq 的条目（这些会走 add_effect 递增计数器）
            no_seq_items = [it for it in items if not it.get("seq", "")]
            no_seq_manual = sum(1 for it in no_seq_items if it.get("source", "关联效果") != "共鸣链效果")
            no_seq_chain = len(no_seq_items) - no_seq_manual
            ms.page_keyword_assoc._counter = max(0, kw_data.get("counter", 0) - no_seq_manual)
            ms.page_keyword_assoc._chain_counter = max(0, kw_data.get("chain_counter", 0) - no_seq_chain)
            for item in items:
                seq = item.get("seq", "")
                source = item.get("source", "关联效果")
                if seq:
                    ms.page_keyword_assoc.add_effect_with_seq(
                        item.get("name", ""), item.get("value", 0),
                        item.get("eff_type", "常驻"),
                        source,
                        item.get("sub_name", ""), item.get("keywords", ""),
                        seq_text=seq)
                elif source == "共鸣链效果":
                    # 旧存档无 seq，来源为共鸣链，用 chain_prefix 生成正确格式
                    ms.page_keyword_assoc.add_effect(
                        item.get("name", ""), item.get("value", 0),
                        item.get("eff_type", "常驻"),
                        source,
                        item.get("sub_name", ""), item.get("keywords", ""),
                        chain_prefix="共鸣链")
                else:
                    ms.page_keyword_assoc.add_effect(
                        item.get("name", ""), item.get("value", 0),
                        item.get("eff_type", "常驻"),
                        source,
                        item.get("sub_name", ""), item.get("keywords", ""),
                    )

        # 9c. 恢复共鸣链增益页面
        cb_data = pages.get("chain_buff", {})
        if cb_data:
            for item in cb_data.get("items", []):
                # 更新已有共鸣链项（按 id 匹配）
                for existing in ms.page_resonance_buff._items:
                    if existing["id"] == item.get("id"):
                        existing["name"] = item.get("name", existing["name"])
                        existing["enabled"] = item.get("enabled", True)
                        existing["effects"] = item.get("effects", [])
                        existing["intro"] = item.get("intro", "")
                        break
            ms.page_resonance_buff._refresh_cards()

        # 9d. 恢复 ResultPage._auto_compute 状态
        if rp_data:
            if rp_data.get("auto_compute", False) and not ms.page_result._auto_compute:
                ms.page_result._toggle_auto_compute()

        # 9. 重建导航树
        ms._sort_echo_nav()

        # 10. 重新连线所有跨页数据流（关键步骤）
        SaveManager._rebuild_bindings(ms)

        # 11. 恢复 trigger_states（必须在 _rebuild_bindings 之后）
        # 11. 恢复防御页状态（必须在 _rebuild_bindings 之后）
        ed_page = ms._scrolls["enemy_defense"].widget()
        if hasattr(ed_page, "_pending_disabled"):
            ed_page._disabled_items = {tuple(it) for it in ed_page._pending_disabled}
            del ed_page._pending_disabled
        if hasattr(ed_page, "_pending_timing_filters"):
            ed_page._timing_filters.update(ed_page._pending_timing_filters)
            del ed_page._pending_timing_filters
        if hasattr(ed_page, "_pending_view_skill"):
            ed_page._view_skill = ed_page._pending_view_skill
            del ed_page._pending_view_skill
            if hasattr(ed_page, "_refresh_view_chips"):
                ed_page._refresh_view_chips()
        ed_page.recalc()

        er_page = ms.page_enemy_resistance
        if hasattr(er_page, '_pending_trigger_states'):
            er_page._recalc()
            for key, val in er_page._pending_trigger_states.items():
                er_page._trigger_states[key] = val
            del er_page._pending_trigger_states
            er_page._recalc()  # 用恢复后的 trigger_states 重新计算

        # 12. 不再恢复存档中的主题，保持当前主题不变

        # 12b. 恢复基础数值覆盖状态
        ms._base_override_enabled = state.get("base_override_enabled", False)
        ms._base_override_value = state.get("base_override_value", 0.0)
        ms.page_result.set_base_override(ms._base_override_enabled, ms._base_override_value)
        ms.page_result_list.set_base_override(ms._base_override_enabled, ms._base_override_value)
        ms.base_adj_btn.setText("基础数值调整 ✓" if ms._base_override_enabled else "基础数值调整")
        ms.base_adj_btn.setProperty("active", ms._base_override_enabled)
        ms.base_adj_btn.style().unpolish(ms.base_adj_btn)
        ms.base_adj_btn.style().polish(ms.base_adj_btn)
        # 若弹窗已打开，同步其状态
        if ms._base_override_dialog is not None:
            current_base = 0.0
            last = getattr(ms.page_result, '_last_computed', None)
            if last:
                current_base = last.get('computed_base_zone', 0.0)
            ms._base_override_dialog.reset_state(
                ms._base_override_enabled, ms._base_override_value, current_base
            )
        # 若启用覆盖，触发重算使覆盖值生效
        if ms._base_override_enabled:
            ms.page_result.auto_compute()
            ms.page_result_list.recalc()

        # 13. 更新错误日志按钮状态
        ms._update_error_log_btn()

        # 14. 导航到安全落地页
        ms._navigate_to_key("char_base")

    @staticmethod
    def _restore_table_page(page, state):
        """从状态恢复一个 BaseTableAttrPage（含 CombinedEntryPage）"""
        old_cb = page._on_change_cb
        page._on_change_cb = None
        rows = state.get("rows", [])
        # 清空现有行
        while page._rows:
            rd = page._rows[0]
            rd["locked"] = False
            page._delete_row(rd)
        page._counter = state.get("counter", 0)
        for rd in rows:
            page._counter = max(page._counter, rd.get("seq", 0))
            src = rd.get("source", "")
            if src and hasattr(page, '_add_row_with_source'):
                page._add_row_with_source(rd["name"], rd["value"], rd["seq"], src)
            else:
                page._add_row(rd["name"], rd["value"], rd["seq"])
            # 恢复副名称
            sub = rd.get("sub_name", "")
            if sub and page._rows:
                last = page._rows[-1]
                if 'sub_name_edit' in last:
                    last['sub_name_edit'].setText(sub)
            if rd.get("locked", False):
                page._toggle_lock(page._rows[-1])
        page._on_change_cb = old_cb
        if old_cb:
            old_cb()

    @staticmethod
    def _create_echo_page(ms, cost, echo_id, ep_state):
        """从状态创建单个 EchoPage 及其滚动包装"""
        page = EchoPage(cost, echo_id)
        page._navigate_summary = ms._navigate_to_key
        page._summary_pages = {
            "summary_base": ms.page_summary_base,
            "summary_bonus": ms.page_summary_bonus,
            "summary_deepen": ms.page_summary_deepen,
            "summary_crit": ms.page_summary_crit,
        }
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ms.content_stack.addWidget(scroll)
        ms.echo_pages[echo_id] = scroll

        # 恢复主词条
        main_stat = ep_state.get("main_stat", ["", 0.0])
        if main_stat[0]:
            idx = page.main_combo.findText(main_stat[0])
            if idx >= 0:
                page.main_combo.setCurrentIndex(idx)
            else:
                page.main_combo.lineEdit().setText(main_stat[0])
        page.main_value.setValue(main_stat[1])

        if ep_state.get("main_locked", False):
            page._toggle_main_lock()

        # 恢复副词条
        page._on_change_cb = None
        for ss in ep_state.get("sub_stats", []):
            page._add_sub_stat_direct(ss["name"], ss["value"])
            if ss.get("locked", False):
                last_item = page.sub_list.item(page.sub_list.count() - 1)
                if last_item:
                    w = page.sub_list.itemWidget(last_item)
                    if w:
                        w._toggle_lock()
        page._on_change_cb = None  # 稍后由 _rebuild_bindings 设置

    @staticmethod
    def _rebuild_bindings(ms):
        """重新建立所有跨页数据流绑定"""
        # Defense sources
        defense_source_pages = [
            ("综合常驻数值", ms.page_combined_perm, "combined_perm", "常驻"),
            ("综合触发数值", ms.page_combined_trigger, "combined_trigger", "触发"),
        ]
        ms.page_enemy_defense.set_external_sources(defense_source_pages)
        ms.page_enemy_defense.navigate_requested = ms._navigate_to_key

        # Resistance sources
        resistance_source_pages = [
            ("综合常驻数值", ms.page_combined_perm, "combined_perm", "常驻"),
            ("综合触发数值", ms.page_combined_trigger, "combined_trigger", "触发"),
        ]
        ms.page_enemy_resistance.set_external_sources(resistance_source_pages)
        ms.page_enemy_resistance.navigate_requested = ms._navigate_to_key

        # — 建立防回调嵌套的稳定回调（每次 _rebuild_bindings 直接覆盖，不累积嵌套） —
        _summary_pages = [ms.page_summary_base, ms.page_summary_bonus,
                          ms.page_summary_deepen, ms.page_summary_crit]

        all_source_pages = set()
        for _, page, _, _ in defense_source_pages + resistance_source_pages:
            all_source_pages.add(page)

        def _make_source_cb(de, er, rp, rl, sps):
            def _cb():
                de.recalc()
                er._recalc()
                for sp in sps:
                    sp.recalc()
                rp.compute()
                rl._update_all()
            return _cb

        combined_cb = _make_source_cb(
            ms.page_enemy_defense, ms.page_enemy_resistance,
            ms.page_result, ms.page_result_list, _summary_pages)
        for page in all_source_pages:
            page._on_change_cb = combined_cb

        # CharBasePage → summaries + result + result_list
        def _make_char_cb(rp, rl, sps):
            def _cb():
                for sp in sps:
                    sp.recalc()
                rp.compute()
                rl._update_all()
            return _cb
        ms.page_char_base._on_change_cb = _make_char_cb(
            ms.page_result, ms.page_result_list, _summary_pages)

        # CombinedEntryPage — 使用上面的 combined_cb
        ms.page_combined_perm._on_change_cb = combined_cb
        ms.page_combined_trigger._on_change_cb = combined_cb

        # Summary sources
        combined_cb = _make_source_cb(
            ms.page_enemy_defense, ms.page_enemy_resistance,
            ms.page_result, ms.page_result_list, _summary_pages)
        ms.page_combined_perm._on_change_cb = combined_cb
        ms.page_combined_trigger._on_change_cb = combined_cb

        # EnemyDefensePage / EnemyResistancePage 内部修改直接触发自动计算
        def _make_defense_resistance_cb():
            for sp in _summary_pages:
                sp.recalc()
            ms.page_result.compute()
            ms.page_result_list.recalc()
        ms.page_enemy_defense._on_change_cb = _make_defense_resistance_cb
        ms.page_enemy_resistance._on_change_cb = _make_defense_resistance_cb

        # Summary sources
        summary_source_pages = [
            ("角色武器", ms.page_char_base, "char_base"),
            ("综合常驻数值", ms.page_combined_perm, "combined_perm"),
            ("综合触发数值", ms.page_combined_trigger, "combined_trigger"),
        ]
        for sp in [ms.page_summary_base, ms.page_summary_bonus,
                    ms.page_summary_deepen, ms.page_summary_crit]:
            sp.set_external_sources(summary_source_pages)
            sp.set_echo_sources(ms.echo_pages)
            sp._navigate = ms._navigate_to_key

        # Result page
        ms.page_result.set_external_sources(summary_source_pages)
        ms.page_result.set_echo_sources(ms.echo_pages)
        ms.page_result.set_defense_page(ms.page_enemy_defense)
        ms.page_result.set_resistance_page(ms.page_enemy_resistance)
        ms.page_result.set_indep_zone_page(ms.page_indep_zone)
        ms.page_result.set_keyword_assoc_page(ms.page_keyword_assoc)
        ms.page_result._navigate = ms._navigate_to_key
        ms.page_result._summary_pages = {
            "summary_base": ms.page_summary_base,
            "summary_bonus": ms.page_summary_bonus,
            "summary_deepen": ms.page_summary_deepen,
            "summary_crit": ms.page_summary_crit,
        }
        ms.page_result.set_result_list_page(ms.page_result_list)

        # Result list page
        ms.page_result_list.set_external_sources(summary_source_pages)
        ms.page_result_list.set_echo_sources(ms.echo_pages)
        ms.page_result_list.set_defense_page(ms.page_enemy_defense)
        ms.page_result_list.set_resistance_page(ms.page_enemy_resistance)
        ms.page_result_list.set_indep_zone_page(ms.page_indep_zone)
        ms.page_result_list._navigate = ms._navigate_to_key
        ms.page_result_list.set_result_page(ms.page_result)

        # Indep zone callback
        ms.page_indep_zone._on_change_cb = lambda: (
            ms.page_result.auto_compute(),
            ms.page_result_list.recalc()
        )

        # Echo page callbacks
        for eid, scroll in ms.echo_pages.items():
            scroll.widget()._on_change_cb = ms._refresh_echo_sources
        ms._refresh_echo_sources()


# ==================== 快速加载弹窗 ====================

class QuickLoadDialog(QDialog):
    """列出 ./save/ 中的存档文件供选择加载"""
    def __init__(self, parent=None, title="选择存档加载"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(420, 380)
        self.selected_path = None
        _center_window(self)


        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        load_btn = QPushButton("加载")
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.clicked.connect(self._on_load)
        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(load_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._populate()

    def _populate(self):
        user_saves = SaveManager.list_saves()
        if not user_saves:
            item = QListWidgetItem("（暂无存档文件）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_widget.addItem(item)
            return
        for path in user_saves:
            name = os.path.splitext(os.path.basename(path))[0]
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            item = QListWidgetItem(f"{name}  ({mtime.strftime('%Y-%m-%d %H:%M')})")
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.list_widget.addItem(item)

    def _on_load(self):
        current = self.list_widget.currentItem()
        if current:
            path = current.data(Qt.ItemDataRole.UserRole)
            if path:
                self.selected_path = path
                self.accept()


# ==================== 通用总结页基类 ====================

from summary_pages import SummaryBaseZonePage, SummaryBonusZonePage, SummaryDeepenZonePage, SummaryCritZonePage
from summary_pages import inject_dependencies as _inject_summary_deps
_inject_summary_deps(fix_table_height, _place_highlight_overlay, CombinedEntryPage, _collect_all_items, PropTable, cell_center, CONSTANT_ATTRS)
# _make_sub_name_cell 在下方定义，通过 setter 延迟注入

from indep_zone import IndepZonePage
from preset_manager import PresetManager
from preset_builder import PresetBuilderDialog
from preset_loader import PresetLoaderDialog
# ==================== 计算用共享常量与工具函数 ====================

ELEMENTS = ["(无)", "冷凝", "热熔", "气动", "导电", "衍射", "湮灭"]
SKILL_TYPES = ["(无)", "普攻", "重击", "共鸣技能", "共鸣解放", "变奏技能", "声骸技能"]
EFFECTS = ["(无)", "光噪", "风蚀", "虚湮", "聚爆", "霜渐", "电磁"]
EFFECT_TYPES = ["常驻", "触发"]
DAMAGE_CATEGORIES = ["常态攻击", "共鸣技能", "共鸣回路", "共鸣解放", "变奏技能"]

ELEMENT_NAMES_SET = {"冷凝", "热熔", "气动", "导电", "衍射", "湮灭"}
SKILL_TYPE_NAMES_SET = {"普攻", "重击", "共鸣技能", "共鸣解放", "变奏技能", "声骸技能"}
EFFECT_NAMES_SET = {"光噪", "风蚀", "虚湮", "聚爆", "霜渐", "电磁"}


def _matches_filter(item_name, selected_element, selected_skill, selected_effect):
    """Check if an item should be included based on filter selection.

    委托给 damage_calc.matches_filter（供主程序和测试共用同一实现）。
    """
    return damage_calc.matches_filter(item_name, selected_element, selected_skill, selected_effect)


class ResonanceBuffPage(QWidget):
    """共鸣链增益页面 —— 卡片式布局，默认6个共鸣链"""

    _BTN_STYLE = (
        "QPushButton {{ color: {}; background: {}; "
        "border: 1px solid {}; border-radius: 4px; padding: 3px 8px; font-size: 14px; }}"
        "QPushButton:hover {{ background: {}; }}"
    )

    def __init__(self, main_screen=None):
        super().__init__()
        self._main_screen = main_screen  # 主界面引用
        self._prefix = ""  # 共鸣链前缀名称
        self._items = []  # 6个共鸣链数据
        self._cards = []

        # 初始化6个默认共鸣链
        for i in range(1, 7):
            self._items.append({
                "id": i,
                "name": f"共鸣链{i}",
                "enabled": False,
                "effects": [],
                "intro": "",
            })

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 主标题
        title = QLabel("共鸣链增益")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # 副标题 + 命名按钮
        desc_row = QHBoxLayout()
        desc = QLabel("管理角色的共鸣链增益效果，每个共鸣链可独立启用/禁用，也可自行添加其效果关联。")
        desc.setObjectName("labelSecondary")
        desc.setWordWrap(True)
        desc_row.addWidget(desc, stretch=1)

        name_btn = QPushButton("命名")
        name_btn.setObjectName("addButton")
        name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        name_btn.clicked.connect(self._name_chains)
        desc_row.addWidget(name_btn)
        layout.addLayout(desc_row)

        # 卡片滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(self._cards_container)
        layout.addWidget(scroll, stretch=1)

        self._refresh_cards()

    def _name_chains(self):
        """命名所有共鸣链"""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "命名共鸣链", "请输入当前共鸣链的角色名称:")
        if ok and name.strip():
            self._prefix = name.strip()
            for i, item in enumerate(self._items):
                item["name"] = f"{self._prefix}的共鸣链{i + 1}"
            self._refresh_cards()

    def _refresh_cards(self):
        # 立即隐藏并清理旧卡片（deleteLater 是异步的，必须先 hide 避免重叠）
        while self._cards_layout.count():
            child = self._cards_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif child.layout() is not None:
                # 清理 QHBoxLayout 行
                row_layout = child.layout()
                while row_layout.count():
                    sub = row_layout.takeAt(0)
                    sw = sub.widget()
                    if sw is not None:
                        sw.hide()
                        sw.setParent(None)
                        sw.deleteLater()
                row_layout.setParent(None)
                row_layout.deleteLater()
        self._cards.clear()

        cols = 2
        for i in range(0, len(self._items), cols):
            row_layout = QHBoxLayout()
            row_layout.setSpacing(12)
            for j in range(cols):
                idx = i + j
                if idx < len(self._items):
                    card = self._build_card(self._items[idx])
                    self._cards.append(card)
                    row_layout.addWidget(card, stretch=1)
                else:
                    row_layout.addStretch(1)
            self._cards_layout.addLayout(row_layout)

        self._cards_layout.addStretch(1)

    def _build_card(self, item):
        card = QFrame()
        card.setObjectName("resultCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setMinimumHeight(280)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # 第一行：标题
        name_lbl = QLabel(item["name"])
        name_lbl.setObjectName("resultHeader")
        layout.addWidget(name_lbl)

        # 第二行：通用增益数量（常驻 + 触发）
        effects = item.get("effects", [])
        general_count = sum(1 for e in effects if e.get("type") in ("常驻", "触发"))
        general_lbl = QLabel(f"通用增益：{general_count} 条")
        general_lbl.setObjectName("labelSecondary")
        layout.addWidget(general_lbl)

        # 第三行：特定增益数量
        specific_count = sum(1 for e in effects if e.get("type") == "特定")
        specific_lbl = QLabel(f"特定增益：{specific_count} 条")
        specific_lbl.setObjectName("labelSecondary")
        layout.addWidget(specific_lbl)

        # 第四到七行：介绍文本框（只读，可选中复制，上下滚动）
        intro_text = item.get("intro", "")
        intro_edit = QTextEdit()
        intro_edit.setObjectName("nameEdit")
        intro_edit.setReadOnly(True)
        intro_edit.setPlainText(intro_text if intro_text else "（暂无介绍，点击展开按钮进行编辑）")
        intro_edit.setMinimumHeight(80)
        intro_edit.setMaximumHeight(120)
        intro_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        intro_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        intro_edit.setStyleSheet(
            "QTextEdit { font-size: 12px; color: #aaa; background: transparent; "
            "border: 1px solid rgba(128,128,128,0.2); border-radius: 4px; padding: 4px; }"
        )
        layout.addWidget(intro_edit, stretch=1)

        # 第三行：按钮
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        # 启用/关闭按钮 — 启用中=「关闭」柔和色，未启用=「启用」暖橙色
        enable_btn = QPushButton("关闭" if item.get("enabled", True) else "启用")
        enable_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if item.get("enabled", True):
            ec, ebc, ebd, ehv = ("#546e7a", "rgba(84,110,122,0.08)", "rgba(84,110,122,0.20)", "rgba(84,110,122,0.14)")
        else:
            ec, ebc, ebd, ehv = ("#e65100", "rgba(255,152,0,0.06)", "rgba(255,152,0,0.18)", "rgba(255,152,0,0.14)")
        enable_btn.setStyleSheet(self._BTN_STYLE.format(ec, ebc, ebd, ehv))
        enable_btn.clicked.connect(lambda _, it=item, btn=enable_btn: self._toggle_enable(it, btn))
        btn_row.addWidget(enable_btn)

        # 展开按钮 — 绿色系
        ec2, ebc2, ebd2, ehv2 = ("#2e7d32", "rgba(76,175,80,0.10)", "rgba(76,175,80,0.25)", "rgba(76,175,80,0.20)")
        expand_btn = QPushButton("展开")
        expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        expand_btn.setStyleSheet(self._BTN_STYLE.format(ec2, ebc2, ebd2, ehv2))
        expand_btn.clicked.connect(lambda _, it=item: self._expand_chain(it))
        btn_row.addWidget(expand_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        return card

    def _expand_chain(self, item):
        # 复用已打开的弹窗
        existing = getattr(self, '_open_chain_dlg', None)
        if existing and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        dlg = ResonanceChainEditDialog(item, self, main_screen=self._main_screen)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.destroyed.connect(lambda: setattr(self, '_open_chain_dlg', None))
        self._open_chain_dlg = dlg
        dlg.finished.connect(self._refresh_cards)
        dlg.show()

    def _toggle_enable(self, item, btn):
        """切换启用/关闭状态"""
        item["enabled"] = not item.get("enabled", True)
        # 启用中 → 显示「关闭」(柔和蓝灰)，未启用 → 显示「启用」(暖橙)
        btn.setText("关闭" if item["enabled"] else "启用")
        if item["enabled"]:
            ec, ebc, ebd, ehv = ("#546e7a", "rgba(84,110,122,0.08)", "rgba(84,110,122,0.20)", "rgba(84,110,122,0.14)")
        else:
            ec, ebc, ebd, ehv = ("#e65100", "rgba(255,152,0,0.06)", "rgba(255,152,0,0.18)", "rgba(255,152,0,0.14)")
        btn.setStyleSheet(self._BTN_STYLE.format(ec, ebc, ebd, ehv))
        # 同步效果到综合填写和关键词关联页面
        self._sync_chain_to_pages(item)

    def _sync_indep_zones(self, item):
        """将 item 的 indep_zones 同步到主程序独立乘区页面"""
        ms = self._main_screen
        if ms is None:
            return
        indep_page = ms.page_indep_zone
        chain_tag = f"chain_{item['id']}"

        # 移除该链的旧独立乘区组
        to_remove = []
        for gd in indep_page._groups:
            frame = gd.get("frame")
            if frame and getattr(frame, "_chain_tag", "") == chain_tag:
                to_remove.append(frame)
        for frame in to_remove:
            indep_page._remove_group(frame)

        # 如果启用且有独立乘区，重新添加
        if not item.get("enabled"):
            return
        for iz_data in item.get("indep_zones", []):
            group_name = iz_data.get("group_name", "")
            values = iz_data.get("values", [])
            if not values:
                continue
            converted = [(v.get("name", ""), v.get("value", 0.0), v.get("hidden", False))
                         for v in values]
            indep_page._add_group(group_name, converted)
            # 给新组打上链标签，方便后续移除
            if indep_page._groups:
                frame = indep_page._groups[-1].get("frame")
                if frame:
                    frame._chain_tag = chain_tag

    def _trigger_downstream_recalc(self):
        """触发下游重算：数值总结 → 计算结果 → 结果列表"""
        ms = self._main_screen
        if ms is None:
            return
        if ms.page_combined_perm._on_change_cb:
            ms.page_combined_perm._on_change_cb()
        if ms.page_keyword_assoc._on_change_cb:
            ms.page_keyword_assoc._on_change_cb()

    def _sync_chain_to_pages(self, item):
        """启用时添加效果到综合填写和关键词关联页面，关闭时移除。"""
        if self._main_screen is None:
            return
        chain_num = item["id"]
        effects = item.get("effects", [])

        # 先移除该链的所有旧效果（传空集合 = 移除该 chain_num 的全部行）
        self._main_screen.page_keyword_assoc.remove_effects_by_chain(chain_num)
        self._main_screen.page_combined_perm.remove_effects_by_source_and_names(
            "共鸣链效果", set(), chain_num=chain_num)
        self._main_screen.page_combined_trigger.remove_effects_by_source_and_names(
            "共鸣链效果", set(), chain_num=chain_num)

        # 如果未启用或无效，移除旧行和独立乘区，再返回
        if not item.get("enabled", True) or not effects:
            self._sync_indep_zones(item)
            self._trigger_downstream_recalc()
            return

        for eff in effects:
            eff_type = eff.get("type", "常驻")
            page = (self._main_screen.page_combined_perm if eff_type == "常驻"
                   else self._main_screen.page_combined_trigger)
            page._counter += 1
            is_mult = "倍率增加" in eff["name"] or "倍率提升" in eff["name"]
            if not is_mult:
                page._add_row_with_source(eff["name"], eff["value"], page._counter, "共鸣链效果", chain_num=chain_num)
                if eff.get("sub_name") and page._rows:
                    last = page._rows[-1]
                    if 'sub_name_edit' in last:
                        last['sub_name_edit'].setText(eff["sub_name"])

        # 关键词关联：仅倍率效果送入，非倍率走综合填写
        kw_page = self._main_screen.page_keyword_assoc
        for idx, eff in enumerate(effects, 1):
            if "倍率" not in eff.get("name", ""):
                continue
            seq_text = f"共鸣链{chain_num}关联{idx}"
            kw_page.add_effect_with_seq(
                eff["name"], eff["value"], eff.get("type", "常驻"),
                eff.get("source", "共鸣链效果"), eff.get("sub_name", ""),
                eff.get("keywords", ""),
                seq_text)

        # 重排序列号（_counter 可能已有值，需对齐行数）
        self._main_screen.page_combined_perm._resequence()
        self._main_screen.page_combined_trigger._resequence()

        # 同步独立乘区到独立乘区页面
        self._sync_indep_zones(item)

        # 触发下游重算（综合填写→数值总结→计算结果→结果列表）
        self._trigger_downstream_recalc()

    def get_items(self):
        return self._items


# ==================== 数据流调试器 ====================

class _ColorLabel(QLabel):
    """带描边彩色文字的 QLabel，用于数据流 ID 列"""

    def __init__(self, text="", fill=None, stroke=None, parent=None):
        super().__init__(text, parent)
        self._fill = fill
        self._stroke = stroke
        self.setStyleSheet("background: transparent; border: none; font-size: 13px; padding-left: 4px;")

    def paintEvent(self, event):
        if not self._fill or not self._stroke:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        text_rect = self.rect().adjusted(4, 0, 0, 0)
        x = text_rect.x()
        y = text_rect.y() + text_rect.height() * 0.75
        # 用 QPainterPath 画柔和描边
        path = QPainterPath()
        path.addText(x, y, self.font(), self.text())
        painter.setPen(QPen(self._stroke, 1.2, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        # 主体
        painter.fillPath(path, self._fill)
        painter.end()


# ==================== 数据流调试器主类 ====================

class DataFlowViewerDialog(QDialog):
    """数据流调试器 —— 显示每条数据从上游→中游→下游的完整路径"""

    @staticmethod
    def _gen_colors(n):
        """生成 n 个视觉上可区分的颜色（HSV 均匀分布）"""
        colors = []
        for i in range(n):
            h = (i * 137.508) % 360  # 黄金角旋转，避免相邻色接近
            s = 180 + (i * 37) % 76  # 饱和度 180~255，保证鲜艳
            v = 200 + (i * 53) % 56  # 明度 200~255，保证暗色主题可见
            colors.append(QColor.fromHsv(int(h), int(s), int(v)))
        return colors

    def __init__(self, main_screen, parent=None):
        super().__init__(parent)
        self._ms = main_screen
        self.setWindowTitle("数据流调试器")
        self.setMinimumSize(1350, 800)
        self.resize(1350, 800)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        _center_window(self)
        theme = "dark"
        w = parent
        while w:
            if hasattr(w, 'current_theme'):
                theme = w.current_theme
                break
            w = w.parent() if hasattr(w, 'parent') else None
        self.setStyleSheet(build_stylesheet(theme))

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        # 标题栏
        top = QHBoxLayout()
        title = QLabel("每条数据从上游 → 中游 → 下游的完整路径")
        title.setObjectName("sectionTitle")
        top.addWidget(title)
        top.addStretch()
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("addButton")
        refresh_btn.setFixedWidth(70)
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        copy_btn = QPushButton("复制报告")
        copy_btn.setObjectName("addButton")
        copy_btn.setFixedWidth(80)
        copy_btn.clicked.connect(self._copy_report)
        top.addWidget(copy_btn)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("backButton")
        close_btn.setFixedWidth(70)
        close_btn.clicked.connect(self.close)
        top.addWidget(close_btn)
        root.addLayout(top)

        # 监测目标选择行
        monitor_row = QHBoxLayout()
        monitor_row.addWidget(QLabel("监测目标:"))
        self._monitor_combo = QComboBox()
        self._monitor_combo.setMinimumWidth(260)
        self._monitor_combo.setMaxVisibleItems(20)
        self._monitor_combo.currentIndexChanged.connect(self._on_target_changed)
        monitor_row.addWidget(self._monitor_combo)
        monitor_row.addSpacing(12)
        self._hide_filter_cb = QCheckBox("排除隐藏")
        self._hide_filter_cb.setChecked(True)
        self._hide_filter_cb.toggled.connect(self.refresh)
        monitor_row.addWidget(self._hide_filter_cb)
        monitor_row.addStretch()
        root.addLayout(monitor_row)

        # 树形视图
        self._tree = QTreeWidget()
        self._tree.setObjectName("dataFlowTree")
        self._tree.setHeaderLabels(["项目", "数值/条数", "分类", "序列号", "副名称/状态", "关键词关联"])
        self._tree.setColumnCount(6)
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # 默认列宽（溢出视口时可水平滚动）
        _default_widths = [350, 200, 160, 200, 200, 140]
        for i, w in enumerate(_default_widths):
            self._tree.header().resizeSection(i, w)
        self._tree.setAnimated(True)
        self._tree.setAllColumnsShowFocus(True)
        self._tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.viewport().installEventFilter(self)

        self._id_colors = {}
        self._stroke = QColor(255, 255, 255) if theme == "dark" else QColor(0, 0, 0)

        root.addWidget(self._tree, stretch=3)

        # 文本报告区（可复制，用于反馈不一致问题）
        self._report = QTextEdit()
        self._report.setReadOnly(True)
        self._report.setPlaceholderText('数据流报告（点击"复制报告"可复制全部内容）')
        self._report.setMaximumHeight(180)
        root.addWidget(self._report, stretch=1)

        self._report_lines = []  # collect plain-text lines during refresh
        self.refresh()

    # 列宽比例：项目/数值条数/分类/序列号/副名称状态
    _COL_RATIOS = [0.30, 0.20, 0.15, 0.20, 0.20]

    def _fit_columns(self):
        """窗口变宽时按比例扩展列宽；窗口窄时保持默认宽度（可水平滚动）"""
        avail = self._tree.header().width()
        if avail < 100:
            return
        # 当前列总宽
        cur_total = sum(self._tree.header().sectionSize(i) for i in range(5))
        # 仅当表头比当前列总宽更宽时才扩展
        if avail <= cur_total:
            return
        used = 0
        n = len(self._COL_RATIOS)
        for i, r in enumerate(self._COL_RATIOS):
            if i < n - 1:
                w = max(self._tree.header().sectionSize(i), int(avail * r))
                used += w
            else:
                w = max(self._tree.header().sectionSize(i), avail - used)
            self._tree.header().resizeSection(i, w)

    # 分类英文→中文
    _CAT_CN = {
        "base": "基础", "bonus": "加成", "deepen": "加深",
        "crit": "暴击", "crit_rate": "暴击率", "crit_dmg": "暴击伤害",
        "defense": "防御", "resistance": "抗性", "other": "其他",
    }

    def _on_target_changed(self, _idx):
        self.refresh()

    def refresh(self):
        self._tree.clear()
        ms = self._ms

        _counter = [0]
        def _nid():
            _counter[0] += 1
            return f"#{_counter[0]:03d}"

        self._id_colors = {}

        def _mk(parent, cols, uid=None):
            """创建 5 列节点，若有 uid 则给第 0 列设置带描边的彩色标签"""
            while len(cols) < 5:
                cols.append("")
            text0 = cols[0]
            if uid and uid in self._id_colors:
                cols[0] = ""
            it = QTreeWidgetItem(parent, cols)
            if uid and uid in self._id_colors:
                lbl = _ColorLabel(text0, self._id_colors[uid], self._stroke)
                self._tree.setItemWidget(it, 0, lbl)
            return it

        # 统一结构: (uid, name, value, source, nav_key, seq, sub_name, category)
        all_items = []

        # 角色武器
        char_data = ms.page_char_base.collect_data()
        for n, v in [
            ("角色基础攻击力", char_data.get('base_atk', 0)),
            ("武器基础攻击力", char_data.get('weapon_base_atk', 0)),
            ("角色基础生命值", char_data.get('base_hp', 0)),
            ("角色基础防御力", char_data.get('base_def', 0)),
        ] + ([("武器附加" + char_data['weapon_bonus'][0], char_data['weapon_bonus'][1])]
             if char_data.get('weapon_bonus') else []):
            all_items.append((_nid(), n, v, "角色武器", "char_base", "", "",
                              damage_calc.classify_item_category(n)))

        # 综合填写（常驻 + 触发）
        for page, key in [(ms.page_combined_perm, "combined_perm"),
                          (ms.page_combined_trigger, "combined_trigger")]:
            tp = "常驻" if key == "combined_perm" else "触发"
            for entry in page.collect_data():
                name, val = entry[0], entry[1]
                src = entry[3] if len(entry) >= 4 else ""
                seq = f"{tp}{entry[4]}" if len(entry) >= 5 else ""
                sub = entry[5] if len(entry) >= 6 and entry[5] else ""
                all_items.append((_nid(), name, val, src, key, seq, sub,
                                  damage_calc.classify_item_category(name)))

        # 声骸
        echo_pages = ms.echo_pages if hasattr(ms, 'echo_pages') else {}
        for eid, scroll in echo_pages.items():
            if eid in HIDDEN_ECHO_IDS:
                continue
            ep = scroll.widget()
            data = ep.collect_data()
            src = f"声骸{ep.cost}费"
            nk = f"echo_{eid}"
            ms_n, ms_v = data['main_stat']
            nm = f"[声骸]主词条-{ms_n}"
            all_items.append((_nid(), nm, ms_v, src, nk, "", "",
                              damage_calc.classify_item_category(nm)))
            fs_n, fs_v = data['fixed_stat']
            nm = f"[声骸]固定词条-{fs_n}"
            all_items.append((_nid(), nm, fs_v, src, nk, "", "",
                              damage_calc.classify_item_category(nm)))
            for si, (ss_n, ss_v, *_) in enumerate(data['sub_stats'], 1):
                nm = f"[声骸]副词条-{ss_n}"
                all_items.append((_nid(), nm, ss_v, src, nk, f"{eid}号副词{si}", "",
                                  damage_calc.classify_item_category(nm)))

        # 共鸣链效果（上游来源）
        chain_effect_map = {}
        if hasattr(ms, 'page_resonance_buff'):
            for it in ms.page_resonance_buff._items:
                if not it.get("enabled"):
                    continue
                for eff in it.get("effects", []):
                    uid = _nid()
                    chain = f"共鸣链{it['id']}"
                    tp = eff.get('type', '')
                    cat = damage_calc.classify_item_category(eff['name'])
                    all_items.append((uid, eff['name'], eff['value'],
                                      "共鸣", f"resonance_{it['id']}",
                                      f"{chain}-{tp}", "", cat))
                    chain_effect_map[(eff['name'], round(eff['value'], 4), chain)] = uid

        # 独立乘区（上游来源——乘区内各组数值）
        if hasattr(ms, 'page_indep_zone'):
            indep = ms.page_indep_zone
            for gd in indep._groups:
                gname = gd.get('name_edit', QLineEdit()).text() or "未命名组"
                for ri, (ne, vs, _hc) in enumerate(gd.get('rows', [])):
                    uid = _nid()
                    ename = ne.text() or f"行{ri+1}"
                    nm = f"[独立乘区]{gname}/{ename}"
                    all_items.append((uid, nm, vs.value(),
                                     "独立乘区", "indep", f"{gname}", "",
                                     damage_calc.classify_item_category(nm)))

        # 敌人减伤（上游来源——展示等级/抗性，不参与乘区分类）
        if hasattr(ms, 'page_enemy_defense'):
            def_vals = ms.page_enemy_defense.collect_data()
            if isinstance(def_vals, dict) and (def_vals.get('char_level') or def_vals.get('enemy_level')):
                uid = _nid()
                all_items.append((uid, "敌人等级/防御", 0,
                                 "敌人减伤", "enemy_defense",
                                 f"敌Lv{def_vals.get('enemy_level',0)}/我Lv{def_vals.get('char_level',0)}", "",
                                 "other"))
        if hasattr(ms, 'page_enemy_resistance'):
            for (row, col), spin in ms.page_enemy_resistance._spins.items():
                if col == 0 and abs(spin.value()) > 0.0001:
                    uid = _nid()
                    all_items.append((uid, f"抗性-{row}", spin.value(),
                                     "敌人减伤", "enemy_resistance", f"{row}基础", "",
                                     "resistance"))

        # 关键词关联（中间层）
        kw_items = ms.page_keyword_assoc.get_items()
        kw_uid_map = {}
        for ki in kw_items:
            uid = _nid()
            cat = damage_calc.classify_item_category(ki['name'])
            all_items.append((uid, ki['name'], ki['value'],
                              ki.get('source', '关联'), "keyword_assoc",
                              ki.get('seq', ''), ki.get('sub_name', ''), cat))
            kw_uid_map[uid] = ki

        # ---- 按乘区分组（暴击拆分为暴击率和暴击伤害）----
        zones = {"base": [], "bonus": [], "deepen": [],
                 "crit_rate": [], "crit_dmg": [],
                 "defense": [], "resistance": [], "other": []}
        for item in all_items:
            cat = item[7]
            if cat == "crit":
                if any(kw in item[1] for kw in damage_calc.CRIT_DMG_KEYWORDS):
                    zones["crit_dmg"].append(item)
                else:
                    zones["crit_rate"].append(item)
            elif cat in zones:
                zones[cat].append(item)
            else:
                zones["other"].append(item)

        # ---- 为每个 ID 生成唯一颜色 ----
        palette = self._gen_colors(len(all_items))
        for i, item in enumerate(all_items):
            self._id_colors[item[0]] = palette[i]

        CN = self._CAT_CN

        # ========== 上游 ==========
        upstream = _mk(self._tree, ["上游：数据来源", "", "", "", ""])
        upstream.setExpanded(True)

        src_groups = {}
        for item in all_items:
            src = item[3]
            if src not in src_groups:
                src_groups[src] = []
            src_groups[src].append(item)

        src_order = ["角色武器", "声骸4费", "声骸3费", "声骸1费", "共鸣", "独立乘区", "敌人减伤"]
        for src in sorted(src_groups.keys(),
                          key=lambda s: src_order.index(s) if s in src_order else 99):
            items = src_groups[src]
            grp = _mk(upstream, [f"{src}（{len(items)} 条）", "", "", "", ""])
            for uid, name, val, _, _, seq, sub, cat in items:
                # 暴击细分
                if cat == "crit":
                    if any(kw in name for kw in damage_calc.CRIT_DMG_KEYWORDS):
                        cat_cn = "暴击伤害"
                    else:
                        cat_cn = "暴击率"
                else:
                    cat_cn = CN.get(cat, cat)
                _mk(grp, [f"  {uid} {name}", f"{val}", cat_cn, seq, sub], uid)

        upstream.setText(1, f"共 {len(all_items)} 条")

        # ========== 中间层：关键词关联 ==========
        middle = _mk(self._tree, ["中间层：关键词关联", "", "", "", ""])
        middle.setExpanded(True)

        chain_kw = []
        manual_kw = []
        for ki in kw_items:
            seq = ki.get('seq', '')
            uid = [u for u, k in kw_uid_map.items() if k is ki][0]
            if '共鸣链' in seq:
                chain_kw.append((uid, ki))
            else:
                manual_kw.append((uid, ki))

        if chain_kw:
            grp = _mk(middle,
                [f"共鸣链同步（{len(chain_kw)} 条）", "", "来自上游共鸣链效果", "", ""])
            for uid, ki in chain_kw:
                seq = ki.get('seq', '')
                cat = CN.get(damage_calc.classify_item_category(ki['name']), "")
                up_ref = ""
                for (n, v, c), up_uid in chain_effect_map.items():
                    if n == ki['name'] and abs(v - ki['value']) < 0.01:
                        up_ref = f"← {up_uid}"
                        break
                _mk(grp, [f"  {uid} {ki['name']}", f"{ki['value']}",
                     f"{cat}  {up_ref}", seq, ki.get('sub_name', '')], uid)

        if manual_kw:
            grp = _mk(middle,
                [f"手动添加（{len(manual_kw)} 条）", "", "用户直接输入", "", ""])
            for uid, ki in manual_kw:
                cat = CN.get(damage_calc.classify_item_category(ki['name']), "")
                _mk(grp, [f"  {uid} {ki['name']}", f"{ki['value']}",
                     cat, ki.get('seq', ''), ki.get('sub_name', '')], uid)

        if not chain_kw and not manual_kw:
            _mk(middle, ["  （无数据）", "", "", "", ""])

        # ========== 中游：乘区汇总 ==========
        midstream = _mk(self._tree, ["中游：乘区汇总", "", "", "", ""])
        midstream.setExpanded(True)

        zone_labels = {
            "base": ("基础乘区", "攻/生/防 百分比+固定值"),
            "bonus": ("加成乘区", "伤害加成/伤害提升"),
            "deepen": ("加深乘区", "伤害加深"),
            "crit_rate": ("暴击率", "基础5% + Σ暴击率"),
            "crit_dmg": ("暴击伤害", "基础150% + Σ暴击伤害"),
            "defense": ("防御乘区", "无视防御"),
            "resistance": ("抗性乘区", "抗性减少/无视"),
        }
        for key in ["base", "bonus", "deepen", "crit_rate", "crit_dmg", "defense", "resistance"]:
            items = zones[key]
            label, desc = zone_labels[key]
            if not items:
                _mk(midstream, [f"{label}", "0 条", desc, "", ""])
                continue
            grp = _mk(midstream, [f"{label}", f"{len(items)} 条", desc, "", ""])
            for uid, name, val, src, _, seq, sub, cat in items:
                _mk(grp, [f"  {uid} {name}", f"{val}",
                     CN.get(cat, cat), seq, sub], uid)

        # 独立乘区（来自独立乘区页，真实数据）
        if hasattr(ms, 'page_indep_zone'):
            indep_page = ms.page_indep_zone
            indep_groups = indep_page.group_factors
            indep_zone_val = getattr(indep_page, 'independent_zone', 1.0)
            if indep_groups:
                grp = _mk(midstream, [f"独立乘区", f"乘积={indep_zone_val:.4f}",
                                      f"{len(indep_groups)} 组", "", ""])
                for gname, gfactor in indep_groups:
                    _mk(grp, [f"    {gname}", f"{gfactor:.4f}", "", "", ""])
            else:
                _mk(midstream, ["独立乘区", "1.0000 (无组)", "", "", ""])

        # ========== 下游：计算结果（真实 vs 独立对比）==========
        downstream = _mk(self._tree, ["下游：计算结果", "", "", "", ""])
        downstream.setExpanded(True)

        rp = ms.page_result

        # 显示当前筛选条件
        for label_text, attr in [("元素", "element_combo"), ("技能", "skill_combo"),
                                  ("效应", "effect_combo"), ("基准", "base_type_combo")]:
            if hasattr(rp, attr):
                _mk(downstream, [f"  {label_text}: {getattr(rp, attr).currentText()}",
                     "", "", "", ""])

        # ── 监测目标选择器 ──
        rl = ms.page_result_list
        old_idx = self._monitor_combo.currentIndex()
        self._monitor_combo.blockSignals(True)
        self._monitor_combo.clear()
        self._monitor_combo.addItem("计算结果页（全局）", None)
        for ci, card in enumerate(rl._items):
            label = card.get("label", f"卡片{ci}")
            self._monitor_combo.addItem(f"[卡{ci+1}] {label}", ci)
        if 0 <= old_idx < self._monitor_combo.count():
            self._monitor_combo.setCurrentIndex(old_idx)
        self._monitor_combo.blockSignals(False)

        # 触发真实计算并读取结果
        rp.compute()
        real = getattr(rp, '_last_computed', None)

        # 独立计算（使用与 ResultPage.compute 相同的数据源 + 筛选条件）
        basis = real.get("basis", "攻击力") if real else "攻击力"
        rp_ext = getattr(rp, '_external_sources', [])
        rp_echo = getattr(rp, '_echo_pages', {})
        deduped_items = _collect_all_items(rp_ext, rp_echo)

        # 同步筛选条件
        sel_elem = rp.filter_element.currentText() if hasattr(rp, 'filter_element') else "(无)"
        sel_skill = rp.filter_skill.currentText() if hasattr(rp, 'filter_skill') else "(无)"
        sel_effect = rp.filter_effect.currentText() if hasattr(rp, 'filter_effect') else "(无)"
        sel_elem = sel_elem if sel_elem != "(无)" else None
        sel_skill = sel_skill if sel_skill != "(无)" else None
        sel_effect = sel_effect if sel_effect != "(无)" else None
        # 卡片模式：覆盖筛选条件
        selected_idx = self._monitor_combo.currentData()
        if selected_idx is not None and selected_idx < len(rl._items):
            card = rl._items[selected_idx]
            sel_elem = card.get("element")
            sel_skill = card.get("skill")
            sel_effect = card.get("effect")
            basis = card.get("basis", "攻击力")

        def _norm6(t):
            """补齐到 6 元组 (name, value, source, nav_key, seq, sub_name)"""
            return t if len(t) >= 6 else (*t, *[""] * (6 - len(t)))
        deduped_items = [_norm6(t) for t in deduped_items
                         if _matches_filter(t[0], sel_elem, sel_skill, sel_effect)
                         and (not self._hide_filter_cb.isChecked() or (t[0], t[3], t[4] if len(t) > 4 else "") not in HIDDEN_ITEMS)]

        # 关键词关联注入（与 compute() 相同逻辑）
        selected_idx = self._monitor_combo.currentData()
        kw_text = ",".join(getattr(rp, '_keywords', []))
        # 卡片模式：额外注入该卡片的关键词关联条目
        if selected_idx is not None and selected_idx < len(rl._items):
            card = rl._items[selected_idx]
            card_kws = set(card.get("keywords", []))
            if card_kws and hasattr(rp, '_keyword_assoc_page') and rp._keyword_assoc_page:
                for kw_item in rp._keyword_assoc_page.get_items():
                    kw_entry_kws = set(k.strip() for k in kw_item.get("keywords", "").split(",") if k.strip())
                    if card_kws & kw_entry_kws:
                        name = kw_item["name"]
                        if self._hide_filter_cb.isChecked() and (name, "keyword_assoc", kw_item.get("seq", "")) in HIDDEN_ITEMS:
                            continue
                        deduped_items.append((
                            name, kw_item["value"],
                            kw_item.get("source", "关键词关联"),
                            "keyword_assoc", kw_item.get("seq", ""), kw_item.get("sub_name", ""),
                        ))
        if kw_text and getattr(rp, '_keyword_assoc_page', None):
            item_kws = set(k.strip() for k in kw_text.split(",") if k.strip())
            if item_kws:
                for kw_item in rp._keyword_assoc_page.get_items():
                    kw_entry_kws = set(k.strip() for k in kw_item.get("keywords", "").split(",") if k.strip())
                    if item_kws & kw_entry_kws:
                        deduped_items.append((
                            kw_item["name"], kw_item["value"],
                            kw_item.get("source", "关键词关联"), "keyword_assoc", "", "",
                        ))

        if basis == "攻击力":
            base_value = sum(v for n, v, *_ in deduped_items if n == "角色基础攻击力")
            weapon_base = sum(v for n, v, *_ in deduped_items if n == "武器基础攻击力")
            total_pct = sum(v for n, v, *_ in deduped_items
                           if "攻击力" in n and "固定" not in n and "基础" not in n)
            total_flat = sum(v for n, v, *_ in deduped_items if "固定攻击" in n)
        elif basis == "生命值":
            base_value = sum(v for n, v, *_ in deduped_items if n == "角色基础生命值")
            weapon_base = 0.0
            total_pct = sum(v for n, v, *_ in deduped_items
                           if "生命值" in n and "固定" not in n and "基础" not in n)
            total_flat = sum(v for n, v, *_ in deduped_items if "固定生命" in n)
        else:  # 防御力
            base_value = sum(v for n, v, *_ in deduped_items if n == "角色基础防御力")
            weapon_base = 0.0
            total_pct = sum(v for n, v, *_ in deduped_items
                           if "防御力" in n and "固定" not in n and "基础" not in n)
            total_flat = sum(v for n, v, *_ in deduped_items if "固定防御" in n)

        indep_base_zone = (base_value + weapon_base) * (1.0 + total_pct / 100.0) + total_flat
        indep_bonus = sum(v for n, v, *_ in deduped_items
                         if any(s in n for s in BONUS_SUFFIX)
                         and not any(kw in n for kw in CRIT_DMG_KEYWORDS))
        indep_bonus_zone = 1.0 + indep_bonus / 100.0
        indep_deepen = sum(v for n, v, *_ in deduped_items if DEEPEN_SUFFIX in n)
        indep_deepen_zone = 1.0 + indep_deepen / 100.0
        indep_crit_rate = 5.0 + sum(v for n, v, *_ in deduped_items
                                    if any(kw in n for kw in CRIT_RATE_KEYWORDS)
                                    and not any(kw in n for kw in CRIT_DMG_KEYWORDS))
        indep_crit_dmg = 150.0 + sum(v for n, v, *_ in deduped_items
                                     if any(kw in n for kw in CRIT_DMG_KEYWORDS))
        indep_crit_zone = indep_crit_dmg / 100.0

        # 防御/抗性/独立乘区：从真实页面读取（无法从 items 独立推算）
        real_def = getattr(ms.page_enemy_defense, 'def_multiplier', 1.0) if hasattr(ms, 'page_enemy_defense') else 1.0
        real_res = 1.0
        if hasattr(ms, 'page_enemy_resistance'):
            sel_elem = rp.filter_element.currentText() if hasattr(rp, 'filter_element') else None
            if sel_elem == "(无)":
                sel_elem = None
            real_res = ms.page_enemy_resistance.get_resistance_multiplier(sel_elem)
        real_indep = getattr(ms.page_indep_zone, 'independent_zone', 1.0) if hasattr(ms, 'page_indep_zone') else 1.0

        # 倍率乘区：从 ResultPage 的 UI 控件读取
        base_m = rp.base_mult.value() if hasattr(rp, 'base_mult') else 1.0
        inc_vals, boost_vals = rp._gather_mult_data() if hasattr(rp, '_gather_mult_data') else ([], [])
        mult_inc = sum(inc_vals)
        indep_mult = base_m + mult_inc
        for bv in boost_vals:
            indep_mult *= (1.0 + bv / 100.0)

        # 独立最终伤害
        indep_base_dmg = (indep_base_zone * indep_bonus_zone * indep_deepen_zone
                          * real_def * real_res * real_indep * indep_mult / 100.0)
        indep_final_crit = indep_base_dmg * indep_crit_zone
        indep_final_no_crit = indep_base_dmg

        # 收集真实值
        rz = real.get("zones", {}) if real else {}

        def _fmt_real_vs_indep(real_val, indep_val, fmt=".4f"):
            """格式化真实值 vs 独立值，返回 (显示文本, 是否一致)"""
            if real_val is None:
                return f"{indep_val:{fmt}} (无真实值)", False
            match = abs(real_val - indep_val) < 0.001
            if match:
                return f"{real_val:{fmt}}", True
            else:
                diff = real_val - indep_val
                return f"真实 {real_val:{fmt}} ≠ 独立 {indep_val:{fmt}} (差 {diff:+{fmt}})", False

        # 逐乘区对比
        compare_items = [
            ("基础乘区", rz.get("atk_zone"), indep_base_zone, f"基础{base_value:.0f}+武器{weapon_base:.0f} 百分比{total_pct:+.1f}% 固定{total_flat:+.1f}"),
            ("加成乘区", rz.get("bonus_zone"), indep_bonus_zone, f"Σ加成={indep_bonus:+.1f}%"),
            ("加深乘区", rz.get("deepen_zone"), indep_deepen_zone, f"Σ加深={indep_deepen:+.1f}%"),
            ("暴击率", rz.get("crit_rate"), indep_crit_rate, f"5% + Σ={indep_crit_rate:.1f}%"),
            ("暴击伤害", rz.get("crit_zone"), indep_crit_zone, f"(150+Σ)/100={indep_crit_zone:.4f}"),
            ("防御乘区", rz.get("def_zone"), real_def, "来自敌人防御页"),
            ("抗性乘区", rz.get("res_zone"), real_res, "来自敌人抗性页"),
            ("独立乘区", rz.get("indep_zone"), real_indep, "来自独立乘区页"),
            ("倍率乘区", rz.get("mult_zone"), indep_mult, f"({base_m}+{mult_inc})*boost"),
        ]

        conflict_count = 0
        for label, real_val, indep_val, desc in compare_items:
            text, match = _fmt_real_vs_indep(real_val, indep_val)
            status = "✅ 一致" if match else "⚠️ 不一致"
            if not match:
                conflict_count += 1
            _mk(downstream, [f"  {label}", text, desc, "", status])

        # 最终伤害对比
        real_fc = rz.get("final_crit")
        real_fn = rz.get("final_no_crit")
        for lbl, rv, iv in [("暴击伤害", real_fc, indep_final_crit),
                             ("非暴击伤害", real_fn, indep_final_no_crit)]:
            text, match = _fmt_real_vs_indep(rv, iv, ".2f")
            status = "✅ 一致" if match else "⚠️ 不一致"
            if not match:
                conflict_count += 1
            _mk(downstream, [f"  {lbl}", text, "", "", status])

        # 总结
        if conflict_count == 0:
            _mk(downstream, ["  ✅ 全部一致", "", "真实计算与独立计算完全匹配", "", "✅"])
        else:
            _mk(downstream, [f"  ⚠️ 发现 {conflict_count} 处不一致",
                 "", "请检查数据源或筛选条件", "", "⚠️"])

        # ---- 构建文本报告 ----
        lines = []
        lines.append("=== 数据流调试器报告 ===")
        lines.append("")

        # 上游
        lines.append("【上游：数据来源】")
        for item in all_items:
            uid, name, val, src, _, seq, sub, cat = item
            cat_cn = CN.get(cat, cat)
            if cat == "crit":
                cat_cn = "暴击伤害" if any(kw in name for kw in damage_calc.CRIT_DMG_KEYWORDS) else "暴击率"
            lines.append(f"  {uid} {name} = {val}  [{cat_cn}]  来源:{src}  {seq}  {sub}")
        lines.append(f"  共 {len(all_items)} 条")
        lines.append("")

        # 中间层
        lines.append("【中间层：关键词关联】")
        for ki in kw_items:
            seq = ki.get('seq', '')
            src = ki.get('source', '关联')
            lines.append(f"  {ki['name']} = {ki['value']}  来源:{src}  {seq}")
        if not kw_items:
            lines.append("  （无数据）")
        lines.append("")

        # 中游
        lines.append("【中游：乘区汇总】")
        for key in ["base", "bonus", "deepen", "crit_rate", "crit_dmg", "defense", "resistance"]:
            items_z = zones[key]
            label, desc = zone_labels[key]
            total = sum(it[2] for it in items_z)
            lines.append(f"  {label}: {len(items_z)} 条, 合计={total:.4f}  ({desc})")
            for uid, name, val, *_ in items_z:
                lines.append(f"    {uid} {name} = {val}")
        # 独立乘区
        if hasattr(ms, 'page_indep_zone'):
            indep_page = ms.page_indep_zone
            indep_groups = indep_page.group_factors
            indep_zone_val = getattr(indep_page, 'independent_zone', 1.0)
            lines.append(f"  独立乘区: 乘积={indep_zone_val:.4f}  ({len(indep_groups)} 组)")
            for gname, gfactor in indep_groups:
                lines.append(f"    {gname} = {gfactor:.4f}")
        lines.append("")

        # 下游
        lines.append("【下游：计算结果（真实 vs 独立对比）】")
        sel_elem = rp.filter_element.currentText() if hasattr(rp, 'filter_element') else "?"
        sel_skill = rp.filter_skill.currentText() if hasattr(rp, 'filter_skill') else "?"
        sel_effect = rp.filter_effect.currentText() if hasattr(rp, 'filter_effect') else "?"
        sel_basis = basis
        sel_kw = ",".join(getattr(rp, '_keywords', []))
        lines.append(f"  筛选: 基准={sel_basis} 元素={sel_elem} 技能={sel_skill} 效应={sel_effect} 关键词={sel_kw or '(无)'}")
        lines.append("")
        for label, real_val, indep_val, desc in compare_items:
            if real_val is None:
                lines.append(f"  {label}: 无真实值, 独立={indep_val:.4f}  ({desc})  ⚠️")
            elif abs(real_val - indep_val) < 0.001:
                lines.append(f"  {label}: {real_val:.4f}  ({desc})  ✅")
            else:
                diff = real_val - indep_val
                lines.append(f"  {label}: 真实={real_val:.4f} ≠ 独立={indep_val:.4f} (差{diff:+.4f})  ({desc})  ⚠️")
        # 最终伤害
        for lbl, rv, iv in [("暴击伤害", real_fc, indep_final_crit),
                             ("非暴击伤害", real_fn, indep_final_no_crit)]:
            if rv is None:
                lines.append(f"  {lbl}: 无真实值, 独立={iv:.2f}  ⚠️")
            elif abs(rv - iv) < 0.001:
                lines.append(f"  {lbl}: {rv:.2f}  ✅")
            else:
                diff = rv - iv
                lines.append(f"  {lbl}: 真实={rv:.2f} ≠ 独立={iv:.2f} (差{diff:+.2f})  ⚠️")
        lines.append("")
        if conflict_count == 0:
            lines.append("结论: ✅ 全部一致")
        else:
            lines.append(f"结论: ⚠️ 发现 {conflict_count} 处不一致")

        self._report_lines = lines
        self._report.setPlainText("\n".join(lines))
        self._fit_columns()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_columns)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_columns()

    def eventFilter(self, obj, event):
        """Shift+滚轮 → 水平滚动"""
        if obj is self._tree.viewport() and event.type() == event.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                hbar = self._tree.horizontalScrollBar()
                delta = event.angleDelta().y()
                hbar.setValue(hbar.value() - delta)
                return True
        return super().eventFilter(obj, event)

    def _copy_report(self):
        """复制文本报告到剪贴板"""
        text = self._report.toPlainText()
        if not text.strip():
            return
        QApplication.clipboard().setText(text)

    def _on_item_clicked(self, item, column):
        """单击三角形文字 → 展开/收起"""
        if item.childCount() > 0 and column == 0:
            item.setExpanded(not item.isExpanded())

    def _on_item_double_clicked(self, item, column):
        """双击任意列 → 展开/收起"""
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())


# ==================== 副名称展开编辑弹窗 ====================

class SubNameEditDialog(QDialog):
    """副名称长文本编辑弹窗（非模式，实时同步到源 QLineEdit）"""
    text_changed = pyqtSignal(str)

    def __init__(self, text="", name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"编辑副名称 — {name}" if name else "编辑副名称")
        self.setMinimumSize(420, 300)
        self.resize(460, 340)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        _center_window(self)

        # 继承主题
        theme = "dark"
        w = parent
        while w:
            if hasattr(w, 'current_theme'):
                theme = w.current_theme
                break
            w = w.parent() if hasattr(w, 'parent') else None
        self.setStyleSheet(build_stylesheet(theme))

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        hint = QLabel("输入副名称内容（支持多行）：")
        hint.setObjectName("labelSecondary")
        layout.addWidget(hint)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setMinimumHeight(160)
        self.text_edit.textChanged.connect(lambda: self.text_changed.emit(self.get_text()))
        layout.addWidget(self.text_edit, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("backButton")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def get_text(self):
        return self.text_edit.toPlainText().strip()


def _make_sub_name_cell(line_edit, get_name_cb=None):
    """将 QLineEdit + '…' 按钮包装成容器，放入表格 cellWidget。
    get_name_cb: 可选回调，返回当前行名称（用于弹窗标题）。
    非模式弹窗，实时同步到 line_edit。"""
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(2)
    row.addWidget(line_edit, stretch=1)

    expand_btn = QPushButton("…")
    expand_btn.setFixedWidth(24)
    expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    expand_btn.setToolTip("展开编辑")

    def _open():
        # 如果已有弹窗，复用
        existing = getattr(line_edit, '_sub_name_dlg', None)
        if existing and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        name = get_name_cb() if get_name_cb else ""
        dlg = SubNameEditDialog(line_edit.text(), name, container)

        # 双向同步（防循环）
        syncing = [False]

        def _from_dlg(t):
            if syncing[0]:
                return
            syncing[0] = True
            line_edit.setText(t)
            syncing[0] = False
            # 300ms 防抖：连续输入不重复触发下游重算
            if not hasattr(line_edit, '_sub_sync_timer'):
                line_edit._sub_sync_timer = QTimer(line_edit)
                line_edit._sub_sync_timer.setSingleShot(True)
                line_edit._sub_sync_timer.setInterval(300)
                line_edit._sub_sync_timer.timeout.connect(line_edit.editingFinished.emit)
            line_edit._sub_sync_timer.start()

        def _from_input():
            if syncing[0]:
                return
            syncing[0] = True
            dlg.text_edit.setPlainText(line_edit.text())
            syncing[0] = False

        dlg.text_changed.connect(_from_dlg)
        line_edit.textChanged.connect(_from_input)
        dlg.destroyed.connect(lambda: (setattr(line_edit, '_sub_name_dlg', None),
                                        line_edit.textChanged.disconnect(_from_input)))
        line_edit._sub_name_dlg = dlg
        dlg.show()

    expand_btn.clicked.connect(_open)
    row.addWidget(expand_btn)
    return container


# 延迟注入 _make_sub_name_cell 到 summary_pages
from summary_pages import set_make_sub_name_cell as _set_smnc
_set_smnc(_make_sub_name_cell)
_inject_enemy_res(CombinedEntryPage, cell_center, fix_table_height, PropTable, _place_highlight_overlay, _make_sub_name_cell)


def _get_sub_name_text(widget):
    """从 cellWidget 中提取副名称文本（兼容 QLineEdit 或容器）"""
    if widget is None:
        return ""
    if isinstance(widget, QLineEdit):
        return widget.text().strip()
    # 容器：找内部 QLineEdit
    le = widget.findChild(QLineEdit)
    return le.text().strip() if le else ""


# ==================== 共鸣链编辑弹窗 ====================

class ResonanceChainEditDialog(QDialog):
    """共鸣链编辑弹窗 —— 2 页分页设计"""

    def __init__(self, item, parent=None, main_screen=None):
        super().__init__(parent)
        self._item = item
        self._main_screen = main_screen  # 主界面引用，用于添加效果到综合填写
        # 解析名称：绯雪的共鸣链1 → 前缀="绯雪"，序号=1
        name = item['name']
        if '的共鸣链' in name:
            parts = name.split('的共鸣链')
            self._prefix = parts[0]
            self._chain_num = parts[1] if len(parts) > 1 else "1"
        else:
            self._prefix = ""
            self._chain_num = name.replace('共鸣链', '')
        self.setWindowTitle(f"{self._prefix}的第{self._chain_num}个共鸣链")
        self.setMinimumSize(1100, 650)
        self.resize(1150, 700)

        QTimer.singleShot(0, lambda: self._center())

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        self._build_intro_tab()
        self._build_general_tab()
        self._build_specific_tab()

        # 实时同步防抖（300ms 内多次变更只同步一次）
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(300)
        self._sync_timer.timeout.connect(self._collect_and_sync)

        self._load_existing_data()

        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("backButton")
        close_btn.setFixedSize(80, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._close_and_save)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _center(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def _build_intro_tab(self):
        """共鸣链介绍标签页 —— 可编辑文本"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel(f"编辑 {self._item['name']} 的介绍信息：")
        lbl.setObjectName("sectionTitle")
        lbl.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(lbl)

        self._intro_edit = QTextEdit()
        self._intro_edit.setObjectName("nameEdit")
        self._intro_edit.setPlaceholderText("在此输入共鸣链的介绍文本...")
        self._intro_edit.setPlainText(self._item.get("intro", ""))
        self._intro_edit.textChanged.connect(self._on_intro_changed)
        layout.addWidget(self._intro_edit, stretch=1)

        self._tabs.addTab(tab, "共鸣链介绍")

    def _on_intro_changed(self):
        """介绍文本变更 → 实时保存到 item"""
        self._item["intro"] = self._intro_edit.toPlainText()

    def _build_general_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(16, 16, 16, 16)

        # 主标题 + 副标题
        title = QLabel("通用增益")
        title.setObjectName("sectionTitle")
        tab_layout.addWidget(title)

        desc = QLabel("管理共鸣链的常驻效果和触发效果，并添加独立乘区组")
        desc.setObjectName("labelSecondary")
        desc.setWordWrap(True)
        tab_layout.addWidget(desc)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setContentsMargins(16, 16, 16, 16)

        # 常驻效果
        perm_group = QGroupBox("常驻效果")
        perm_group.setMinimumHeight(500)    # 给表格预留空间，后续添加行时窗口不会变得过于狭小
        perm_layout = QVBoxLayout(perm_group)  

        perm_input = QHBoxLayout()
        # SearchCombo and CombinedEntryPage are defined in this file
        self._perm_combo = SearchCombo(WEAPON_RESONANCE_ATTRS)
        self._perm_combo.lineEdit().setPlaceholderText("输入搜索...")
        perm_input.addWidget(self._perm_combo, stretch=3)

        self._perm_value = QDoubleSpinBox()
        self._perm_value.setRange(0, 9999)
        self._perm_value.setDecimals(4)
        self._perm_value.setFixedWidth(100)
        perm_input.addWidget(self._perm_value)
        perm_input.addWidget(QLabel("%"))

        self._perm_source = SearchCombo(CombinedEntryPage.SOURCES)
        self._perm_source.setMinimumWidth(100)
        self._perm_source.setCurrentIndex(5)  # 默认"共鸣链效果"
        perm_input.addWidget(self._perm_source)

        add_perm = QPushButton("添加")
        add_perm.setObjectName("addButton")
        add_perm.setFixedWidth(50)
        add_perm.setCursor(Qt.CursorShape.PointingHandCursor)
        add_perm.clicked.connect(self._add_perm_row)
        perm_input.addWidget(add_perm)
        perm_layout.addLayout(perm_input)

        self._perm_combo.lineEdit().returnPressed.connect(self._add_perm_row)

        self._perm_table = QTableWidget()
        self._perm_table.setObjectName("attrTable")
        self._perm_table.setColumnCount(7)
        self._perm_table.setHorizontalHeaderLabels(
            ["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"])
        self._perm_table.verticalHeader().setVisible(False)
        perm_hdr = self._perm_table.horizontalHeader()
        perm_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            perm_hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        perm_hdr.resizeSection(1, 140)  # 副名称
        perm_hdr.resizeSection(2, 120)  # 序列号
        perm_hdr.resizeSection(3, 140)  # 数值
        perm_hdr.resizeSection(4, 70)   # 取值
        perm_hdr.resizeSection(5, 100)  # 来源
        perm_hdr.resizeSection(6, 100)  # 操作
        perm_layout.addWidget(self._perm_table)
        layout.addWidget(perm_group)

        # 触发效果
        trig_group = QGroupBox("触发效果")
        trig_group.setMinimumHeight(500)    #框架高度
        trig_layout = QVBoxLayout(trig_group)

        trig_input = QHBoxLayout()
        self._trig_combo = SearchCombo(WEAPON_RESONANCE_ATTRS)
        self._trig_combo.lineEdit().setPlaceholderText("输入搜索...")
        trig_input.addWidget(self._trig_combo, stretch=3)

        self._trig_value = QDoubleSpinBox()
        self._trig_value.setRange(0, 9999)
        self._trig_value.setDecimals(4)
        self._trig_value.setFixedWidth(100)
        trig_input.addWidget(self._trig_value)
        trig_input.addWidget(QLabel("%"))

        self._trig_source = SearchCombo(CombinedEntryPage.SOURCES)
        self._trig_source.setMinimumWidth(100)
        self._trig_source.setCurrentIndex(5)  # 默认"共鸣链效果"
        trig_input.addWidget(self._trig_source)

        add_trig = QPushButton("添加")
        add_trig.setObjectName("addButton")
        add_trig.setFixedWidth(50)
        add_trig.setCursor(Qt.CursorShape.PointingHandCursor)
        add_trig.clicked.connect(self._add_trig_row)
        trig_input.addWidget(add_trig)
        trig_layout.addLayout(trig_input)

        self._trig_combo.lineEdit().returnPressed.connect(self._add_trig_row)

        self._trig_table = QTableWidget()
        self._trig_table.setObjectName("attrTable")
        self._trig_table.setColumnCount(7)
        self._trig_table.setHorizontalHeaderLabels(
            ["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"])
        self._trig_table.verticalHeader().setVisible(False)
        trig_hdr = self._trig_table.horizontalHeader()
        trig_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            trig_hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        trig_hdr.resizeSection(1, 140)  # 副名称
        trig_hdr.resizeSection(2, 120)  # 序列号
        trig_hdr.resizeSection(3, 140)  # 数值
        trig_hdr.resizeSection(4, 70)   # 取值
        trig_hdr.resizeSection(5, 100)  # 来源
        trig_hdr.resizeSection(6, 100)  # 操作
        trig_layout.addWidget(self._trig_table)
        layout.addWidget(trig_group)

        # ── 独立乘区组 ──
        iz_label = QLabel("独立乘区组")
        iz_label.setObjectName("labelSecondary")
        iz_label.setStyleSheet("font-size: 13px; font-weight: 600; margin-top: 8px;")
        layout.addWidget(iz_label)

        self._indep_container = QVBoxLayout()
        self._indep_container.setSpacing(6)
        layout.addLayout(self._indep_container)

        self._indep_groups = []

        add_iz_btn = QPushButton("+ 添加独立乘区组")
        add_iz_btn.setObjectName("addButton")
        add_iz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_iz_btn.clicked.connect(self._add_indep_group)
        layout.addWidget(add_iz_btn)

        layout.addStretch()

        scroll.setWidget(scroll_widget)
        tab_layout.addWidget(scroll)

        self._tabs.addTab(tab, "通用增益")

    def _build_specific_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("特定增益")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        desc = QLabel("为共鸣链效果设置特定增益规则，选择效果后指定目标关键词卡片")
        desc.setObjectName("labelSecondary")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        specific_group = QGroupBox("特定增益")
        specific_layout = QVBoxLayout(specific_group)

        input_row = QHBoxLayout()
        # SearchCombo and CombinedEntryPage are defined in this file
        self._spec_combo = SearchCombo(MULTIPLIER_ONLY_ATTRS)
        self._spec_combo.lineEdit().setPlaceholderText("输入搜索...")
        input_row.addWidget(self._spec_combo, stretch=3)

        self._spec_value = QDoubleSpinBox()
        self._spec_value.setRange(0, 9999)
        self._spec_value.setDecimals(4)
        self._spec_value.setFixedWidth(100)
        input_row.addWidget(self._spec_value)
        input_row.addWidget(QLabel("%"))

        self._spec_source = SearchCombo(CombinedEntryPage.SOURCES)
        self._spec_source.setMinimumWidth(100)
        self._spec_source.setCurrentIndex(5)  # 默认"共鸣链效果"
        input_row.addWidget(self._spec_source)

        add_spec = QPushButton("添加")
        add_spec.setObjectName("addButton")
        add_spec.setFixedWidth(50)
        add_spec.setCursor(Qt.CursorShape.PointingHandCursor)
        add_spec.clicked.connect(self._add_spec_row)
        input_row.addWidget(add_spec)
        specific_layout.addLayout(input_row)

        self._spec_combo.lineEdit().returnPressed.connect(self._add_spec_row)

        self._spec_table = QTableWidget()
        self._spec_table.setObjectName("attrTable")
        self._spec_table.setColumnCount(8)
        self._spec_table.setHorizontalHeaderLabels(
            ["名称", "副名称", "序列号", "数值", "取值", "来源", "关键词关联", "操作"])
        self._spec_table.verticalHeader().setVisible(False)
        spec_hdr = self._spec_table.horizontalHeader()
        spec_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 8):
            spec_hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        spec_hdr.resizeSection(1, 140)   # 副名称
        spec_hdr.resizeSection(2, 120)   # 序列号
        spec_hdr.resizeSection(3, 140)   # 数值
        spec_hdr.resizeSection(4, 70)    # 取值
        spec_hdr.resizeSection(5, 100)   # 来源
        spec_hdr.resizeSection(6, 120)   # 关键词关联
        spec_hdr.resizeSection(7, 100)   # 操作
        specific_layout.addWidget(self._spec_table)
        layout.addWidget(specific_group)

        self._tabs.addTab(tab, "特定增益")

    def _add_perm_row(self):
        name = self._perm_combo.currentText().strip()
        if not name:
            return
        self._add_table_row(self._perm_table, name, self._perm_value.value(),
                           self._perm_source.currentText(), "常驻", show_kw=False)
        self._perm_combo.lineEdit().clear()
        self._perm_value.setValue(0)
        self._debounced_sync()

    def _add_trig_row(self):
        name = self._trig_combo.currentText().strip()
        if not name:
            return
        self._add_table_row(self._trig_table, name, self._trig_value.value(),
                           self._trig_source.currentText(), "触发", show_kw=False)
        self._trig_combo.lineEdit().clear()
        self._trig_value.setValue(0)
        self._debounced_sync()

    def _add_spec_row(self):
        name = self._spec_combo.currentText().strip()
        if not name:
            return
        self._add_table_row(self._spec_table, name, self._spec_value.value(),
                           self._spec_source.currentText(), "特定")
        self._spec_combo.lineEdit().clear()
        self._spec_value.setValue(0)
        self._debounced_sync()

    def _add_table_row(self, table, name, value, source, eff_type, sub_name_text="", keywords="", show_kw=True):
        row_idx = table.rowCount()
        table.insertRow(row_idx)
        table.setRowHeight(row_idx, 42)

        name_edit = QLineEdit(name)
        name_edit.setObjectName("nameEdit")
        name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_edit.textChanged.connect(lambda: self._debounced_sync())
        table.setCellWidget(row_idx, 0, name_edit)

        sub_name = QLineEdit(sub_name_text)
        sub_name.setObjectName("nameEdit")
        sub_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_name.setPlaceholderText("（备注）")
        sub_name.textChanged.connect(lambda: self._debounced_sync())
        table.setCellWidget(row_idx, 1, _make_sub_name_cell(sub_name, lambda: name))

        chain_num = self._item['id']
        seq = QLabel(f"共鸣链{chain_num}关联{row_idx + 1}")  # 临时占位，会被 _refresh_all_seq_labels 更新
        seq.setObjectName("seqLabel")
        seq.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setCellWidget(row_idx, 2, seq)

        value_spin = QDoubleSpinBox()
        value_spin.setObjectName("itemValueSpin")
        value_spin.setRange(0, 9999)
        value_spin.setDecimals(4)
        value_spin.setValue(value)
        value_spin.setFixedWidth(120)
        value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_spin.valueChanged.connect(lambda: self._debounced_sync())
        table.setCellWidget(row_idx, 3, value_spin)

        unit = QLabel("百分比")
        unit.setObjectName("unitLabel")
        unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setCellWidget(row_idx, 4, unit)

        source_lbl = QLabel(source)
        source_lbl.setObjectName("seqLabel")
        source_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setCellWidget(row_idx, 5, source_lbl)

        # 关键词关联按钮（仅特定增益显示）
        if show_kw:
            kw_btn = QPushButton(keywords if keywords else "点击编辑")
            kw_btn.setObjectName("itemLockBtn")
            kw_btn.setFixedSize(110, 35)
            kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            kw_btn.clicked.connect(lambda _, r=row_idx, t=table: self._edit_chain_keywords(r, t))
            table.setCellWidget(row_idx, 6, kw_btn)

        ops_col = 7 if show_kw else 6
        ops = QWidget()
        ops_layout = QHBoxLayout(ops)
        ops_layout.setContentsMargins(2, 0, 2, 0)
        ops_layout.setSpacing(3)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("itemDeleteBtn")
        del_btn.setFixedSize(55, 28)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        def _del_this():
            sender = self.sender()
            for r in range(table.rowCount()):
                ops_w = table.cellWidget(r, ops_col)
                if ops_w and sender in ops_w.findChildren(QPushButton):
                    table.removeRow(r)
                    self._debounced_sync()
                    return
        del_btn.clicked.connect(_del_this)
        ops_layout.addWidget(del_btn)

        table.setCellWidget(row_idx, ops_col, ops)

    def _edit_chain_keywords(self, row_idx, table):
        """编辑共鸣链效果的关键词关联"""
        kw_btn = table.cellWidget(row_idx, 6)
        if not kw_btn:
            return
        current_kw = kw_btn.text() if kw_btn.text() != "点击编辑" else ""
        current_list = [k.strip() for k in current_kw.split(",") if k.strip()] if current_kw else []

        dlg = QDialog(self)
        dlg.setWindowTitle("编辑关键词关联")
        dlg.setMinimumSize(400, 350)
        dlg.resize(450, 400)

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(12, 12, 12, 12)

        kw_title = QLabel("关键词关联")
        kw_title.setObjectName("sectionTitle")
        dlg_layout.addWidget(kw_title)

        kw_desc = QLabel("输入关键词后点击添加，留空则增益全部卡片")
        kw_desc.setObjectName("labelSecondary")
        kw_desc.setWordWrap(True)
        dlg_layout.addWidget(kw_desc)

        input_row = QHBoxLayout()
        kw_input = QLineEdit()
        kw_input.setPlaceholderText("输入关键词...")
        kw_input.setObjectName("nameEdit")
        input_row.addWidget(kw_input, stretch=1)

        add_kw_btn = QPushButton("添加")
        add_kw_btn.setObjectName("addButton")
        add_kw_btn.setFixedWidth(50)
        add_kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        input_row.addWidget(add_kw_btn)
        dlg_layout.addLayout(input_row)

        kw_list = QListWidget()
        kw_list.setObjectName("attrList")
        for kw in current_list:
            kw_list.addItem(kw)
        dlg_layout.addWidget(kw_list, stretch=1)

        del_kw_btn = QPushButton("删除选中")
        del_kw_btn.setObjectName("itemDeleteBtn")
        del_kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dlg_layout.addWidget(del_kw_btn)

        def add_keyword():
            text = kw_input.text().strip()
            if text and text not in [kw_list.item(i).text() for i in range(kw_list.count())]:
                kw_list.addItem(text)
                kw_input.clear()

        add_kw_btn.clicked.connect(add_keyword)
        kw_input.returnPressed.connect(add_keyword)

        def del_keyword():
            for item in reversed(kw_list.selectedItems()):
                kw_list.takeItem(kw_list.row(item))

        del_kw_btn.clicked.connect(del_keyword)

        def on_ok():
            keywords = ", ".join(kw_list.item(i).text() for i in range(kw_list.count()))
            kw_btn.setText(keywords if keywords else "点击编辑")
            self._debounced_sync()
            dlg.close()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("addButton")
        ok_btn.setFixedWidth(80)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(on_ok)
        btn_row.addWidget(ok_btn)
        dlg_layout.addLayout(btn_row)

        dlg.exec()

    def _load_existing_data(self):
        for eff in self._item.get("effects", []):
            eff_type = eff.get("type", "常驻")
            if eff_type == "常驻":
                table = self._perm_table
            elif eff_type == "触发":
                table = self._trig_table
            else:
                table = self._spec_table
            self._add_table_row(table, eff.get("name", ""), eff.get("value", 0.0),
                               eff.get("source", "共鸣链效果"), eff_type,
                               sub_name_text=eff.get("sub_name", ""),
                               keywords=eff.get("keywords", ""),
                               show_kw=(eff_type == "特定"))

        # 加载独立乘区
        for iz_data in self._item.get("indep_zones", []):
            from preset_builder import _IndepZoneGroupBox
            gb = _IndepZoneGroupBox(iz_data.get("group_name", ""), iz_data.get("values", []))
            gb.del_group_btn.clicked.connect(lambda _checked=False, g=gb: self._remove_indep_group(g))
            self._indep_container.addWidget(gb)
            self._indep_groups.append(gb)

        # 刷新序列号为全局编号，与关键词关联格式一致
        self._refresh_all_seq_labels()

    def _debounced_sync(self):
        """防抖：300ms 内多次变更只同步一次"""
        self._sync_timer.start()

    def _close_and_save(self):
        """关闭前保存：停掉防抖定时器，立即同步一次"""
        self._sync_timer.stop()
        self._collect_and_sync()
        self.close()

    def _collect_and_sync(self):
        """收集所有表格数据，更新 item，同步到下游页面"""
        # 保持名称格式：绯雪的共鸣链1
        self._item["name"] = f"{self._prefix}的共鸣链{self._chain_num}"

        effects = []
        for table, eff_type in [(self._perm_table, "常驻"), (self._trig_table, "触发"), (self._spec_table, "特定")]:
            has_kw = table.columnCount() == 8
            for row in range(table.rowCount()):
                name_edit = table.cellWidget(row, 0)
                sub_name = table.cellWidget(row, 1)
                value_spin = table.cellWidget(row, 3)
                source_lbl = table.cellWidget(row, 5)
                if name_edit and value_spin:
                    eff = {
                        "name": name_edit.text().strip(),
                        "value": value_spin.value(),
                        "type": eff_type,
                        "source": source_lbl.text() if source_lbl else "共鸣链效果",
                        "sub_name": _get_sub_name_text(sub_name),
                    }
                    if has_kw:
                        kw_btn = table.cellWidget(row, 6)
                        eff["keywords"] = kw_btn.text() if kw_btn and kw_btn.text() != "点击编辑" else ""
                    effects.append(eff)
        self._item["effects"] = effects

        # 收集独立乘区
        indep_zones = []
        for gb in self._indep_groups:
            data = gb.to_dict() if hasattr(gb, 'to_dict') else {}
            if data.get("group_name") or data.get("values"):
                indep_zones.append(data)
        self._item["indep_zones"] = indep_zones

        # 同步效果到综合填写页和关键词关联页面
        parent_page = self.parent()
        if hasattr(parent_page, '_sync_chain_to_pages'):
            parent_page._sync_chain_to_pages(self._item)

        # 刷新所有表格的序列号，确保与关键词关联的 seq 一致
        self._refresh_all_seq_labels()

    def _refresh_all_seq_labels(self):
        """用全局编号（跨常驻/触发/特定三张表）刷新所有序列号标签，
        与 _sync_chain_to_pages → 关键词关联的 seq_text 格式保持一致。"""
        chain_num = self._item['id']
        global_idx = 0
        for table in (self._perm_table, self._trig_table, self._spec_table):
            for row in range(table.rowCount()):
                global_idx += 1
                w = table.cellWidget(row, 2)
                if w is not None and hasattr(w, 'setText'):
                    w.setText(f"共鸣链{chain_num}关联{global_idx}")

    # ── 独立乘区组管理 ──

    def _add_indep_group(self):
        from preset_builder import _IndepZoneGroupBox
        gb = _IndepZoneGroupBox("", [])
        gb.del_group_btn.clicked.connect(lambda _checked=False, g=gb: self._remove_indep_group(g))
        self._indep_container.addWidget(gb)
        self._indep_groups.append(gb)

    def _remove_indep_group(self, gb):
        if gb in self._indep_groups:
            self._indep_groups.remove(gb)
            self._indep_container.removeWidget(gb)
            gb.hide()
            gb.setParent(None)
            gb.deleteLater()


# ==================== 结果列表页面 ====================

# ==================== 结果详情弹窗 ====================

class ResultDetailDialog(QDialog):
    """半透明弹窗，展示单条结果的计算过程、名称、倍率，支持锁定/解锁/删除"""
    def __init__(self, item, idx, parent_page, parent_window=None):
        super().__init__(parent_window)
        self._item = item
        self._idx = idx
        self._page = parent_page
        self.setWindowTitle(f"结果详情 — {item['label']}")
        self.setMinimumSize(1100,800)
        self.setWindowOpacity(0.96)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        _center_window(self)


        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # —— 名称 ——
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("名称:"))
        self.name_edit = QLineEdit(item["label"])
        self.name_edit.setObjectName("nameEdit")
        self.name_edit.textChanged.connect(self._on_name_changed)
        name_row.addWidget(self.name_edit, stretch=1)
        layout.addLayout(name_row)

        # —— 滚动区域（筛选条件 + 倍率设置 + 计算结果） ——
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        # —— 筛选条件 ——
        filter_group = QGroupBox("筛选条件")
        filter_form = QFormLayout(filter_group)

        self.filter_basis = QComboBox()
        self.filter_basis.addItems(["攻击力", "生命值", "防御力"])
        self.filter_basis.setCurrentText(item["basis"])
        self.filter_basis.currentTextChanged.connect(self._on_filter_changed)
        filter_form.addRow("基础数值类型:", self.filter_basis)

        self.filter_element = QComboBox()
        self.filter_element.addItems(ELEMENTS)
        self.filter_element.setCurrentText(item["element"] if item["element"] else "(无)")
        self.filter_element.currentTextChanged.connect(self._on_filter_changed)
        filter_form.addRow("元素属性:", self.filter_element)

        self.filter_skill = QComboBox()
        self.filter_skill.addItems(SKILL_TYPES)
        self.filter_skill.setCurrentText(item["skill"] if item["skill"] else "(无)")
        self.filter_skill.currentTextChanged.connect(self._on_filter_changed)
        filter_form.addRow("技能类型:", self.filter_skill)

        self.filter_category = QComboBox()
        self.filter_category.addItems(DAMAGE_CATEGORIES)
        self.filter_category.setCurrentText(item.get("category", "") if item.get("category", "") in DAMAGE_CATEGORIES else "常态攻击")
        self.filter_category.currentTextChanged.connect(self._on_filter_changed)
        filter_form.addRow("分类:", self.filter_category)

        self.filter_effect = QComboBox()
        self.filter_effect.addItems(EFFECTS)
        self.filter_effect.setCurrentText(item["effect"] if item["effect"] else "(无)")
        self.filter_effect.currentTextChanged.connect(self._on_filter_changed)
        filter_form.addRow("效应类型:", self.filter_effect)

        scroll_layout.addWidget(filter_group)

        # —— 倍率编辑 ——
        mult_group = QGroupBox("倍率设置")
        mult_form = QFormLayout(mult_group)
        self.base_mult = QDoubleSpinBox()
        self.base_mult.setRange(0, 99999)
        self.base_mult.setDecimals(4)
        self.base_mult.setValue(item["base_mult"])
        self.base_mult.valueChanged.connect(self._on_mult_changed)
        mult_form.addRow("基础倍率(%):", self.base_mult)

        self.mult_inc_table = QTableWidget()
        self.mult_inc_table.setObjectName("attrTable")
        self.mult_inc_table.setColumnCount(8)
        self.mult_inc_table.setHorizontalHeaderLabels(
            ["名称", "副名称", "序列号", "数值", "取值", "来源", "关键词关联", "操作"])
        self.mult_inc_table.verticalHeader().setVisible(False)
        self.mult_inc_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mult_inc_table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.mult_inc_table.setMinimumHeight(150)
        hdr_inc = self.mult_inc_table.horizontalHeader()
        hdr_inc.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 8):
            hdr_inc.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        hdr_inc.resizeSection(1, 130)
        hdr_inc.resizeSection(2, 110)
        hdr_inc.resizeSection(3, 150)
        hdr_inc.resizeSection(4, 70)
        hdr_inc.resizeSection(5, 90)
        hdr_inc.resizeSection(6, 120)
        hdr_inc.resizeSection(7, 80)
        inc_toggle = QPushButton("▼ 倍率增加(%)")
        inc_toggle.setObjectName("formToggle")
        inc_toggle.setStyleSheet("QPushButton { border: none; background: transparent; padding: 2px 6px; text-align: left; } QPushButton:checked { font-weight: bold; }")
        inc_toggle.setFlat(True)
        inc_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        inc_toggle.setCheckable(True)
        inc_toggle.setChecked(True)
        inc_toggle.toggled.connect(lambda checked, b=inc_toggle: (b.setText(("▼ " if checked else "▶ ") + "倍率增加(%)")))
        inc_toggle.toggled.connect(self.mult_inc_table.setVisible)
        mult_form.addRow(inc_toggle, self.mult_inc_table)
        self.mult_boost_table = QTableWidget()
        self.mult_boost_table.setObjectName("attrTable")
        self.mult_boost_table.setColumnCount(8)
        self.mult_boost_table.setHorizontalHeaderLabels(
            ["名称", "副名称", "序列号", "数值", "取值", "来源", "关键词关联", "操作"])
        self.mult_boost_table.verticalHeader().setVisible(False)
        self.mult_boost_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mult_boost_table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.mult_boost_table.setMinimumHeight(150)
        hdr_boost = self.mult_boost_table.horizontalHeader()
        hdr_boost.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 8):
            hdr_boost.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        hdr_boost.resizeSection(1, 130)
        hdr_boost.resizeSection(2, 110)
        hdr_boost.resizeSection(3, 150)
        hdr_boost.resizeSection(4, 70)
        hdr_boost.resizeSection(5, 90)
        hdr_boost.resizeSection(6, 120)
        hdr_boost.resizeSection(7, 80)
        boost_toggle = QPushButton("▼ 倍率提升(%)")
        boost_toggle.setObjectName("formToggle")
        boost_toggle.setStyleSheet("QPushButton { border: none; background: transparent; padding: 2px 6px; text-align: left; } QPushButton:checked { font-weight: bold; }")
        boost_toggle.setFlat(True)
        boost_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        boost_toggle.setCheckable(True)
        boost_toggle.setChecked(True)
        boost_toggle.toggled.connect(lambda checked, b=boost_toggle: (b.setText(("▼ " if checked else "▶ ") + "倍率提升(%)")))
        boost_toggle.toggled.connect(self.mult_boost_table.setVisible)
        mult_form.addRow(boost_toggle, self.mult_boost_table)
        scroll_layout.addWidget(mult_group)

        # —— 计算过程（已包含所有乘区数值 + 来源超链接） ——
        zones = item["zones"]
        process_group = QGroupBox("计算过程")
        process_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        process_layout = QVBoxLayout(process_group)
        process_layout.setSpacing(6)

        # 复制按钮
        process_copy_header = QHBoxLayout()
        process_copy_header.setContentsMargins(0, 0, 0, 0)
        process_copy_header.addStretch()
        self._detail_process_copy_btn = QPushButton("📋 复制计算过程")
        self._detail_process_copy_btn.setObjectName("processCopyBtn")
        self._detail_process_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._detail_process_copy_btn.clicked.connect(self._copy_detail_process)
        process_copy_header.addWidget(self._detail_process_copy_btn)
        process_layout.addLayout(process_copy_header)

        # 过程内容标签（富文本 + 可拖选 + 可点击链接）
        self._detail_process_label = QLabel()
        self._detail_process_label.setObjectName("processLabel")
        self._detail_process_label.setWordWrap(True)
        self._detail_process_label.setTextFormat(Qt.TextFormat.RichText)
        self._detail_process_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._detail_process_label.linkActivated.connect(self._on_detail_process_link)
        self._detail_process_label.linkHovered.connect(self._on_detail_process_hover)

        process_html = item.get("process_html", "")
        if process_html:
            self._detail_process_label.setText(process_html)
        else:
            self._detail_process_label.setText("<p style='color: #888;'>无计算过程数据</p>")
        process_layout.addWidget(self._detail_process_label)

        scroll_layout.addWidget(process_group)

        # 关键词编辑区（在计算结果下方）
        kw_group = QGroupBox("搜索关键词")
        kw_layout = QVBoxLayout(kw_group)
        kw_layout.setContentsMargins(8, 6, 8, 6)
        self._kw_flow = QWidget()
        self._kw_flow_layout = FlowLayout(self._kw_flow)
        self._kw_flow_layout.setSpacing(4)
        self._kw_flow_layout._center_rows = True
        self._build_detail_keyword_tags(item)
        kw_layout.addWidget(self._kw_flow)
        scroll_layout.addWidget(kw_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # —— 按钮栏 ——
        btn_row = QHBoxLayout()

        self.lock_btn = QPushButton("解锁" if item["locked"] else "锁定")
        self.lock_btn.setObjectName("backButton")
        self.lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_btn.clicked.connect(self._toggle_lock)
        btn_row.addWidget(self.lock_btn)

        update_btn = QPushButton("更新")
        update_btn.setObjectName("backButton")
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.clicked.connect(self._update_from_source)
        btn_row.addWidget(update_btn)

        btn_row.addStretch()

        del_btn = QPushButton("删除")
        del_btn.setObjectName("backButton")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(self._confirm_delete)
        btn_row.addWidget(del_btn)

        close_btn = QPushButton("关闭")
        close_btn.setObjectName("backButton")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        self.adjustSize()

    def _copy_detail_process(self):
        """将详情弹窗中的计算过程纯文本复制到剪贴板。"""
        html = self._detail_process_label.text()
        if not html.strip():
            QMessageBox.information(self, "提示", "没有可复制的计算过程。")
            return
        doc = QTextDocument()
        doc.setHtml(html)
        QApplication.clipboard().setText(doc.toPlainText())
        QMessageBox.information(self, "已复制", "计算过程已复制到剪贴板。")

    def _on_detail_process_link(self, url):
        """处理详情弹窗中链接点击，导航跳转。"""
        if "\x1e" in url:
            url = url.split("\x1e")[0]
        if url.startswith("hl:"):
            parts = url[3:].split(":", 4)
            if len(parts) >= 5:
                sk, name, src, nk, sq = parts[0], parts[1], parts[2], parts[3], parts[4]
                # 详情弹窗中的链接跳转到主界面
                main_win = self.parent()
                if main_win and hasattr(main_win, 'main_screen'):
                    ms = main_win.main_screen
                    if hasattr(ms, '_navigate_to'):
                        ms._navigate_to(sk)
                    tp = getattr(ms, f'page_{sk}', None)
                    if tp and hasattr(tp, 'highlight_item'):
                        QTimer.singleShot(200, lambda: tp.highlight_item(name, src, nk, sq))

    def _on_detail_process_hover(self, url):
        """鼠标悬停链接时显示来源 tooltip。"""
        if "\x1e" in url:
            tip = url.split("\x1e", 1)[1]
            tip = tip.replace("&#10;", "\n")
            QToolTip.showText(QCursor.pos(), tip, self._detail_process_label)
        else:
            QToolTip.hideText()

    def _build_detail_keyword_tags(self, item):
        """在详情弹窗中构建关键词标签（可增删），并自动关联「关键词关联」页面匹配的关键词。"""
        while self._kw_flow_layout.count():
            child = self._kw_flow_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        keywords = item.setdefault("keywords", [])
        # 从关键词关联页面查找匹配的关键词
        item_name = item.get("label", "")
        try:
            w = self.parent()
            if w and hasattr(w, 'main_screen'):
                kw_page = getattr(w.main_screen, 'page_keyword_assoc', None)
                if kw_page:
                    for kw_item in kw_page.get_items():
                        kw_name = kw_item.get("name", "")
                        # 精确匹配或子串匹配（例如 "攻击力加成" 匹配 "攻击力加成_火伤_重击"）
                        if kw_name and (kw_name == item_name or kw_name in item_name or item_name in kw_name):
                            kw_text = kw_item.get("keywords", "")
                            for kw in kw_text.split(","):
                                kw = kw.strip()
                                if kw and kw not in keywords:
                                    keywords.append(kw)
        except Exception:
            pass
        for kw in keywords:
            tag = QWidget()
            tl = QHBoxLayout(tag)
            tl.setContentsMargins(0, 0, 0, 0)
            tl.setSpacing(2)
            tag.setStyleSheet(
                "background: rgba(100,181,246,0.15); border: 1px solid rgba(100,181,246,0.3);"
                "border-radius: 3px; padding: 4px 6px;"
            )
            kl = QLabel(kw)
            kl.setStyleSheet("color: #64b5f6; font-size: 11px; border: none; background: transparent;")
            tl.addWidget(kl)
            db = QPushButton("×")
            db.setFixedSize(16, 16)
            db.setStyleSheet(
                "QPushButton { color: #e94560; font-size: 10px; border: none; background: transparent; }"
                "QPushButton:hover { color: #ff4444; }"
            )
            db.clicked.connect(lambda checked, k=kw: self._detail_remove_keyword(item, k))
            tl.addWidget(db)
            self._kw_flow_layout.addWidget(tag)
        ab = QPushButton("+ 添加")
        ab.setStyleSheet(
            "QPushButton { color: #64b5f6; font-size: 11px; border: 1px dashed rgba(100,181,246,0.4);"
            "border-radius: 3px; background: transparent; padding: 2px 6px; }"
            "QPushButton:hover { background: rgba(100,181,246,0.1); }"
        )
        ab.clicked.connect(lambda: self._detail_add_keyword(item))
        self._kw_flow_layout.addWidget(ab)

    def _detail_add_keyword(self, item):
        text, ok = QInputDialog.getText(self, "添加关键词", "输入新关键词（最多 30 字符）：")
        if ok and text.strip():
            keywords = item.setdefault("keywords", [])
            kw = text.strip()[:30]
            if kw not in keywords:
                keywords.append(kw)
            self._build_detail_keyword_tags(item)
            self._page._refresh_cards()

    def _detail_remove_keyword(self, item, keyword):
        keywords = item.get("keywords", [])
        if keyword in keywords:
            keywords.remove(keyword)
        self._build_detail_keyword_tags(item)
        self._page._refresh_cards()

    def _on_name_changed(self, text):
        self._item["label"] = text
        self.setWindowTitle(f"结果详情 — {text}")
        self._build_detail_keyword_tags(self._item)
        self._page._refresh_cards()

    def _on_filter_changed(self):
        self._item["basis"] = self.filter_basis.currentText()
        self._item["element"] = None if self.filter_element.currentText() == "(无)" else self.filter_element.currentText()
        self._item["skill"] = None if self.filter_skill.currentText() == "(无)" else self.filter_skill.currentText()
        self._item["category"] = self.filter_category.currentText()
        self._item["effect"] = None if self.filter_effect.currentText() == "(无)" else self.filter_effect.currentText()
        items_data = _collect_all_items(self._page._external_sources, self._page._echo_pages)
        self._page._recalc_one(self._item, items_data)
        self._update_result_labels()
        self._update_result_labels()
        self._page._refresh_cards()

    def _on_mult_changed(self):
        self._item["base_mult"] = self.base_mult.value()
        inc_vals, boost_vals = self._gather_mult_data()
        self._item["mult_increase"] = sum(inc_vals)
        self._item["mult_boosts"] = boost_vals
        if not self._item["locked"]:
            items_data = _collect_all_items(self._page._external_sources, self._page._echo_pages)
            self._page._recalc_one(self._item, items_data)
            self._update_result_labels()
        else:
            z = self._item["zones"]
            base_m = self._item["base_mult"]
            mult_inc = self._item["mult_increase"]
            mult_zone = (base_m + mult_inc)
            for bv in self._item["mult_boosts"]:
                mult_zone *= (1.0 + bv / 100.0)
            base_dmg = z["atk_zone"] * z["bonus_zone"] * z["deepen_zone"] * z["def_zone"] * z["res_zone"] * z["indep_zone"] * mult_zone / 100.0
            z["mult_zone"] = mult_zone
            z["final_crit"] = base_dmg * z["crit_zone"]
            z["final_no_crit"] = base_dmg
        self._update_result_labels()
        self._update_result_labels()
        self._page._refresh_cards()


    # ── 倍率动态列表 ──
    # ⚠️ 以下 7 个方法（~183 行）与 ResultPage（~L8959 同名方法）完全重复：
    #    _sync_mult_entries / _jump_to_kw_row / _toggle_kw_hide / _get_kw_page
    #    _sync_sub_name_to_kw / _populate_mult_table / _gather_mult_data
    # 修改此处必须同步修改 ResultPage 的对应方法，否则行为分歧。
    # 未来重构：抽取到共享 mixin，从两个类引入，消除双份维护负担。见 docs/项目总结.md

    def _sync_mult_entries(self):
        """从关键词关联同步倍率值到表格（实时互通，只读展示）"""
        kw_page = getattr(self._page, '_keyword_assoc_page', None)
        card_kw_set = set(k.strip() for k in self._item.get("keywords", []))
        inc_rows = []
        boost_rows = []
        if kw_page:
            for kw_item in kw_page.get_items():
                kw_entry_kws = kw_item.get("keywords", "")
                if not kw_entry_kws or not card_kw_set:
                    continue
                entry_kw_set = set(k.strip() for k in kw_entry_kws.split(",") if k.strip())
                if not (entry_kw_set & card_kw_set):
                    continue
                name = kw_item.get("name", "")
                value = kw_item.get("value", 0.0)
                source = kw_item.get("source", "")
                sub_name = kw_item.get("sub_name", "")
                seq = kw_item.get("seq", "")
                if "倍率增加" in name:
                    inc_rows.append((name, sub_name, seq, value, source, kw_entry_kws))
                elif "倍率提升" in name:
                    boost_rows.append((name, sub_name, seq, value, source, kw_entry_kws))
        self._populate_mult_table(self.mult_inc_table, inc_rows)
        self._populate_mult_table(self.mult_boost_table, boost_rows)

    def _jump_to_kw_row(self, seq):
        """跳转到关键词关联页并高亮匹配序列号的行"""
        if not seq:
            return
        # 从当前 widget 向上找 MainScreen（centralWidget）
        ms = self
        while ms and not hasattr(ms, '_navigate_to_key'):
            ms = ms.parent() if hasattr(ms, 'parent') and callable(ms.parent) else None
        if ms and hasattr(ms, 'page_keyword_assoc'):
            ms._navigate_to_key("keyword_assoc", hl_seq=seq)

    def _toggle_kw_hide(self, kw_key, btn):
        """切换关键词关联条目的隐藏状态（实时触发重算）"""
        if kw_key in HIDDEN_ITEMS:
            HIDDEN_ITEMS.discard(kw_key)
            if btn:
                btn.setText("隐藏")
                btn.setObjectName("itemLockBtn")
        else:
            HIDDEN_ITEMS.add(kw_key)
            if btn:
                btn.setText("隐藏中")
                btn.setObjectName("itemDeleteBtn")
        if btn:
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        # 实时刷新表格 + 重算
        self._sync_mult_entries()
        if hasattr(self, 'auto_compute'):
            self.compute()  # 隐藏强制重算，无视 auto_compute 开关
        elif hasattr(self, '_on_mult_changed'):
            self._on_mult_changed()

    def _get_kw_page(self):
        """获取关键词关联页引用"""
        if hasattr(self, '_keyword_assoc_page') and self._keyword_assoc_page:
            return self._keyword_assoc_page
        if hasattr(self, '_page') and hasattr(self._page, '_keyword_assoc_page'):
            return self._page._keyword_assoc_page
        return None

    def _sync_sub_name_to_kw(self, seq, text):
        """将倍率表格中的副名称编辑同步回关键词关联对应行"""
        kw_page = self._get_kw_page()
        if not kw_page or not seq:
            return
        for row in range(kw_page._table.rowCount()):
            sl = kw_page._table.cellWidget(row, 2)
            if sl and hasattr(sl, 'text') and sl.text() == seq:
                sub_cell = kw_page._table.cellWidget(row, 1)
                if sub_cell:
                    le = sub_cell.findChild(QLineEdit) if not isinstance(sub_cell, QLineEdit) else sub_cell
                    if le and le.text() != text:
                        le.setText(text)
                return

    def _populate_mult_table(self, table, rows):
        """填充倍率表格（照搬关键词关联表格结构，来源可跳转，操作可隐藏）"""
        table.setRowCount(0)
        for name, sub_name, seq, value, source, kw_entry_kws in rows:
            r = table.rowCount()
            table.insertRow(r)
            table.setRowHeight(r, 40)
            # 名称
            name_w = QLineEdit(name)
            name_w.setObjectName("nameEdit")
            name_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_w.setReadOnly(True)
            table.setCellWidget(r, 0, name_w)
            # 副名称（编辑后自动映射回关键词关联表格）
            sub_container = _make_sub_name_cell(QLineEdit(), lambda n=name: n)
            sub_w = sub_container.findChild(QLineEdit)
            if sub_w:
                sub_w.setText(sub_name)
                sub_w.setObjectName("nameEdit")
                sub_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sub_w.setPlaceholderText("（备注）")
                sub_w.textChanged.connect(lambda text, sq=seq: self._sync_sub_name_to_kw(sq, text))
            table.setCellWidget(r, 1, sub_container)
            # 序列号
            seq_w = QLabel(seq if seq else "—")
            seq_w.setObjectName("seqLabel")
            seq_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setCellWidget(r, 2, seq_w)
            # 数值
            val_w = QDoubleSpinBox()
            val_w.setObjectName("itemValueSpin")
            val_w.setRange(0, 9999)
            val_w.setDecimals(4)
            val_w.setValue(value)
            val_w.setFixedWidth(100)
            val_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_w.setReadOnly(True)
            val_w.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            table.setCellWidget(r, 3, val_w)
            # 取值
            unit_w = QLabel("百分比")
            unit_w.setObjectName("unitLabel")
            unit_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setCellWidget(r, 4, unit_w)
            # 来源（按钮 — 点击跳转关键词关联页对应行）
            src_btn = QPushButton(source if source else "—")
            src_btn.setObjectName("itemLockBtn")
            src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            src_btn.setToolTip("跳转到关键词关联页定位此行")
            src_btn.clicked.connect(lambda checked, sq=seq:
                self._jump_to_kw_row(sq))
            table.setCellWidget(r, 5, src_btn)
            # 关键词关联
            kw_w = QLabel(kw_entry_kws)
            kw_w.setObjectName("seqLabel")
            kw_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            kw_w.setWordWrap(True)
            table.setCellWidget(r, 6, kw_w)
            # 操作（隐藏按钮）
            kw_key = (name, "keyword_assoc", seq)
            is_hid = kw_key in HIDDEN_ITEMS
            hide_btn = QPushButton("隐藏中" if is_hid else "隐藏")
            hide_btn.setObjectName("itemDeleteBtn" if is_hid else "itemLockBtn")
            hide_btn.setFixedSize(48, 28)
            hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            hide_btn.clicked.connect(lambda checked, k=kw_key, b=hide_btn:
                self._toggle_kw_hide(k, b))
            ops = QWidget()
            ops_layout = QHBoxLayout(ops)
            ops_layout.setContentsMargins(0, 0, 0, 0)
            ops_layout.addStretch()
            ops_layout.addWidget(hide_btn)
            ops_layout.addStretch()
            table.setCellWidget(r, 7, ops)


    def _gather_mult_data(self):
        "从关键词关联收集有效倍率值（必须有匹配关键词）"
        inc_vals = []
        boost_vals = []
        kw_page = self._keyword_assoc_page if hasattr(self, '_keyword_assoc_page') else getattr(getattr(self, '_page', None), '_keyword_assoc_page', None)
        card_kw_set = set(self._keywords) if hasattr(self, '_keywords') else set(k.strip() for k in self._item.get("keywords", []))
        if kw_page and card_kw_set:
            for kw_item in kw_page.get_items():
                kw_entry_kws = kw_item.get("keywords", "")
                if not kw_entry_kws:
                    continue
                entry_kw_set = set(k.strip() for k in kw_entry_kws.split(",") if k.strip())
                if not (entry_kw_set & card_kw_set):
                    continue
                name = kw_item.get("name", "")
                value = kw_item.get("value", 0.0)
                source = kw_item.get("source", "")
                seq = kw_item.get("seq", "")
                if (name, "keyword_assoc", seq) in HIDDEN_ITEMS:
                    continue
                if "倍率增加" in name:
                    inc_vals.append(value)
                elif "倍率提升" in name:
                    boost_vals.append(value)
        return inc_vals, boost_vals
    def _patch_process_html(self):
        """重新生成与 ResultPage 相同格式的计算过程 HTML"""
        items_data = _collect_all_items(self._page._external_sources, self._page._echo_pages)
        filtered = [(n, v, s, nk, sq) for n, v, s, nk, sq, *_ in items_data
                    if _matches_filter(n, self._item.get("element"), self._item.get("skill"), self._item.get("effect"))
                    and (n, nk, sq) not in HIDDEN_ITEMS]
        # 关键词注入
        if hasattr(self._page, '_keyword_assoc_page') and self._page._keyword_assoc_page:
            item_kws = set(k.strip() for k in self._item.get("keywords", []))
            if item_kws:
                for kw_item in self._page._keyword_assoc_page.get_items():
                    kw_entry_kws = set(k.strip() for k in kw_item.get("keywords", "").split(",") if k.strip())
                    if item_kws & kw_entry_kws:
                        seq = kw_item.get("seq", "")
                        filtered.append((
                            kw_item["name"], kw_item["value"],
                            kw_item.get("source", "关键词关联"), "keyword_assoc", seq,
                        ))
        self._item["process_html"] = self._page._build_card_process_html(filtered, self._item)

    def _update_result_labels(self):
        """更新计算过程显示 — 优先使用 item 中已有的详细 process_html"""
        if not hasattr(self, '_detail_process_label'):
            return
        html = self._item.get("process_html", "")
        if not html:
            html = self._rebuild_process_html()
        self._detail_process_label.setText(html)

    def _rebuild_process_html(self):
        """从 item 的 zones 实时构建计算过程 HTML"""
        z = self._item.get("zones", {})
        if not z:
            return "<p style='color: #888;'>无计算过程数据</p>"
        base_m = self._item.get("base_mult", 100)
        mult_inc = self._item.get("mult_increase", 0)
        mult_boosts = self._item.get("mult_boosts", [0, 0, 0])

        def _row(label, formula, result):
            return (f'<tr><td style="color:#a0a0b0;padding:2px 8px;white-space:nowrap;">'
                    f'{label}</td>'
                    f'<td style="color:#e0e0e0;padding:2px 8px;font-family:monospace;">'
                    f'{formula}</td>'
                    f'<td style="color:#e94560;padding:2px 8px;text-align:right;font-weight:600;">'
                    f'{result}</td></tr>')

        mult_formula = f"({base_m:.2f}%"
        if mult_inc > 0:
            mult_formula += f" + {mult_inc:.2f}%"
        mult_formula += ")"
        for i, bv in enumerate(mult_boosts):
            if bv > 0:
                mult_formula += f" × (1 + {bv:.2f}%)"

        override_hint = ""
        page_list = getattr(self, "_page", None)
        if page_list and getattr(page_list, "_base_override_enabled", False):
            override_hint = (
                '<tr><td colspan="3" style="color:#64b5f6;font-weight:600;font-size:12px;padding:2px 8px;border:0;">'
                '\u25b8 已启用手动填写基础数值</td></tr>'
            )
        html = (
            '<table style="border-collapse:collapse;width:100%;font-size:13px;">'
            + _row("基础数值", f"{z['atk_zone']:.10f}", "")
            + override_hint
            + _row("× 加成乘区", f"{z['bonus_zone']:.10f}", "")
            + _row("× 加深乘区", f"{z['deepen_zone']:.10f}", "")
            + _row("× 暴击乘区", f"{z['crit_zone']:.10f}", "")
            + _row("× 防御乘区", f"{z['def_zone']:.10f}", "")
            + _row("× 抗性乘区", f"{z['res_zone']:.10f}", "")
            + _row("× 独立乘区", f"{z['indep_zone']:.10f}", "")
            + _row("× 倍率乘区", mult_formula, f"{z['mult_zone']:.10f}")
            + '</table>'
            + f'<hr style="border:none;border-top:1px solid #444;margin:8px 0;">'
            + f'<p style="color:#e94560;font-size:18px;font-weight:700;">'
            + f'暴击后伤害 = {z["final_crit"]:.2f}</p>'
            + f'<p style="color:#a0a0b0;font-size:14px;">'
            + f'无暴击伤害 = {z["final_no_crit"]:.2f}</p>'
        )
        return html

    def _toggle_lock(self):
        self._item["locked"] = not self._item["locked"]
        self.lock_btn.setText("解锁" if self._item["locked"] else "锁定")
        if not self._item["locked"]:
            items_data = _collect_all_items(self._page._external_sources, self._page._echo_pages)
            self._page._recalc_one(self._item, items_data)
            self._update_result_labels()
        self._page._refresh_cards()

    def _update_from_source(self):
        """从数值来源同步数据并重算"""
        if self._item.get("locked"):
            _show_toast(self, "当前结果已锁定，请先解锁")
            return
        items_data = _collect_all_items(self._page._external_sources, self._page._echo_pages)
        self._page._recalc_one(self._item, items_data)
        self._update_result_labels()
        self._update_result_labels()
        self._page._refresh_cards()

    def _confirm_delete(self):
        if self._item.get("locked"):
            reply1 = QMessageBox.question(
                self, "解锁确认", f"「{self._item['label']}」已被锁定，是否解锁？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply1 != QMessageBox.StandardButton.Yes:
                return
            self._item["locked"] = False
            self.lock_btn.setText("锁定")
            self._page._refresh_cards()
        reply2 = QMessageBox.question(
            self, "确认删除", f"是否删除「{self._item['label']}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply2 == QMessageBox.StandardButton.Yes:
            self._page._delete_item(self._idx)
            self.accept()

    def update_results(self, item):
        """外部数据变更时更新当前详情窗口的显示（由 ResultListPage.recalc 调用）"""
        self._item = item
        # 保留已有的详细 process_html，仅更新显示
        if hasattr(self, '_detail_process_label'):
            html = item.get("process_html", "")
            if not html and hasattr(self, '_rebuild_process_html'):
                html = self._rebuild_process_html()
            if html:
                self._detail_process_label.setText(html)


# ==================== 走马灯标签 ====================

class MarqueeLabel(QLabel):
    """走马灯标签：文字超出宽度时自动从右到左无缝滚动，悬停时暂停。"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._offset = 0.0
        self._marquee = False
        self._paused = False
        self._speed = 0.65
        self.setMouseTracking(True)

    # ---------- public ----------

    def setText(self, text):
        super().setText(text)
        self._offset = 0.0
        self._check_marquee()

    # ---------- helpers ----------

    def _tw(self):
        return self.fontMetrics().horizontalAdvance(self.text())

    def _gap(self):
        return max(self.width() * 0.35, 30.0)

    def _text_color(self):
        try:
            w = self.window()
            if w and hasattr(w, 'current_theme') and w.current_theme == "light":
                return QColor("#2c2c2c")
        except Exception as e:
            _logger.debug("MarqueeLabel._text_color 失败: %s", e)
        return QColor("#dde0e6")

    # ---------- marquee ----------

    def _check_marquee(self):
        if self.width() <= 0:
            return
        self._marquee = self._tw() > self.width() - 4
        if self._marquee:
            if not self._paused:
                self._timer.start(16)
        else:
            self._timer.stop()
            self._offset = 0.0
        self.update()

    def _step(self):
        self._offset += self._speed
        cycle = self._tw() + self._gap()
        if self._offset >= cycle:
            self._offset -= cycle
        self.update()

    # ---------- paint ----------

    def paintEvent(self, event):
        if not self._marquee:
            super().paintEvent(event)
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self.font())
        p.setPen(self._text_color())

        tw = self._tw()
        gap = self._gap()
        h = self.height()

        p.drawText(QRectF(-self._offset, 0, tw, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self.text())
        p.drawText(QRectF(tw + gap - self._offset, 0, tw, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self.text())
        p.end()

    # ---------- events ----------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._check_marquee()

    def enterEvent(self, event):
        self._paused = True
        self._timer.stop()

    def leaveEvent(self, event):
        self._paused = False
        if self._marquee:
            self._timer.start(16)


# ==================== 结果列表页面 ====================

class ResultListPage(QWidget):
    """结果列表页. 以卡片形式保存多条计算结果, 支持锁定/批量操作/自动更新."""
    def __init__(self):
        super().__init__()
        self._items = []
        self._id_counter = 0
        self._navigate = None
        self._external_sources = []
        self._echo_pages = {}
        self._keyword_assoc_page = None  # 关键词关联页引用
        self._open_detail_dialogs = []  # 跟踪已打开的详情弹窗
        self._defense_page = None
        self._resistance_page = None
        self._indep_zone_page = None
        self._auto_update = False
        self._selection_mode = None  # None / "update" / "delete"
        self._checked = set()
        self._result_page = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("结果列表")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # —— 搜索栏 ——
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索标题或关键词...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setObjectName("resultSearchInput")
        light = self._is_light_theme()
        sr_bg = "#f0f4fa" if light else "#1e2a3a"
        sr_fg = "#1b2035" if light else "#e0e0e0"
        sr_bd = "#b8c4d6" if light else "#555"
        sr_focus = "#5070e8" if light else "#e94560"
        self._search_input.setStyleSheet(
            f"QLineEdit#resultSearchInput {{ padding: 4px 6px; border: 1px solid {sr_bd}; border-radius: 6px;"
            f"font-size: 14px; background: {sr_bg}; color: {sr_fg}; }}"
            f"QLineEdit#resultSearchInput:focus {{ border-color: {sr_focus}; }}"
        )
        self._search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_input)

        # —— 工具栏 ——
        toolbar = QHBoxLayout()

        self.update_all_btn = QPushButton("全部更新")
        self.update_all_btn.setObjectName("backButton")
        self.update_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_all_btn.clicked.connect(self._update_all)
        toolbar.addWidget(self.update_all_btn)

        self.batch_update_btn = QPushButton("批量更新")
        self.batch_update_btn.setObjectName("backButton")
        self.batch_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.batch_update_btn.clicked.connect(lambda: self._enter_selection("update"))
        toolbar.addWidget(self.batch_update_btn)

        self.delete_all_btn = QPushButton("全部删除")
        self.delete_all_btn.setObjectName("backButton")
        self.delete_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_all_btn.clicked.connect(self._delete_all)
        toolbar.addWidget(self.delete_all_btn)

        self.batch_delete_btn = QPushButton("批量删除")
        self.batch_delete_btn.setObjectName("backButton")
        self.batch_delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.batch_delete_btn.clicked.connect(lambda: self._enter_selection("delete"))
        toolbar.addWidget(self.batch_delete_btn)

        self.auto_update_btn = QPushButton("开启自动更新")
        self.auto_update_btn.setObjectName("backButton")
        self.auto_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_update_btn.setStyleSheet(self._AUTO_OFF_STYLE)
        self.auto_update_btn.clicked.connect(self._toggle_auto_update)
        toolbar.addWidget(self.auto_update_btn)

        # OCR 倍率识别按钮
        self.dmg_ocr_file_btn = QPushButton("导图识别")
        self.dmg_ocr_file_btn.setObjectName("backButton")
        self.dmg_ocr_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dmg_ocr_file_btn.clicked.connect(lambda: self._on_ocr_file_btn())
        toolbar.addWidget(self.dmg_ocr_file_btn)

        self.dmg_ocr_clip_btn = QPushButton("截图识别")
        self.dmg_ocr_clip_btn.setObjectName("backButton")
        self.dmg_ocr_clip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dmg_ocr_clip_btn.clicked.connect(lambda: self._on_ocr_clip_btn())
        toolbar.addWidget(self.dmg_ocr_clip_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # —— 分类筛选行 ——
        self._category_filter = "全部"
        cat_row = QHBoxLayout()
        cat_row.setSpacing(4)
        self._category_buttons = {}
        for cat in ["全部"] + DAMAGE_CATEGORIES:
            btn = QPushButton(cat)
            btn.setObjectName("backButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            if cat == "全部":
                btn.setChecked(True)
                btn.setStyleSheet(
                    "QPushButton { font-size: 12px; padding: 4px 12px; "
                    "background: rgba(80,112,232,0.3); color: #5070e8; border: 1px solid #5070e8; "
                    "border-radius: 4px; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { font-size: 12px; padding: 4px 10px; "
                    "border: 1px solid #555; border-radius: 4px; "
                    "color: #aaa; background: transparent; }"
                )
            btn.clicked.connect(lambda checked, c=cat: self._on_category_changed(c))
            cat_row.addWidget(btn)
            self._category_buttons[cat] = btn
        cat_row.addStretch()
        layout.addLayout(cat_row)

        # —— 批量操作确认栏（选择模式下可见） ——
        self._batch_action_bar = QWidget()
        self._batch_action_bar.setVisible(False)
        ba_layout = QHBoxLayout(self._batch_action_bar)
        ba_layout.setContentsMargins(0, 0, 0, 0)
        self._batch_label = QLabel("")
        ba_layout.addWidget(self._batch_label)
        ba_layout.addStretch()
        self._batch_confirm_btn = QPushButton("确认")
        self._batch_confirm_btn.setObjectName("backButton")
        self._batch_confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._batch_confirm_btn.clicked.connect(self._batch_confirm)
        ba_layout.addWidget(self._batch_confirm_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("backButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self._cancel_selection)
        ba_layout.addWidget(cancel_btn)
        layout.addWidget(self._batch_action_bar)

        # —— 卡片容器（可滚动） ——
        self._cards_area = QScrollArea()
        self._cards_area.setWidgetResizable(True)
        self._cards_area.setFrameShape(QFrame.Shape.NoFrame)
        self._cards_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._cards_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards_container = QWidget()
        self._cards_layout = QGridLayout(self._cards_container)
        self._cards_layout.setSpacing(4)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_area.setWidget(self._cards_container)
        layout.addWidget(self._cards_area, stretch=1)

    def set_external_sources(self, sources):
        self._external_sources = sources

    def set_echo_sources(self, echo_pages_dict):
        self._echo_pages = echo_pages_dict or {}

    def set_defense_page(self, page):
        self._defense_page = page

    def set_resistance_page(self, page):
        self._resistance_page = page

    def set_indep_zone_page(self, page):
        self._indep_zone_page = page

    def set_result_page(self, page):
        self._result_page = page

    def set_keyword_assoc_page(self, page):
        self._keyword_assoc_page = page

    def set_base_override(self, enabled, value):
        self._base_override_enabled = enabled
        self._base_override_value = value
        # 强制刷新卡片以更新基础数值行状态
        self._refresh_cards()

    def set_dmg_ocr_buttons_enabled(self, enabled):
        self.dmg_ocr_file_btn.setEnabled(enabled)
        self.dmg_ocr_clip_btn.setEnabled(enabled)
        if enabled:
            self.dmg_ocr_file_btn.setText("导图识别")
            self.dmg_ocr_clip_btn.setText("截图识别")
        else:
            self.dmg_ocr_file_btn.setText("识别中...")
            self.dmg_ocr_clip_btn.setText("识别中...")

    def _on_ocr_file_btn(self):
        if not self._result_page:
            QMessageBox.warning(self, "错误", "识别功能未正确初始化，请重启应用。")
            return
        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self.window() or self, "选择伤害倍率截图（最多5张）", "",
                "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*.*)"
            )
            if not file_paths:
                return
            sources = [(fp, False) for fp in file_paths[:5]]
            self._result_page._start_dmg_ocr(sources)
        except Exception as e:
            _logger.exception("导图识别失败: %s", e)
            QMessageBox.critical(self, "错误", f"导图识别失败:\n{e}")

    def _on_ocr_clip_btn(self):
        if not self._result_page:
            QMessageBox.warning(self, "错误", "识别功能未正确初始化，请重启应用。")
            return
        try:
            clipboard = QApplication.clipboard()
            if not clipboard.mimeData().hasImage():
                QMessageBox.information(self.window() or self, "无截图",
                    "剪贴板中没有图片。\n请先使用截图工具截图，再点击此按钮。")
                return
            qimage = clipboard.image()
            if qimage.isNull():
                QMessageBox.information(self.window() or self, "无截图",
                    "剪贴板中没有图片。\n请先使用截图工具截图，再点击此按钮。")
                return
            self._result_page._start_dmg_ocr([(qimage, True)])
        except Exception as e:
            _logger.exception("截图识别失败: %s", e)
            QMessageBox.critical(self, "错误", f"截图识别失败:\n{e}")

    # —— 核心计算 ——
    def recalc(self, force=False):
        """外部回调触发；仅当开启自动更新或 force 时重算所有未锁定条目。"""
        if not force and not self._auto_update:
            return
        items_data = _collect_all_items(self._external_sources, self._echo_pages)
        for item in self._items:
            if item["locked"]:
                continue
            self._recalc_one(item, items_data)
            # 自动更新时同步重新生成计算过程 HTML
            sub_map = {}
            for it in items_data:
                if len(it) >= 6 and it[5]:
                    sub_map[(it[0], it[2], it[3], it[4])] = it[5]
            filtered = [(n, v, s, nk, sq) for n, v, s, nk, sq, *_ in items_data
                        if _matches_filter(n, item.get("element"), item.get("skill"), item.get("effect"))
                        and (n, nk, sq) not in HIDDEN_ITEMS]
            if self._keyword_assoc_page:
                item_kws = set(k.strip() for k in item.get("keywords", []))
                if item_kws:
                    for kw_item in self._keyword_assoc_page.get_items():
                        kw_entry_kws = set(k.strip() for k in kw_item.get("keywords", "").split(",") if k.strip())
                        if item_kws & kw_entry_kws:
                            name = kw_item["name"]
                            value = kw_item["value"]
                            source = kw_item.get("source", "关键词关联")
                            seq = kw_item.get("seq", "")
                            if (name, "keyword_assoc", seq) in HIDDEN_ITEMS:
                                continue
                            filtered.append((name, value, source, "keyword_assoc", seq))
            item["process_html"] = self._build_card_process_html(filtered, item, sub_map)
        self._refresh_cards()
        # 如果详情弹窗打开着，同步更新当前显示的那张卡片（不是第一个未锁定）
        open_dlg = getattr(self, '_open_detail', None)
        if open_dlg is not None and open_dlg.isVisible():
            current_item = getattr(open_dlg, '_item', None)
            if current_item is not None and not current_item.get("locked"):
                open_dlg.update_results(current_item)

    def _recalc_one(self, item, all_items):
        # 构建 sub_map（副名称 tooltip，来自原始数据）
        sub_map = {}
        for it in all_items:
            if len(it) >= 6 and it[5]:
                sub_map[(it[0], it[2], it[3], it[4])] = it[5]
        filtered = [(n, v, s, nk, sq) for n, v, s, nk, sq, *_sub in all_items
                    if _matches_filter(n, item["element"], item["skill"], item["effect"])
                    and (n, nk, sq) not in HIDDEN_ITEMS]
        # 从关键词关联页面注入匹配的效果（倍率增加/提升单独提取给倍率乘区）
        kw_mult_inc = 0.0
        kw_mult_boosts = []
        if self._keyword_assoc_page:
            item_keywords = set(k.strip() for k in item.get("keywords", []))
            if item_keywords:
                for kw_item in self._keyword_assoc_page.get_items():
                    kw_entry_kws_comma = kw_item.get("keywords", "")
                    if not kw_entry_kws_comma:
                        continue
                    kw_entry_kws = set(k.strip() for k in kw_entry_kws_comma.split(",") if k.strip())
                    if not (item_keywords & kw_entry_kws):
                        continue
                    name = kw_item["name"]
                    value = kw_item["value"]
                    source = kw_item.get("source", "关键词关联")
                    seq = kw_item.get("seq", "")
                    # 检查 HIDDEN_ITEMS
                    if (name, "keyword_assoc", seq) in HIDDEN_ITEMS:
                        continue
                    # 注入到 filtered 参与常规乘区分类
                    filtered.append((name, value, source, "keyword_assoc", seq))
                    # 倍率增加/提升单独累加（不参与 BONUS_SUFFIX 等分类）
                    if "倍率增加" in name:
                        kw_mult_inc += value
                    elif "倍率提升" in name:
                        kw_mult_boosts.append(value)
        basis = item["basis"]
        base_value = 0.0; weapon_base = 0.0; total_pct = 0.0; total_flat = 0.0
        if basis == "攻击力":
            for name, value, _, _, _ in filtered:
                if name == "角色基础攻击力": base_value = value
                elif name == "武器基础攻击力": weapon_base = value
                elif "攻击力" in name and "固定" not in name: total_pct += value
                elif "固定攻击" in name: total_flat += value
        elif basis == "生命值":
            for name, value, _, _, _ in filtered:
                if name == "角色基础生命值": base_value = value
                elif "生命值" in name and "固定" not in name: total_pct += value
                elif "固定生命" in name: total_flat += value
        else:
            for name, value, _, _, _ in filtered:
                if name == "角色基础防御力": base_value = value
                elif "防御力" in name and "固定" not in name: total_pct += value
                elif "固定防御" in name: total_flat += value
        computed_base_zone = (base_value + weapon_base) * (1.0 + total_pct / 100.0) + total_flat
        if getattr(self, '_base_override_enabled', False):
            base_zone = self._base_override_value
        else:
            base_zone = computed_base_zone
        total_bonus = sum(v for n, v, _, _, _ in filtered
                         if any(s in n for s in BONUS_SUFFIX)
                         and not any(kw in n for kw in CRIT_DMG_KEYWORDS))
        bonus_zone = 1.0 + total_bonus / 100.0
        total_deepen = sum(v for n, v, _, _, _ in filtered if DEEPEN_SUFFIX in n)
        deepen_zone = 1.0 + total_deepen / 100.0
        total_crit_rate = 5.0 + sum(v for n, v, _, _, _ in filtered
                                     if any(kw in n for kw in CRIT_RATE_KEYWORDS)
                                     and not any(kw in n for kw in CRIT_DMG_KEYWORDS))
        total_crit_dmg = 150.0 + sum(v for n, v, _, _, _ in filtered if any(kw in n for kw in CRIT_DMG_KEYWORDS))
        crit_zone = total_crit_dmg / 100.0
        if self._defense_page and hasattr(self._defense_page, 'get_defense_zone'):
            def_zone = self._defense_page.get_defense_zone(item.get("skill"))
        else:
            def_zone = 1.0
        res_zone = 1.0
        if self._resistance_page:
            res_zone = self._resistance_page.get_resistance_multiplier(item["element"])
        indep_zone = getattr(self._indep_zone_page, 'independent_zone', 1.0) if self._indep_zone_page else 1.0
        # 倍率乘区：基础倍率 + 关键词关联注入的倍率增加/倍率提升
        base_m = item["base_mult"]
        mult_inc = kw_mult_inc
        mult_boosts = kw_mult_boosts
        item["mult_increase"] = mult_inc
        item["mult_boosts"] = mult_boosts
        mult_zone = (base_m + mult_inc)
        for bv in mult_boosts:
            mult_zone *= (1.0 + bv / 100.0)
        base_dmg = base_zone * bonus_zone * deepen_zone * def_zone * res_zone * indep_zone * mult_zone / 100.0
        item["zones"] = {
            "atk_zone": base_zone, "bonus_zone": bonus_zone, "deepen_zone": deepen_zone,
            "crit_zone": crit_zone, "crit_rate": total_crit_rate,
            "def_zone": def_zone, "res_zone": res_zone,
            "indep_zone": indep_zone,
            "mult_zone": mult_zone, "final_crit": base_dmg * crit_zone, "final_no_crit": base_dmg,
            "computed_base_zone": computed_base_zone,
        }
        item["process_html"] = self._build_card_process_html(filtered, item)

    def _build_card_process_html(self, filtered, item, sub_map=None):
        """从 filtered 词条列表生成与 ResultPage 相同格式的计算过程 HTML"""
        z = item.get("zones", {})
        if not z:
            return ""
        basis = item.get("basis", "攻击力")
        base_m = item.get("base_mult", 100)
        mult_inc = item.get("mult_increase", 0)
        mult_boosts = item.get("mult_boosts", [])

        # 从 filtered 提取各乘区词条
        if basis == "攻击力":
            zone_label = "攻击力"
            pct_names = {"攻击力加成", "攻击力", "攻击"}
        elif basis == "生命值":
            zone_label = "生命值"
            pct_names = {"生命值"}
        else:
            zone_label = "防御力"
            pct_names = {"防御力"}

        base_value = sum(v for n, v, s, nk, sq in filtered if n == "角色基础攻击力")
        weapon_base = sum(v for n, v, s, nk, sq in filtered if n == "武器基础攻击力")
        if basis == "生命值":
            base_value = sum(v for n, v, s, nk, sq in filtered if n == "角色基础生命值")
        elif basis == "防御力":
            base_value = sum(v for n, v, s, nk, sq in filtered if n == "角色基础防御力")

        pct_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered
                     if any(kw in n for kw in pct_names)
                     and "固定" not in n and "基础" not in n and "伤害" not in n]
        flat_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered
                      if ("固定攻击" in n if basis == "攻击力" else
                          "固定生命" in n if basis == "生命值" else "固定防御" in n)]
        total_pct = sum(v for _, v, _, _, _ in pct_items)
        total_flat = sum(v for _, v, _, _, _ in flat_items)
        bonus_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered
                       if any(sfx in n for sfx in BONUS_SUFFIX)
                       and not any(kw in n for kw in CRIT_DMG_KEYWORDS)]
        total_bonus = sum(v for _, v, _, _, _ in bonus_items)
        deepen_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered if DEEPEN_SUFFIX in n]
        total_deepen = sum(v for _, v, _, _, _ in deepen_items)
        rate_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered
                      if any(kw in n for kw in CRIT_RATE_KEYWORDS)
                      and not any(kw in n for kw in CRIT_DMG_KEYWORDS)]
        total_crit_rate = z.get("crit_rate", 5.0)
        dmg_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered
                     if any(kw in n for kw in CRIT_DMG_KEYWORDS)]
        total_crit_dmg = 150.0 + sum(v for _, v, _, _, _ in dmg_items)

        return _render_process_html(
            basis, zone_label, base_value, weapon_base,
            pct_items, flat_items, total_pct, total_flat, z.get("atk_zone", 0),
            bonus_items, total_bonus, z.get("bonus_zone", 1),
            deepen_items, total_deepen, z.get("deepen_zone", 1),
            rate_items, dmg_items, total_crit_rate, total_crit_dmg, z.get("crit_zone", 1.5),
            z.get("def_zone", 1), z.get("res_zone", 1), z.get("indep_zone", 1), [],
            base_m, mult_inc, mult_boosts, z.get("mult_zone", 100),
            z.get("final_crit", 0), z.get("final_no_crit", 0),
            is_light=False, sub_map=sub_map,
            base_override_active=getattr(self, "_base_override_enabled", False),
            computed_base_zone=z.get("computed_base_zone", None),
        )

    # —— 添加条目 ——
    def add_item(self, settings):
        self._id_counter += 1
        """从计算结果页接收新记录, 添加到卡片列表并刷新."""
        # 将 "(无)" 统一规范为 None，与 _matches_filter 逻辑一致
        def _norm(v):
            return None if v == "(无)" else v
        label = settings.get("label") or f"计算_{self._id_counter}"
        item = {
            "id": self._id_counter,
            "label": label,
            "locked": False,
            "basis": settings["basis"],
            "element": _norm(settings["element"]),
            "skill": _norm(settings["skill"]),
            "effect": _norm(settings["effect"]),
            "category": settings.get("category", ""),
            "base_mult": settings["base_mult"],
            "mult_increase": settings["mult_increase"],
            "mult_boosts": list(settings["mult_boosts"]),
            "zones": dict(settings["zones"]),
            "timestamp": datetime.now().isoformat(),
            "keywords": settings.get("keywords") or _auto_keywords(label),
            "process_html": settings.get("process_html", ""),
        }
        self._items.append(item)
        self._refresh_cards()

    # —— 分类筛选 ——
    def _on_category_changed(self, category):
        self._category_filter = category
        # 更新按钮样式
        for cat, btn in self._category_buttons.items():
            if cat == category:
                btn.setChecked(True)
                btn.setStyleSheet(
                    "QPushButton { font-size: 12px; padding: 4px 12px; "
                    "background: rgba(80,112,232,0.3); color: #5070e8; border: 1px solid #5070e8; "
                    "border-radius: 4px; }"
                )
            else:
                btn.setChecked(False)
                btn.setStyleSheet(
                    "QPushButton { font-size: 12px; padding: 4px 10px; "
                    "border: 1px solid #555; border-radius: 4px; "
                    "color: #aaa; background: transparent; }"
                )
        self._refresh_cards()

    # —— 卡片视图 ——
    def _on_search_changed(self):
        self._refresh_cards()

    def _refresh_cards(self):
        # 获取搜索文本
        search_text = self._search_input.text().strip().lower() if hasattr(self, '_search_input') else ""

        # 清除旧卡片（先隐藏再标记删除，避免新旧卡片重叠）
        while self._cards_layout.count():
            child = self._cards_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif child.layout() is not None:
                lyt = child.layout()
                self._clear_layout(lyt)
                lyt.setParent(None)
                lyt.deleteLater()

        # 重置所有行列伸缩（避免旧值累积）
        for r in range(100):
            self._cards_layout.setRowStretch(r, 0)
        for c in range(4):
            self._cards_layout.setColumnStretch(c, 0)

        cols = 3
        # 三列均分宽度，配合居中实现整行居中
        for c in range(cols):
            self._cards_layout.setColumnStretch(c, 1)

        # 分类筛选 + 搜索过滤
        visible_items = []
        search_text = self._search_input.text().strip().lower() if hasattr(self, '_search_input') else ""
        cat_filter = getattr(self, '_category_filter', "全部")
        for item in self._items:
            # 分类筛选
            if cat_filter != "全部":
                item_cat = item.get("category", "")
                if item_cat != cat_filter:
                    continue
            # 搜索过滤（在分类筛选的基础上）
            if search_text:
                keywords = item.get("keywords", [])
                match_texts = [item.get("label", "").lower()] + [k.lower() for k in keywords]
                if not any(search_text in t for t in match_texts):
                    continue
            visible_items.append(item)

        for i, item in enumerate(visible_items):
            orig_idx = self._items.index(item)  # 用原列表中的真实索引
            card = self._build_card(orig_idx, item)
            row, col = divmod(i, cols)
            self._cards_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        # 底部弹簧
        vis_count = len(visible_items)
        last_row = max(0, (vis_count - 1) // cols) if vis_count else 0
        self._cards_layout.setRowStretch(last_row + 1, 1)

        # 同步刷新已打开的详情弹窗
        if hasattr(self, '_open_detail') and self._open_detail:
            try:
                dlg = self._open_detail
                dlg._sync_mult_entries()
                dlg._update_result_labels()
                if dlg._idx >= 0 and dlg._idx < len(self._items):
                    dlg.lock_btn.setText("解锁" if self._items[dlg._idx].get("locked") else "锁定")
            except Exception:
                pass

    def _clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            child = layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif child.layout() is not None:
                self._clear_layout(child.layout())

    def _build_card(self, idx, item):
        z = item["zones"]
        card = QFrame()
        card.setObjectName("resultCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        card.setFixedWidth(320)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(4)

        # 第一行：选择框(可选) + 名称 + 锁定标记
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        if self._selection_mode is not None:
            cb = QCheckBox()
            cb.setChecked(idx in self._checked)
            cb.toggled.connect(lambda checked, i=idx: self._on_check_toggled(i, checked))
            row1.addWidget(cb)
        name_lbl = MarqueeLabel(item["label"])
        name_lbl.setObjectName("resultHeader")
        row1.addWidget(name_lbl, stretch=1)
        if item["locked"]:
            lock_mark = QLabel("[锁]")
            lock_mark.setObjectName("labelSecondary")
            row1.addWidget(lock_mark)
        row1.addStretch()
        card_layout.addLayout(row1)

        # 第二行：暴击后伤害
        override_active = getattr(self, '_base_override_enabled', False)
        # 第二行：无暴击伤害
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        if 'final_no_crit' in z:
            row2.addWidget(QLabel(f"无暴击伤害: {z['final_no_crit']:.10f}"))
        else:
            row2.addWidget(QLabel("无暴击伤害: — (未计算)"))
        row2.addStretch()
        card_layout.addLayout(row2)

        # 第三行：暴击后伤害
        row3 = QHBoxLayout()
        row3.setContentsMargins(0, 0, 0, 0)
        if 'final_crit' in z:
            row3.addWidget(QLabel(f"暴击后伤害: {z['final_crit']:.10f}"))
        else:
            row3.addWidget(QLabel("暴击后伤害: — (未计算)"))
        row3.addStretch()
        card_layout.addLayout(row3)

        # 基础数值行（始终显示，状态不同文案不同）
        row_base = QHBoxLayout()
        row_base.setContentsMargins(0, 0, 0, 0)
        if override_active:
            base_text = "基础数值（手动填写）"
        else:
            base_text = "基础数值（原本数值）"
        base_lbl = QLabel(base_text)
        base_lbl.setStyleSheet("color: #64b5f6; font-weight: 600; font-size: 12px;")
        row_base.addWidget(base_lbl)
        row_base.addStretch()
        card_layout.addLayout(row_base)

        # 搜索关键词行（始终显示，方便用户添加）
        keywords = item.setdefault("keywords", [])
        kw_row = QHBoxLayout()
        kw_row.setContentsMargins(0, 0, 0, 0)
        kw_lbl = QLabel("关键词:")
        kw_lbl.setStyleSheet("color: #888; font-size: 11px;")
        kw_row.addWidget(kw_lbl)
        kw_flow = QWidget()
        kw_flow.setFixedHeight(46)
        kw_flow_layout = FlowLayout(kw_flow)
        kw_flow_layout.setSpacing(3)
        kw_flow_layout._center_rows = True
        self._build_keyword_tags(kw_flow_layout, keywords, item)
        kw_row.addWidget(kw_flow, stretch=1)
        card_layout.addLayout(kw_row)

        # 第四行：基础数值类型 & 元素属性
        row4 = QHBoxLayout()
        row4.setContentsMargins(0, 0, 0, 0)
        basis_text = item.get("basis", "攻击力")
        element_text = item.get("element") or "(无)"
        info1 = QLabel(f"基础: {basis_text} | 元素: {element_text}")
        info1.setObjectName("labelSecondary")
        row4.addWidget(info1)
        row4.addStretch()
        card_layout.addLayout(row4)

        # 第五行：技能类型 & 效应类型
        row5 = QHBoxLayout()
        row5.setContentsMargins(0, 0, 0, 0)
        skill_text = item.get("skill") or "(无)"
        effect_text = item.get("effect") or "(无)"
        info2 = QLabel(f"技能: {skill_text} | 效应: {effect_text}")
        info2.setObjectName("labelSecondary")
        row5.addWidget(info2)
        row5.addStretch()
        card_layout.addLayout(row5)

        # 第六行：按钮（锁定 / 更新 / 展开 / 删除）
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        light = self._is_light_theme()
        _btn_base = (
            "QPushButton {{ color: {}; background: {}; "
            "border: 1px solid {}; border-radius: 3px; padding: 4px 6px; }}"
            "QPushButton:hover {{ background: {}; }}"
        )

        lock_btn = QPushButton("锁定" if not item["locked"] else "解锁")
        lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if item["locked"]:
            lc, lbg, lbd, lhv = ("#b85c00", "rgba(255,152,0,0.25)", "rgba(255,152,0,0.50)", "rgba(255,152,0,0.38)") if light else ("#ffb74d", "rgba(255,152,0,0.32)", "rgba(255,152,0,0.55)", "rgba(255,152,0,0.44)")
        else:
            lc, lbg, lbd, lhv = ("#e65100", "rgba(255,152,0,0.06)", "rgba(255,152,0,0.18)", "rgba(255,152,0,0.14)") if light else ("#ffcc80", "rgba(255,152,0,0.10)", "rgba(255,152,0,0.22)", "rgba(255,152,0,0.18)")
        lock_btn.setStyleSheet(_btn_base.format(lc, lbg, lbd, lhv))
        lock_btn.clicked.connect(lambda _, i=idx: self._toggle_lock(i))
        btn_row.addWidget(lock_btn)

        # 更新 — 蓝色系
        uc, ubg, ubd, uhv = ("#1565c0", "rgba(33,150,243,0.10)", "rgba(33,150,243,0.25)", "rgba(33,150,243,0.20)") if light else ("#64b5f6", "rgba(33,150,243,0.16)", "rgba(33,150,243,0.30)", "rgba(33,150,243,0.24)")
        update_btn = QPushButton("更新")
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.setStyleSheet(_btn_base.format(uc, ubg, ubd, uhv))
        update_btn.clicked.connect(lambda _, i=idx: self._update_item(i))
        btn_row.addWidget(update_btn)

        # 展开 — 绿色系
        ec, ebg, ebd, ehv = ("#2e7d32", "rgba(76,175,80,0.10)", "rgba(76,175,80,0.25)", "rgba(76,175,80,0.20)") if light else ("#81c784", "rgba(76,175,80,0.16)", "rgba(76,175,80,0.30)", "rgba(76,175,80,0.24)")
        expand_btn = QPushButton("展开")
        expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        expand_btn.setStyleSheet(_btn_base.format(ec, ebg, ebd, ehv))
        expand_btn.clicked.connect(lambda _, i=idx: self._show_detail(i))
        btn_row.addWidget(expand_btn)

        # 删除 — 红色系
        dc, dbg, dbd, dhv = ("#c62828", "rgba(198,40,40,0.10)", "rgba(198,40,40,0.25)", "rgba(198,40,40,0.20)") if light else ("#ef9a9a", "rgba(198,40,40,0.18)", "rgba(198,40,40,0.35)", "rgba(198,40,40,0.28)")
        del_btn = QPushButton("删除")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(_btn_base.format(dc, dbg, dbd, dhv))
        del_btn.clicked.connect(lambda _, i=idx: self._confirm_delete_item(i))
        btn_row.addWidget(del_btn)

        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        return card

    def _is_light_theme(self):
        try:
            w = self.window()
            if w and hasattr(w, 'current_theme'):
                return w.current_theme == "light"
        except Exception as e:
            _logger.debug("主题检测失败: %s", e)
        return False

    # —— 卡片操作 ——

    # 批量选择
    def _enter_selection(self, mode):
        self._selection_mode = mode
        self._checked = set()
        if mode == "update":
            self._batch_label.setText("请勾选要更新的条目：")
            self._batch_confirm_btn.setText("确认更新")
        else:
            self._batch_label.setText("请勾选要删除的条目：")
            self._batch_confirm_btn.setText("确认删除")
        self._batch_action_bar.setVisible(True)
        self._refresh_cards()

    def _cancel_selection(self):
        self._selection_mode = None
        self._checked = set()
        self._batch_action_bar.setVisible(False)
        self._refresh_cards()

    def _on_check_toggled(self, idx, checked):
        if checked:
            self._checked.add(idx)
        else:
            self._checked.discard(idx)

    def _batch_confirm(self):
        if not self._checked:
            return
        indices = sorted(self._checked, reverse=True)
        if self._selection_mode == "update":
            items_data = _collect_all_items(self._external_sources, self._echo_pages)
            for i in indices:
                if 0 <= i < len(self._items):
                    self._recalc_one(self._items[i], items_data)
        else:
            # 处理锁定条目：先解锁确认
            locked_indices = [i for i in indices if 0 <= i < len(self._items) and self._items[i].get("locked")]
            if locked_indices:
                names_locked = [self._items[i]["label"] for i in locked_indices]
                msg1 = f"以下 {len(locked_indices)} 条记录已锁定，是否解锁？\n" + \
                       "\n".join(f"  • {n}" for n in names_locked[:10]) + \
                       ("\n  …" if len(names_locked) > 10 else "")
                reply1 = QMessageBox.question(
                    self, "解锁确认", msg1,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply1 != QMessageBox.StandardButton.Yes:
                    # 取消：把锁定的条目从勾选中移除
                    for i in locked_indices:
                        self._checked.discard(i)
                    self._refresh_cards()
                    return
                # 确认：解锁
                for i in locked_indices:
                    self._items[i]["locked"] = False

            # 第二步：删除确认
            delete_indices = [i for i in indices if 0 <= i < len(self._items)]
            if not delete_indices:
                self._cancel_selection()
                self._refresh_cards()
                return
            names = [self._items[i]["label"] for i in delete_indices]
            msg2 = f"是否删除以下 {len(names)} 条记录？\n" + \
                   "\n".join(f"  • {n}" for n in names[:10]) + \
                   ("\n  …" if len(names) > 10 else "")
            reply2 = QMessageBox.question(
                self, "确认批量删除", msg2,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply2 == QMessageBox.StandardButton.Yes:
                for i in sorted(delete_indices, reverse=True):
                    if 0 <= i < len(self._items):
                        self._items.pop(i)
        self._cancel_selection()
        self._refresh_cards()

    _AUTO_ON_STYLE = (
        "QPushButton { font-size: 13px; padding: 3px 8px; min-width: 100px; "
        "background: rgba(76,175,80,0.25); color: #81c784; border: 1px solid rgba(76,175,80,0.5); "
        "border-radius: 4px; font-weight: bold; }"
        "QPushButton:hover { background: rgba(76,175,80,0.40); }"
    )
    _AUTO_OFF_STYLE = (
        "QPushButton { font-size: 13px; padding: 3px 8px; min-width: 100px; "
        "background: rgba(158,158,158,0.15); color: #9e9e9e; border: 1px solid rgba(158,158,158,0.3); "
        "border-radius: 4px; font-weight: bold; }"
        "QPushButton:hover { background: rgba(158,158,158,0.25); }"
    )

    def _toggle_auto_update(self):
        self._auto_update = not self._auto_update
        if self._auto_update:
            self.auto_update_btn.setText("关闭自动更新")
            self.auto_update_btn.setStyleSheet(self._AUTO_ON_STYLE)
            self.recalc()
        else:
            self.auto_update_btn.setText("开启自动更新")
            self.auto_update_btn.setStyleSheet(self._AUTO_OFF_STYLE)

    def _apply_auto_update_button_style(self):
        """仅更新按钮外观（用于从存档恢复 _auto_update 状态后）"""
        if self._auto_update:
            self.auto_update_btn.setText("关闭自动更新")
            self.auto_update_btn.setStyleSheet(self._AUTO_ON_STYLE)

    def _update_all(self):
        """全部更新：对所有条目从数值来源同步数据并重新计算"""
        items_data = _collect_all_items(self._external_sources, self._echo_pages)
        for item in self._items:
            self._recalc_one(item, items_data)
        self._refresh_cards()

    def _delete_all(self):
        if not self._items:
            return
        locked = [item for item in self._items if item.get("locked")]
        unlocked_count = len(self._items) - len(locked)
        if unlocked_count == 0:
            QMessageBox.information(self, "提示", "所有记录均已锁定，无法删除。请先解锁后再试。")
            return
        msg = f"是否删除全部 {unlocked_count} 条未锁定记录？"
        if locked:
            msg += f"\n（{len(locked)} 条已锁定记录将保留）"
        msg += "\n此操作不可撤销。"
        reply = QMessageBox.question(
            self, "确认全部删除", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._items = locked
            self._refresh_cards()

    def _update_item(self, idx):
        """按下更新按钮：从数值来源同步数据并重新计算"""
        if idx < 0 or idx >= len(self._items):
            return
        if self._items[idx].get("locked"):
            _show_toast(self, "当前结果已锁定，请先解锁")
            return
        items_data = _collect_all_items(self._external_sources, self._echo_pages)
        self._recalc_one(self._items[idx], items_data)
        self._refresh_cards()

    def _toggle_lock(self, idx):
        if 0 <= idx < len(self._items):
            item = self._items[idx]
            item["locked"] = not item.get("locked", False)
            self._refresh_cards()
            # 同步已打开的详情弹窗的锁定按钮
            if hasattr(self, '_open_detail') and self._open_detail:
                try:
                    self._open_detail.lock_btn.setText("解锁" if item["locked"] else "锁定")
                except Exception:
                    pass

    def _confirm_delete_item(self, idx):
        if idx < 0 or idx >= len(self._items):
            return
        item = self._items[idx]
        if item.get("locked"):
            reply1 = QMessageBox.question(
                self, "解锁确认", f"「{item['label']}」已被锁定，是否解锁？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply1 != QMessageBox.StandardButton.Yes:
                return
            item["locked"] = False
            self._refresh_cards()
        reply2 = QMessageBox.question(
            self, "确认删除", f"是否删除「{item['label']}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply2 == QMessageBox.StandardButton.Yes:
            self._delete_item(idx)

    def _delete_item(self, idx):
        if 0 <= idx < len(self._items):
            self._items.pop(idx)
            self._refresh_cards()

    def _build_keyword_tags(self, layout, keywords, item):
        """构建关键词标签（小型按钮 + × 删除），末尾 + 添加按钮。"""
        # 清除旧标签（先隐藏再标记删除）
        while layout.count():
            child = layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        for kw in keywords:
            tag = QWidget()
            tag_layout = QHBoxLayout(tag)
            tag_layout.setContentsMargins(0, 0, 0, 0)
            tag_layout.setSpacing(1)
            tag.setStyleSheet(
                "background: rgba(100,181,246,0.15); border: 1px solid rgba(100,181,246,0.3);"
                "border-radius: 3px; padding: 3px 5px;"
            )
            kw_lbl = QLabel(kw)
            kw_lbl.setStyleSheet("color: #64b5f6; font-size: 10px; border: none; background: transparent;")
            tag_layout.addWidget(kw_lbl)
            del_btn = QPushButton("×")
            del_btn.setFixedSize(14, 14)
            del_btn.setStyleSheet(
                "QPushButton { color: #e94560; font-size: 9px; border: none; background: transparent; }"
                "QPushButton:hover { color: #ff4444; }"
            )
            del_btn.clicked.connect(lambda checked, k=kw: self._remove_keyword(item, k))
            tag_layout.addWidget(del_btn)
            layout.addWidget(tag)

        # + 添加按钮
        add_btn = QPushButton("+")
        add_btn.setFixedSize(18, 18)
        add_btn.setStyleSheet(
            "QPushButton { color: #64b5f6; font-size: 11px; border: 1px dashed rgba(100,181,246,0.4);"
            "border-radius: 3px; background: transparent; }"
            "QPushButton:hover { background: rgba(100,181,246,0.1); }"
        )
        add_btn.clicked.connect(lambda: self._add_keyword(item))
        layout.addWidget(add_btn)

    def _add_keyword(self, item):
        text, ok = QInputDialog.getText(self, "添加关键词", "输入新关键词（最多 30 字符）：")
        if ok and text.strip():
            keywords = item.setdefault("keywords", [])
            kw = text.strip()[:30]
            if kw not in keywords:
                keywords.append(kw)
            self._refresh_cards()

    def _remove_keyword(self, item, keyword):
        keywords = item.get("keywords", [])
        if keyword in keywords:
            keywords.remove(keyword)
        self._refresh_cards()

    def _show_detail(self, idx):
        """展开按钮：弹出半透明详情窗口（同一窗口复用，切换条目内容）"""
        if idx < 0 or idx >= len(self._items):
            return
        if hasattr(self, '_open_detail') and self._open_detail is not None:
            try:
                # 复用已有窗口：更新指向的条目并刷新显示
                dlg = self._open_detail
                dlg._item = self._items[idx]
                dlg._idx = idx
                item = self._items[idx]
                dlg.setWindowTitle(f"结果详情 — {item['label']}")
                # 同步输入控件值到新条目
                dlg.name_edit.setText(item["label"])
                dlg.base_mult.setValue(item["base_mult"])
                # 倍率值由关键词关联驱动，show 时 _sync_mult_entries() 自动填充表格
                dlg._sync_mult_entries()
                dlg.filter_basis.setCurrentText(item["basis"])
                dlg.filter_element.setCurrentText(item["element"] if item["element"] else "(无)")
                dlg.filter_skill.setCurrentText(item["skill"] if item["skill"] else "(无)")
                dlg.filter_effect.setCurrentText(item["effect"] if item["effect"] else "(无)")
                dlg._update_result_labels()
                dlg.lock_btn.setText("解锁" if item.get("locked") else "锁定")
                # 刷新关键词标签（关联关键词关联页面的最新映射）
                if hasattr(dlg, '_build_detail_keyword_tags'):
                    dlg._build_detail_keyword_tags(item)
                dlg.show()
                dlg.raise_()
                dlg.activateWindow()
            except Exception:
                self._open_detail = None
            return
        dlg = ResultDetailDialog(self._items[idx], idx, self, self.window())
        dlg.setModal(False)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._open_detail = dlg
        dlg._sync_mult_entries()
        dlg.destroyed.connect(lambda: setattr(self, '_open_detail', None))
        dlg.show()

    # —— 序列化 ——
    def collect_data(self):
        return [
            {
                "id": item["id"], "label": item["label"], "locked": item["locked"],
                "basis": item["basis"], "element": item["element"],
                "skill": item["skill"], "effect": item["effect"],
                "category": item.get("category", ""),
                "base_mult": item["base_mult"], "mult_increase": item["mult_increase"],
                "mult_boosts": item["mult_boosts"], "zones": item["zones"],
                "timestamp": item.get("timestamp", ""),
                "keywords": item.get("keywords", []),
                "process_html": item.get("process_html", ""),
            }
            for item in self._items
        ]

    def apply_data(self, data_list):
        self._items = []
        max_id = 0
        for d in data_list:
            item = dict(d)
            # 兼容旧存档中可能存储的 "(无)" 字符串
            for k in ("element", "skill", "effect"):
                if item.get(k) == "(无)":
                    item[k] = None
            # 旧存档无 keywords → 如果标题符合 名称_技能_伤害_倍率 格式则自动生成，否则留空
            if "keywords" not in item:
                item["keywords"] = _auto_keywords(item.get("label", ""))
            max_id = max(max_id, item.get("id", 0))
            self._items.append(item)
        self._id_counter = max_id
        self._refresh_cards()


# ==================== 流式布局（自动换行） ====================

class FlowLayout(QLayout):
    """自动换行的流式布局，用于计算过程等需要自动折行的场景。"""
    def __init__(self, parent=None, margin=0, spacing_h=4, spacing_v=2):
        super().__init__(parent)
        self._items = []
        self._h_spacing = spacing_h
        self._v_spacing = spacing_v
        self._center_rows = False  # 每行是否居中
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        max_width = rect.width() - m.left() - m.right()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        line_height = 0
        line_items = []  # 当前行的 items

        def _flush_line():
            nonlocal x, y, line_height, line_items
            if not line_items:
                return
            if self._center_rows and not test_only:
                row_width = sum(it.sizeHint().width() for it in line_items) + self._h_spacing * (len(line_items) - 1)
                offset = (max_width - row_width) // 2
                cx = rect.x() + m.left() + max(0, offset)
                for it in line_items:
                    w = it.sizeHint().width()
                    h = it.sizeHint().height()
                    it.setGeometry(QRect(cx, y, w, h))
                    cx += w + self._h_spacing
            x = rect.x() + m.left()
            y += line_height + self._v_spacing
            line_height = 0
            line_items = []

        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            if x + w > rect.x() + m.left() + max_width and line_height > 0:
                _flush_line()
            line_items.append(item)
            if not test_only and not self._center_rows:
                item.setGeometry(QRect(x, y, w, h))
            x += w + self._h_spacing
            line_height = max(line_height, h)

        _flush_line()
        return y + line_height - rect.y() + m.bottom()


# ==================== 计算过程 HTML 渲染（ResultPage 和卡片弹窗共用） ====================

def _render_process_html(
    basis, zone_label, base_value, weapon_base,
    pct_items, flat_items, total_pct, total_flat, base_zone,
    bonus_items, total_bonus, bonus_zone,
    deepen_items, total_deepen, deepen_zone,
    rate_items, dmg_items, total_crit_rate, total_crit_dmg, crit_zone,
    def_zone, res_zone, indep_zone, indep_groups,
    base_m, mult_inc, mult_boosts_vals, mult_zone, final_crit, final_no_crit,
    is_light=False, sub_map=None, navigate_fn=None, summary_pages=None,
    base_override_active=False, computed_base_zone=None,
):
    """生成计算过程 HTML。navigate_fn/summary_pages 为 None 时链接不可点击但格式一致。"""
    text_c = "#2c3040" if is_light else "#c0c4ce"
    accent_c = "#5070e8" if is_light else "#e94560"
    link_c = "#7c3aed" if is_light else "#f59e42"

    def _esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _txt(s):
        return f'<span style="color:{text_c};font-size:14px;">{_esc(s)}</span>'

    def _link(text, tooltip, nav_url):
        t = _esc(tooltip).replace("\n", "&#10;")
        if nav_url:
            return f'<a href="{nav_url}\x1e{t}" style="color:{link_c};font-weight:700;text-decoration:underline;">{text}</a>'
        return f'<span style="color:{accent_c};font-weight:700;" title="{t}">{text}</span>'

    def _hl_link(text, tooltip, summary_key, name, src_label, nav_key, seq_label=None):
        t = _esc(tooltip).replace("\n", "&#10;")
        sq = _esc(seq_label) if seq_label else ""
        href = f"hl:{summary_key}:{_esc(name)}:{_esc(src_label)}:{_esc(nav_key)}:{sq}\x1e{t}"
        return f'<a href="{href}" style="color:{link_c};font-weight:700;text-decoration:underline;">{text}</a>'

    def _item_link(name, value, src_label, nav_key, summary_key=None, seq_label=None):
        is_const = name in CONSTANT_ATTRS or "固定" in name or "基础" in name
        # 全精度显示，去掉末尾多余的零，保留小数点后最多4位
        def _fmt_val(v):
            s = f"{v:.10f}"
            return s.rstrip("0").rstrip(".") if "." in s else s
        fmt = _fmt_val(value) if is_const else (_fmt_val(value) + "%")
        tip = f"{name} = {fmt}\n来源: {src_label}"
        sub_key = (name, src_label, nav_key, seq_label)
        if sub_map and sub_key in sub_map:
            tip += f"\n副名称: {sub_map[sub_key]}"
        if summary_key and navigate_fn and summary_pages and summary_pages.get(summary_key):
            return _hl_link(fmt, tip, summary_key, name, src_label, nav_key, seq_label)
        target = summary_key if summary_key else nav_key
        return _link(fmt, tip, f"nav:{target}" if target else None)

    def _render_items(items, joiner=" + ", summary_key=None):
        parts = []
        for i, (name, value, src_label, nav_key, seq_label) in enumerate(items):
            if i > 0:
                parts.append(_txt(joiner))
            parts.append(_item_link(name, value, src_label, nav_key, summary_key, seq_label))
        return parts

    def _zone(title, parts):
        inner = (
            f'<span style="color:{accent_c};font-size:16px;font-weight:700;">[</span>'
            f'<span style="color:{accent_c};font-size:14px;font-weight:600;">{_esc(title)}</span>'
            f'<span style="color:{accent_c};font-size:16px;font-weight:700;">]</span> '
        )
        inner += "".join(parts)
        return f'<div style="padding:6px 0;margin-bottom:2px;line-height:2.0;">{inner}</div>'

    html = []

    # ===== 基础数值 =====
    source_tip = "来源: 角色武器"
    nav_to = "char_base"
    if basis == "攻击力":
        base_parts = [
            _txt("("),
            _link(f"{base_value:.0f}", f"角色基础攻击力 = {base_value:.0f}\n{source_tip}", f"nav:{nav_to}"),
            _txt(" + "),
            _link(f"{weapon_base:.0f}", f"武器基础攻击力 = {weapon_base:.0f}\n{source_tip}", f"nav:{nav_to}"),
            _txt(") × (1"),
        ]
    else:
        base_parts = [
            _link(f"{base_value:.0f}", f"角色基础{zone_label} = {base_value:.0f}\n{source_tip}", f"nav:{nav_to}"),
            _txt(" × (1"),
        ]
    if pct_items:
        base_parts.append(_txt(" + "))
        base_parts.extend(_render_items(pct_items, summary_key="summary_base"))
    elif total_pct > 0:
        base_parts.append(_txt(" + "))
        base_parts.append(_link(f"{total_pct:.1f}%", f"{zone_label}%合计 = {total_pct:.1f}%", "nav:summary_base"))
    base_parts.append(_txt(")"))
    if flat_items:
        base_parts.append(_txt(" + "))
        base_parts.extend(_render_items(flat_items, summary_key="summary_base"))
    elif total_flat > 0:
        base_parts.append(_txt(" + "))
        base_parts.append(_link(f"{total_flat:.1f}", f"固定{zone_label}合计 = {total_flat:.1f}", "nav:summary_base"))
    base_parts.append(_txt(" = "))
    base_parts.append(_link(f"{base_zone:.10f}", f"基础数值结果 = {base_zone:.10f}", None))
    if base_override_active and computed_base_zone is not None:
        base_parts.append(
            f'<br><span style="color:#64b5f6;font-size:13px;font-weight:600;">'
            f'  ▸ 已启用手动填写，原本计算值: {computed_base_zone:.2f}</span>')
    html.append(_zone("基础数值", base_parts))

    # ===== 加成乘区 =====
    bonus_parts = [_txt("1")]
    if bonus_items:
        bonus_parts.append(_txt(" + "))
        bonus_parts.extend(_render_items(bonus_items, summary_key="summary_bonus"))
    elif total_bonus > 0:
        bonus_parts.append(_txt(" + "))
        bonus_parts.append(_link(f"{total_bonus:.1f}%", f"伤害加成合计 = {total_bonus:.1f}%", "nav:summary_bonus"))
    bonus_parts.append(_txt(" = "))
    bonus_parts.append(_link(f"{bonus_zone:.10f}", f"加成乘区结果 = {bonus_zone:.10f}", None))
    html.append(_zone("加成乘区", bonus_parts))

    # ===== 加深乘区 =====
    deepen_parts = [_txt("1")]
    if deepen_items:
        deepen_parts.append(_txt(" + "))
        deepen_parts.extend(_render_items(deepen_items, summary_key="summary_deepen"))
    elif total_deepen > 0:
        deepen_parts.append(_txt(" + "))
        deepen_parts.append(_link(f"{total_deepen:.1f}%", f"伤害加深合计 = {total_deepen:.1f}%", "nav:summary_deepen"))
    deepen_parts.append(_txt(" = "))
    deepen_parts.append(_link(f"{deepen_zone:.10f}", f"加深乘区结果 = {deepen_zone:.10f}", None))
    html.append(_zone("加深乘区", deepen_parts))

    # ===== 暴击率 =====
    rate_parts = [_txt("(")]
    if rate_items:
        rate_parts.append(_txt("5% + "))
        rate_parts.extend(_render_items(rate_items, summary_key="summary_crit"))
    else:
        added_rate = total_crit_rate - 5.0
        rate_parts.append(_txt("5%" + (" + " if added_rate > 0 else "")))
        if added_rate > 0:
            rate_parts.append(_link(f"{added_rate:.1f}%", f"暴击率来源合计 = {added_rate:.1f}%", "nav:summary_crit"))
    rate_parts.append(_txt(") = "))
    rate_parts.append(_link(f"{total_crit_rate:.1f}%", f"最终暴击率 = {total_crit_rate:.1f}%", None))
    html.append(_zone("暴击率", rate_parts))

    # ===== 暴击伤害乘区 =====
    crit_parts = [_txt("(150%")]
    if dmg_items:
        crit_parts.append(_txt(" + "))
        crit_parts.extend(_render_items(dmg_items, summary_key="summary_crit"))
    else:
        added_crit = total_crit_dmg - 150.0
        if added_crit > 0:
            crit_parts.append(_txt(" + "))
            crit_parts.append(_link(f"{added_crit:.1f}%", f"暴击伤害来源合计 = {added_crit:.1f}%", "nav:summary_crit"))
    crit_parts.append(_txt(") = "))
    crit_parts.append(_link(f"{total_crit_dmg:.1f}%", f"暴击伤害合计 = {total_crit_dmg:.1f}%", None))
    crit_parts.append(_txt(" = "))
    crit_parts.append(_link(f"{crit_zone:.10f}", f"暴击乘区结果 = {crit_zone:.10f}", None))
    html.append(_zone("暴击乘区 (暴击时)", crit_parts))

    # 防御乘区
    html.append(_zone("防御乘区", [
        _link(f"{def_zone:.10f}", f"防御乘数 = {def_zone:.10f}\n来源: 防御减伤", "nav:enemy_defense"),
    ]))

    # 抗性乘区
    html.append(_zone("抗性乘区", [
        _link(f"{res_zone:.10f}", f"抗性乘数 = {res_zone:.10f}\n来源: 抗性数值", "nav:enemy_resistance"),
    ]))

    # 独立乘区
    indep_parts = []
    if indep_groups:
        for i, (name, factor) in enumerate(indep_groups):
            if i > 0:
                indep_parts.append(_txt(" × "))
            dname = name if name else f"独立乘区{i+1}"
            indep_parts.append(_link(f"{factor:.10f}", f"{dname} = {factor:.10f}\n来源: 独立乘区", "nav:summary_indep"))
        indep_parts.append(_txt(" = "))
        indep_parts.append(_link(f"{indep_zone:.10f}", f"独立乘区总计 = {indep_zone:.10f}\n来源: 独立乘区", "nav:summary_indep"))
    else:
        indep_parts.append(_link(f"{indep_zone:.10f}", f"独立乘区 = {indep_zone:.10f}\n来源: 独立乘区", "nav:summary_indep"))
    html.append(_zone("独立乘区", indep_parts))

    # 倍率乘区
    mult_parts = [
        _txt("("),
        _link(f"{base_m:.3f}%", f"基础倍率 = {base_m:.3f}%\n手动输入", None),
        _txt(" + "),
        _link(f"{mult_inc:.3f}%", f"倍率增加 = {mult_inc:.3f}%\n手动输入", None),
        _txt(")"),
    ]
    for j, bv in enumerate(mult_boosts_vals):
        if bv > 0:
            mult_parts.append(_txt(" × (1 + "))
            mult_parts.append(_link(f"{bv:.3f}%", f"倍率提升{j+1} = {bv:.3f}%\n手动输入", None))
            mult_parts.append(_txt(")"))
    mult_parts.append(_txt(" = "))
    mult_parts.append(_link(f"{mult_zone:.10f}%", f"倍率乘区结果 = {mult_zone:.10f}%", None))
    html.append(_zone("倍率乘区", mult_parts))

    # 最终伤害
    html.append(_zone("无暴击最终伤害", [
        _link(f"{final_no_crit:.10f}", f"无暴击最终伤害 = {final_no_crit:.10f}", None),
    ]))
    html.append(_zone("暴击后最终伤害", [
        _link(f"{final_crit:.10f}", f"暴击后最终伤害 = {final_crit:.10f}", None),
    ]))

    return "".join(html)


# ==================== 计算结果页面 ====================

class ResultPage(QWidget):
    """计算结果页. 倍率设置 + 筛选条件 + 伤害计算 + 过程展示."""
    def __init__(self):
        super().__init__()
        self._last_computed = None
        self._result_list_page = None
        self._auto_compute = False
        self._external_sources = []
        self._echo_pages = {}
        self._defense_page = None
        self._resistance_page = None
        self._indep_zone_page = None
        self._navigate = None
        self._highlight_cb = None
        self._summary_pages = {}
        self._ocr_loading_show = None
        self._ocr_loading_hide = None
        self._ocr_loading_progress = None
        self._dmg_ocr_worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("计算结果")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # —— 倍率设置 ——
        mult_group = QGroupBox("倍率设置")
        mult_form = QFormLayout(mult_group)
        self.base_mult = QDoubleSpinBox()
        self.base_mult.setRange(0, 99999)
        self.base_mult.setDecimals(4)
        self.base_mult.setValue(100.0)
        mult_form.addRow("基础倍率(%):", self.base_mult)

        # 倍率增加（只读，由关键词关联自动填充）
        self.mult_inc_table = QTableWidget()
        self.mult_inc_table.setObjectName("attrTable")
        self.mult_inc_table.setColumnCount(8)
        self.mult_inc_table.setHorizontalHeaderLabels(
            ["名称", "副名称", "序列号", "数值", "取值", "来源", "关键词关联", "操作"])
        self.mult_inc_table.verticalHeader().setVisible(False)
        self.mult_inc_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mult_inc_table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.mult_inc_table.setMinimumHeight(150)
        hdr_inc = self.mult_inc_table.horizontalHeader()
        hdr_inc.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 8):
            hdr_inc.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        hdr_inc.resizeSection(1, 130)
        hdr_inc.resizeSection(2, 110)
        hdr_inc.resizeSection(3, 150)
        hdr_inc.resizeSection(4, 70)
        hdr_inc.resizeSection(5, 90)
        hdr_inc.resizeSection(6, 120)
        hdr_inc.resizeSection(7, 80)
        inc_toggle = QPushButton("▼ 倍率增加(%)")
        inc_toggle.setObjectName("formToggle")
        inc_toggle.setStyleSheet("QPushButton { border: none; background: transparent; padding: 2px 6px; text-align: left; } QPushButton:checked { font-weight: bold; }")
        inc_toggle.setFlat(True)
        inc_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        inc_toggle.setCheckable(True)
        inc_toggle.setChecked(True)
        inc_toggle.toggled.connect(lambda checked, b=inc_toggle: (b.setText(("▼ " if checked else "▶ ") + "倍率增加(%)")))
        inc_toggle.toggled.connect(self.mult_inc_table.setVisible)
        mult_form.addRow(inc_toggle, self.mult_inc_table)
        self.mult_boost_table = QTableWidget()
        self.mult_boost_table.setObjectName("attrTable")
        self.mult_boost_table.setColumnCount(8)
        self.mult_boost_table.setHorizontalHeaderLabels(
            ["名称", "副名称", "序列号", "数值", "取值", "来源", "关键词关联", "操作"])
        self.mult_boost_table.verticalHeader().setVisible(False)
        self.mult_boost_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mult_boost_table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.mult_boost_table.setMinimumHeight(150)
        hdr_boost = self.mult_boost_table.horizontalHeader()
        hdr_boost.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 8):
            hdr_boost.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        hdr_boost.resizeSection(1, 130)
        hdr_boost.resizeSection(2, 110)
        hdr_boost.resizeSection(3, 150)
        hdr_boost.resizeSection(4, 70)
        hdr_boost.resizeSection(5, 90)
        hdr_boost.resizeSection(6, 120)
        hdr_boost.resizeSection(7, 80)
        boost_toggle = QPushButton("▼ 倍率提升(%)")
        boost_toggle.setObjectName("formToggle")
        boost_toggle.setStyleSheet("QPushButton { border: none; background: transparent; padding: 2px 6px; text-align: left; } QPushButton:checked { font-weight: bold; }")
        boost_toggle.setFlat(True)
        boost_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        boost_toggle.setCheckable(True)
        boost_toggle.setChecked(True)
        boost_toggle.toggled.connect(lambda checked, b=boost_toggle: (b.setText(("▼ " if checked else "▶ ") + "倍率提升(%)")))
        boost_toggle.toggled.connect(self.mult_boost_table.setVisible)
        mult_form.addRow(boost_toggle, self.mult_boost_table)

        layout.addWidget(mult_group)

        # —— 筛选设置 ——
        filter_group = QGroupBox("筛选条件")
        filter_form = QFormLayout(filter_group)

        self.filter_basis = QComboBox()
        self.filter_basis.addItems(["攻击力", "生命值", "防御力"])
        filter_form.addRow("基础数值类型:", self.filter_basis)

        self.filter_element = QComboBox()
        self.filter_element.addItems(ELEMENTS)
        filter_form.addRow("元素属性:", self.filter_element)

        self.filter_skill = QComboBox()
        self.filter_skill.addItems(SKILL_TYPES)
        filter_form.addRow("技能类型:", self.filter_skill)

        self.filter_effect = QComboBox()
        self.filter_effect.addItems(EFFECTS)
        filter_form.addRow("效应类型:", self.filter_effect)

        self._keywords = []
        kw_row_widget = QWidget()
        self._kw_flow = FlowLayout(kw_row_widget, margin=0, spacing_h=4, spacing_v=2)
        self._rebuild_kw_tags()
        filter_form.addRow("关键词:", kw_row_widget)

        layout.addWidget(filter_group)

        # 筛选条件与倍率变更时自动计算（受 _auto_compute 开关控制）
        for w in [self.base_mult,
                  self.filter_basis, self.filter_element,
                  self.filter_effect]:
            if hasattr(w, "valueChanged"):
                w.valueChanged.connect(self.auto_compute)
            elif hasattr(w, "currentTextChanged"):
                w.currentTextChanged.connect(self.auto_compute)
        # 技能类型切换直接触发计算（影响防御乘区）
        self.filter_skill.currentTextChanged.connect(self.compute)


        # —— 按钮行 ——
        btn_row = QHBoxLayout()
        self.calc_btn = QPushButton("计算")
        self.calc_btn.setObjectName("itemAddBtn")
        self.calc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.calc_btn.clicked.connect(self.compute)
        btn_row.addWidget(self.calc_btn)

        self.add_to_list_btn = QPushButton("计入结果")
        self.add_to_list_btn.setObjectName("itemAddBtn")
        self.add_to_list_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_to_list_btn.clicked.connect(self._add_to_result_list)
        btn_row.addWidget(self.add_to_list_btn)

        self.auto_compute_btn = QPushButton("开启自动更新")
        self.auto_compute_btn.setObjectName("itemAddBtn")
        self.auto_compute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_compute_btn.setStyleSheet(self._AUTO_OFF_STYLE)
        self.auto_compute_btn.clicked.connect(self._toggle_auto_compute)
        btn_row.addWidget(self.auto_compute_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # —— 计算过程 ——
        process_group = QGroupBox("计算过程")
        process_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._process_layout = QVBoxLayout(process_group)
        self._process_layout.setSpacing(6)


        # 复制按钮（计算后有内容时显示）
        copy_header = QHBoxLayout()
        copy_header.setContentsMargins(0, 0, 0, 0)
        copy_header.addStretch()
        self._process_copy_btn = QPushButton("📋 复制计算过程")
        self._process_copy_btn.setObjectName("processCopyBtn")
        self._process_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._process_copy_btn.clicked.connect(self._copy_process_text)
        self._process_copy_btn.setVisible(False)
        copy_header.addWidget(self._process_copy_btn)
        self._process_layout.addLayout(copy_header)

        # 过程内容标签（富文本 + 可拖选 + 可点击链接）
        self._process_label = QLabel()
        self._process_label.setObjectName("processLabel")
        self._process_label.setWordWrap(True)
        self._process_label.setTextFormat(Qt.TextFormat.RichText)
        self._process_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._process_label.linkActivated.connect(self._on_process_link_activated)
        self._process_label.linkHovered.connect(self._on_process_link_hovered)
        self._process_label.setVisible(False)
        self._process_layout.addWidget(self._process_label)

        self._process_empty_label = QLabel("点击计算后，过程会显示在这里。")
        self._process_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._process_empty_label.setObjectName("processEmptyLabel")
        self._process_layout.addWidget(self._process_empty_label)
        layout.addWidget(process_group, stretch=1)

    def set_result_list_page(self, page):
        self._result_list_page = page

    def set_ocr_loading_callbacks(self, show_cb, hide_cb, progress_cb=None, cancel_cb=None):
        self._ocr_loading_show = show_cb
        self._ocr_loading_hide = hide_cb
        self._ocr_loading_progress = progress_cb
        self._ocr_cancel_cb = cancel_cb

    # —— 伤害倍率 OCR ——

    def _set_dmg_ocr_buttons_enabled(self, enabled):
        if self._result_list_page:
            self._result_list_page.set_dmg_ocr_buttons_enabled(enabled)

    def _import_dmg_mult_ocr(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择伤害倍率截图（最多5张）", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*.*)"
        )
        if not file_paths:
            return
        sources = [(fp, False) for fp in file_paths[:5]]
        self._start_dmg_ocr(sources)

    def _screenshot_dmg_mult_ocr(self):
        try:
            clipboard = QApplication.clipboard()
            if not clipboard.mimeData().hasImage():
                QMessageBox.information(self, "无截图", "剪贴板中没有图片。\n请先使用截图工具截图，再点击此按钮。")
                return
            qimage = clipboard.image()
            if qimage.isNull():
                QMessageBox.information(self, "无截图", "剪贴板中没有图片。\n请先使用截图工具截图，再点击此按钮。")
                return
            self._start_dmg_ocr([(qimage, True)])
        except Exception as e:
            _logger.exception("截图识别失败: %s", e)
            QMessageBox.critical(self, "错误", f"截图识别失败:\n{e}")

    def abort_ocr(self):
        """中断当前 OCR 识别"""
        # 立即隐藏遮罩，不等线程 finished 信号（terminate 后信号可能延迟/丢失）
        if self._ocr_loading_hide:
            self._ocr_loading_hide()
        self._set_dmg_ocr_buttons_enabled(True)
        if hasattr(self, '_dmg_ocr_worker') and self._dmg_ocr_worker and self._dmg_ocr_worker.isRunning():
            self._dmg_ocr_worker.abort()

    def _start_dmg_ocr(self, sources):
        # 断开旧 worker 信号，防止残留信号污染
        if hasattr(self, '_dmg_ocr_worker') and self._dmg_ocr_worker:
            try:
                self._dmg_ocr_worker.finished.disconnect(self._on_dmg_ocr_finished)
                self._dmg_ocr_worker.error.disconnect(self._on_dmg_ocr_error)
                self._dmg_ocr_worker.progress.disconnect(self._on_dmg_ocr_progress)
            except Exception:
                pass
        self._set_dmg_ocr_buttons_enabled(False)
        total = len(sources)
        if self._ocr_loading_show:
            self._ocr_loading_show(f"识别中...（上限5张）")
        self._dmg_ocr_worker = OCRWorker(sources, parser=_parse_dmg_mult_ocr_results)
        self._dmg_ocr_worker.finished.connect(self._on_dmg_ocr_finished)
        self._dmg_ocr_worker.error.connect(self._on_dmg_ocr_error)
        self._dmg_ocr_worker.progress.connect(self._on_dmg_ocr_progress)
        self._dmg_ocr_worker.start()

    def _on_dmg_ocr_finished(self, results_list):
        # ⚠️ 必须最先检查 sender，防止旧 worker 残留信号
        # 污染新 OCR 的 UI 状态（遮罩、按钮），导致卡死/闪退
        if self.sender() is not getattr(self, '_dmg_ocr_worker', None):
            return
        if self._ocr_loading_hide:
            self._ocr_loading_hide()
        self._set_dmg_ocr_buttons_enabled(True)

        # 如果被中断，跳过结果处理
        if getattr(self._dmg_ocr_worker, '_abort', False):
            return

        all_items = []
        all_raw_texts = []
        for item in (results_list or []):
            if item is None:
                continue
            # parser 返回 (list, raw_text) 元组
            if isinstance(item, tuple):
                parsed, rt = item
                all_raw_texts.append(rt)
                if isinstance(parsed, list):
                    all_items.extend(parsed)
            elif isinstance(item, list):
                all_items.extend(item)
            elif isinstance(item, dict) and item.get("label"):
                all_items.append(item)

        # 组装右侧原始识别文本：解析器已生成完整的逐行解析 + 识别倍率
        raw_parts = []
        for rt in all_raw_texts:
            if rt.strip():
                raw_parts.append(rt.strip())
        raw_text = "\n\n".join(raw_parts)

        if not all_items:
            detail = raw_text.strip()[:500] if raw_text.strip() else "OCR 引擎未返回任何文字。"
            _logger.warning("倍率识别失败：未能从截图中解析出伤害倍率。原始文本预览:\n%s", detail)
            self._update_error_log_btn_if_possible()
            QMessageBox.warning(
                self, "OCR 识别失败",
                "未能从截图中识别出伤害倍率。\n\n"
                "可点击侧边栏「错误日志」查看原始识别文本详情。"
            )
            return

        # 先让用户填写角色名称
        char_name, ok = QInputDialog.getText(
            self, "角色名称", "请输入角色名称：",
            text=self._dmg_ocr_char_name if hasattr(self, '_dmg_ocr_char_name') else ""
        )
        if not ok or not char_name.strip():
            return
        char_name = char_name.strip()
        self._dmg_ocr_char_name = char_name

        # 选择角色元素（继承上次选择）
        last_elem = getattr(self, '_dmg_ocr_char_elem', '')
        default_elem_idx = ELEMENTS.index(last_elem) if last_elem in ELEMENTS else 0
        char_elem, ok2 = QInputDialog.getItem(
            self, "角色元素", "选择角色元素属性：",
            ELEMENTS, default_elem_idx, False
        )
        if not ok2:
            return
        self._dmg_ocr_char_elem = char_elem

        # 给每条结果加上角色名前缀和元素
        for item in all_items:
            item["label"] = f"{char_name}_{item['label']}"
            if char_elem != "(无)":
                item["element"] = char_elem

        dlg = DamageMultConfirmDialog(all_items, self, raw_text)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        confirmed = dlg.get_confirmed_data()
        if self._result_list_page:
            self._result_list_page.setUpdatesEnabled(False)
            try:
                for item in confirmed:
                    settings = {
                        "label": item.get("label", ""),
                        "basis": item.get("basis", "攻击力"),
                        "element": item.get("element"),
                        "skill": item.get("skill"),
                        "effect": item.get("effect"),
                        "category": item.get("category", ""),
                        "base_mult": item.get("base_mult", 100.0),
                        "mult_increase": item.get("mult_increase", 0.0),
                        "mult_boosts": item.get("mult_boosts", [0.0, 0.0, 0.0]),
                        "zones": item.get("zones", {}),
                    }
                    self._result_list_page.add_item(settings)
            finally:
                self._result_list_page.setUpdatesEnabled(True)
            # 导入后自动触发一次全部计算，让刚加入的条目立刻显示伤害数值
            self._result_list_page._update_all()

    def _on_dmg_ocr_error(self, msg):
        if self.sender() is not getattr(self, '_dmg_ocr_worker', None):
            return
        if self._ocr_loading_hide:
            self._ocr_loading_hide()
        self._set_dmg_ocr_buttons_enabled(True)
        QMessageBox.warning(self, "OCR 识别失败", f"识别过程出错：\n{msg}")

    def _on_dmg_ocr_progress(self, current, total):
        if self._ocr_loading_progress:
            self._ocr_loading_progress(f"识别中 {current}/{total}...")

    _AUTO_ON_STYLE = (
        "QPushButton { font-size: 13px; padding: 3px 8px; min-width: 100px; "
        "background: rgba(76,175,80,0.25); color: #81c784; border: 1px solid rgba(76,175,80,0.5); "
        "border-radius: 4px; font-weight: bold; }"
        "QPushButton:hover { background: rgba(76,175,80,0.40); }"
    )
    _AUTO_OFF_STYLE = (
        "QPushButton { font-size: 13px; padding: 3px 8px; min-width: 100px; "
        "background: rgba(158,158,158,0.15); color: #9e9e9e; border: 1px solid rgba(158,158,158,0.3); "
        "border-radius: 4px; font-weight: bold; }"
        "QPushButton:hover { background: rgba(158,158,158,0.25); }"
    )

    def _toggle_auto_compute(self):
        self._auto_compute = not self._auto_compute
        if self._auto_compute:
            self.auto_compute_btn.setText("关闭自动更新")
            self.auto_compute_btn.setStyleSheet(self._AUTO_ON_STYLE)
            self.compute()
        else:
            self.auto_compute_btn.setText("开启自动更新")
            self.auto_compute_btn.setStyleSheet(self._AUTO_OFF_STYLE)

    def auto_compute(self):
        """外部回调触发；仅当开启自动更新时才执行"""
        if self._auto_compute:
            self.compute()

    def _add_to_result_list(self):
        if self._last_computed is None:
            return
        if self._result_list_page:
            self._result_list_page.add_item(self._last_computed)

    def set_external_sources(self, sources):
        self._external_sources = sources

    def set_echo_sources(self, echo_pages_dict):
        self._echo_pages = echo_pages_dict or {}

    def set_defense_page(self, page):
        self._defense_page = page

    def set_resistance_page(self, page):
        self._resistance_page = page

    def set_indep_zone_page(self, page):
        self._indep_zone_page = page

    def set_keyword_assoc_page(self, page):
        self._keyword_assoc_page = page

    def _rebuild_kw_tags(self):
        """重建关键词标签（每个关键词一个小标签 + × 删除按钮）"""
        # 清除所有（先隐藏再标记删除）
        while self._kw_flow.count():
            item = self._kw_flow.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        # 添加关键词标签
        for kw in self._keywords:
            tag = QWidget()
            tl = QHBoxLayout(tag)
            tl.setContentsMargins(0, 0, 0, 0)
            tl.setSpacing(1)
            tag.setStyleSheet(
                "background: rgba(100,181,246,0.15); border: 1px solid rgba(100,181,246,0.3);"
                "border-radius: 3px; padding: 2px 4px;"
            )
            lbl = QLabel(kw)
            lbl.setStyleSheet("color: #64b5f6; font-size: 11px; border: none; background: transparent;")
            tl.addWidget(lbl)
            del_btn = QPushButton("×")
            del_btn.setFixedSize(14, 14)
            del_btn.setStyleSheet(
                "QPushButton { color: #e94560; font-size: 9px; border: none; background: transparent; }"
                "QPushButton:hover { color: #ff4444; }"
            )
            del_btn.clicked.connect(lambda checked, k=kw: self._remove_keyword(k))
            tl.addWidget(del_btn)
            self._kw_flow.addWidget(tag)
        # 末尾 "+" 按钮
        add_btn = QPushButton("+")
        add_btn.setFixedSize(22, 22)
        add_btn.setObjectName("addButton")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_keyword)
        self._kw_flow.addWidget(add_btn)

    def _add_keyword(self):
        """弹出输入框添加关键词"""
        text, ok = QInputDialog.getText(self, "添加关键词", "输入关键词:")
        if ok and text.strip():
            kw = text.strip()
            if kw not in self._keywords:
                self._keywords.append(kw)
                self._rebuild_kw_tags()
                self._sync_mult_entries()
                self.auto_compute()

    def _remove_keyword(self, kw):
        """移除关键词"""
        if kw in self._keywords:
            self._keywords.remove(kw)
            self._rebuild_kw_tags()
            self._sync_mult_entries()
            self.auto_compute()

    def _update_error_log_btn_if_possible(self):
        try:
            win = self.window()
            if win and hasattr(win, 'main_screen'):
                win.main_screen._update_error_log_btn()
        except Exception:
            pass

    def set_base_override(self, enabled, value):
        self._base_override_enabled = enabled
        self._base_override_value = value

    def compute(self):
        items = _collect_all_items(self._external_sources, self._echo_pages)

        selected_element = self.filter_element.currentText()
        if selected_element == "(无)":
            selected_element = None
        selected_skill = self.filter_skill.currentText()
        if selected_skill == "(无)":
            selected_skill = None
        selected_effect = self.filter_effect.currentText()
        if selected_effect == "(无)":
            selected_effect = None

        filtered_items = [(n, v, s, nk, sq) for n, v, s, nk, sq, *_sub in items
                          if _matches_filter(n, selected_element, selected_skill, selected_effect)
                          and (n, nk, sq) not in HIDDEN_ITEMS]

        # ═══ 最终防线：再次过滤 HIDDEN_ITEMS（确保不在集合中的项被排除） ═══
        filtered_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered_items
                          if (n, nk, sq) not in HIDDEN_ITEMS]

        # 关键词关联注入（与 ResultListPage._recalc_one 相同逻辑）
        kw_text = ",".join(self._keywords)
        if kw_text and getattr(self, '_keyword_assoc_page', None):
            item_keywords = set(k.strip() for k in kw_text.split(",") if k.strip())
            if item_keywords:
                for kw_item in self._keyword_assoc_page.get_items():
                    kw_entry_kws = set(k.strip() for k in kw_item.get("keywords", "").split(",") if k.strip())
                    if item_keywords & kw_entry_kws:
                        name = kw_item["name"]
                        value = kw_item["value"]
                        source = kw_item.get("source", "关键词关联")
                        seq = kw_item.get("seq", "")
                        if (name, "keyword_assoc", seq) in HIDDEN_ITEMS:
                            continue
                        filtered_items.append((
                            name, value, source, "keyword_assoc", seq,
                        ))

        basis = self.filter_basis.currentText()  # 攻击力 / 生命值 / 防御力

        if basis == "攻击力":
            base_value = 0.0
            weapon_base = 0.0
            total_pct = 0.0
            total_flat = 0.0
            for name, value, _, _, _ in filtered_items:
                if name == "角色基础攻击力":
                    base_value = value
                elif name == "武器基础攻击力":
                    weapon_base = value
                elif "攻击力" in name and "固定" not in name:
                    total_pct += value
                elif "固定攻击" in name:
                    total_flat += value
            zone_label = "攻击力"
        elif basis == "生命值":
            base_value = 0.0
            weapon_base = 0.0
            total_pct = 0.0
            total_flat = 0.0
            for name, value, _, _, _ in filtered_items:
                if name == "角色基础生命值":
                    base_value = value
                elif "生命值" in name and "固定" not in name:
                    total_pct += value
                elif "固定生命" in name:
                    total_flat += value
            zone_label = "生命值"
        else:  # 防御力
            base_value = 0.0
            weapon_base = 0.0
            total_pct = 0.0
            total_flat = 0.0
            for name, value, _, _, _ in filtered_items:
                if name == "角色基础防御力":
                    base_value = value
                elif "防御力" in name and "固定" not in name:
                    total_pct += value
                elif "固定防御" in name:
                    total_flat += value
            zone_label = "防御力"

        computed_base_zone = (base_value + weapon_base) * (1.0 + total_pct / 100.0) + total_flat
        override_active = getattr(self, '_base_override_enabled', False)
        if override_active:
            base_zone = self._base_override_value
        else:
            base_zone = computed_base_zone
        self._computed_base_zone = computed_base_zone  # 保存原始计算值供显示

        total_bonus = sum(v for n, v, _, _, _ in filtered_items
                         if any(s in n for s in BONUS_SUFFIX)
                         and not any(kw in n for kw in CRIT_DMG_KEYWORDS))
        bonus_zone = 1.0 + total_bonus / 100.0

        total_deepen = sum(v for n, v, _, _, _ in filtered_items if DEEPEN_SUFFIX in n)
        deepen_zone = 1.0 + total_deepen / 100.0

        total_crit_rate = 5.0 + sum(v for n, v, _, _, _ in filtered_items
                                     if any(kw in n for kw in CRIT_RATE_KEYWORDS)
                                     and not any(kw in n for kw in CRIT_DMG_KEYWORDS))
        total_crit_dmg = 150.0 + sum(v for n, v, _, _, _ in filtered_items
                                     if any(kw in n for kw in CRIT_DMG_KEYWORDS))
        crit_zone = total_crit_dmg / 100.0

        def_zone = 1.0
        if self._defense_page and hasattr(self._defense_page, 'get_defense_zone'):
            skill = self.filter_skill.currentText()
            def_zone = self._defense_page.get_defense_zone(None if skill == "(无)" else skill)
        elif self._defense_page:
            def_zone = getattr(self._defense_page, 'def_multiplier', 1.0)

        res_zone = 1.0
        if self._resistance_page:
            res_zone = self._resistance_page.get_resistance_multiplier(selected_element)

        indep_zone = 1.0
        indep_groups = []
        if self._indep_zone_page:
            indep_zone = getattr(self._indep_zone_page, 'independent_zone', 1.0)
            indep_groups = self._indep_zone_page.group_factors

        base_m = self.base_mult.value()
        inc_vals, boost_vals = self._gather_mult_data()
        mult_inc = sum(inc_vals)
        mult_zone = (base_m + mult_inc)
        for bv in boost_vals:
            mult_zone *= (1.0 + bv / 100.0)

        base_dmg = base_zone * bonus_zone * deepen_zone * def_zone * res_zone * indep_zone * mult_zone / 100.0
        final_crit = base_dmg * crit_zone
        final_no_crit = base_dmg

        
        # 收集各乘区单个词条列表（含来源信息），供计算过程逐条展示
        pct_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered_items
                     if any(kw in n for kw in (ATK_PCT_NAMES if basis == "攻击力" else
                         ({"生命值"} if basis == "生命值" else {"防御力"})))
                     and "固定" not in n and "基础" not in n]
        flat_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered_items
                      if ("固定攻击" in n if basis == "攻击力" else
                          "固定生命" in n if basis == "生命值" else
                          "固定防御" in n)]
        bonus_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered_items
                       if any(sfx in n for sfx in BONUS_SUFFIX)
                       and not any(kw in n for kw in CRIT_DMG_KEYWORDS)]
        deepen_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered_items
                        if DEEPEN_SUFFIX in n]
        rate_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered_items
                      if any(kw in n for kw in CRIT_RATE_KEYWORDS)
                      and not any(kw in n for kw in CRIT_DMG_KEYWORDS)]
        dmg_items = [(n, v, s, nk, sq) for n, v, s, nk, sq in filtered_items
                     if any(kw in n for kw in CRIT_DMG_KEYWORDS)]

        # 构建副名称查找表（供计算过程 hover 提示使用）
        sub_map = {}
        for entry in items:
            if len(entry) >= 6 and entry[5]:
                # 用 (名称, 来源标签, nav_key, 数值) 做键，避免同名同源不同值条目覆盖
                sub_map[(entry[0], entry[2], entry[3], entry[4])] = entry[5]

        # 构建计算过程（可点击值跳转来源）
        self._build_process(
            basis, zone_label, base_value, weapon_base,
            pct_items, flat_items, total_pct, total_flat, base_zone,
            bonus_items, total_bonus, bonus_zone,
            deepen_items, total_deepen, deepen_zone,
            rate_items, dmg_items, total_crit_rate, total_crit_dmg, crit_zone,
            def_zone, res_zone, indep_zone, indep_groups,
            base_m, mult_inc, mult_zone, final_crit, final_no_crit,
            sub_map, boost_vals
        )

        mult_boosts = boost_vals
        self._last_computed = {
            "basis": basis,
            "element": selected_element,
            "skill": selected_skill,
            "effect": selected_effect,
            "category": "常态攻击",
            "keywords": list(self._keywords),
            "base_mult": base_m,
            "mult_increase": mult_inc,
            "mult_boosts": mult_boosts,
            "zones": {
                "atk_zone": base_zone, "bonus_zone": bonus_zone,
                "deepen_zone": deepen_zone, "crit_zone": crit_zone,
                "crit_rate": total_crit_rate,
                "def_zone": def_zone, "res_zone": res_zone,
                "indep_zone": indep_zone,
                "mult_zone": mult_zone, "final_crit": final_crit,
                "final_no_crit": final_no_crit,
                "computed_base_zone": computed_base_zone,
            },
            "process_html": self._process_label.text(),
        }


    # ── 倍率动态列表 ──
    # ⚠️ 以下 7 个方法（~183 行）与 ResultDetailDialog（~L6493 同名方法）完全重复。
    # 修改此处必须同步修改 ResultDetailDialog 的对应方法，否则行为分歧。
    # 未来重构：抽取到共享 mixin，从两个类引入，消除双份维护负担。见 docs/项目总结.md

    def _sync_mult_entries(self):
        """从关键词关联同步倍率值到表格（实时互通，只读展示）"""
        kw_page = self._keyword_assoc_page if hasattr(self, '_keyword_assoc_page') else getattr(getattr(self, '_page', None), '_keyword_assoc_page', None)
        card_kw_set = set(self._keywords) if hasattr(self, '_keywords') else set(getattr(getattr(self, '_page', None), '_keywords', []))
        inc_rows = []
        boost_rows = []
        if kw_page:
            for kw_item in kw_page.get_items():
                kw_entry_kws = kw_item.get("keywords", "")
                if not kw_entry_kws or not card_kw_set:
                    continue
                entry_kw_set = set(k.strip() for k in kw_entry_kws.split(",") if k.strip())
                if not (entry_kw_set & card_kw_set):
                    continue
                name = kw_item.get("name", "")
                value = kw_item.get("value", 0.0)
                source = kw_item.get("source", "")
                sub_name = kw_item.get("sub_name", "")
                seq = kw_item.get("seq", "")
                if "倍率增加" in name:
                    inc_rows.append((name, sub_name, seq, value, source, kw_entry_kws))
                elif "倍率提升" in name:
                    boost_rows.append((name, sub_name, seq, value, source, kw_entry_kws))
        self._populate_mult_table(self.mult_inc_table, inc_rows)
        self._populate_mult_table(self.mult_boost_table, boost_rows)

    def _jump_to_kw_row(self, seq):
        """跳转到关键词关联页并高亮匹配序列号的行"""
        if not seq:
            return
        # 从当前 widget 向上找 MainScreen（centralWidget）
        ms = self
        while ms and not hasattr(ms, '_navigate_to_key'):
            ms = ms.parent() if hasattr(ms, 'parent') and callable(ms.parent) else None
        if ms and hasattr(ms, 'page_keyword_assoc'):
            ms._navigate_to_key("keyword_assoc", hl_seq=seq)

    def _toggle_kw_hide(self, kw_key, btn):
        """切换关键词关联条目的隐藏状态（实时触发重算）"""
        if kw_key in HIDDEN_ITEMS:
            HIDDEN_ITEMS.discard(kw_key)
            if btn:
                btn.setText("隐藏")
                btn.setObjectName("itemLockBtn")
        else:
            HIDDEN_ITEMS.add(kw_key)
            if btn:
                btn.setText("隐藏中")
                btn.setObjectName("itemDeleteBtn")
        if btn:
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        # 实时刷新表格 + 重算
        self._sync_mult_entries()
        if hasattr(self, 'auto_compute'):
            self.compute()  # 隐藏强制重算，无视 auto_compute 开关
        elif hasattr(self, '_on_mult_changed'):
            self._on_mult_changed()

    def _get_kw_page(self):
        """获取关键词关联页引用"""
        if hasattr(self, '_keyword_assoc_page') and self._keyword_assoc_page:
            return self._keyword_assoc_page
        if hasattr(self, '_page') and hasattr(self._page, '_keyword_assoc_page'):
            return self._page._keyword_assoc_page
        return None

    def _sync_sub_name_to_kw(self, seq, text):
        """将倍率表格中的副名称编辑同步回关键词关联对应行"""
        kw_page = self._get_kw_page()
        if not kw_page or not seq:
            return
        for row in range(kw_page._table.rowCount()):
            sl = kw_page._table.cellWidget(row, 2)
            if sl and hasattr(sl, 'text') and sl.text() == seq:
                sub_cell = kw_page._table.cellWidget(row, 1)
                if sub_cell:
                    le = sub_cell.findChild(QLineEdit) if not isinstance(sub_cell, QLineEdit) else sub_cell
                    if le and le.text() != text:
                        le.setText(text)
                return

    def _populate_mult_table(self, table, rows):
        """填充倍率表格（照搬关键词关联表格结构，来源可跳转，操作可隐藏）"""
        table.setRowCount(0)
        for name, sub_name, seq, value, source, kw_entry_kws in rows:
            r = table.rowCount()
            table.insertRow(r)
            table.setRowHeight(r, 40)
            # 名称
            name_w = QLineEdit(name)
            name_w.setObjectName("nameEdit")
            name_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_w.setReadOnly(True)
            table.setCellWidget(r, 0, name_w)
            # 副名称（编辑后自动映射回关键词关联表格）
            sub_container = _make_sub_name_cell(QLineEdit(), lambda n=name: n)
            sub_w = sub_container.findChild(QLineEdit)
            if sub_w:
                sub_w.setText(sub_name)
                sub_w.setObjectName("nameEdit")
                sub_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sub_w.setPlaceholderText("（备注）")
                sub_w.textChanged.connect(lambda text, sq=seq: self._sync_sub_name_to_kw(sq, text))
            table.setCellWidget(r, 1, sub_container)
            # 序列号
            seq_w = QLabel(seq if seq else "—")
            seq_w.setObjectName("seqLabel")
            seq_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setCellWidget(r, 2, seq_w)
            # 数值
            val_w = QDoubleSpinBox()
            val_w.setObjectName("itemValueSpin")
            val_w.setRange(0, 9999)
            val_w.setDecimals(4)
            val_w.setValue(value)
            val_w.setFixedWidth(100)
            val_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_w.setReadOnly(True)
            val_w.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            table.setCellWidget(r, 3, val_w)
            # 取值
            unit_w = QLabel("百分比")
            unit_w.setObjectName("unitLabel")
            unit_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setCellWidget(r, 4, unit_w)
            # 来源（按钮 — 点击跳转关键词关联页对应行）
            src_btn = QPushButton(source if source else "—")
            src_btn.setObjectName("itemLockBtn")
            src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            src_btn.setToolTip("跳转到关键词关联页定位此行")
            src_btn.clicked.connect(lambda checked, sq=seq:
                self._jump_to_kw_row(sq))
            table.setCellWidget(r, 5, src_btn)
            # 关键词关联
            kw_w = QLabel(kw_entry_kws)
            kw_w.setObjectName("seqLabel")
            kw_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            kw_w.setWordWrap(True)
            table.setCellWidget(r, 6, kw_w)
            # 操作（隐藏按钮）
            kw_key = (name, "keyword_assoc", seq)
            is_hid = kw_key in HIDDEN_ITEMS
            hide_btn = QPushButton("隐藏中" if is_hid else "隐藏")
            hide_btn.setObjectName("itemDeleteBtn" if is_hid else "itemLockBtn")
            hide_btn.setFixedSize(48, 28)
            hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            hide_btn.clicked.connect(lambda checked, k=kw_key, b=hide_btn:
                self._toggle_kw_hide(k, b))
            ops = QWidget()
            ops_layout = QHBoxLayout(ops)
            ops_layout.setContentsMargins(0, 0, 0, 0)
            ops_layout.addStretch()
            ops_layout.addWidget(hide_btn)
            ops_layout.addStretch()
            table.setCellWidget(r, 7, ops)


    def _gather_mult_data(self):
        "从关键词关联收集有效倍率值（必须有匹配关键词）"
        inc_vals = []
        boost_vals = []
        kw_page = self._keyword_assoc_page if hasattr(self, '_keyword_assoc_page') else getattr(getattr(self, '_page', None), '_keyword_assoc_page', None)
        card_kw_set = set(self._keywords) if hasattr(self, '_keywords') else set(k.strip() for k in self._item.get("keywords", []))
        if kw_page and card_kw_set:
            for kw_item in kw_page.get_items():
                kw_entry_kws = kw_item.get("keywords", "")
                if not kw_entry_kws:
                    continue
                entry_kw_set = set(k.strip() for k in kw_entry_kws.split(",") if k.strip())
                if not (entry_kw_set & card_kw_set):
                    continue
                name = kw_item.get("name", "")
                value = kw_item.get("value", 0.0)
                source = kw_item.get("source", "")
                seq = kw_item.get("seq", "")
                if (name, "keyword_assoc", seq) in HIDDEN_ITEMS:
                    continue
                if "倍率增加" in name:
                    inc_vals.append(value)
                elif "倍率提升" in name:
                    boost_vals.append(value)
        return inc_vals, boost_vals
    def _clear_process(self):
        """清除旧的计算过程文本。"""
        self._process_label.clear()
        self._process_label.setVisible(False)
        self._process_empty_label.setVisible(True)
        self._process_copy_btn.setVisible(False)

    def _copy_process_text(self):
        """将计算过程纯文本复制到剪贴板。"""
        html = self._process_label.text()
        if not html.strip():
            QMessageBox.information(self, "提示", "没有可复制的计算过程。")
            return
        doc = QTextDocument()
        doc.setHtml(html)
        QApplication.clipboard().setText(doc.toPlainText())
        QMessageBox.information(self, "已复制", "计算过程已复制到剪贴板。")

    def _is_light_theme(self):
        """向上遍历父级查找 DmgCalculator 的 current_theme 属性。"""
        try:
            w = self.parent()
            while w is not None:
                if hasattr(w, "current_theme"):
                    return w.current_theme == "light"
                w = w.parent()
        except Exception as e:
            _logger.debug("主题检测失败: %s", e)
        return False

    def _on_process_link_activated(self, url):
        """处理 QLabel 中链接点击，实现导航跳转和高亮。"""
        # 去掉 \x1e 后面的 tooltip 部分
        if "\x1e" in url:
            url = url.split("\x1e")[0]
        if url.startswith("hl:"):
            parts = url[3:].split(":", 4)
            if len(parts) >= 5:
                sk, name, src, nk, sq = parts[0], parts[1], parts[2], parts[3], parts[4]
                if self._navigate:
                    self._navigate(sk)
                tp = self._summary_pages.get(sk) if self._summary_pages else None
                if tp:
                    QTimer.singleShot(200, lambda: tp.highlight_item(name, src, nk, sq))
            return
        if url.startswith("nav:"):
            nk = url[4:]
            if nk and self._navigate:
                self._navigate(nk)

    def _on_process_link_hovered(self, url):
        """鼠标悬停链接时，在光标右下角显示来源 tooltip。"""
        if "\x1e" in url:
            tip = url.split("\x1e", 1)[1]
            tip = tip.replace("&#10;", "\n")
            QToolTip.showText(QCursor.pos(), tip, self._process_label)
        else:
            QToolTip.hideText()

    def _build_process(self, basis, zone_label, base_value, weapon_base,
                       pct_items, flat_items, total_pct, total_flat, base_zone,
                       bonus_items, total_bonus, bonus_zone,
                       deepen_items, total_deepen, deepen_zone,
                       rate_items, dmg_items, total_crit_rate, total_crit_dmg, crit_zone,
                       def_zone, res_zone, indep_zone, indep_groups,
                       base_m, mult_inc, mult_zone, final_crit, final_no_crit,
                       sub_map=None, boost_vals=None):
        self._clear_process()
        self._process_empty_label.setVisible(False)
        self._process_copy_btn.setVisible(True)
        if boost_vals is None:
            _, boost_vals = self._gather_mult_data()
        mult_boosts_vals = boost_vals
        html = _render_process_html(
            basis, zone_label, base_value, weapon_base,
            pct_items, flat_items, total_pct, total_flat, base_zone,
            bonus_items, total_bonus, bonus_zone,
            deepen_items, total_deepen, deepen_zone,
            rate_items, dmg_items, total_crit_rate, total_crit_dmg, crit_zone,
            def_zone, res_zone, indep_zone, indep_groups,
            base_m, mult_inc, mult_boosts_vals, mult_zone, final_crit, final_no_crit,
            is_light=self._is_light_theme(), sub_map=sub_map,
            navigate_fn=self._navigate, summary_pages=self._summary_pages,
            base_override_active=getattr(self, "_base_override_enabled", False),
            computed_base_zone=getattr(self, '_computed_base_zone', None),
        )
        self._process_label.setText(html)
        self._process_label.setVisible(True)
        # 以下为原 _build_process 内联代码，已迁移到 _render_process_html

from char_base_page import CharBasePage
# ==================== 使用手册弹窗 ====================

MANUAL_DIR = os.path.join(_DATA_DIR, "manual")
MANUAL_CONTENT_FILE = os.path.join(MANUAL_DIR, "content.json")
MANUAL_IMAGES_DIR = os.path.join(MANUAL_DIR, "images")

# 导航树 key → 使用手册 key 的默认映射
DEFAULT_NAV_MAPPING = {
    "data_source":       "char_bonus",
    "echo_counter":      "char_bonus",
    "combined_perm":     "char_bonus",
    "combined_trigger":  "char_bonus",
    "summary_base":      "char_deepen",
    "summary_bonus":     "char_deepen",
    "summary_deepen":    "char_deepen",
    "summary_crit":      "char_deepen",
    "summary_indep":     "char_deepen",
    "enemy_defense":     "char_crit",
    "enemy_resistance":  "char_crit",
    "result":            "char_indep",
    "result_list":       "char_indep",
}

MANUAL_DEFAULTS = {
    "char_base": {
        "name": "角色与武器",
        "html": (
            "<h2>角色与武器</h2>"
            "<p>在此页面设置角色的<strong>基础属性</strong>（生命值、攻击力、防御力）"
            "以及<strong>武器基础攻击力</strong>和<strong>武器属性加成</strong>。</p>"
            "<p>这些数值是所有后续计算的基础。</p>"
            "<ul><li>角色基础属性默认为 1</li>"
            "<li>武器属性加成可选择攻击力/生命值/防御力的百分比或固定值</li></ul>"
        ),
    },
    "char_bonus": {
        "name": "数值来源",
        "html": (
            "<h2>数值来源</h2>"
            "<p>在此区域添加角色的各种<strong>加成词条</strong>，所有来源汇总后作用于最终伤害计算。</p>"
            "<h3>声骸数值</h3><p>录入声骸的主词条与副词条。支持手动添加和 OCR 截图识别（最多 5 张）。</p>"
            "<h3>综合填写</h3><p>统一添加武器谐振、合鸣效果、技能效果、其他效果四类来源的加成词条，分常驻数值和触发数值。每条词条需选择来源，添加后自动同步到对应子页面。</p>"
            "<h3>词条分类</h3><p>含「伤害加成」或「伤害提升」→ 加成乘区；含「加深」→ 加深乘区；含「暴击率/暴击伤害」→ 暴击乘区；攻击力/生命值/防御力 → 基础乘区。</p>"
        ),
    },
    "char_deepen": {
        "name": "数值总结",
        "html": (
            "<h2>数值总结</h2>"
            "<p>将「数值来源」中所有词条按<strong>乘区</strong>自动分类汇总。</p>"
            "<h3>基础乘区</h3><p>汇总攻击力/生命值/防御力。基础数值 = (角色基础+武器基础) x (1+百分比合计/100) + 固定值</p>"
            "<h3>加成乘区</h3><p>汇总伤害加成与伤害提升。加成乘区 = 1 + 加成合计/100</p>"
            "<h3>加深乘区</h3><p>汇总伤害加深。加深乘区 = 1 + 加深合计/100</p>"
            "<h3>暴击乘区</h3><p>基础暴击率 5%，基础暴击伤害 150%。暴击乘区(暴击时) = (150% + 暴击伤害来源合计)/100</p>"
            "<h3>独立乘区</h3><p>各组内部相加后组间相乘。独立乘区 = 组1 x 组2 x ...</p>"
        ),
    },
    "char_crit": {
        "name": "敌人减伤",
        "html": (
            "<h2>敌人减伤</h2>"
            "<h3>防御减伤</h3><p>设置敌人等级和防御力，防御乘区根据等级差和防御力无视/减少词条计算。</p>"
            "<h3>抗性数值</h3><p>每种元素独立设置基础抗性、抗性提升、抗性减少。最终抗性 >= 0：抗性乘区 = 1 - 最终抗性/100；最终抗性 &lt; 0：抗性乘区 = 1 - 最终抗性/200。</p>"
        ),
    },
    "char_indep": {
        "name": "计算结果",
        "html": (
            "<h2>计算结果</h2>"
            "<h3>倍率设置</h3><p>基础倍率 + 倍率增加（相加），倍率提升 1~3（独立乘算）。</p>"
            "<h3>筛选条件</h3><p>限定本次计算使用哪些来源的词条：基础数值类型、元素属性、技能类型、效应类型。仅匹配所有条件的词条参与计算。</p>"
            "<h3>计算过程</h3><p>按顺序展示各乘区详细计算，数值可点击跳转来源页面。最终输出暴击后伤害和无暴击伤害。</p>"
            "<h3>结果列表</h3><p>保存多条计算结果，支持锁定/更新/展开/自动更新/批量操作。卡片标题过长时自动滚动。</p>"
        ),
    },
    "summary_base": {
        "name": "基础乘区",
        "html": (
            "<h2>基础乘区</h2>"
            "<p>展示所有来源中关于<strong>基础数值</strong>（攻击力/生命值/防御力）的加成汇总。</p>"
            "<p>包括百分比加成和固定值加成，最终计算公式为：</p>"
            "<p><code>基础数值 = (角色基础 + 武器基础) x (1 + 百分比合计/100) + 固定值合计</code></p>"
        ),
    },
    "summary_bonus": {
        "name": "加成乘区",
        "html": (
            "<h2>加成乘区</h2>"
            "<p>展示所有<strong>伤害加成</strong>与<strong>伤害提升</strong>属性的汇总（全属性、各元素、各技能类别）。</p>"
            "<p>加成乘区 = 1 + 加成合计/100</p>"
        ),
    },
    "summary_deepen": {
        "name": "加深乘区",
        "html": (
            "<h2>加深乘区</h2>"
            "<p>展示所有<strong>伤害加深</strong>属性的汇总（全属性、各元素、各技能类别、各效应）。</p>"
            "<p>加深乘区 = 1 + 加深合计/100</p>"
        ),
    },
    "summary_crit": {
        "name": "暴击乘区",
        "html": (
            "<h2>暴击乘区</h2>"
            "<p>展示<strong>暴击率</strong>与<strong>暴击伤害</strong>的汇总。</p>"
            "<p>角色基础暴击率为 <strong>5%</strong>，基础暴击伤害为 <strong>150%</strong>。</p>"
            "<p>最终暴击率 = 5% + 暴击率来源合计</p>"
            "<p>暴击乘区（暴击时）= (150% + 暴击伤害加成合计)/100</p>"
        ),
    },
    "summary_indep": {
        "name": "独立乘区",
        "html": (
            "<h2>独立乘区</h2>"
            "<p>独立乘区是游戏中最稀有的乘区类型。</p>"
            "<p>每个<strong>独立乘区组</strong>内部各数值相加（1 + 合计/100），"
            "各组之间为<strong>乘法</strong>关系。</p>"
            "<p>最终独立乘区 = 独立乘区组1 x 独立乘区组2 x ...</p>"
        ),
    },
    "enemy_defense": {
        "name": "防御减伤",
        "html": (
            "<h2>防御减伤</h2>"
            "<p>设置敌人的<strong>等级</strong>和<strong>防御力相关</strong>参数。</p>"
            "<p>防御乘区根据角色等级、敌人等级、防御力无视/减少等参数计算。</p>"
        ),
    },
    "enemy_resistance": {
        "name": "抗性数值",
        "html": (
            "<h2>抗性数值</h2>"
            "<p>设置敌人的<strong>抗性</strong>相关参数。</p>"
            "<p>每种元素独立设置基础抗性、抗性提升、抗性减少，"
            "并可通过外部来源叠加抗性无视/减少效果。</p>"
            "<p>抗性乘区根据最终抗性值自动计算。</p>"
        ),
    },
    "result": {
        "name": "计算结果",
        "html": (
            "<h2>计算结果</h2>"
            "<p>配置<strong>倍率</strong>和<strong>筛选条件</strong>后点击 [计算] 按钮。</p>"
            "<p>计算过程区域会展示每个乘区的详细计算步骤，数值可点击跳转到对应来源页面。</p>"
            "<p>点击<strong>[计入结果]</strong>可将当前结果保存到结果列表。</p>"
            "<p>开启<strong>[自动计算]</strong>后，数值来源变更时自动重新计算。</p>"
        ),
    },
    "result_list": {
        "name": "结果列表",
        "html": (
            "<h2>结果列表</h2>"
            "<p>保存多条计算结果，每条记录可独立调整倍率参数。</p>"
            "<p><strong>锁定</strong>：锁定后源数据变更不影响该条记录。</p>"
            "<p><strong>自动更新</strong>：开启后源数据变更时自动重算未锁定条目。</p>"
            "<p>点击卡片可查看详细计算过程和结果。</p>"
        ),
    },
}

def _load_manual_content():
    """加载手动内容，含章节数据与导航重定向映射。"""
    if os.path.exists(MANUAL_CONTENT_FILE):
        try:
            with open(MANUAL_CONTENT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, val in MANUAL_DEFAULTS.items():
                if key not in data:
                    data[key] = val
            if "_nav_mapping" not in data:
                data["_nav_mapping"] = dict(DEFAULT_NAV_MAPPING)
            return data
        except (json.JSONDecodeError, OSError):
            pass
    data = dict(MANUAL_DEFAULTS)
    data["_nav_mapping"] = dict(DEFAULT_NAV_MAPPING)
    return data

def _save_manual_content(data):
    os.makedirs(MANUAL_DIR, exist_ok=True)
    os.makedirs(MANUAL_IMAGES_DIR, exist_ok=True)
    with open(MANUAL_CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class BaseOverrideDialog(QDialog):
    """基础数值调整弹窗 — 手动覆盖 base_zone 以对齐游戏内量子化取整"""

    def __init__(self, parent=None, current_base=0.0, enabled=False, override_value=0.0):
        super().__init__(parent)
        self.setWindowTitle("基础数值调整")
        self.setMinimumSize(420, 220)
        self.setWindowOpacity(0.97)

        self._enabled = enabled
        self._callback = None
        _center_window(self)


        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # 当前自动计算值（只读参考）
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("当前自动计算值："))
        self._current_label = QLabel(f"{current_base:.2f}")
        self._current_label.setStyleSheet("font-weight: 700; font-size: 16px; color: #e94560;")
        info_layout.addWidget(self._current_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 说明文字
        hint = QLabel(
            "游戏计算基础数值时，会将每个百分比加成单独乘以基础值后再取整"
            "因此理论计算结果与游戏实际显示值可能存在偏差。（具体查看使用手册）"
            "请在此输入游戏内显示的实际数值，以强制同步计算器中的基础数值。"
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(hint)

        # 输入框
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("手动基础数值："))
        self._spin = QDoubleSpinBox()
        self._spin.setRange(0.0, 999999.0)
        self._spin.setDecimals(1)
        self._spin.setSingleStep(10.0)
        self._spin.setValue(override_value if enabled else current_base)
        self._spin.setMinimumWidth(140)
        input_layout.addWidget(self._spin)
        input_layout.addStretch()
        layout.addLayout(input_layout)

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._toggle_btn = QPushButton("取消" if enabled else "启用")
        self._toggle_btn.setMinimumWidth(80)
        self._toggle_btn.clicked.connect(self._on_toggle)
        btn_layout.addWidget(self._toggle_btn)

        layout.addLayout(btn_layout)

    def set_callback(self, cb):
        """cb(enabled: bool, value: float) — 状态变更时回调"""
        self._callback = cb

    def set_current_base(self, value):
        """更新当前自动计算值显示"""
        self._current_label.setText(f"{value:.2f}")

    def reset_state(self, enabled, value, current_base):
        """加载存档后重置弹窗状态（不触发回调）"""
        self._enabled = enabled
        self._toggle_btn.setText("取消" if enabled else "启用")
        self._spin.setValue(value if enabled else current_base)
        self._current_label.setText(f"{current_base:.2f}")

    def _on_toggle(self):
        self._enabled = not self._enabled
        if self._enabled:
            self._toggle_btn.setText("取消")
        else:
            self._toggle_btn.setText("启用")
        if self._callback:
            self._callback(self._enabled, self._spin.value())

    @property
    def enabled(self):
        return self._enabled

    @property
    def override_value(self):
        return self._spin.value()


class ManualDialog(QDialog):
    """使用手册弹窗，支持富文本查看/编辑、图片插入"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("使用手册")
        self.setMinimumSize(800, 600)
        self.resize(900, 680)
        self.setWindowOpacity(0.97)

        self._content = _load_manual_content()
        self._current_key = None
        self._editing = False
        self._image_counter = 0
        self._content_snapshot = None  # 进入编辑模式前的快照，取消时恢复
        self._raw_html = ""

        # 检测当前主题（白天模式用深色字，黑夜模式用浅色字）
        light = self._is_light_theme()
        self._section_color = "#1b2035" if light else "#dde0e6"
        self._section_bg = "#edf2f9" if light else "#1b2030"
        self._section_hover = "rgba(0,0,0,0.06)" if light else "rgba(255,255,255,0.06)"
        self._section_select = "rgba(0,120,212,0.15)" if light else "rgba(0,120,212,0.25)"
        self._section_border = "#d0d5db" if light else "rgba(128,128,128,0.25)"
        _center_window(self)


        layout = QHBoxLayout(self)
        layout.setSpacing(0)

        # —— 左侧目录 ——
        left = QWidget()
        left.setFixedWidth(180)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)

        left_title = QLabel("目录")
        left_title.setStyleSheet(f"font-size: 14px; font-weight: 700; padding: 4px 0; color: {self._section_color};")
        left_layout.addWidget(left_title)

        self.section_list = QListWidget()
        self.section_list.setStyleSheet(
            f"QListWidget {{ border: 1px solid {self._section_border}; border-radius: 4px;"
            f" background: {self._section_bg}; color: {self._section_color}; }}"
            f"QListWidget::item {{ padding: 4px 6px; }}"
            f"QListWidget::item:hover {{ background: {self._section_hover}; }}"
            f"QListWidget::item:selected {{ background: {self._section_select}; }}"
        )
        # 按保存的顺序排列章节（_toc_order 不存在则用默认顺序）
        _toc_order = self._content.get("_toc_order", [])
        _known = list(_toc_order)
        for key, val in self._content.items():
            if key.startswith("_"):
                continue
            if key not in _known:
                _known.append(key)
        self._section_keys = []
        for key in _known:
            if key.startswith("_") or key not in self._content:
                continue
            val = self._content[key]
            name = val.get("name", key) if isinstance(val, dict) else key
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            # 恢复保存的样式
            styles = (self._content.get("_toc_styles") or {}).get(key, {})
            if styles:
                item.setFont(self._build_toc_font(styles, item.font()))
                if styles.get("color"):
                    item.setForeground(QColor(styles["color"]))
            self.section_list.addItem(item)
            self._section_keys.append(key)

        self.section_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.section_list.customContextMenuRequested.connect(self._on_toc_context_menu)
        self.section_list.currentRowChanged.connect(self._on_section_changed)
        left_layout.addWidget(self.section_list, stretch=1)
        layout.addWidget(left)

        # —— 右侧内容区 ——
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)

        toolbar = QHBoxLayout()
        self.section_title = QLabel("")
        self.section_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {self._section_color};")
        toolbar.addWidget(self.section_title)
        toolbar.addStretch()

        self.edit_btn = QPushButton("编辑")
        self.edit_btn.setObjectName("backButton")
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(self._toggle_edit)
        toolbar.addWidget(self.edit_btn)

        self.insert_img_btn = QPushButton("插入图片")
        self.insert_img_btn.setObjectName("backButton")
        self.insert_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.insert_img_btn.clicked.connect(self._insert_image)
        self.insert_img_btn.setVisible(False)
        toolbar.addWidget(self.insert_img_btn)

        self.insert_link_btn = QPushButton("插入链接")
        self.insert_link_btn.setObjectName("backButton")
        self.insert_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.insert_link_btn.clicked.connect(self._insert_link)
        self.insert_link_btn.setVisible(False)
        toolbar.addWidget(self.insert_link_btn)

        self.cancel_edit_btn = QPushButton("取消更改")
        self.cancel_edit_btn.setObjectName("backButton")
        self.cancel_edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_edit_btn.clicked.connect(self._cancel_edit)
        self.cancel_edit_btn.setVisible(False)
        toolbar.addWidget(self.cancel_edit_btn)

        right_layout.addLayout(toolbar)

        # —— 查找/替换栏（编辑模式下可见） ——
        self.find_bar = QWidget()
        find_bar_layout = QHBoxLayout(self.find_bar)
        find_bar_layout.setContentsMargins(0, 4, 0, 2)
        find_bar_layout.setSpacing(4)

        find_bar_layout.addWidget(QLabel("查找:"))
        self.find_input = QLineEdit()
        self.find_input.setMaximumWidth(160)
        self.find_input.setPlaceholderText("搜索文本...")
        self.find_input.returnPressed.connect(self._find_next)
        self.find_input.textChanged.connect(self._on_find_text_changed)
        find_bar_layout.addWidget(self.find_input)

        find_bar_layout.addWidget(QLabel("替换:"))
        self.replace_input = QLineEdit()
        self.replace_input.setMaximumWidth(160)
        self.replace_input.setPlaceholderText("替换为...")
        find_bar_layout.addWidget(self.replace_input)

        self.find_prev_btn = QPushButton("↑")
        self.find_prev_btn.setObjectName("backButton")
        self.find_prev_btn.setToolTip("查找上一个")
        self.find_prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.find_prev_btn.clicked.connect(self._find_prev)
        find_bar_layout.addWidget(self.find_prev_btn)

        self.find_next_btn = QPushButton("↓")
        self.find_next_btn.setObjectName("backButton")
        self.find_next_btn.setToolTip("查找下一个")
        self.find_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.find_next_btn.clicked.connect(self._find_next)
        find_bar_layout.addWidget(self.find_next_btn)

        self.replace_btn = QPushButton("替换")
        self.replace_btn.setObjectName("backButton")
        self.replace_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.replace_btn.clicked.connect(self._replace_one)
        find_bar_layout.addWidget(self.replace_btn)

        self.replace_all_btn = QPushButton("替换全部")
        self.replace_all_btn.setObjectName("backButton")
        self.replace_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.replace_all_btn.clicked.connect(self._replace_all)
        find_bar_layout.addWidget(self.replace_all_btn)

        self.find_status = QLabel("")
        self.find_status.setMinimumWidth(80)
        find_status_color = "#888888" if light else "#999999"
        self.find_status.setStyleSheet(f"font-size: 12px; color: {find_status_color};")
        find_bar_layout.addWidget(self.find_status)
        find_bar_layout.addStretch()

        self.find_bar.setVisible(False)
        right_layout.addWidget(self.find_bar)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet(
            f"QTextEdit {{ border: 1px solid {self._section_border}; border-radius: 4px;"
            f"padding: 0px 12px 12px 12px; font-size: 14px; background: {self._section_bg}; color: {self._section_color}; }}"
        )
        self._link_color = "#7c3aed" if light else "#8db8ff"
        self.text_edit.viewport().setMouseTracking(True)
        self.text_edit.viewport().installEventFilter(self)
        right_layout.addWidget(self.text_edit, stretch=1)
        layout.addWidget(right, stretch=1)

        if self._section_keys:
            self.section_list.setCurrentRow(0)

        # 快捷键：查找/替换（仅在编辑模式下生效）
        self._shortcut_find = QShortcut("Ctrl+F", self)
        self._shortcut_find.activated.connect(self._show_find_bar)
        self._shortcut_f3 = QShortcut("F3", self)
        self._shortcut_f3.activated.connect(self._find_next)
        self._shortcut_sf3 = QShortcut("Shift+F3", self)
        self._shortcut_sf3.activated.connect(self._find_prev)
        # Escape 隐藏查找栏
        self._shortcut_esc = QShortcut("Escape", self.find_input)
        self._shortcut_esc.activated.connect(self._hide_find_bar)
        self._shortcut_esc2 = QShortcut("Escape", self.replace_input)
        self._shortcut_esc2.activated.connect(self._hide_find_bar)

    def _show_find_bar(self):
        """Ctrl+F：仅在编辑模式下切换查找栏显示/隐藏。"""
        if not self._editing:
            return
        if self.find_bar.isVisible():
            self._hide_find_bar()
        else:
            self.find_bar.setVisible(True)
            self.find_input.setFocus()
            self.find_input.selectAll()

    def _hide_find_bar(self):
        self.find_bar.setVisible(False)
        self.text_edit.setExtraSelections([])

    def _is_light_theme(self):
        """向上遍历父级查找 DmgCalculator 的 current_theme 属性."""
        try:
            w = self.parent()
            while w is not None:
                if hasattr(w, "current_theme"):
                    return w.current_theme == "light"
                w = w.parent()
        except Exception as e:
            _logger.debug("主题检测失败: %s", e)
        return False

    def _cursor_on_image(self, pt):
        """检查坐标是否在图片上，若是返回图片路径，否则 None"""
        try:
            cursor = self.text_edit.cursorForPosition(pt)
            fmt = cursor.charFormat()
            if fmt.isImageFormat():
                return fmt.toImageFormat().name()
        except Exception:
            pass
        return None

    def eventFilter(self, obj, event):
        """处理图片点击查看原图、链接跳转、阻止 Ctrl+滚轮缩放."""
        if obj != self.text_edit.viewport():
            return super().eventFilter(obj, event)
        try:
            if event.type() == QEvent.Type.Wheel:
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                pt = event.position().toPoint()
                on_link = bool(self.text_edit.anchorAt(pt))
                on_img = bool(self._cursor_on_image(pt))
                if on_link or on_img:
                    obj.setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    obj.setCursor(Qt.CursorShape.IBeamCursor)
            elif event.type() == QEvent.Type.MouseButtonPress:
                if self._editing:
                    return super().eventFilter(obj, event)
                pt = event.position().toPoint()
                # 优先图片点击
                img_src = self._cursor_on_image(pt)
                if img_src:
                    path = img_src.replace("file:///", "")
                    os.startfile(path)
                    return True
                # 其次链接点击
                href = self.text_edit.anchorAt(pt)
                if href:
                    if href.startswith("file:///"):
                        os.startfile(href.replace("file:///", ""))
                    else:
                        QDesktopServices.openUrl(QUrl(href))
                    return True
            elif event.type() == QEvent.Type.Leave:
                obj.setCursor(Qt.CursorShape.ArrowCursor)
        except Exception:
            pass
        return super().eventFilter(obj, event)

    @staticmethod
    def _prettify_html(html):
        """用 xml.dom.minidom 格式化 HTML，添加换行和缩进."""
        import re
        import xml.dom.minidom
        try:
            html = html.strip()
            # 去掉 DOCTYPE（xml.dom.minidom 无法处理）
            html = re.sub(r'<!DOCTYPE[^>]*>', '', html)
            # 检查是否为完整 HTML 文档
            has_html_tag = bool(re.search(r'<html\b', html, re.IGNORECASE))
            if not has_html_tag:
                html = f'<root>{html}</root>'
            dom = xml.dom.minidom.parseString(html)
            pretty = dom.toprettyxml(indent="  ")
            pretty = re.sub(r'^<\?xml[^?]*\?>\s*', '', pretty)
            if not has_html_tag:
                pretty = re.sub(r'^\s*<root>\s*', '', pretty)
                pretty = re.sub(r'\s*</root>\s*$', '', pretty)
            pretty = re.sub(r'\n\s*\n', '\n', pretty)
            return pretty.strip()
        except Exception:
            return html

    def _fix_image_paths(self, html):
        """将各种相对路径转为绝对 file:/// 路径"""
        import re
        def _replace(match):
            src = match.group(1)
            # 已经是 file:/// 绝对路径就跳过
            if src.startswith("file:///"):
                return match.group(0)
            # 其他所有相对路径：提取文件名，拼到 MANUAL_IMAGES_DIR
            # 兼容: images/xxx.png  ./manual/images/xxx.png  manual/images/xxx.png
            basename = os.path.basename(src)
            if basename:
                abs_path = os.path.join(MANUAL_IMAGES_DIR, basename)
                abs_path = abs_path.replace("\\", "/")
                return f'src="file:///{abs_path}"'
            return match.group(0)
        return re.sub(r'src="([^"]+)"', _replace, html)

    def _prepare_display_html(self, html):
        """处理 HTML 以供显示：修复图片路径、注入主题色、覆盖常见标签样式."""
        import re

        # 主题适配的通用样式块
        code_bg = "rgba(128,128,128,0.15)"
        table_border = "rgba(128,128,128,0.25)"
        highlight_bg = "rgba(80,112,232,0.15)" if self._is_light_theme() else "rgba(233,69,96,0.15)"
        highlight_fg = "#5070e8" if self._is_light_theme() else "#ff6b81"
        theme_css = (
            f'<style>'
            f'code, pre {{ background:{code_bg}!important; font-family:"Courier New",monospace; }}'
            f'pre {{ padding:8px; border-radius:4px; }}'
            f'table {{ border-collapse:collapse; }}'
            f'th, td {{ border:1px solid {table_border}; padding:4px 8px; }}'
            f'mark {{ background:{highlight_bg}; color:{highlight_fg}; }}'
            f'kbd {{ background:{code_bg}; border:1px solid {table_border}; border-radius:3px; padding:1px 4px; }}'
            f'blockquote {{ border-left:3px solid {table_border}; margin:8px 0; padding:4px 12px; }}'
            f'hr {{ border:none; border-top:1px solid {table_border}; }}'
            f'a {{ color:{self._link_color}; }}'
            f'</style>'
        )

        html = self._fix_image_paths(html)
        # 注入主题 <style> 到 </head> 前或 <body> 前
        if '</head>' in html:
            html = html.replace('</head>', theme_css + '</head>')
        elif '<body' in html:
            html = html.replace('<body', theme_css + '<body')
        else:
            html = theme_css + html

        # 向 <body> 注入背景色和文字色
        if re.search(r'<body\b', html, re.IGNORECASE):
            if re.search(r'<body\b[^>]*style="', html, re.IGNORECASE):
                html = re.sub(
                    r'(<body\b[^>]*style=")([^"]*)"',
                    rf'\1\2; background-color: {self._section_bg}; color: {self._section_color};"',
                    html
                )
            else:
                html = re.sub(
                    r'<body\b',
                    f'<body style="background-color: {self._section_bg}; color: {self._section_color};"',
                    html
                )
        return html

    def _on_section_changed(self, row):
        if row < 0 or row >= len(self._section_keys):
            return
        # 编辑模式下先保存当前章节再切换
        if self._editing and self._current_key:
            html = self.text_edit.toPlainText()
            existing = self._content.get(self._current_key, {})
            name = existing.get("name", self._current_key) if isinstance(existing, dict) else self._current_key
            self._content[self._current_key] = {"name": name, "html": html}
            _save_manual_content(self._content)
        key = self._section_keys[row]
        self._current_key = key
        info = self._content.get(key, {"name": key, "html": ""})
        name = info.get("name", key) if isinstance(info, dict) else key
        html = info.get("html", "") if isinstance(info, dict) else ""
        html = self._fix_image_paths(html)
        self.section_title.setText(name)
        self._raw_html = html
        if self._editing:
            if "\n" not in html.strip():
                html = self._prettify_html(html)
            self.text_edit.clear()
            self.text_edit.setAcceptRichText(False)
            self.text_edit.setPlainText(html)
        else:
            self.text_edit.clear()
            self.text_edit.setAcceptRichText(True)
            self.text_edit.setHtml(self._prepare_display_html(html))

    def _toggle_edit(self):
        self._editing = not self._editing
        if self._editing:
            # 进入编辑模式：保存快照供取消时恢复
            self._content_snapshot = copy.deepcopy(self._content)
            # 强制清除富文本状态，再设纯文本
            self.text_edit.clear()
            raw = self._raw_html
            if "\n" not in raw.strip():
                raw = self._prettify_html(raw)
            self.text_edit.setAcceptRichText(False)
            self.text_edit.setPlainText(raw)
            self.text_edit.setReadOnly(False)
            self.text_edit.viewport().setCursor(Qt.CursorShape.IBeamCursor)
            self.edit_btn.setText("保存")
            edit_color = "#1b5e20" if self._is_light_theme() else "#a5d6a7"
            self.edit_btn.setStyleSheet(
                f"QPushButton {{ color: {edit_color}; background: rgba(76,175,80,0.2);"
                f"border: 1px solid rgba(76,175,80,0.4); border-radius: 3px; padding: 3px 8px; }}"
                f"QPushButton:hover {{ background: rgba(76,175,80,0.3); }}"
            )
            self.insert_img_btn.setVisible(True)
            self.insert_link_btn.setVisible(True)
            self.cancel_edit_btn.setVisible(True)
            # 启用目录拖拽排序
            self.section_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
            self.section_list.setDefaultDropAction(Qt.DropAction.MoveAction)
            self.section_list.model().rowsMoved.connect(self._on_toc_order_changed)
        else:
            # 退出编辑模式：保存并渲染，保留用户编辑的格式
            html = self.text_edit.toPlainText()
            self.text_edit.setAcceptRichText(True)
            self.text_edit.clear()
            self.text_edit.setReadOnly(True)
            self.text_edit.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self.edit_btn.setText("编辑")
            self.edit_btn.setStyleSheet("")
            self.insert_img_btn.setVisible(False)
            self.insert_link_btn.setVisible(False)
            self.cancel_edit_btn.setVisible(False)
            self.find_bar.setVisible(False)
            # 禁用目录拖拽，保存当前顺序
            self.section_list.setDragDropMode(QListWidget.DragDropMode.NoDragDrop)
            self._save_toc_order()
            if self._current_key:
                existing = self._content.get(self._current_key, {})
                name = existing.get("name", self._current_key) if isinstance(existing, dict) else self._current_key
                self._content[self._current_key] = {"name": name, "html": html}
                _save_manual_content(self._content)
                # 渲染：注入主题色后显示富文本，但保留用户原始格式供下次编辑
                self._raw_html = html
                self.text_edit.setHtml(self._prepare_display_html(html))

    def _cancel_edit(self):
        """放弃更改，直接退出编辑模式（含目录排序/样式等所有修改）"""
        saved_row = self.section_list.currentRow()  # 记录当前选中行
        self._editing = False
        # 恢复进入编辑前的快照
        if self._content_snapshot is not None:
            self._content = self._content_snapshot
            self._content_snapshot = None
            # 重建目录列表
            _toc_order = self._content.get("_toc_order", [])
            _known = list(_toc_order)
            for k, v in self._content.items():
                if k.startswith("_") or k in _known:
                    continue
                _known.append(k)
            self.section_list.clear()
            self._section_keys = []
            for key in _known:
                if key.startswith("_") or key not in self._content:
                    continue
                val = self._content[key]
                name = val.get("name", key) if isinstance(val, dict) else key
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, key)
                styles = (self._content.get("_toc_styles") or {}).get(key, {})
                if styles:
                    item.setFont(self._build_toc_font(styles, QFont()))
                    if styles.get("color"):
                        item.setForeground(QColor(styles["color"]))
                self.section_list.addItem(item)
                self._section_keys.append(key)
        self.section_list.setDragDropMode(QListWidget.DragDropMode.NoDragDrop)
        self.text_edit.setReadOnly(True)
        self.edit_btn.setText("编辑")
        self.edit_btn.setStyleSheet("")
        self.insert_img_btn.setVisible(False)
        self.insert_link_btn.setVisible(False)
        self.cancel_edit_btn.setVisible(False)
        self.find_bar.setVisible(False)
        # 恢复到保存前的 HTML 渲染视图（重建后恢复选中行）
        if saved_row >= 0 and saved_row < self.section_list.count():
            self.section_list.setCurrentRow(saved_row)
        elif self.section_list.count() > 0:
            self.section_list.setCurrentRow(0)

    # —— 目录编辑（右键菜单） ——

    def _on_toc_context_menu(self, pos):
        if not self._editing:
            return
        item = self.section_list.itemAt(pos)
        menu = QMenu(self)

        add_action = menu.addAction("＋ 新增章节")
        menu.addSeparator()

        rename_action = None
        redirect_action = None
        delete_action = None
        if item is not None:
            rename_action = menu.addAction("✎ 重命名")
            redirect_action = menu.addAction("⇄ 编辑重定向键")
            style_action = menu.addAction("🎨 样式")
            menu.addSeparator()
            delete_action = menu.addAction("✕ 删除章节")

        chosen = menu.exec(self.section_list.viewport().mapToGlobal(pos))

        if chosen == add_action:
            self._toc_add_section()
        elif item is not None:
            row = self.section_list.row(item)
            if chosen == rename_action:
                self._toc_rename_section(row)
            elif chosen == redirect_action:
                self._toc_edit_redirect(row)
            elif chosen == style_action:
                self._toc_style_section(row)
            elif chosen == delete_action:
                self._toc_delete_section(row)

    def _toc_add_section(self):
        name, ok = QInputDialog.getText(self, "新增章节", "请输入章节名称：")
        if not ok or not name.strip():
            return
        name = name.strip()
        # 根据名称生成拼音风格的 key
        import re
        key = re.sub(r'[^a-zA-Z0-9_一-鿿]', '_', name).strip('_').lower()
        if not key:
            key = f"section_{len(self._section_keys) + 1}"
        # 若 key 已存在则追加数字
        base_key = key
        n = 1
        while key in self._content:
            key = f"{base_key}_{n}"
            n += 1
        self._content[key] = {"name": name, "html": f"<h2>{name}</h2><p></p>"}
        _save_manual_content(self._content)
        # 刷新目录
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, key)
        self.section_list.addItem(item)
        self._section_keys.append(key)
        self.section_list.setCurrentRow(len(self._section_keys) - 1)

    def _toc_rename_section(self, row):
        key = self._section_keys[row]
        info = self._content.get(key, {})
        old_name = info.get("name", key) if isinstance(info, dict) else key
        new_name, ok = QInputDialog.getText(self, "重命名章节", "请输入新名称：", text=old_name)
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        existing = self._content.get(key, {})
        if isinstance(existing, dict):
            existing["name"] = new_name
        else:
            self._content[key] = {"name": new_name, "html": existing if isinstance(existing, str) else ""}
        _save_manual_content(self._content)
        self.section_list.item(row).setText(new_name)
        self.section_title.setText(new_name)

    def _toc_edit_redirect(self, row):
        key = self._section_keys[row]
        nav_map = self._content.get("_nav_mapping", {})
        # 找到所有指向当前 key 的 nav keys
        current_keys = [nk for nk, mk in nav_map.items() if mk == key]
        current_text = ", ".join(current_keys) if current_keys else ""

        dialog = QDialog(self)
        dialog.setWindowTitle(f"编辑重定向键 — {key}")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(f"所有在计算器中点击「{key}」对应页面时，\n将跳转到本手册章节。"))
        layout.addWidget(QLabel("请输入导航键（多个用逗号或空格分隔）："))

        text_edit = QLineEdit(current_text)
        text_edit.setPlaceholderText("例如: data_source, echo_counter")
        layout.addWidget(text_edit)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        ok_btn.setObjectName("backButton")
        cancel_btn.setObjectName("backButton")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # 解析输入
        new_text = text_edit.text().strip()
        new_keys = [k.strip() for k in re.split(r'[,，\s]+', new_text) if k.strip()]

        # 移除旧的映射
        for nk in current_keys:
            nav_map.pop(nk, None)
        # 添加新的映射
        for nk in new_keys:
            nav_map[nk] = key

        self._content["_nav_mapping"] = nav_map
        _save_manual_content(self._content)

    @staticmethod
    def _build_toc_font(styles, base_font):
        """根据样式字典构建 QFont"""
        font = QFont(base_font)
        if styles.get("bold"):
            font.setBold(True)
        if styles.get("italic"):
            font.setItalic(True)
        if styles.get("size"):
            font.setPointSize(int(styles["size"]))
        return font

    def _toc_style_section(self, row):
        """弹出样式设置对话框"""
        key = self._section_keys[row]
        styles = (self._content.get("_toc_styles") or {}).get(key, {})
        # 简易样式选择
        menu = QMenu(self)
        bold_a = menu.addAction("粗体" if not styles.get("bold") else "✓ 粗体")
        italic_a = menu.addAction("斜体" if not styles.get("italic") else "✓ 斜体")
        menu.addSeparator()
        color_menu = menu.addMenu("文字颜色")
        colors = {
                "经典蓝": "#3B82F6",
                "冰川蓝": "#60A5FA",
                "湖蓝色": "#06B6D4",
                "青玉色": "#2DD4BF",

                "星云紫": "#8B5CF6",
                "淡紫色": "#A78BFA",

                "石板灰": "#64748B",
                "琥珀金": "#F59E0B",

                "默认": "",
        }
        color_actions = {}
        for name, code in colors.items():
            prefix = "✓ " if styles.get("color") == code else ""
            color_actions[name] = color_menu.addAction(f"{prefix}{name}")
        menu.addSeparator()
        clear_a = menu.addAction("清除样式")

        chosen = menu.exec(self.section_list.viewport().mapToGlobal(
            self.section_list.visualItemRect(self.section_list.item(row)).center()))

        all_styles = self._content.get("_toc_styles") or {}
        cur = all_styles.get(key, {})
        changed = False
        if chosen == bold_a:
            cur["bold"] = not cur.get("bold", False)
            changed = True
        elif chosen == italic_a:
            cur["italic"] = not cur.get("italic", False)
            changed = True
        elif chosen == clear_a:
            if key in all_styles:
                del all_styles[key]
                self._content["_toc_styles"] = all_styles
                cur = {}
                changed = True
        else:
            for name, ca in color_actions.items():
                if chosen == ca:
                    code = colors[name]
                    if code:
                        cur["color"] = code
                    elif "color" in cur:
                        del cur["color"]
                    changed = True
                    break
        if changed and cur:
            all_styles[key] = cur
            self._content["_toc_styles"] = all_styles
        if changed:
            _save_manual_content(self._content)
            # 重新渲染该项
            item = self.section_list.item(row)
            item.setFont(self._build_toc_font(cur, QFont()))
            if cur.get("color"):
                item.setForeground(QColor(cur["color"]))
            else:
                item.setForeground(QColor(self._section_color))

    def _on_toc_order_changed(self, parent, start, end, dest, row):
        """拖拽排序后更新 _section_keys 列表"""
        # 根据 QListWidget 当前顺序重建 _section_keys
        new_keys = []
        for i in range(self.section_list.count()):
            item = self.section_list.item(i)
            if item:
                key = item.data(Qt.ItemDataRole.UserRole)
                if key:
                    new_keys.append(key)
        if new_keys:
            self._section_keys = new_keys

    def _save_toc_order(self):
        """将当前目录顺序保存到 content"""
        self._content["_toc_order"] = list(self._section_keys)
        _save_manual_content(self._content)

    def _toc_delete_section(self, row):
        key = self._section_keys[row]
        info = self._content.get(key, {})
        name = info.get("name", key) if isinstance(info, dict) else key
        reply = QMessageBox.question(
            self, "删除章节",
            f"确定要删除章节「{name}」吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._content.pop(key, None)
        _save_manual_content(self._content)
        self._section_keys.pop(row)
        self.section_list.takeItem(row)
        # 切换到第一个
        if self._section_keys:
            self.section_list.setCurrentRow(0)

    # —— 查找/替换 ——

    def _collect_matches(self, text):
        """收集所有匹配位置（selection end position），返回列表和文档。"""
        positions = []
        doc = self.text_edit.document()
        tc = QTextCursor(doc)
        tc.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(10000):  # 安全上限
            tc = doc.find(text, tc)
            if tc.isNull():
                break
            positions.append(tc.position())
        return positions

    def _find_text(self, forward=True):
        """执行查找，返回是否找到。forward=True 为向下，False 为向上。"""
        text = self.find_input.text()
        if not text:
            self.find_status.setText("")
            return False

        if forward:
            found = self.text_edit.find(text)
        else:
            found = self.text_edit.find(text, QTextDocument.FindFlag.FindBackward)

        if found:
            cur_pos = self.text_edit.textCursor().position()
            # 高亮
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(255, 255, 0, 80))
            highlight = QTextEdit.ExtraSelection()
            highlight.format = fmt
            highlight.cursor = self.text_edit.textCursor()
            self.text_edit.setExtraSelections([highlight])
            # 计算 nth / total
            positions = self._collect_matches(text)
            total = len(positions)
            nth = 1
            for i, pos in enumerate(positions):
                if pos == cur_pos:
                    nth = i + 1
                    break
            self.find_status.setText(f"{nth}/{total}" if total > 0 else "1/?")
        else:
            self.text_edit.setExtraSelections([])
            positions = self._collect_matches(text)
            total = len(positions)
            self.find_status.setText("已搜索完毕" if total > 0 else "无匹配")
        return found

    def _find_next(self):
        if not self._editing:
            return
        if not self._find_text(forward=True):
            self.text_edit.setExtraSelections([])

    def _find_prev(self):
        if not self._editing:
            return
        if not self._find_text(forward=False):
            self.text_edit.setExtraSelections([])

    def _on_find_text_changed(self):
        if not self.find_input.text():
            self.text_edit.setExtraSelections([])
            self.find_status.setText("")

    def _replace_one(self):
        text = self.find_input.text()
        if not text:
            return
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == text:
            cursor.insertText(self.replace_input.text())
        self._find_next()

    def _replace_all(self):
        text = self.find_input.text()
        replacement = self.replace_input.text()
        if not text or text == replacement:
            return
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.text_edit.setTextCursor(cursor)
        count = 0
        while self.text_edit.find(text):
            cursor = self.text_edit.textCursor()
            cursor.insertText(replacement)
            count += 1
        self.text_edit.setExtraSelections([])
        self.find_status.setText("")
        QMessageBox.information(self, "替换完成", f"共替换 {count} 处。")

    def _insert_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"
        )
        if not file_path:
            return
        dest_name = os.path.basename(file_path)
        dest_path = os.path.join(MANUAL_IMAGES_DIR, dest_name)
        try:
            with open(file_path, "rb") as src:
                img_data = src.read()
            with open(dest_path, "wb") as dst:
                dst.write(img_data)
        except OSError:
            return

        width, ok_w = QInputDialog.getInt(
            self, "图片宽度", "显示宽度（像素，0 = 原始）:",
            400, 0, 9999, 1
        )
        if not ok_w:
            return

        styles = ["原始", "左浮动（文绕图）", "右浮动（文绕图）", "居中"]
        style_css = {
            "原始": "",
            "左浮动（文绕图）": "float:left;margin:0 12px 8px 0;",
            "右浮动（文绕图）": "float:right;margin:0 0 8px 12px;",
            "居中": "",
        }
        choice, ok_s = QInputDialog.getItem(
            self, "图片样式", "选择布局:", styles, 0, False
        )
        if not ok_s:
            return

        radius, ok_r = QInputDialog.getInt(
            self, "圆角", "圆角半径（像素，0 = 直角）:",
            0, 0, 200, 1
        )
        if not ok_r:
            return

        # 圆角处理：先用纯色画圆角矩形作为蒙版，再用 SourceIn 合成原图
        if radius > 0:
            img = QImage(dest_path)
            if not img.isNull():
                if img.format() != QImage.Format.Format_ARGB32:
                    img.convertTo(QImage.Format.Format_ARGB32)
                result = QImage(img.size(), QImage.Format.Format_ARGB32)
                result.fill(Qt.GlobalColor.transparent)

                p = QPainter(result)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

                path = QPainterPath()
                path.addRoundedRect(0, 0, img.width(), img.height(), radius, radius)
                p.fillPath(path, QColor(255, 255, 255, 255))

                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                p.drawImage(0, 0, img)
                p.end()

                result.save(dest_path, "PNG")

        css_parts = []
        base_css = style_css.get(choice, "")
        if base_css:
            css_parts.append(base_css)

        parts = [f'src="manual/images/{dest_name}"', f'alt="{dest_name}"']
        if width > 0:
            parts.append(f'width="{width}"')
        if css_parts:
            parts.append(f'style="{" ".join(css_parts)}"')

        img_tag = f'<img {" ".join(parts)}>'
        if choice == "居中":
            img_tag = f'<p align="center">{img_tag}</p>'

        cursor = self.text_edit.textCursor()
        cursor.insertText(img_tag)
        self.text_edit.setTextCursor(cursor)

    def _insert_link(self):
        """弹出对话框输入 URL 和显示文本, 在光标处插入超链接."""
        url, ok1 = QInputDialog.getText(self, "插入链接", "请输入 URL:")
        if not ok1 or not url.strip():
            return
        text, ok2 = QInputDialog.getText(self, "插入链接", "请输入显示文本:", text=url.strip())
        if not ok2:
            text = url.strip()
        if not text.strip():
            text = url.strip()
        cursor = self.text_edit.textCursor()
        cursor.insertText(f'<a href="{url.strip()}">{text.strip()}</a>')
        self.text_edit.setTextCursor(cursor)


# ==================== 主界面 ====================

class MainScreen(QWidget):
    """主界面. 左侧导航树 + 右侧页面栈 + 顶部工具栏. 管理全部跨页回调."""
    def __init__(self, on_back):
        super().__init__()
        self.setObjectName("MainScreen")
        self.on_back = on_back
        self.echo_pages = {}
        self._base_override_enabled = False
        self._base_override_value = 0.0
        self._base_override_dialog = None
        self._build_ui()

    def _is_light_theme(self):
        """判断当前是否为亮色主题"""
        try:
            w = self.window()
            if w and hasattr(w, 'current_theme'):
                return w.current_theme == "light"
        except Exception:
            pass
        return False

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        nav_top = QWidget()
        nav_top_layout = QVBoxLayout(nav_top)
        nav_top_layout.setContentsMargins(16, 16, 16, 8)

        nav_title = QLabel("鸣潮计算器")
        nav_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        nav_top_layout.addWidget(nav_title)

        back_btn = QPushButton("返回")
        back_btn.setObjectName("backButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.on_back)
        nav_top_layout.addWidget(back_btn)

        self.base_adj_btn = QPushButton("基础数值调整")
        self.base_adj_btn.setObjectName("backButton")
        self.base_adj_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.base_adj_btn.clicked.connect(self._open_base_override)
        nav_top_layout.addWidget(self.base_adj_btn)

        manual_btn = QPushButton("使用手册")
        manual_btn.setObjectName("backButton")
        manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manual_btn.clicked.connect(self._open_manual)
        nav_top_layout.addWidget(manual_btn)

        self.error_log_btn = QPushButton("错误日志")
        self.error_log_btn.setObjectName("backButton")
        self.error_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.error_log_btn.clicked.connect(self._open_error_log)
        nav_top_layout.addWidget(self.error_log_btn)
        self._update_error_log_btn()

        self.data_flow_btn = QPushButton("数据流")
        self.data_flow_btn.setObjectName("backButton")
        self.data_flow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.data_flow_btn.clicked.connect(self._open_data_flow_viewer)
        nav_top_layout.addWidget(self.data_flow_btn)

        # 注册新错误回调：滚动侧边栏到错误日志按钮 + 颜色闪烁
        _set_new_error_callback(lambda: self._on_new_error())
        self._error_flash_anim = None

        nav_top_layout.addSpacing(4)

        # 把按钮区包在固定高度的 QScrollArea 里，按钮再多也不挤占导航树空间
        self._nav_scroll = QScrollArea()
        self._nav_scroll.setWidgetResizable(True)
        self._nav_scroll.setFixedHeight(190)
        self._nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._nav_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._nav_scroll.setWidget(nav_top)
        sidebar_layout.addWidget(self._nav_scroll)

        # 分割线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame { color: rgba(128,128,128,0.25); margin: 0 12px; }")
        sidebar_layout.addWidget(sep)

        self.nav_tree = NavTree()
        self.nav_tree.setObjectName("navTree")
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setIndentation(0)

        def _add_parent(text, key, children):
            item = QTreeWidgetItem([f"▼ {text}"])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, text)
            for child_text, child_key in children:
                child = QTreeWidgetItem([child_text])
                child.setData(0, Qt.ItemDataRole.UserRole, child_key)
                item.addChild(child)
            self.nav_tree.addTopLevelItem(item)
            return item

        section_font = QFont()
        section_font.setBold(True)

        def _apply_section_color(item, fg_color, bg_color):
            """递归给 item 及其所有子项设置前景色和背景色"""
            item.setData(0, Qt.ItemDataRole.ForegroundRole, QBrush(fg_color))
            item.setData(0, Qt.ItemDataRole.BackgroundRole, QBrush(bg_color))
            item.setData(0, Qt.ItemDataRole.FontRole, section_font)
            for i in range(item.childCount()):
                _apply_section_color(item.child(i), fg_color, bg_color)

        # ---- 区域一：角色与武器 ----
        is_light = self._is_light_theme()
        if is_light:
            sec1_fg = QColor(210, 105, 0)        # 深橙色（亮色主题）
            sec1_bg = QColor(255, 152, 0, 25)
            child_fg1 = QColor(180, 90, 0)       # 暗橙色（亮色主题子级）
        else:
            sec1_fg = QColor(255, 152, 0)        # 琥珀色（暗色主题）
            sec1_bg = QColor(255, 152, 0, 40)
            child_fg1 = QColor(255, 183, 77)     # 淡橙色（暗色主题子级）
        item1 = QTreeWidgetItem(["▼ 角色与武器"])
        item1.setData(0, Qt.ItemDataRole.UserRole, "char_base")
        item1.setData(0, Qt.ItemDataRole.UserRole + 1, "角色与武器")
        _apply_section_color(item1, sec1_fg, sec1_bg)
        self.nav_tree.addTopLevelItem(item1)

        char_child1 = QTreeWidgetItem(["    角色基础"])
        char_child1.setData(0, Qt.ItemDataRole.UserRole, "char_base")
        item1.addChild(char_child1)

        resonance_buff_child = QTreeWidgetItem(["    共鸣链增益"])
        resonance_buff_child.setData(0, Qt.ItemDataRole.UserRole, "resonance_buff")
        item1.addChild(resonance_buff_child)

        for ch in [char_child1, resonance_buff_child]:
            ch.setData(0, Qt.ItemDataRole.ForegroundRole, QBrush(child_fg1))
            ch.setData(0, Qt.ItemDataRole.FontRole, section_font)
        item1.setExpanded(True)

        # ---- 区域二：数值来源 ----
        sec2_fg = QColor(25, 118, 210)       # 蓝色
        sec2_bg = QColor(33, 150, 243, 40)
        source_item = QTreeWidgetItem(["▼ 数值来源"])
        source_item.setData(0, Qt.ItemDataRole.UserRole, "data_source")
        source_item.setData(0, Qt.ItemDataRole.UserRole + 1, "数值来源")
        self.nav_tree.addTopLevelItem(source_item)

        def _add_sub_parent(parent_item, text, key, children, expanded=True):
            sub = QTreeWidgetItem([f"▼ {text}" if expanded else f"▶ {text}"])
            sub.setData(0, Qt.ItemDataRole.UserRole, key)
            sub.setData(0, Qt.ItemDataRole.UserRole + 1, text)
            for child_text, child_key in children:
                child = QTreeWidgetItem([child_text])
                child.setData(0, Qt.ItemDataRole.UserRole, child_key)
                sub.addChild(child)
            parent_item.addChild(sub)
            sub.setExpanded(expanded)
            return sub

        # 声骸数值（第一位）
        self.nav_echo_parent = _add_sub_parent(source_item, "声骸数值", "echo_counter", [
            ("    声骸计数", "echo_counter"),
        ])

        # 综合填写（大目录：含综合常驻/综合触发）
        combined_parent = QTreeWidgetItem(["▼ 综合填写"])
        combined_parent.setData(0, Qt.ItemDataRole.UserRole, "combined_perm")
        combined_parent.setData(0, Qt.ItemDataRole.UserRole + 1, "综合填写")
        source_item.addChild(combined_parent)
        combined_parent.setExpanded(True)

        for ct, ck in [("    综合常驻数值", "combined_perm"), ("    综合触发数值", "combined_trigger"),
                       ("    关键词关联", "keyword_assoc")]:
            child = QTreeWidgetItem([ct])
            child.setData(0, Qt.ItemDataRole.UserRole, ck)
            combined_parent.addChild(child)

        _apply_section_color(source_item, sec2_fg, sec2_bg)
        sub_fg = QColor(66, 165, 245)
        sub_child_fg = QColor(144, 202, 249)
        for sub in [self.nav_echo_parent, combined_parent]:
            sub.setData(0, Qt.ItemDataRole.ForegroundRole, QBrush(sub_fg))
            for i in range(sub.childCount()):
                sub.child(i).setData(0, Qt.ItemDataRole.ForegroundRole, QBrush(sub_child_fg))
        source_item.setExpanded(True)

        # ---- 区域三：数值总结 ----
        sec3_fg = QColor(56, 142, 60)        # 绿色
        sec3_bg = QColor(76, 175, 80, 40)
        summary_item = QTreeWidgetItem(["▼ 数值总结"])
        summary_item.setData(0, Qt.ItemDataRole.UserRole, "summary_base")
        summary_item.setData(0, Qt.ItemDataRole.UserRole + 1, "数值总结")
        self.nav_tree.addTopLevelItem(summary_item)

        summary_children = []
        for child_text, child_key in [
            ("    基础乘区", "summary_base"),
            ("    加成乘区", "summary_bonus"),
            ("    加深乘区", "summary_deepen"),
            ("    暴击乘区", "summary_crit"),
            ("    独立乘区", "summary_indep"),
        ]:
            child = QTreeWidgetItem([child_text])
            child.setData(0, Qt.ItemDataRole.UserRole, child_key)
            summary_item.addChild(child)
            summary_children.append(child)

        _apply_section_color(summary_item, sec3_fg, sec3_bg)
        child_fg3 = QColor(129, 199, 132)
        for ch in summary_children:
            ch.setData(0, Qt.ItemDataRole.ForegroundRole, QBrush(child_fg3))
        summary_item.setExpanded(True)

        # ---- 区域四：敌人减伤 ----
        sec4_fg = QColor(0, 131, 143)        # 青蓝色
        sec4_bg = QColor(0, 188, 212, 40)
        enemy_item = QTreeWidgetItem(["▼ 敌人减伤"])
        enemy_item.setData(0, Qt.ItemDataRole.UserRole, "enemy_defense")
        enemy_item.setData(0, Qt.ItemDataRole.UserRole + 1, "敌人减伤")
        self.nav_tree.addTopLevelItem(enemy_item)

        enemy_child1 = QTreeWidgetItem(["    防御减伤"])
        enemy_child1.setData(0, Qt.ItemDataRole.UserRole, "enemy_defense")
        enemy_item.addChild(enemy_child1)

        enemy_child2 = QTreeWidgetItem(["    抗性数值"])
        enemy_child2.setData(0, Qt.ItemDataRole.UserRole, "enemy_resistance")
        enemy_item.addChild(enemy_child2)

        _apply_section_color(enemy_item, sec4_fg, sec4_bg)
        child_fg4 = QColor(77, 208, 225)
        for ch in [enemy_child1, enemy_child2]:
            ch.setData(0, Qt.ItemDataRole.ForegroundRole, QBrush(child_fg4))
        enemy_item.setExpanded(True)

        # ---- 区域五：计算结果 ----
        sec5_fg = QColor(123, 31, 162)       # 紫色
        sec5_bg = QColor(156, 39, 176, 40)
        calc_item = QTreeWidgetItem(["▼ 计算结果"])
        calc_item.setData(0, Qt.ItemDataRole.UserRole, "result")
        calc_item.setData(0, Qt.ItemDataRole.UserRole + 1, "计算结果")
        self.nav_tree.addTopLevelItem(calc_item)

        result_child = QTreeWidgetItem(["    计算结果"])
        result_child.setData(0, Qt.ItemDataRole.UserRole, "result")
        calc_item.addChild(result_child)

        result_list_child = QTreeWidgetItem(["    结果列表"])
        result_list_child.setData(0, Qt.ItemDataRole.UserRole, "result_list")
        calc_item.addChild(result_list_child)

        _apply_section_color(calc_item, sec5_fg, sec5_bg)
        child_fg5 = QColor(206, 147, 216)
        for ch in [result_child, result_list_child]:
            ch.setData(0, Qt.ItemDataRole.ForegroundRole, QBrush(child_fg5))
        calc_item.setExpanded(True)

        self.nav_tree.itemExpanded.connect(self._on_nav_expand_collapse)
        self.nav_tree.itemCollapsed.connect(self._on_nav_expand_collapse)
        self.nav_tree.currentItemChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self.nav_tree, stretch=1)

        main_layout.addWidget(sidebar)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentArea")

        def _wrap(page):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return scroll

        self.page_char_base = CharBasePage()
        # 综合填写页（替代原来的八个独立来源页面）
        self.page_combined_perm = CombinedEntryPage("综合常驻数值")
        self.page_combined_perm.page_key = "combined_perm"
        self.page_combined_perm._navigate_summary = self._navigate_to_key
        self.page_combined_trigger = CombinedEntryPage("综合触发数值")
        self.page_combined_trigger.page_key = "combined_trigger"
        self.page_combined_trigger._navigate_summary = self._navigate_to_key

        self.page_enemy_defense = EnemyDefensePage()
        self.page_enemy_resistance = EnemyResistancePage()

        self.page_echo_counter = EchoCounterPage()
        def _echo_change_cb():
            self.page_enemy_defense.recalc()
            self.page_enemy_resistance._recalc()
            for sp in [self.page_summary_base, self.page_summary_bonus,
                       self.page_summary_deepen, self.page_summary_crit]:
                sp.recalc()
            self.page_result.auto_compute()
            self.page_result_list.recalc()

        self.page_echo_counter.set_callbacks(self._add_echo, self._remove_echo,
                                              change_cb=_echo_change_cb)
        self.page_echo_counter.set_ocr_callback(self._fill_echo_from_ocr)
        self.page_echo_counter.set_ocr_loading_callbacks(
            lambda text="": self._ocr_overlay.show_overlay(text),
            lambda: self._ocr_overlay.hide_overlay(),
            lambda text: self._ocr_overlay.set_progress(text)
        )

        self.page_summary_base = SummaryBaseZonePage()
        self.page_summary_bonus = SummaryBonusZonePage()
        self.page_summary_deepen = SummaryDeepenZonePage()
        self.page_summary_crit = SummaryCritZonePage()
        self.page_indep_zone = IndepZonePage()

        # 给 CombinedEntryPage 和 EchoPage 注入总结页引用（供"查看总结"跳转使用）
        _sp = {
            "summary_base": self.page_summary_base,
            "summary_bonus": self.page_summary_bonus,
            "summary_deepen": self.page_summary_deepen,
            "summary_crit": self.page_summary_crit,
            "enemy_defense": self.page_enemy_defense,
            "enemy_resistance": self.page_enemy_resistance,
        }
        self.page_combined_perm._summary_pages = _sp
        self.page_combined_trigger._summary_pages = _sp
        # 已创建的 EchoPage 在 _add_echo/_create_echo_page 中单独注入
        self.page_result = ResultPage()
        self.page_result_list = ResultListPage()

        # 共鸣链增益页面
        self.page_resonance_buff = ResonanceBuffPage(main_screen=self)

        # 关键词关联页面
        self.page_keyword_assoc = KeywordAssociationPage()

        # 所有页面包裹 QScrollArea（内容超出时滚动）
        self._scrolls = {
            "char_base":          _wrap(self.page_char_base),
            "combined_perm":      _wrap(self.page_combined_perm),
            "combined_trigger":   _wrap(self.page_combined_trigger),
            "enemy_defense":      _wrap(self.page_enemy_defense),
            "enemy_resistance":   _wrap(self.page_enemy_resistance),
            "echo_counter":       _wrap(self.page_echo_counter),
            "summary_base":       _wrap(self.page_summary_base),
            "summary_bonus":      _wrap(self.page_summary_bonus),
            "summary_deepen":     _wrap(self.page_summary_deepen),
            "summary_crit":       _wrap(self.page_summary_crit),
            "summary_indep":      _wrap(self.page_indep_zone),
            "result":             _wrap(self.page_result),
            "result_list":        _wrap(self.page_result_list),
            "resonance_buff":     _wrap(self.page_resonance_buff),
            "keyword_assoc":      _wrap(self.page_keyword_assoc),
        }
        for scroll in self._scrolls.values():
            self.content_stack.addWidget(scroll)

        main_layout.addWidget(self.content_stack, stretch=1)

        # 关联外部来源页面的减防属性到防御减伤页
        defense_source_pages = [
            ("综合常驻数值", self.page_combined_perm, "combined_perm", "常驻"),
            ("综合触发数值", self.page_combined_trigger, "combined_trigger", "触发"),
        ]
        self.page_enemy_defense.set_external_sources(defense_source_pages)
        self.page_enemy_defense.navigate_requested = self._navigate_to_key

        # 关联外部来源页面的抗性属性到抗性数值页
        resistance_source_pages = [
            ("综合常驻数值", self.page_combined_perm, "combined_perm", "常驻"),
            ("综合触发数值", self.page_combined_trigger, "combined_trigger", "触发"),
        ]
        self.page_enemy_resistance.set_external_sources(resistance_source_pages)
        self.page_enemy_resistance.navigate_requested = self._navigate_to_key

        # 每个来源页变更时同时刷新防御/抗性/四个总结页 + 计算结果 + 结果列表
        all_source_pages = set()
        for _, page, _, _ in defense_source_pages + resistance_source_pages:
            all_source_pages.add(page)

        _summary_pages = [self.page_summary_base, self.page_summary_bonus,
                          self.page_summary_deepen, self.page_summary_crit]

        def _make_source_cb(de, er, rp, rl, sps):
            def _cb():
                de.recalc()
                er._recalc()
                for sp in sps:
                    sp.recalc()
                rp.compute()
                rl.recalc()
            return _cb

        for page in all_source_pages:
            page._on_change_cb = _make_source_cb(
                self.page_enemy_defense, self.page_enemy_resistance,
                self.page_result, self.page_result_list, _summary_pages)

        # —— 角色基础页变更 ——
        def _make_char_cb(rp, rl, sps):
            def _cb():
                for sp in sps:
                    sp.recalc()
                rp.compute()
                rl.recalc()
            return _cb
        self.page_char_base._on_change_cb = _make_char_cb(
            self.page_result, self.page_result_list, _summary_pages)

        # CombinedEntryPage → 变更时触发全局重算
        combined_cb = _make_source_cb(
            self.page_enemy_defense, self.page_enemy_resistance,
            self.page_result, self.page_result_list, _summary_pages)
        self.page_combined_perm._on_change_cb = combined_cb
        self.page_combined_trigger._on_change_cb = combined_cb

        # 关键词关联页变更 → 触发完整计算链（因关键词匹配影响结果列表）
        self.page_keyword_assoc._on_change_cb = lambda: (
            [sp.recalc() for sp in _summary_pages],
            self.page_result._sync_mult_entries(),
            self.page_result.auto_compute(),
            self.page_result_list.recalc(),
        )

        # EnemyDefensePage / EnemyResistancePage 内部修改直接触发自动计算
        def _make_defense_resistance_cb():
            for sp in _summary_pages:
                sp.recalc()
            self.page_result.compute()
            self.page_result_list.recalc()
        self.page_enemy_defense._on_change_cb = _make_defense_resistance_cb
        self.page_enemy_resistance._on_change_cb = _make_defense_resistance_cb

        # 关联来源页到四个数值总结页（含CharBase页）
        summary_source_pages = [
            ("角色武器", self.page_char_base, "char_base"),
            ("综合常驻数值", self.page_combined_perm, "combined_perm"),
            ("综合触发数值", self.page_combined_trigger, "combined_trigger"),
        ]
        for sp in [self.page_summary_base, self.page_summary_bonus,
                    self.page_summary_deepen, self.page_summary_crit]:
            sp._navigate = self._navigate_to_key
            sp.set_external_sources(summary_source_pages)
            sp.set_echo_sources(self.echo_pages)

        # 关联来源页到计算结果页
        self.page_result.set_external_sources(summary_source_pages)
        self.page_result.set_echo_sources(self.echo_pages)
        self.page_result.set_defense_page(self.page_enemy_defense)
        self.page_result.set_resistance_page(self.page_enemy_resistance)
        self.page_result._navigate = self._navigate_to_key
        self.page_result._summary_pages = {
            "summary_base": self.page_summary_base,
            "summary_bonus": self.page_summary_bonus,
            "summary_deepen": self.page_summary_deepen,
            "summary_crit": self.page_summary_crit,
        }
        self.page_result.set_result_list_page(self.page_result_list)
        self.page_result.set_ocr_loading_callbacks(
            lambda text="": self._ocr_overlay.show_overlay(text),
            lambda: self._ocr_overlay.hide_overlay(),
            lambda text: self._ocr_overlay.set_progress(text)
        )

        # 关联来源页到结果列表页
        self.page_result.set_keyword_assoc_page(self.page_keyword_assoc)
        self.page_result_list.set_external_sources(summary_source_pages)
        self.page_result_list.set_keyword_assoc_page(self.page_keyword_assoc)
        self.page_result_list.set_echo_sources(self.echo_pages)
        self.page_result_list.set_defense_page(self.page_enemy_defense)
        self.page_result_list.set_resistance_page(self.page_enemy_resistance)
        self.page_result_list._navigate = self._navigate_to_key
        self.page_result_list.set_result_page(self.page_result)

        # 独立乘区页 → 计算结果页 + 结果列表页
        self.page_result.set_indep_zone_page(self.page_indep_zone)
        self.page_result_list.set_indep_zone_page(self.page_indep_zone)
        self.page_indep_zone._on_change_cb = lambda: (
            self.page_result.auto_compute(),
            self.page_result_list.recalc()
        )

        # OCR 加载遮罩
        self._ocr_overlay = LoadingOverlay(self)
        self._ocr_overlay.cancel_requested.connect(lambda: (
            self.page_echo_counter.abort_ocr(),
            self.page_result.abort_ocr()
        ))

    def _open_base_override(self):
        """打开基础数值调整弹窗"""
        # 获取当前计算出的 base_zone
        current_base = 0.0
        last = getattr(self.page_result, '_last_computed', None)
        if last and 'zones' in last:
            current_base = last['zones'].get('atk_zone', 0.0)

        # 复用已有弹窗或创建新的
        if self._base_override_dialog is None:
            self._base_override_dialog = BaseOverrideDialog(
                self, current_base,
                self._base_override_enabled,
                self._base_override_value
            )
            self._base_override_dialog.set_callback(self._on_base_override_changed)
        else:
            self._base_override_dialog.set_current_base(current_base)

        self._base_override_dialog.show()
        self._base_override_dialog.raise_()
        self._base_override_dialog.activateWindow()

    def _on_base_override_changed(self, enabled, value):
        """基础数值覆盖状态变更回调"""
        self._base_override_enabled = enabled
        self._base_override_value = value
        # 传播到计算结果页和结果列表页
        self.page_result.set_base_override(enabled, value)
        self.page_result_list.set_base_override(enabled, value)
        # 刷新按钮状态
        self.base_adj_btn.setText("基础数值调整 ✓" if enabled else "基础数值调整")
        self.base_adj_btn.setProperty("active", enabled)
        self.base_adj_btn.style().unpolish(self.base_adj_btn)
        self.base_adj_btn.style().polish(self.base_adj_btn)
        # 触发重算（结果列表使用 _update_all 强制重算，不受自动更新开关影响）
        self.page_result.auto_compute()
        self.page_result_list._update_all()

    def _on_new_error(self):
        """新错误触发：更新按钮 + 平滑滚动侧边栏按钮区到底部。"""
        self._update_error_log_btn()
        if hasattr(self, '_nav_scroll'):
            vbar = self._nav_scroll.verticalScrollBar()
            if vbar:
                anim = QPropertyAnimation(vbar, b"value")
                anim.setDuration(300)
                anim.setStartValue(vbar.value())
                anim.setEndValue(vbar.maximum())
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.start()

    def _open_error_log(self):
        # 已有一个窗口打开则提到最前，不重复创建
        if hasattr(self, '_error_log_dialog') and self._error_log_dialog is not None:
            try:
                self._error_log_dialog.raise_()
                self._error_log_dialog.activateWindow()
            except Exception:
                pass
            return
        self._error_log_dialog = ErrorReportDialog(self)
        self._error_log_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._error_log_dialog.destroyed.connect(self._on_error_log_closed)
        self._error_log_dialog.show()

    def _on_error_log_closed(self):
        self._error_log_dialog = None
        _new_error_count[0] = 0
        self.error_log_btn.setText("错误日志")
        self.error_log_btn.setStyleSheet("")
        self._update_error_log_btn()

    def _open_data_flow_viewer(self):
        dlg = DataFlowViewerDialog(self, parent=self)
        dlg.show()

    def _update_error_log_btn(self):
        """更新错误日志按钮：有未读错误时显示计数和红色。"""
        if not _log_entries or _new_error_count[0] <= 0:
            self.error_log_btn.setText("错误日志")
            self.error_log_btn.setStyleSheet("")
            return
        count = _new_error_count[0]
        self.error_log_btn.setText(f"错误日志 ({count})")
        self.error_log_btn.setStyleSheet(
            "QPushButton { color: #e94560; border-color: #e94560; font-weight: 600; }"
            "QPushButton:hover { background-color: rgba(233,69,96,0.15); }"
        )

    def _open_manual(self):
        # 已有一个窗口打开则提到最前
        if hasattr(self, '_manual_dialog') and self._manual_dialog is not None:
            try:
                self._manual_dialog.raise_()
                self._manual_dialog.activateWindow()
            except Exception:
                self._manual_dialog = None
            return
        self._manual_dialog = ManualDialog(self)
        self._manual_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._manual_dialog.destroyed.connect(lambda: setattr(self, '_manual_dialog', None))
        current = self.nav_tree.currentItem()
        if current:
            current_key = current.data(0, Qt.ItemDataRole.UserRole)
            nav_map = self._manual_dialog._content.get("_nav_mapping", {})
            manual_key = nav_map.get(current_key, current_key)
            for i in range(self._manual_dialog.section_list.count()):
                item = self._manual_dialog.section_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == manual_key:
                    self._manual_dialog.section_list.setCurrentRow(i)
                    break
        self._manual_dialog.show()

    def _on_nav_expand_collapse(self, item):
        base = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if base:
            arrow = "▼" if item.isExpanded() else "▶"
            item.setText(0, f"{arrow} {base}")

    def _navigate_to_key(self, nav_key, hl_name=None, hl_src=None, hl_seq=None):
        """根据导航键跳转到对应页面（递归搜索深层树）。
        如果提供了 hl_name/hl_seq，跳转后高亮对应行。"""
        def _find_recursive(item):
            if item.data(0, Qt.ItemDataRole.UserRole) == nav_key:
                return item
            for j in range(item.childCount()):
                found = _find_recursive(item.child(j))
                if found:
                    return found
            return None

        for i in range(self.nav_tree.topLevelItemCount()):
            target = _find_recursive(self.nav_tree.topLevelItem(i))
            if target:
                self.nav_tree.setCurrentItem(target)
                self._on_nav_changed(target, None)
                if hl_seq or hl_name:
                    QTimer.singleShot(200, lambda nk=nav_key, nm=hl_name, s=hl_src, sq=hl_seq:
                                      self._highlight_in_source(nk, nm, s, sq))
                return

    def _highlight_in_source(self, nav_key, name, src_label, seq_label=""):
        """在来源页中高亮匹配行（供总结页 '来源' 按钮使用）。
        seq_label 格式：{ei}号声骸{type}{num} 用于定位声骸词条。"""
        import re
        # 优先用序列号匹配声骸
        if seq_label:
            m = re.match(r'(\d+)号声骸(主词|固词|副词)(\d*)', seq_label)
            if m:
                ei = int(m.group(1))
                etype = m.group(2)
                si = int(m.group(3)) if m.group(3) else 0
                echo_items = list(self.echo_pages.items())
                if 1 <= ei <= len(echo_items):
                    _, scroll = echo_items[ei - 1]
                    ep = scroll.widget()
                    if etype in ("主词", "固词"):
                        ep._highlight_main_area()
                        return
                    elif etype == "副词" and si > 0 and si <= ep.sub_list.count():
                        item = ep.sub_list.item(si - 1)
                        w = ep.sub_list.itemWidget(item)
                        if w:
                            ep._highlight_sub_row(w)
                            return
        # CombinedEntryPage — 序列号匹配 + 整行黄色叠层
        for key in ["combined_perm", "combined_trigger"]:
            if key not in self._scrolls:
                continue
            scroll = self._scrolls[key]
            pw = scroll.widget()
            if not isinstance(pw, CombinedEntryPage):
                continue
            type_label = "常驻" if key == "combined_perm" else "触发"
            for r, rd in enumerate(pw._rows):
                for r in range(len(pw._rows)):
                    try:
                        row_data = pw.collect_data()[r]
                        row_seq = row_data[4] if len(row_data) > 4 else ""
                        if seq_label == row_seq:
                            pw._highlight_row(r, scroll)
                            return
                    except (IndexError, AttributeError):
                        continue
        # KeywordAssociationPage — 序列号匹配 + 平滑滚动 + 黄色叠层
        if nav_key == "keyword_assoc" and hasattr(self, 'page_keyword_assoc'):
            kw_page = self.page_keyword_assoc
            kw_scroll = self._scrolls.get("keyword_assoc")
            for r in range(kw_page._table.rowCount()):
                sl = kw_page._table.cellWidget(r, 2)
                if sl and hasattr(sl, 'text') and sl.text() == seq_label:
                    if kw_scroll:
                        QApplication.processEvents()
                        row_y = sum(kw_page._table.rowHeight(i) for i in range(r))
                        hdr_h = kw_page._table.horizontalHeader().height() if kw_page._table.horizontalHeader().isVisible() else 0
                        table_origin = kw_page._table.mapTo(kw_scroll.widget(), QPoint(0, 0))
                        target_y = table_origin.y() + hdr_h + row_y
                        vp_h = kw_scroll.viewport().height()
                        desired = max(0, target_y - vp_h // 5)
                        sb = kw_scroll.verticalScrollBar()
                        old_pos = sb.value()
                        if abs(desired - old_pos) < 2:
                            QTimer.singleShot(80, lambda: _place_highlight_overlay(
                                kw_page._table.viewport(), kw_page._table.visualRect(kw_page._table.model().index(r, 0))))
                            return
                        anim = QPropertyAnimation(sb, b"value")
                        anim.setDuration(450)
                        anim.setStartValue(old_pos)
                        anim.setEndValue(min(desired, sb.maximum()))
                        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                        anim.finished.connect(
                            lambda tb=kw_page._table, row=r:
                            QTimer.singleShot(80, lambda:
                                _place_highlight_overlay(tb.viewport(), tb.visualRect(tb.model().index(row, 0)))))
                        anim.start()
                    else:
                        QApplication.processEvents()
                        _place_highlight_overlay(kw_page._table.viewport(),
                            kw_page._table.visualRect(kw_page._table.model().index(r, 0)))
                    return

    def _on_nav_changed(self, current, _previous):
        if current is None:
            return

        key = current.data(0, Qt.ItemDataRole.UserRole)
        # 记录每个父分类下最后访问的子节点
        if not hasattr(self, '_last_child_key'):
            self._last_child_key = {}

        if key in self._scrolls:
            self.content_stack.setCurrentWidget(self._scrolls[key])
            # 更新父分类记忆
            p = current.parent()
            if p:
                base = p.data(0, Qt.ItemDataRole.UserRole) or p.data(0, Qt.ItemDataRole.UserRole + 1)
                if base:
                    self._last_child_key[base] = key
        elif key and key.startswith("echo_"):
            try:
                eid = int(key.split("_")[1])
                if eid in self.echo_pages:
                    self.content_stack.setCurrentWidget(self.echo_pages[eid])
                p = current.parent()
                if p:
                    base = p.data(0, Qt.ItemDataRole.UserRole) or p.data(0, Qt.ItemDataRole.UserRole + 1)
                    if base:
                        self._last_child_key[base] = key
            except (ValueError, IndexError):
                pass
        elif current.childCount() > 0:
            # 父节点：跳转到上次访问的子节点，否则第一个子节点
            base = key or current.data(0, Qt.ItemDataRole.UserRole + 1)
            remembered = self._last_child_key.get(base)
            if remembered:
                # 递归在子节点中查找匹配的 key
                def _find_child(item):
                    for i in range(item.childCount()):
                        c = item.child(i)
                        if c.data(0, Qt.ItemDataRole.UserRole) == remembered:
                            return c
                        if c.childCount() > 0:
                            found = _find_child(c)
                            if found: return found
                    return None
                target = _find_child(current)
                if target:
                    self.nav_tree.setCurrentItem(target)
                    return
            # 没有记忆：跳到第一个有 key 的子节点
            def _first_key(item):
                for i in range(item.childCount()):
                    c = item.child(i)
                    k = c.data(0, Qt.ItemDataRole.UserRole)
                    if k in self._scrolls or (k and k.startswith("echo_")):
                        return c
                    if c.childCount() > 0:
                        found = _first_key(c)
                        if found: return found
                return None
            target = _first_key(current)
            if target:
                self.nav_tree.setCurrentItem(target)

    def _add_echo(self, cost, echo_id):
        page = EchoPage(cost, echo_id)
        page._navigate_summary = self._navigate_to_key
        page._summary_pages = {
            "summary_base": self.page_summary_base,
            "summary_bonus": self.page_summary_bonus,
            "summary_deepen": self.page_summary_deepen,
            "summary_crit": self.page_summary_crit,
        }
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_stack.addWidget(scroll)
        self.echo_pages[echo_id] = scroll
        page._on_change_cb = self._refresh_echo_sources
        self._refresh_echo_sources()
        self._sort_echo_nav()

    def _fill_echo_from_ocr(self, echo_id, ocr_data):
        """根据 OCR 识别的结果填充 EchoPage 的词条和数值"""
        scroll = self.echo_pages.get(echo_id)
        if not scroll:
            return
        page = scroll.widget()

        # 填充主词条
        ms = ocr_data.get("main_stat", {})
        if ms and ms.get("name"):
            page.main_combo.setCurrentText(ms["name"])
            page.main_value.setValue(ms.get("value", 0.0))
            # 切换到百分比或固定值
            if ms.get("is_percent"):
                page.main_combo.setCurrentText(ms["name"])  # 触发 _on_main_stat_changed

        # 填充副词条
        for sub in ocr_data.get("sub_stats", []):
            if not sub.get("name"):
                continue
            page._add_sub_stat_direct(sub["name"], sub.get("value", 0.0))

        self._refresh_echo_sources()

    def _refresh_echo_sources(self):
        """通知所有消费者页面声骸数据已变更"""
        ep = self.echo_pages
        for sp in [self.page_summary_base, self.page_summary_bonus,
                    self.page_summary_deepen, self.page_summary_crit]:
            sp.set_echo_sources(ep)
        self.page_result.set_echo_sources(ep)
        self.page_result_list.set_echo_sources(ep)
        self.page_result.auto_compute()
        self.page_result_list.recalc()

    def _remove_echo(self, echo_id):
        if echo_id not in self.echo_pages:
            return

        page = self.echo_pages[echo_id]
        if self.content_stack.currentWidget() == page:
            self.content_stack.setCurrentWidget(self._scrolls["echo_counter"])

        idx = self.content_stack.indexOf(page)
        if idx >= 0:
            self.content_stack.removeWidget(page)
            page.deleteLater()

        del self.echo_pages[echo_id]
        self._refresh_echo_sources()
        self._sort_echo_nav()

    def _sort_echo_nav(self):
        self.nav_tree.blockSignals(True)

        while self.nav_echo_parent.childCount() > 0:
            self.nav_echo_parent.removeChild(self.nav_echo_parent.child(0))

        counter_item = QTreeWidgetItem(["    声骸计数"])
        counter_item.setData(0, Qt.ItemDataRole.UserRole, "echo_counter")
        self.nav_echo_parent.addChild(counter_item)

        for cost, eid in sorted(
            ((p.widget().cost, eid) for eid, p in self.echo_pages.items()),
            key=lambda x: (-x[0], x[1])
        ):
            item = QTreeWidgetItem([f"    {cost}费声骸"])
            item.setData(0, Qt.ItemDataRole.UserRole, f"echo_{eid}")
            self.nav_echo_parent.addChild(item)

        self.nav_echo_parent.setExpanded(True)
        self.nav_tree.blockSignals(False)
        self._on_nav_expand_collapse(self.nav_echo_parent)
        self.nav_tree.update()

    # —— 存档槽方法 ——

    def _quick_save(self):
        state = SaveManager.collect_full_state(self)
        default_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ok = QInputDialog.getText(self, "保存存档", "输入存档名称：", text=default_name)
        if not ok or not name:
            return
        name = name.strip()
        _INVALID_CHARS = r'\/:*?"<>|'
        _bad = [c for c in name if c in _INVALID_CHARS]
        if _bad:
            QMessageBox.warning(self, "名称无效",
                f"存档名称不能包含以下字符：\n{' '.join(sorted(set(_bad)))}\n\n请修改后重试。")
            return
        if not name:
            QMessageBox.warning(self, "名称无效", "存档名称不能为空。")
            return
        SaveManager.ensure_save_dir()
        filepath = os.path.join(SAVE_DIR, f"{name}.json")
        SaveManager.save_to_file(state, filepath)
        QMessageBox.information(self, "保存成功", f"存档已保存到:\n{filepath}")

    def _quick_load(self):
        saves = SaveManager.list_saves()
        if not saves:
            QMessageBox.information(self, "无存档", "save 文件夹中没有存档文件。")
            return
        reply = QMessageBox.question(
            self, "加载存档", "未保存的更改将丢失，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        dlg = QuickLoadDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            state, err = SaveManager.load_from_file(dlg.selected_path)
            if err:
                QMessageBox.warning(self, "加载失败", err)
                return
            SaveManager.apply_state(self, state)

    def _import_save(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入存档", SAVE_DIR, "JSON Files (*.json);;All Files (*.*)"
        )
        if not path:
            return
        reply = QMessageBox.question(
            self, "导入存档", "未保存的更改将丢失，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        state, err = SaveManager.load_from_file(path)
        if err:
            QMessageBox.warning(self, "加载失败", err)
            return
        SaveManager.apply_state(self, state)

    def _export_save(self):
        state = SaveManager.collect_full_state(self)
        path, _ = QFileDialog.getSaveFileName(
            self, "导出存档", os.path.join(SAVE_DIR, "build.json"), "JSON Files (*.json);;All Files (*.*)"
        )
        if not path:
            return
        SaveManager.save_to_file(state, path)
        QMessageBox.information(self, "导出成功", f"存档已导出到:\n{path}")

    def activate_auto_all(self):
        """开启自动更新（由全局自动按钮调用）"""
        if hasattr(self, 'page_result_list') and not self.page_result_list._auto_update:
            self.page_result_list._toggle_auto_update()
        if hasattr(self, 'page_result') and not self.page_result._auto_compute:
            self.page_result._toggle_auto_compute()

    def deactivate_auto_all(self):
        """关闭自动更新（由全局自动按钮调用）"""
        if hasattr(self, 'page_result_list') and self.page_result_list._auto_update:
            self.page_result_list._toggle_auto_update()
        if hasattr(self, 'page_result') and self.page_result._auto_compute:
            self.page_result._toggle_auto_compute()

# ==================== 全局事件过滤器 ====================

class _NoWheelFilter(QObject):
    """禁止鼠标滚轮修改所有 QSpinBox / QDoubleSpinBox 的数值."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if isinstance(obj, (QSpinBox, QDoubleSpinBox)):
                event.ignore()
                return True
        return super().eventFilter(obj, event)

# ==================== 主窗口 ====================

class DmgCalculator(QMainWindow):
    """应用主窗口. 持有 WelcomeScreen 和 MainScreen, 管理主题切换."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("鸣潮伤害计算器")

        # 窗口图标：优先加载 icon.ico，否则生成默认图标
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "icon.ico")
        if not os.path.exists(icon_path) and getattr(sys, 'frozen', False):
            # 打包后 icon.ico 在 _internal 子目录
            icon_path = os.path.join(sys._MEIPASS, "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            px = QPixmap(64, 64)
            px.fill(Qt.GlobalColor.transparent)
            painter = QPainter(px)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(60, 140, 210))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Microsoft YaHei", 28, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "鸣")
            painter.end()
            self.setWindowIcon(QIcon(px))

        self.current_theme = "dark"

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.welcome_screen = WelcomeScreen(on_start=self._show_main)
        self.stack.addWidget(self.welcome_screen)

        self.main_screen = MainScreen(on_back=self._show_welcome)
        self.stack.addWidget(self.main_screen)

        self.stack.setCurrentWidget(self.welcome_screen)

        # 必须先创建 theme_btn，避免 resizeEvent 先触发导致访问不到而崩溃
        self.theme_btn = QPushButton("切换到白天模式", self)
        self.theme_btn.setObjectName("themeButton")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)

        # 存档按钮（放在主题按钮左边）
        btn_style = (
            "QPushButton { font-size: 12px; padding: 3px 8px; border: 1px solid #555; "
            "border-radius: 4px; background: rgba(255,255,255,0.06); color: #ccc; }"
            "QPushButton:hover { background: rgba(255,255,255,0.14); }"
        )
        self.save_btns = []
        for text, slot in [("快速保存", self._save_wrapper),
                           ("快速加载", self._load_wrapper),
                           ("导入", self._import_wrapper),
                           ("导出", self._export_wrapper)]:
            btn = QPushButton(text, self)
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            self.save_btns.append(btn)

        # 全局自动按钮（在导出左边）
        self._auto_all_active = self._load_auto_all_config()
        auto_all_style = self._build_auto_all_style(self._auto_all_active)
        self.auto_all_btn = QPushButton(
            "关闭自动更新" if self._auto_all_active else "开启自动更新", self
        )
        self.auto_all_btn.setStyleSheet(auto_all_style)
        self.auto_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_all_btn.clicked.connect(self._toggle_auto_all)

        # 预设构建器按钮（放在使用预设左边）
        builder_style = (
            "QPushButton { font-size: 12px; padding: 2px 8px; border: 1px solid #8e44ad; "
            "border-radius: 4px; background: rgba(142,68,173,0.20); color: #bb8fce; font-weight: 600; }"
            "QPushButton:hover { background: rgba(142,68,173,0.35); }"
        )
        self.builder_btn = QPushButton("预设构建器", self)
        self.builder_btn.setStyleSheet(builder_style)
        self.builder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.builder_btn.clicked.connect(self._open_preset_builder)

        # 使用预设按钮（使用 accent 色突出）
        preset_style = (
            "QPushButton { font-size: 12px; padding: 5px 14px; border: 1px solid #e94560; "
            "border-radius: 4px; background: rgba(233,69,96,0.25); color: #ff8c9a; font-weight: 600; }"
            "QPushButton:hover { background: rgba(233,69,96,0.45); }"
        )
        self.preset_btn = QPushButton("使用预设", self)
        self.preset_btn.setStyleSheet(preset_style)
        self.preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preset_btn.clicked.connect(self._open_preset_loader)

        # 自适应窗口大小（0.85），最小宽度1000px
        screen = QGuiApplication.primaryScreen().availableGeometry()
        w = max(int(screen.width() * 0.85), 1000)
        h = int(screen.height() * 0.85)
        self.resize(w, h)

        self._apply_theme()

        # 启动时若上次开启了全局自动，自动激活两个自动按钮
        self._apply_auto_all_on_startup()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "theme_btn") or self.theme_btn is None:
            return
        self.theme_btn.adjustSize()
        x = self.width() - self.theme_btn.width() - 20
        self.theme_btn.move(x, 12)

        # 预设按钮放在 theme_btn 左边（与其他存档按钮分开）
        if hasattr(self, "preset_btn"):
            self.preset_btn.adjustSize()
            x = x - self.preset_btn.width() - 8
            self.preset_btn.move(x, 14)

        # 预设构建器按钮放在预设按钮左边
        if hasattr(self, "builder_btn"):
            self.builder_btn.adjustSize()
            x = x - self.builder_btn.width() - 8
            self.builder_btn.move(x, 14)

        # 把全局自动按钮排在预设构建器左边
        if hasattr(self, "auto_all_btn"):
            self.auto_all_btn.adjustSize()
            x = x - self.auto_all_btn.width() - 8
            self.auto_all_btn.move(x, 14)

        # 把存档按钮排在全局自动按钮左边
        if not hasattr(self, "save_btns"):
            return
        gap = 8
        for btn in self.save_btns:
            btn.adjustSize()
            x = x - btn.width() - gap
            btn.move(x, 14)

    def _show_main(self):
        self.stack.setCurrentWidget(self.main_screen)

    def _show_welcome(self):
        self.stack.setCurrentWidget(self.welcome_screen)

    def _toggle_theme(self):
        if self.current_theme == "dark":
            self.current_theme = "light"
            self.theme_btn.setText("切换到黑夜模式")
        else:
            self.current_theme = "dark"
            self.theme_btn.setText("切换到白天模式")
        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(build_stylesheet(self.current_theme))
        # 更新存档按钮主题
        if self.current_theme == "dark":
            btn_css = (
                "QPushButton { font-size: 12px; padding: 3px 8px; border: 1px solid #3d4458; "
                "border-radius: 4px; background: rgba(255,255,255,0.05); color: #b0b6c2; }"
                "QPushButton:hover { background: rgba(255,255,255,0.10); }"
            )
            preset_css = (
                "QPushButton { font-size: 12px; padding: 3px 8px; border: 1px solid #e94560; "
                "border-radius: 4px; background: rgba(233,69,96,0.25); color: #ff8c9a; font-weight: 600; }"
                "QPushButton:hover { background: rgba(233,69,96,0.45); }"
            )
            builder_css = (
                "QPushButton { font-size: 12px; padding: 3px 8px; border: 1px solid #8e44ad; "
                "border-radius: 4px; background: rgba(142,68,173,0.20); color: #bb8fce; font-weight: 600; }"
                "QPushButton:hover { background: rgba(142,68,173,0.35); }"
            )
        else:
            btn_css = (
                "QPushButton { font-size: 12px; padding: 3px 8px; border: 1px solid #b0b8c4; "
                "border-radius: 4px; background: rgba(0,0,0,0.04); color: #3a4050; }"
                "QPushButton:hover { background: rgba(0,0,0,0.08); }"
            )
            preset_css = (
                "QPushButton { font-size: 12px; padding: 3px 8px; border: 1px solid #5070e8; "
                "border-radius: 4px; background: rgba(80,112,232,0.15); color: #3d5fd4; font-weight: 600; }"
                "QPushButton:hover { background: rgba(80,112,232,0.28); }"
            )
            builder_css = (
                "QPushButton { font-size: 12px; padding: 3px 8px; border: 1px solid #7c3aed; "
                "border-radius: 4px; background: rgba(124,58,237,0.12); color: #6d28d9; font-weight: 600; }"
                "QPushButton:hover { background: rgba(124,58,237,0.22); }"
            )
        for btn in self.save_btns:
            btn.setStyleSheet(btn_css)
        if hasattr(self, "preset_btn"):
            self.preset_btn.setStyleSheet(preset_css)
        if hasattr(self, "builder_btn"):
            self.builder_btn.setStyleSheet(builder_css)
        if hasattr(self, "auto_all_btn"):
            self.auto_all_btn.setStyleSheet(
                self._build_auto_all_style(self._auto_all_active)
            )

        # 主题切换后重新生成计算过程（内联颜色需更新）和结果列表卡片
        if hasattr(self.main_screen, 'page_result'):
            rp = self.main_screen.page_result
            if getattr(rp, '_last_computed', None) is not None:
                rp.compute()
        if hasattr(self.main_screen, 'page_result_list'):
            self.main_screen.page_result_list._refresh_cards()
            # 更新结果列表搜索框主题
            rl = self.main_screen.page_result_list
            light = self.current_theme == "light"
            sr_bg = "#f0f4fa" if light else "#1e2a3a"
            sr_fg = "#1b2035" if light else "#e0e0e0"
            sr_bd = "#b8c4d6" if light else "#555"
            sr_focus = "#5070e8" if light else "#e94560"
            rl._search_input.setStyleSheet(
                f"QLineEdit#resultSearchInput {{ padding: 4px 6px; border: 1px solid {sr_bd}; "
                f"border-radius: 6px; font-size: 14px; background: {sr_bg}; color: {sr_fg}; }}"
                f"QLineEdit#resultSearchInput:focus {{ border-color: {sr_focus}; }}"
            )

    # —— 存档槽方法（委托到 MainScreen） ——

    def _save_wrapper(self):
        self.main_screen._quick_save()

    def _load_wrapper(self):
        self.main_screen._quick_load()

    def _import_wrapper(self):
        self.main_screen._import_save()

    def _export_wrapper(self):
        self.main_screen._export_save()

    def _open_preset_builder(self):
        """打开预设构建器窗口（非模态，保留引用防止被回收）"""
        if getattr(self, '_preset_builder_dlg', None) is not None:
            self._preset_builder_dlg.raise_()
            self._preset_builder_dlg.activateWindow()
            return
        self._preset_builder_dlg = PresetBuilderDialog(self)
        self._preset_builder_dlg.setWindowModality(Qt.WindowModality.NonModal)
        self._preset_builder_dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._preset_builder_dlg.destroyed.connect(lambda: setattr(self, '_preset_builder_dlg', None))
        self._preset_builder_dlg.show()

    def _open_preset_loader(self):
        """打开使用预设窗口"""
        dlg = PresetLoaderDialog(self, main_screen=self.main_screen)
        dlg.exec()

    # —— 全局自动按钮 ——

    def _build_auto_all_style(self, active):
        if active:
            if self.current_theme == "dark":
                return (
                    "QPushButton { font-size: 12px; padding: 3px 8px; "
                    "border: 1px solid #43A047; border-radius: 4px; "
                    "background: rgba(76,175,80,0.20); color: #81c784; font-weight: 600; }"
                    "QPushButton:hover { background: rgba(76,175,80,0.30); }"
                )
            else:
                return (
                    "QPushButton { font-size: 12px; padding: 3px 8px; "
                    "border: 1px solid #388E3C; border-radius: 4px; "
                    "background: rgba(76,175,80,0.12); color: #2e7d32; font-weight: 600; }"
                    "QPushButton:hover { background: rgba(76,175,80,0.22); }"
                )
        else:
            if self.current_theme == "dark":
                return (
                    "QPushButton { font-size: 12px; padding: 3px 8px; "
                    "border: 1px solid #555; border-radius: 4px; "
                    "background: rgba(255,255,255,0.06); color: #ccc; }"
                    "QPushButton:hover { background: rgba(255,255,255,0.14); }"
                )
            else:
                return (
                    "QPushButton { font-size: 12px; padding: 3px 8px; "
                    "border: 1px solid #bbb; border-radius: 4px; "
                    "background: rgba(0,0,0,0.04); color: #333; }"
                    "QPushButton:hover { background: rgba(0,0,0,0.08); }"
                )

    def _toggle_auto_all(self):
        self._auto_all_active = not self._auto_all_active
        self._save_auto_all_config(self._auto_all_active)
        if self._auto_all_active:
            self.main_screen.activate_auto_all()
            self.auto_all_btn.setText("关闭自动更新")
        else:
            self.main_screen.deactivate_auto_all()
            self.auto_all_btn.setText("开启自动更新")
        self.auto_all_btn.setStyleSheet(
            self._build_auto_all_style(self._auto_all_active)
        )

    def _load_auto_all_config(self):
        config_path = os.path.join(_APP_DIR, "config", "auto_all_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("auto_all_active", False)
            except Exception as e:
                _logger.warning("读取 auto_all_config 失败: %s", e)
                return False
        return False

    def _save_auto_all_config(self, active):
        config_path = os.path.join(_APP_DIR, "config", "auto_all_config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"auto_all_active": active}, f)
        except Exception as e:
            _logger.debug("保存 auto_all_config 失败: %s", e)

    # —— 关闭确认 ——

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.stack.currentWidget() == self.main_screen:
            self.close()  # 触发 closeEvent → 弹出保存提示
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        msg = QMessageBox(self)
        msg.setWindowTitle("退出程序")
        msg.setText("确定要退出程序吗？\n\n退出前是否需要保存当前数据？")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel  # 隐藏，仅用于启用 X 按钮
        )
        msg.button(QMessageBox.StandardButton.Save).setText("保存并退出")
        msg.button(QMessageBox.StandardButton.Discard).setText("不保存")
        cancel_btn = msg.button(QMessageBox.StandardButton.Cancel)
        cancel_btn.hide()  # 不显示，X 按钮自动绑定到它
        msg.setDefaultButton(QMessageBox.StandardButton.Save)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked is msg.button(QMessageBox.StandardButton.Save):
            self._save_wrapper()
            event.accept()
        elif clicked is msg.button(QMessageBox.StandardButton.Discard):
            event.accept()
        else:
            event.ignore()

    # —— 启动时自动激活 ——

    def _apply_auto_all_on_startup(self):
        if self._auto_all_active:
            self.main_screen.activate_auto_all()

# ==================== 程序入口 ====================

def main():
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei")
    font.setPointSize(12)  # 原先 14；12 更适合 1080p
    app.setFont(font)

    # 禁止所有输入框的滚轮修改数值
    _no_wheel = _NoWheelFilter(app)
    app.installEventFilter(_no_wheel)

    # ── 全局异常捕获：闪退/未处理异常 → 写入日志 + 弹出外部窗口 ──
    _original_excepthook = sys.excepthook
    def _crash_handler(exc_type, exc_value, exc_tb):
        import traceback
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _add_log_entry("CRITICAL", f"程序异常退出: {exc_value}", tb_text)

        # 启动外部错误报告程序
        if getattr(sys, 'frozen', False):
            # 打包后：启动同目录下的 ErrorViewer.exe
            viewer_path = os.path.join(
                os.path.dirname(sys.executable), "ErrorViewer", "ErrorViewer.exe"
            )
            try:
                subprocess.Popen([viewer_path, "--crash"],
                               creationflags=subprocess.CREATE_NO_WINDOW
                               if sys.platform == "win32" else 0)
            except Exception:
                pass
        else:
            # 开发时：用 Python 运行 error_viewer.py
            viewer_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "error_handler", "error_viewer.py"
            )
            try:
                subprocess.Popen([sys.executable, viewer_path, "--crash"],
                               creatinflags=subprocess.CREATE_NO_WINDOW
                               if sys.platform == "win32" else 0)
            except Exception:
                pass
        _original_excepthook(exc_type, exc_value, exc_tb)
    sys.excepthook = _crash_handler

    window = DmgCalculator()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
      