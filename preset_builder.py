# -*- coding: utf-8 -*-
# 预设构建器窗口 —— 分页式设计（角色/武器/声骸套装）
#
# 设计：
#   角色预设：3 页（基本内容 / 共鸣链 / 结果列表）
#   武器预设：2 页（基本内容 / 阶段等级）
#   声骸套装：保持原有设计

__all__ = ["PresetBuilderDialog"]

import json
import os
import sys

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QDoubleSpinBox, QSpinBox,
    QCheckBox, QComboBox, QGroupBox, QFrame, QScrollArea,
    QStackedWidget, QSizePolicy, QMessageBox, QInputDialog,
    QTableWidget, QHeaderView, QTableWidgetItem, QTabWidget,
    QGridLayout, QListWidget, QListWidgetItem, QTextEdit,
)
from PyQt6.QtCore import Qt, QEvent, QTimer, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QFont, QDesktopServices

from preset_manager import PresetManager
from damage_calc import BONUS_SUFFIX, DEEPEN_SUFFIX, CRIT_RATE_KEYWORDS, CRIT_DMG_KEYWORDS

# 延迟导入避免循环依赖
def _get_search_combo():
    from WWDmgCalc import SearchCombo, WEAPON_RESONANCE_ATTRS
    return SearchCombo, WEAPON_RESONANCE_ATTRS

def _get_render_fn():
    from WWDmgCalc import _render_process_html
    return _render_process_html

# ── 常量 ──
ELEMENTS = ["冷凝", "热熔", "气动", "导电", "衍射", "湮灭"]
EFFECTS = ["(无)", "光噪", "风蚀", "虚湮", "聚爆", "霜渐", "电磁"]
SOURCES = ["武器谐振", "合鸣效果", "技能效果", "角色效果", "其他效果", "共鸣链效果"]
WEAPON_BONUS_TYPES = ["生命值", "攻击力", "防御力", "暴击率", "暴击伤害", "共鸣效率"]
EFFECT_TYPES = ["常驻", "触发"]


def _fit_to_screen(window, default_w):
    """低分辨率保护：屏幕宽度不足时自动缩小窗口。
    2K/4K 不受影响，1080p 及以下才会缩放。"""
    from PyQt6.QtGui import QGuiApplication
    screen_w = QGuiApplication.primaryScreen().availableGeometry().width()
    if screen_w < default_w:
        scale = max(0.75, screen_w / default_w)
        cur_min_w, cur_min_h = window.minimumWidth(), window.minimumHeight()
        cur_w, cur_h = window.width(), window.height()
        window.setMinimumSize(max(800, int(cur_min_w * scale)), int(cur_min_h * scale))
        window.resize(max(800, int(cur_w * scale)), int(cur_h * scale))


# ═══════════════════════════════════════════════════════════════
# 适配器类 —— 将预设数据包装为主程序接口格式
# ═══════════════════════════════════════════════════════════════

class _PresetCharBaseAdapter:
    """模拟 CharBasePage.collect_data() 接口"""

    def __init__(self):
        self._base_hp = 1.0
        self._base_atk = 1.0
        self._base_def = 1.0

    def update(self, base_hp, base_atk, base_def):
        self._base_hp = base_hp
        self._base_atk = base_atk
        self._base_def = base_def

    def collect_data(self):
        return {
            'base_hp': self._base_hp,
            'base_atk': self._base_atk,
            'base_def': self._base_def,
            'weapon_base_atk': 0,
            'weapon_bonus': None,
        }


class _PresetCombinedEntryAdapter:
    """模拟 CombinedEntryPage.collect_data() 接口，从共鸣链效果展平"""

    def __init__(self):
        self._entries = []

    def update_from_chain_data(self, chain_data):
        """从 _chain_data 构建展平的词条列表"""
        entries = []
        for chain_idx, cd in enumerate(chain_data):
            for eff_i, eff in enumerate(cd.get("effects", [])):
                name = eff.get("name", "")
                value = eff.get("value", 0.0)
                if not name:
                    continue
                source = eff.get("source", "共鸣链效果")
                seq = f"共鸣链{chain_idx + 1}-{eff_i + 1}"
                sub_name = eff.get("sub_name", "")
                entries.append((name, value, False, source, seq, sub_name))
        self._entries = entries

    def collect_data(self):
        return list(self._entries)


class _PresetIndepZoneAdapter:
    """模拟 IndepZonePage 接口"""

    def __init__(self):
        self._groups = []
        self.independent_zone = 1.0
        self.group_factors = []

    def update_from_chain_data(self, chain_data):
        groups = []
        for cd in chain_data:
            for iz in cd.get("indep_zones", []):
                if iz.get("values"):
                    groups.append(iz)
        self._groups = groups
        self._recalc()

    def _recalc(self):
        self.independent_zone = 1.0
        self.group_factors = []
        for ig in self._groups:
            factor = 1.0
            for v in ig.get("values", []):
                factor *= (1.0 + v.get("value", 0.0) / 100.0)
            self.independent_zone *= factor
            self.group_factors.append((ig.get("group_name", ""), factor))

    def collect_data(self):
        return [
            {
                "name": ig.get("group_name", ""),
                "values": [(v["name"], v["value"], v.get("hidden", False))
                           for v in ig.get("values", [])],
            }
            for ig in self._groups
        ]


class _PresetDefenseAdapter:
    """固定防御乘区 = 1.0"""
    def __init__(self):
        self.def_multiplier = 1.0


class _PresetResistanceAdapter:
    """固定抗性乘区 = 1.0"""
    def __init__(self):
        pass

    def get_resistance_multiplier(self, _element=None):
        return 1.0


class _PresetKeywordAdapter:
    """空关键词关联"""
    def get_items(self):
        return []


# ═══════════════════════════════════════════════════════════════
# 效果表格编辑器
# ═══════════════════════════════════════════════════════════════

class _EffectTableWidget(QWidget):
    """(已废弃，由 _EditDialog 内嵌双表格替代)"""

    def __init__(self, default_source="其他效果", show_type=True, parent=None):
        super().__init__(parent)
        self._default_source = default_source
        self._show_type = show_type
        self._counter = 0
        self._rows = []

        # 延迟导入 SearchCombo
        SearchCombo, WEAPON_RESONANCE_ATTRS = _get_search_combo()
        self._attr_list = WEAPON_RESONANCE_ATTRS

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── 输入行 ──
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        # 属性名搜索下拉框
        self._name_combo = SearchCombo(self._attr_list)
        self._name_combo.setMinimumWidth(160)
        self._name_combo.lineEdit().setPlaceholderText("输入搜索...")
        input_row.addWidget(self._name_combo, stretch=2)

        self._value_spin = QDoubleSpinBox()
        self._value_spin.setRange(0, 99999)
        self._value_spin.setDecimals(4)
        self._value_spin.setFixedWidth(100)
        input_row.addWidget(self._value_spin)

        input_row.addWidget(QLabel("%"))

        if self._show_type:
            self._type_combo = QComboBox()
            self._type_combo.addItems(EFFECT_TYPES)
            self._type_combo.setFixedWidth(60)
            input_row.addWidget(self._type_combo)

        self._source_combo = QComboBox()
        self._source_combo.addItems(SOURCES)
        self._source_combo.setCurrentText(self._default_source)
        self._source_combo.setMinimumWidth(90)
        input_row.addWidget(self._source_combo)

        add_btn = QPushButton("添加")
        add_btn.setObjectName("addButton")
        add_btn.setFixedWidth(50)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_row)
        input_row.addWidget(add_btn)

        layout.addLayout(input_row)

        # ── 数据表格 ──
        col_count = 7 if self._show_type else 6
        headers = ["名称", "副名称", "数值"]
        if self._show_type:
            headers.append("类型")
        headers.extend(["来源", "默认隐藏", "删除"])

        self._table = QTableWidget()
        self._table.setObjectName("attrTable")
        self._table.setColumnCount(col_count)
        self._table.setHorizontalHeaderLabels(headers)
        self._table.verticalHeader().setVisible(False)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, col_count):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(1, 130)   # 副名称
        hdr.resizeSection(2, 140)   # 数值
        if self._show_type:
            hdr.resizeSection(3, 140)    # 类型
            hdr.resizeSection(4, 140)    # 来源
            hdr.resizeSection(5, 100)    # 默认隐藏
            hdr.resizeSection(6, 50)    # 删除
        else:
            hdr.resizeSection(3, 140)    # 来源
            hdr.resizeSection(4, 100)    # 默认隐藏
            hdr.resizeSection(5, 50)    # 删除

        layout.addWidget(self._table)

        self._name_combo.lineEdit().returnPressed.connect(self._add_row)

    def _add_row(self):
        name = self._name_combo.currentText().strip()
        if not name:
            return

        value = self._value_spin.value()
        eff_type = self._type_combo.currentText() if self._show_type else "常驻"
        source = self._source_combo.currentText()

        self._counter += 1
        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)
        self._table.setRowHeight(row_idx, 38)

        name_edit = QLineEdit(name)
        name_edit.setObjectName("nameEdit")
        name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 0, name_edit)

        sub_name_edit = QLineEdit()
        sub_name_edit.setObjectName("nameEdit")
        sub_name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_name_edit.setPlaceholderText("（备注）")
        self._table.setCellWidget(row_idx, 1, sub_name_edit)

        value_spin = QDoubleSpinBox()
        value_spin.setObjectName("itemValueSpin")
        value_spin.setRange(0, 99999)
        value_spin.setDecimals(4)
        value_spin.setValue(value)
        value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setCellWidget(row_idx, 2, value_spin)

        col_offset = 3

        if self._show_type:
            type_combo = QComboBox()
            type_combo.addItems(EFFECT_TYPES)
            type_combo.setCurrentText(eff_type)
            type_combo.setFixedWidth(60)
            self._table.setCellWidget(row_idx, col_offset, type_combo)
            col_offset += 1
        else:
            type_combo = None

        source_combo = QComboBox()
        source_combo.addItems(SOURCES)
        source_combo.setCurrentText(source)
        source_combo.setMinimumWidth(90)
        self._table.setCellWidget(row_idx, col_offset, source_combo)
        col_offset += 1

        hidden_cb = QCheckBox()
        hidden_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        hidden_cb.setStyleSheet("QCheckBox { text-align: center; }")
        hidden_container = QWidget()
        hidden_layout = QHBoxLayout(hidden_container)
        hidden_layout.setContentsMargins(0, 0, 0, 0)
        hidden_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hidden_layout.addWidget(hidden_cb)
        self._table.setCellWidget(row_idx, col_offset, hidden_container)
        col_offset += 1

        del_btn = QPushButton("✕")
        del_btn.setObjectName("itemDeleteBtn")
        del_btn.setFixedSize(28, 28)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self._remove_row(row_idx))
        del_container = QWidget()
        del_layout = QHBoxLayout(del_container)
        del_layout.setContentsMargins(0, 0, 0, 0)
        del_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        del_layout.addWidget(del_btn)
        self._table.setCellWidget(row_idx, col_offset, del_container)

        self._rows.append({
            "name_edit": name_edit,
            "sub_name_edit": sub_name_edit,
            "value_spin": value_spin,
            "type_combo": type_combo,
            "source_combo": source_combo,
            "hidden_cb": hidden_cb,
            "del_btn": del_btn,
        })

        self._name_combo.lineEdit().clear()
        self._value_spin.setValue(0)

    def _remove_row(self, row_idx):
        if 0 <= row_idx < len(self._rows):
            self._rows.pop(row_idx)
            self._table.removeRow(row_idx)
            for i, rd in enumerate(self._rows):
                rd["del_btn"].clicked.disconnect()
                idx = i
                rd["del_btn"].clicked.connect(lambda _, ri=idx: self._remove_row(ri))

    def to_list(self):
        result = []
        for rd in self._rows:
            eff = {
                "name": rd["name_edit"].text().strip(),
                "value": rd["value_spin"].value(),
                "source": rd["source_combo"].currentText(),
                "sub_name": rd["sub_name_edit"].text().strip(),
                "default_hidden": rd["hidden_cb"].isChecked(),
            }
            if rd["type_combo"] is not None:
                eff["type"] = rd["type_combo"].currentText()
            else:
                eff["type"] = "常驻"
            result.append(eff)
        return result

    def from_list(self, effects):
        self._table.setRowCount(0)
        self._rows.clear()
        for eff in effects:
            self._name_combo.lineEdit().setText(eff.get("name", ""))
            self._value_spin.setValue(eff.get("value", 0.0))
            if self._show_type and hasattr(self, '_type_combo'):
                self._type_combo.setCurrentText(eff.get("type", "常驻"))
            self._source_combo.setCurrentText(eff.get("source", self._default_source))
            self._add_row()
            if self._rows:
                last = self._rows[-1]
                last["sub_name_edit"].setText(eff.get("sub_name", ""))
                last["hidden_cb"].setChecked(eff.get("default_hidden", False))

    def row_count(self):
        return len(self._rows)


# ═══════════════════════════════════════════════════════════════
# 独立乘区组
# ═══════════════════════════════════════════════════════════════

class _IndepZoneGroupBox(QFrame):
    """独立乘区组（外观与 IndepZonePage._add_group 一致）"""

    def __init__(self, group_name="", values=None):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("indepGroupFrame")
        self._value_widgets = []
        self._row_widgets = []

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        # ── 顶部：组名 + 一键隐藏 + 删除组 ──
        top_row = QHBoxLayout()
        self.group_name_edit = QLineEdit(group_name)
        self.group_name_edit.setObjectName("nameEdit")
        self.group_name_edit.setPlaceholderText("乘区组名称")
        self.group_name_edit.setMinimumWidth(120)
        self.group_name_edit.setMaximumWidth(200)
        top_row.addWidget(self.group_name_edit)
        top_row.addStretch()

        self._hide_all_btn = QPushButton("一键隐藏")
        self._hide_all_btn.setObjectName("backButton")
        self._hide_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hide_all_btn.setToolTip("隐藏/显示当前组内所有数值")
        top_row.addWidget(self._hide_all_btn)

        self.del_group_btn = QPushButton("删除组")
        self.del_group_btn.setObjectName("backButton")
        self.del_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        top_row.addWidget(self.del_group_btn)
        layout.addLayout(top_row)

        # ── 数值行容器 ──
        self._values_layout = QVBoxLayout()
        self._values_layout.setSpacing(3)
        layout.addLayout(self._values_layout)

        # ── 添加数值按钮 ──
        add_val_btn = QPushButton("添加数值")
        add_val_btn.setObjectName("backButton")
        add_val_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_val_btn.clicked.connect(lambda: self._add_value_row())
        layout.addWidget(add_val_btn)

        # ── 组结果 ──
        self._result_label = QLabel("该乘区总数值 = 1.0000000000")
        self._result_label.setObjectName("labelSecondary")
        layout.addWidget(self._result_label)

        # 恢复已有数值
        if values:
            for v in values:
                if isinstance(v, dict):
                    self._add_value_row(v.get("name", ""), v.get("value", 0.0), v.get("hidden", False))
                elif len(v) >= 3:
                    self._add_value_row(v[0], v[1], v[2])
                elif len(v) >= 2:
                    self._add_value_row(v[0], v[1], False)

        self._update_result()

    def _add_value_row(self, name="", value=0.0, hidden=False):
        row_widget = QWidget()
        row_widget.setObjectName("indepValueRow")
        rl = QHBoxLayout(row_widget)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)

        ne = QLineEdit(name)
        ne.setObjectName("nameEdit")
        ne.setPlaceholderText("名称")
        ne.setMinimumWidth(100)
        ne.setMaximumWidth(150)
        ne.textChanged.connect(lambda: self._update_result())
        rl.addWidget(ne)

        vs = QDoubleSpinBox()
        vs.setRange(0, 99999)
        vs.setDecimals(4)
        vs.setValue(value)
        vs.setSuffix("%")
        vs.valueChanged.connect(lambda: self._update_result())
        rl.addWidget(vs)

        hc = QCheckBox("隐藏")
        hc.setObjectName("smallCheckbox")
        hc.setChecked(hidden)
        hc.setCursor(Qt.CursorShape.PointingHandCursor)
        hc.setToolTip("勾选后该数值不参与独立乘区计算")
        hc.toggled.connect(lambda checked: self._dim_row(row_widget, checked))
        rl.addWidget(hc)

        db = QPushButton("删除")
        db.setObjectName("backButton")
        db.setCursor(Qt.CursorShape.PointingHandCursor)
        db.clicked.connect(lambda: self._remove_value_row(row_widget))
        rl.addWidget(db)

        rl.addStretch()

        self._values_layout.addWidget(row_widget)
        self._value_widgets.append((ne, vs, hc))
        self._row_widgets.append(row_widget)
        if hidden:
            self._dim_row(row_widget, True)
        self._update_result()

        # 绑定一键隐藏
        try:
            self._hide_all_btn.clicked.disconnect()
        except Exception:
            pass
        self._hide_all_btn.clicked.connect(self._toggle_hide_all)

    def _remove_value_row(self, row_widget):
        idx = self._values_layout.indexOf(row_widget)
        if 0 <= idx < len(self._value_widgets):
            self._value_widgets.pop(idx)
            self._row_widgets.pop(idx)
        self._values_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self._update_result()

    def _dim_row(self, row_widget, dim):
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        if dim:
            eff = row_widget.graphicsEffect()
            if eff is None:
                eff = QGraphicsOpacityEffect()
                row_widget.setGraphicsEffect(eff)
            eff.setOpacity(0.35)
        else:
            row_widget.setGraphicsEffect(None)

    def _toggle_hide_all(self):
        if not self._value_widgets:
            return
        all_hidden = all(cb.isChecked() for _, _, cb in self._value_widgets)
        new_state = not all_hidden
        for _, _, cb in self._value_widgets:
            if cb.isChecked() != new_state:
                cb.setChecked(new_state)
        self._hide_all_btn.setText("取消隐藏" if new_state else "一键隐藏")
        self._update_result()

    def _update_result(self):
        total = sum(vs.value() for _, vs, cb in self._value_widgets if not cb.isChecked())
        factor = 1.0 + total / 100.0
        self._result_label.setText(f"该乘区总数值 = {factor:.10f}")

    def to_dict(self):
        return {
            "group_name": self.group_name_edit.text().strip(),
            "values": [
                {"name": ne.text().strip(), "value": vs.value(), "hidden": hc.isChecked()}
                for ne, vs, hc in self._value_widgets
            ],
        }


# ═══════════════════════════════════════════════════════════════
# 展开编辑弹窗
# ═══════════════════════════════════════════════════════════════

class _EffectTabDialog(QDialog):
    """分页式效果编辑弹窗 —— 通用增益（常驻+触发+独立乘区）+ 特定增益"""

    def __init__(self, title, default_source="其他效果", parent=None,
                 intro_tab_label="", intro_title="", intro_text="", intro_placeholder="",
                 intro_extra=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(1100, 680)
        self.resize(1150, 720)
        _fit_to_screen(self, 1150)

        QTimer.singleShot(0, lambda: self._center())

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("sectionTitle")
        layout.addWidget(title_lbl)

        # ═══ 分页 ═══
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        # 可选：介绍页（第一个页面）
        self._intro_edit = None
        if intro_tab_label:
            self._build_intro_tab(intro_tab_label, intro_title, intro_text, intro_placeholder, intro_extra)

        self._build_general_tab(default_source)
        self._build_specific_tab(default_source)

        # ═══ 底部按钮 ═══
        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("backButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)
        confirm_btn = QPushButton("确认")
        confirm_btn.setObjectName("presetSaveBtn")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.clicked.connect(self.accept)
        bottom.addWidget(confirm_btn)
        layout.addLayout(bottom)

    def _center(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    # ═══════════════════════════════════════════════════════════
    # Tab 0（可选）: 介绍页
    # ═══════════════════════════════════════════════════════════

    def _build_intro_tab(self, tab_label, intro_title, intro_text, intro_placeholder, extra_layout=None):
        """构建介绍标签页（照搬共鸣链介绍页）"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        # 可选：额外控件（如声骸所需同套数量）
        if extra_layout is not None:
            layout.addLayout(extra_layout)

        lbl = QLabel(intro_title)
        lbl.setObjectName("sectionTitle")
        lbl.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(lbl)

        self._intro_edit = QTextEdit()
        self._intro_edit.setObjectName("nameEdit")
        self._intro_edit.setPlaceholderText(intro_placeholder)
        self._intro_edit.setPlainText(intro_text)
        layout.addWidget(self._intro_edit, stretch=1)

        self._tabs.addTab(tab, tab_label)

    def get_intro_text(self):
        if self._intro_edit:
            return self._intro_edit.toPlainText()
        return ""

    def set_intro_text(self, text):
        if self._intro_edit:
            self._intro_edit.setPlainText(text)

    # ═══════════════════════════════════════════════════════════
    # Tab: 通用增益（常驻 + 触发 + 独立乘区）
    # ═══════════════════════════════════════════════════════════

    def _build_general_tab(self, default_source):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("通用增益")
        title.setObjectName("sectionTitle")
        tab_layout.addWidget(title)

        desc = QLabel("管理常驻效果和触发效果，并添加独立乘区组")
        desc.setObjectName("labelSecondary")
        desc.setWordWrap(True)
        tab_layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(12)

        SearchCombo, WEAPON_RESONANCE_ATTRS = _get_search_combo()

        # ── 常驻效果 ──
        perm_group = QGroupBox("常驻效果")
        perm_group.setMinimumHeight(500)
        perm_layout = QVBoxLayout(perm_group)

        perm_input = QHBoxLayout()
        self._perm_combo = SearchCombo(WEAPON_RESONANCE_ATTRS)
        self._perm_combo.lineEdit().setPlaceholderText("输入搜索...")
        perm_input.addWidget(self._perm_combo, stretch=3)

        self._perm_value = QDoubleSpinBox()
        self._perm_value.setRange(0, 99999)
        self._perm_value.setDecimals(4)
        self._perm_value.setFixedWidth(100)
        perm_input.addWidget(self._perm_value)
        perm_input.addWidget(QLabel("%"))

        self._perm_source = QComboBox()
        self._perm_source.addItems(SOURCES)
        self._perm_source.setCurrentText(default_source)
        self._perm_source.setMinimumWidth(100)
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
        perm_hdr.resizeSection(1, 130)
        perm_hdr.resizeSection(2, 120)
        perm_hdr.resizeSection(3, 140)
        perm_hdr.resizeSection(4, 70)
        perm_hdr.resizeSection(5, 100)
        perm_hdr.resizeSection(6, 100)
        perm_layout.addWidget(self._perm_table)
        scroll_layout.addWidget(perm_group)

        # ── 触发效果 ──
        trig_group = QGroupBox("触发效果")
        trig_group.setMinimumHeight(500)
        trig_layout = QVBoxLayout(trig_group)

        trig_input = QHBoxLayout()
        self._trig_combo = SearchCombo(WEAPON_RESONANCE_ATTRS)
        self._trig_combo.lineEdit().setPlaceholderText("输入搜索...")
        trig_input.addWidget(self._trig_combo, stretch=3)

        self._trig_value = QDoubleSpinBox()
        self._trig_value.setRange(0, 99999)
        self._trig_value.setDecimals(4)
        self._trig_value.setFixedWidth(100)
        trig_input.addWidget(self._trig_value)
        trig_input.addWidget(QLabel("%"))

        self._trig_source = QComboBox()
        self._trig_source.addItems(SOURCES)
        self._trig_source.setCurrentText(default_source)
        self._trig_source.setMinimumWidth(100)
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
        trig_hdr.resizeSection(1, 130)
        trig_hdr.resizeSection(2, 120)
        trig_hdr.resizeSection(3, 140)
        trig_hdr.resizeSection(4, 70)
        trig_hdr.resizeSection(5, 100)
        trig_hdr.resizeSection(6, 100)
        trig_layout.addWidget(self._trig_table)
        scroll_layout.addWidget(trig_group)

        # ── 独立乘区组 ──
        iz_label = QLabel("独立乘区组")
        iz_label.setObjectName("labelSecondary")
        iz_label.setStyleSheet("font-size: 13px; font-weight: 600; margin-top: 8px;")
        scroll_layout.addWidget(iz_label)

        self._indep_container = QVBoxLayout()
        self._indep_container.setSpacing(6)
        scroll_layout.addLayout(self._indep_container)

        self._indep_groups = []

        add_iz_btn = QPushButton("+ 添加独立乘区组")
        add_iz_btn.setObjectName("addButton")
        add_iz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_iz_btn.clicked.connect(self._add_indep_group)
        scroll_layout.addWidget(add_iz_btn)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        tab_layout.addWidget(scroll)

        self._tabs.addTab(tab, "通用增益")

        # 行计数器
        self._perm_counter = 0
        self._trig_counter = 0

    # ═══════════════════════════════════════════════════════════
    # Tab 2: 特定增益
    # ═══════════════════════════════════════════════════════════

    def _build_specific_tab(self, default_source):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("特定增益")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        desc = QLabel("设置特定增益规则，选择效果后指定目标关键词卡片")
        desc.setObjectName("labelSecondary")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        SearchCombo, WEAPON_RESONANCE_ATTRS = _get_search_combo()

        spec_group = QGroupBox("特定增益")
        spec_group.setMinimumHeight(300)
        spec_layout = QVBoxLayout(spec_group)

        spec_input = QHBoxLayout()
        self._spec_combo = SearchCombo(WEAPON_RESONANCE_ATTRS)
        self._spec_combo.lineEdit().setPlaceholderText("输入搜索...")
        spec_input.addWidget(self._spec_combo, stretch=3)

        self._spec_value = QDoubleSpinBox()
        self._spec_value.setRange(0, 99999)
        self._spec_value.setDecimals(4)
        self._spec_value.setFixedWidth(100)
        spec_input.addWidget(self._spec_value)
        spec_input.addWidget(QLabel("%"))

        self._spec_source = QComboBox()
        self._spec_source.addItems(SOURCES)
        self._spec_source.setCurrentText(default_source)
        self._spec_source.setMinimumWidth(100)
        spec_input.addWidget(self._spec_source)

        add_spec = QPushButton("添加")
        add_spec.setObjectName("addButton")
        add_spec.setFixedWidth(50)
        add_spec.setCursor(Qt.CursorShape.PointingHandCursor)
        add_spec.clicked.connect(self._add_spec_row)
        spec_input.addWidget(add_spec)
        spec_layout.addLayout(spec_input)

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
        spec_hdr.resizeSection(1, 130)
        spec_hdr.resizeSection(2, 120)
        spec_hdr.resizeSection(3, 140)
        spec_hdr.resizeSection(4, 70)
        spec_hdr.resizeSection(5, 100)
        spec_hdr.resizeSection(6, 120)
        spec_hdr.resizeSection(7, 100)
        spec_layout.addWidget(self._spec_table)
        layout.addWidget(spec_group)

        self._tabs.addTab(tab, "特定增益")

        self._spec_counter = 0

    # ═══════════════════════════════════════════════════════════
    # 添加行
    # ═══════════════════════════════════════════════════════════

    def _add_perm_row(self):
        name = self._perm_combo.currentText().strip()
        if not name:
            return
        self._perm_counter += 1
        self._add_table_row(self._perm_table, name, self._perm_value.value(),
                            self._perm_source.currentText(), "常驻",
                            seq_prefix="常驻", show_kw=False)
        self._perm_combo.lineEdit().clear()
        self._perm_value.setValue(0)

    def _add_trig_row(self):
        name = self._trig_combo.currentText().strip()
        if not name:
            return
        self._trig_counter += 1
        self._add_table_row(self._trig_table, name, self._trig_value.value(),
                            self._trig_source.currentText(), "触发",
                            seq_prefix="触发", show_kw=False)
        self._trig_combo.lineEdit().clear()
        self._trig_value.setValue(0)

    def _add_spec_row(self):
        name = self._spec_combo.currentText().strip()
        if not name:
            return
        self._spec_counter += 1
        self._add_table_row(self._spec_table, name, self._spec_value.value(),
                            self._spec_source.currentText(), "特定",
                            seq_prefix="特定")
        self._spec_combo.lineEdit().clear()
        self._spec_value.setValue(0)

    def _add_table_row(self, table, name, value, source, eff_type, seq_prefix="", sub_name_text="", keywords="", show_kw=True):
        from WWDmgCalc import _make_sub_name_cell

        row_idx = table.rowCount()
        table.insertRow(row_idx)
        table.setRowHeight(row_idx, 42)

        name_edit = QLineEdit(name)
        name_edit.setObjectName("nameEdit")
        name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setCellWidget(row_idx, 0, name_edit)

        sub_name = QLineEdit(sub_name_text)
        sub_name.setObjectName("nameEdit")
        sub_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_name.setPlaceholderText("（备注）")
        table.setCellWidget(row_idx, 1, _make_sub_name_cell(sub_name, lambda: name))

        seq = QLabel(f"{seq_prefix}{row_idx + 1}")
        seq.setObjectName("seqLabel")
        seq.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setCellWidget(row_idx, 2, seq)

        value_spin = QDoubleSpinBox()
        value_spin.setObjectName("itemValueSpin")
        value_spin.setRange(0, 99999)
        value_spin.setDecimals(4)
        value_spin.setValue(value)
        value_spin.setFixedWidth(120)
        value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setCellWidget(row_idx, 3, value_spin)

        unit = QLabel("百分比")
        unit.setObjectName("unitLabel")
        unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setCellWidget(row_idx, 4, unit)

        source_lbl = QLabel(source)
        source_lbl.setObjectName("seqLabel")
        source_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setCellWidget(row_idx, 5, source_lbl)

        if show_kw:
            kw_btn = QPushButton(keywords if keywords else "点击编辑")
            kw_btn.setObjectName("itemLockBtn")
            kw_btn.setFixedSize(110, 35)
            kw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            kw_btn.clicked.connect(lambda _, r=row_idx, t=table: self._edit_keywords(r, t))
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
                    return
        del_btn.clicked.connect(_del_this)
        ops_layout.addWidget(del_btn)
        table.setCellWidget(row_idx, ops_col, ops)

    def _edit_keywords(self, row_idx, table):
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

    # ═══════════════════════════════════════════════════════════
    # 独立乘区
    # ═══════════════════════════════════════════════════════════

    def _add_indep_group(self):
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

    # ═══════════════════════════════════════════════════════════
    # 数据访问
    # ═══════════════════════════════════════════════════════════

    def _collect_table(self, table, eff_type):
        from WWDmgCalc import _get_sub_name_text
        has_kw = table.columnCount() == 8
        effects = []
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
                    "source": source_lbl.text() if source_lbl else "",
                    "sub_name": _get_sub_name_text(sub_name),
                }
                if has_kw:
                    kw_btn = table.cellWidget(row, 6)
                    eff["keywords"] = kw_btn.text() if kw_btn and kw_btn.text() != "点击编辑" else ""
                effects.append(eff)
        return effects

    def get_effects(self):
        effects = []
        effects.extend(self._collect_table(self._perm_table, "常驻"))
        effects.extend(self._collect_table(self._trig_table, "触发"))
        effects.extend(self._collect_table(self._spec_table, "特定"))
        return effects

    def get_indep_zones(self):
        return [iz.to_dict() for iz in self._indep_groups]

    def set_effects(self, effects):
        self._perm_table.setRowCount(0)
        self._trig_table.setRowCount(0)
        self._spec_table.setRowCount(0)
        self._perm_counter = 0
        self._trig_counter = 0
        self._spec_counter = 0
        for eff in effects:
            eff_type = eff.get("type", "常驻")
            if eff_type == "触发":
                self._trig_counter += 1
                self._add_table_row(self._trig_table,
                    eff.get("name", ""), eff.get("value", 0.0),
                    eff.get("source", ""), "触发",
                    seq_prefix="触发",
                    sub_name_text=eff.get("sub_name", ""),
                    show_kw=False)
            elif eff_type == "特定":
                self._spec_counter += 1
                self._add_table_row(self._spec_table,
                    eff.get("name", ""), eff.get("value", 0.0),
                    eff.get("source", ""), "特定",
                    seq_prefix="特定",
                    sub_name_text=eff.get("sub_name", ""),
                    keywords=eff.get("keywords", ""))
            else:
                self._perm_counter += 1
                self._add_table_row(self._perm_table,
                    eff.get("name", ""), eff.get("value", 0.0),
                    eff.get("source", ""), "常驻",
                    seq_prefix="常驻",
                    sub_name_text=eff.get("sub_name", ""),
                    show_kw=False)

    def set_indep_zones(self, zones):
        for iz_data in zones:
            gb = _IndepZoneGroupBox(iz_data.get("group_name", ""), iz_data.get("values", []))
            gb.del_group_btn.clicked.connect(lambda _checked=False, g=gb: self._remove_indep_group(g))
            self._indep_container.addWidget(gb)
            self._indep_groups.append(gb)

# 向后兼容别名
_EditDialog = _EffectTabDialog


# ═══════════════════════════════════════════════════════════════
# 紧凑卡片组件
# ═══════════════════════════════════════════════════════════════

class _CompactCard(QFrame):
    """紧凑卡片 —— 显示标题、摘要信息、「展开」按钮"""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("presetCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("accentLabel")
        self._title_label.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
        layout.addWidget(self._title_label)

        self._info_label = QLabel("")
        self._info_label.setObjectName("labelSecondary")
        self._info_label.setStyleSheet("font-size: 12px; background: transparent;")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._expand_btn = QPushButton("展开")
        self._expand_btn.setObjectName("addButton")
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.setFixedWidth(60)
        btn_row.addWidget(self._expand_btn)
        layout.addLayout(btn_row)

        self._expand_cb = None
        self._expand_btn.clicked.connect(lambda: self._expand_cb() if self._expand_cb else None)

    def set_title(self, text):
        self._title_label.setText(text)

    def set_info(self, text):
        self._info_label.setText(text)

    def set_expand_callback(self, cb):
        self._expand_cb = cb


# ═══════════════════════════════════════════════════════════════
# 角色预设窗口（分页式）
# ═══════════════════════════════════════════════════════════════

class _CharacterPresetWindow(QDialog):
    """角色预设窗口 —— 3 页分页设计"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("角色预设")
        self.setMinimumSize(1000, 700)
        self.resize(1050, 750)
        _fit_to_screen(self, 1050)

        QTimer.singleShot(0, lambda: self._center())

        # 继承主程序主题
        self._apply_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 返回按钮 + 自动更新
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        back_btn = QPushButton("← 返回总界面")
        back_btn.setObjectName("backButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedWidth(140)
        top_row.addWidget(back_btn)
        self.back_clicked = back_btn.clicked
        top_row.addStretch()
        self._preset_auto_btn = QPushButton("开启自动更新")
        self._preset_auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preset_auto_btn.setFixedWidth(120)
        self._preset_auto_btn.setStyleSheet(self._AUTO_OFF_STYLE)
        self._preset_auto_btn.clicked.connect(self._toggle_preset_auto)
        top_row.addWidget(self._preset_auto_btn)
        main_layout.addLayout(top_row)

        # 记住父级自动更新状态，等 ResultPage 创建后再应用
        self._pending_auto_state = (
            parent is not None and getattr(parent, '_auto_update_enabled', False))

        # 分页标签
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        # ── 页面1: 基本内容 ──
        self.tab_basic = QWidget()
        self._build_basic_tab()
        self.tabs.addTab(self.tab_basic, "基本内容")

        # ── 页面2: 共鸣链 ──
        self.tab_chain = QWidget()
        self._build_chain_tab()
        self.tabs.addTab(self.tab_chain, "共鸣链")

        # ── 页面3: 技能增益 ──
        self.tab_skill_buff = QWidget()
        self._build_skill_buff_tab()
        self.tabs.addTab(self.tab_skill_buff, "技能增益")

        # ── 适配器（延迟导入避免循环依赖） ──
        from WWDmgCalc import ResultPage, ResultListPage
        self._adapter_char_base = _PresetCharBaseAdapter()
        self._adapter_entries = _PresetCombinedEntryAdapter()
        self._adapter_indep = _PresetIndepZoneAdapter()
        self._adapter_defense = _PresetDefenseAdapter()
        self._adapter_resistance = _PresetResistanceAdapter()
        self._adapter_keyword = _PresetKeywordAdapter()
        self._adapters_dirty = True

        # ── 页面3: 计算结果 ──
        self.tab_calc = QWidget()
        self._preset_result_page = ResultPage()
        self._build_calc_tab()
        self.tabs.addTab(self.tab_calc, "计算结果")

        # ── 页面5: 结果列表 ──
        self.tab_result_list = QWidget()
        self._preset_result_list = ResultListPage()
        self._build_result_list_tab()
        self.tabs.addTab(self.tab_result_list, "结果列表")

        # 互相关联
        self._preset_result_page.set_result_list_page(self._preset_result_list)
        self._preset_result_list.set_result_page(self._preset_result_page)

        # 注入适配器到 ResultPage
        source_pages = [
            ("角色武器", self._adapter_char_base, "char_base"),
            ("共鸣链效果", self._adapter_entries, "combined_perm"),
        ]
        self._preset_result_page.set_external_sources(source_pages)
        self._preset_result_page.set_defense_page(self._adapter_defense)
        self._preset_result_page.set_resistance_page(self._adapter_resistance)
        self._preset_result_page.set_indep_zone_page(self._adapter_indep)
        self._preset_result_page.set_keyword_assoc_page(self._adapter_keyword)

        # 注入适配器到 ResultListPage
        self._preset_result_list.set_external_sources(source_pages)
        self._preset_result_list.set_defense_page(self._adapter_defense)
        self._preset_result_list.set_resistance_page(self._adapter_resistance)
        self._preset_result_list.set_indep_zone_page(self._adapter_indep)
        self._preset_result_list.set_keyword_assoc_page(self._adapter_keyword)

        # 切换到计算相关页时同步适配器数据
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # 应用父级持久化的自动更新状态
        if self._pending_auto_state:
            self._toggle_preset_auto()

        # 查看文本描述 + 保存按钮
        save_row = QHBoxLayout()
        save_row.addStretch()
        desc_btn = QPushButton("查看文本描述")
        desc_btn.setObjectName("backButton")
        desc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        desc_btn.clicked.connect(self._show_text_description)
        save_row.addWidget(desc_btn)
        save_btn = QPushButton("💾 保存角色预设")
        save_btn.setObjectName("presetSaveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_row.addWidget(save_btn)
        main_layout.addLayout(save_row)
        self.save_clicked = save_btn.clicked

    def _show_text_description(self):
        """生成当前角色预设的文本描述并展示"""
        lines = []
        lines.append("═" * 50)
        lines.append("【角色预设】")
        name = self.char_name.text().strip() or "(未命名)"
        lines.append(f"名称: {name}")
        lines.append(f"元素: {self.char_element.currentText()}    效应: {self.char_effect.currentText()}")
        lines.append(f"基础数值: HP={self.base_hp.value():.0f}, ATK={self.base_atk.value():.0f}, DEF={self.base_def.value():.0f}")
        rp = self._preset_result_page
        lines.append(f"倍率设置: 基础倍率={rp.base_mult.value():.1f}%, 倍率增加={rp.mult_increase.value():.1f}%")
        for i, s in enumerate(rp.mult_boosts):
            lines.append(f"          倍率提升{i + 1}={s.value():.1f}%")
        lines.append("")

        items = self._resonance_page.get_items()
        for it in items:
            enabled = "已启用" if it.get("enabled", True) else "已关闭"
            lines.append(f"── {it['name']} [{enabled}] ──")
            intro = it.get("intro", "")
            if intro:
                lines.append(f"  介绍: {intro}")
            effects = it.get("effects", [])
            if effects:
                lines.append(f"  效果 ({len(effects)} 条):")
                for eff in effects:
                    kw = f" [关键词: {eff.get('keywords', '')}]" if eff.get('keywords', '') else ""
                    lines.append(f"    {eff.get('type', '常驻')}: {eff.get('name', '')} +{eff.get('value', 0):.1f}%  (来源: {eff.get('source', '')}){kw}")
            else:
                lines.append("  效果: (无)")
            indep_zones = it.get("indep_zones", [])
            if indep_zones:
                lines.append(f"  独立乘区 ({len(indep_zones)} 组):")
                for iz in indep_zones:
                    lines.append(f"    组名: {iz.get('group_name', '')}")
                    for v in iz.get("values", []):
                        hidden = " [隐藏]" if v.get("hidden", False) else ""
                        lines.append(f"      {v.get('name', '')} = {v.get('value', 0):.1f}%{hidden}")
            else:
                lines.append("  独立乘区: (无)")
            lines.append("")

        # 技能增益
        lines.append("── 技能增益 ──")
        skill_effs = (
            self._collect_skill_table(self._skill_perm_table, "常驻")
            + self._collect_skill_table(self._skill_trig_table, "触发")
        )
        if skill_effs:
            lines.append(f"  效果 ({len(skill_effs)} 条):")
            for eff in skill_effs:
                lines.append(f"    {eff.get('type', '常驻')}: {eff.get('name', '')} +{eff.get('value', 0):.1f}%  (来源: {eff.get('source', '')})")
        else:
            lines.append("  效果: (无)")
        skill_iz = [iz.to_dict() for iz in self._skill_indep_groups]
        if skill_iz:
            lines.append(f"  独立乘区 ({len(skill_iz)} 组):")
            for iz in skill_iz:
                lines.append(f"    组名: {iz.get('group_name', '')}")
                for v in iz.get("values", []):
                    hidden = " [隐藏]" if v.get("hidden", False) else ""
                    lines.append(f"      {v.get('name', '')} = {v.get('value', 0):.1f}%{hidden}")
        else:
            lines.append("  独立乘区: (无)")
        lines.append("")
        lines.append("═" * 50)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"文本描述 - {name}")
        dlg.setMinimumSize(550, 500)
        dlg.resize(600, 600)
        dl = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText("\n".join(lines))
        dl.addWidget(te)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("backButton")
        close_btn.clicked.connect(dlg.accept)
        dl.addWidget(close_btn)
        dlg.exec()

    def reject(self):
        reply = QMessageBox.question(
            self, "退出角色预设", "确定要退出角色预设窗口吗？\n未保存的更改将丢失。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            super().reject()

    def _center(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def _apply_theme(self):
        """继承主程序主题"""
        try:
            from theme_system import THEMES, build_stylesheet
            w = self.parent()
            while w is not None:
                if hasattr(w, 'current_theme') and w.current_theme in THEMES:
                    self.setStyleSheet(build_stylesheet(w.current_theme))
                    return
                w = w.parent()
            self.setStyleSheet(build_stylesheet("dark"))
        except Exception:
            pass

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

    def _toggle_preset_auto(self):
        """切换预设窗口的自动更新状态，同步 ResultPage 和 ResultListPage"""
        rp = self._preset_result_page
        rlp = self._preset_result_list
        new_state = not rp._auto_compute

        # 同步 ResultPage
        rp._auto_compute = new_state
        if new_state:
            rp.auto_compute_btn.setText("关闭自动更新")
            rp.auto_compute_btn.setStyleSheet(rp._AUTO_ON_STYLE)
        else:
            rp.auto_compute_btn.setText("开启自动更新")
            rp.auto_compute_btn.setStyleSheet(rp._AUTO_OFF_STYLE)

        # 同步 ResultListPage
        rlp._auto_update = new_state
        if new_state:
            rlp.auto_update_btn.setText("关闭自动更新")
            rlp.auto_update_btn.setStyleSheet(rlp._AUTO_ON_STYLE)
        else:
            rlp.auto_update_btn.setText("开启自动更新")
            rlp.auto_update_btn.setStyleSheet(rlp._AUTO_OFF_STYLE)

        # 更新预设窗口按钮
        if new_state:
            self._preset_auto_btn.setText("关闭自动更新")
            self._preset_auto_btn.setStyleSheet(self._AUTO_ON_STYLE)
            self._sync_adapters()
            rp.compute()
        else:
            self._preset_auto_btn.setText("开启自动更新")
            self._preset_auto_btn.setStyleSheet(self._AUTO_OFF_STYLE)

        # 持久化状态到父级 PresetBuilderDialog
        p = self.parent()
        if p is not None and hasattr(p, '_auto_update_enabled'):
            p._auto_update_enabled = new_state

    def _on_preset_data_changed(self):
        """基础数值/倍率变更时，若自动更新开启则重新计算"""
        if self._preset_result_page._auto_compute:
            self._sync_adapters()
            self._preset_result_page.compute()

    # ── 页面1: 基本内容 ──

    def _build_basic_tab(self):
        layout = QVBoxLayout(self.tab_basic)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 基本信息
        basic = QGroupBox("基本信息")
        basic_form = QFormLayout(basic)
        basic_form.setSpacing(6)
        self.preset_name_edit = QLineEdit()
        self.preset_name_edit.setPlaceholderText("预设文件名称")
        basic_form.addRow("预设名称:", self.preset_name_edit)
        self.author_edit = QLineEdit()
        self.author_edit.hide()
        self.char_name = QLineEdit()
        self.char_name.setPlaceholderText("角色名称")
        self.char_name.textChanged.connect(self._sync_chain_names)
        basic_form.addRow("角色名称:", self.char_name)
        elem_row = QHBoxLayout()
        self.char_element = QComboBox()
        self.char_element.addItems(ELEMENTS)
        elem_row.addWidget(self.char_element)
        self.char_effect = QComboBox()
        self.char_effect.addItems(EFFECTS)
        elem_row.addWidget(QLabel("  效应:"))
        elem_row.addWidget(self.char_effect)
        elem_row.addStretch()
        basic_form.addRow("元素:", elem_row)
        layout.addWidget(basic)

        # 基础数值
        stats = QGroupBox("基础数值")
        stats_form = QFormLayout(stats)
        stats_form.setSpacing(4)
        self.base_hp = QDoubleSpinBox()
        self.base_hp.setRange(1, 100000)
        self.base_hp.setDecimals(0)
        self.base_hp.setValue(1)
        stats_form.addRow("基础生命值:", self.base_hp)
        self.base_atk = QDoubleSpinBox()
        self.base_atk.setRange(1, 10000)
        self.base_atk.setDecimals(0)
        self.base_atk.setValue(1)
        stats_form.addRow("基础攻击力:", self.base_atk)
        self.base_def = QDoubleSpinBox()
        self.base_def.setRange(1, 10000)
        self.base_def.setDecimals(0)
        self.base_def.setValue(1)
        stats_form.addRow("基础防御力:", self.base_def)
        layout.addWidget(stats)

        # 基础数值变更时触发自动计算
        for sp in (self.base_hp, self.base_atk, self.base_def):
            sp.valueChanged.connect(self._on_preset_data_changed)

        # 访问官方维基按钮
        wiki_btn = QPushButton("访问官方维基")
        wiki_btn.setObjectName("backButton")
        wiki_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wiki_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://wiki.kurobbs.com/mc/home")))
        layout.addWidget(wiki_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

    # ── 页面2: 共鸣链 ──

    def _build_chain_tab(self):
        """嵌入主程序的 ResonanceBuffPage，数据格式完全一致"""
        from WWDmgCalc import ResonanceBuffPage
        self._resonance_page = ResonanceBuffPage(main_screen=None)
        tab_layout = QVBoxLayout(self.tab_chain)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(self._resonance_page)

    def _sync_chain_names(self):
        """角色名称变更时自动联动更新所有共鸣链名称"""
        if not hasattr(self, '_resonance_page'):
            return
        name = self.char_name.text().strip()
        self._resonance_page._prefix = name if name else ""
        for i, it in enumerate(self._resonance_page._items):
            it["name"] = f"{name}的共鸣链{i + 1}" if name else f"共鸣链{i + 1}"
        self._resonance_page._refresh_cards()

    # ── 技能增益页 ──

    def _build_skill_buff_tab(self):
        """技能增益页：常驻/触发效果 + 独立乘区，照搬通用增益"""
        tab_layout = QVBoxLayout(self.tab_skill_buff)
        tab_layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("技能增益")
        title.setObjectName("sectionTitle"); tab_layout.addWidget(title)
        desc = QLabel("管理角色技能页的常驻效果和触发效果，并添加独立乘区组")
        desc.setObjectName("labelSecondary"); desc.setWordWrap(True); tab_layout.addWidget(desc)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_widget = QWidget(); scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(4, 4, 4, 4); scroll_layout.setSpacing(12)

        SearchCombo, WEAPON_RESONANCE_ATTRS = _get_search_combo()

        # 常驻效果
        perm_group = QGroupBox("常驻效果"); perm_group.setMinimumHeight(350)
        perm_layout = QVBoxLayout(perm_group)
        perm_input = QHBoxLayout()
        self._skill_perm_combo = SearchCombo(WEAPON_RESONANCE_ATTRS); self._skill_perm_combo.lineEdit().setPlaceholderText("输入搜索...")
        perm_input.addWidget(self._skill_perm_combo, stretch=3)
        self._skill_perm_value = QDoubleSpinBox(); self._skill_perm_value.setRange(0, 99999); self._skill_perm_value.setDecimals(4); self._skill_perm_value.setFixedWidth(100)
        perm_input.addWidget(self._skill_perm_value); perm_input.addWidget(QLabel("%"))
        self._skill_perm_source = QComboBox(); self._skill_perm_source.addItems(SOURCES); self._skill_perm_source.setCurrentText("技能效果"); self._skill_perm_source.setMinimumWidth(100)
        perm_input.addWidget(self._skill_perm_source)
        add_perm = QPushButton("添加"); add_perm.setObjectName("addButton"); add_perm.setFixedWidth(50); add_perm.setCursor(Qt.CursorShape.PointingHandCursor)
        add_perm.clicked.connect(lambda: self._add_skill_row("perm")); perm_input.addWidget(add_perm); perm_layout.addLayout(perm_input)
        self._skill_perm_combo.lineEdit().returnPressed.connect(lambda: self._add_skill_row("perm"))
        self._skill_perm_table = self._make_skill_table(show_kw=False); perm_layout.addWidget(self._skill_perm_table); scroll_layout.addWidget(perm_group)

        # 触发效果
        trig_group = QGroupBox("触发效果"); trig_group.setMinimumHeight(350)
        trig_layout = QVBoxLayout(trig_group)
        trig_input = QHBoxLayout()
        self._skill_trig_combo = SearchCombo(WEAPON_RESONANCE_ATTRS); self._skill_trig_combo.lineEdit().setPlaceholderText("输入搜索...")
        trig_input.addWidget(self._skill_trig_combo, stretch=3)
        self._skill_trig_value = QDoubleSpinBox(); self._skill_trig_value.setRange(0, 99999); self._skill_trig_value.setDecimals(4); self._skill_trig_value.setFixedWidth(100)
        trig_input.addWidget(self._skill_trig_value); trig_input.addWidget(QLabel("%"))
        self._skill_trig_source = QComboBox(); self._skill_trig_source.addItems(SOURCES); self._skill_trig_source.setCurrentText("技能效果"); self._skill_trig_source.setMinimumWidth(100)
        trig_input.addWidget(self._skill_trig_source)
        add_trig = QPushButton("添加"); add_trig.setObjectName("addButton"); add_trig.setFixedWidth(50); add_trig.setCursor(Qt.CursorShape.PointingHandCursor)
        add_trig.clicked.connect(lambda: self._add_skill_row("trig")); trig_input.addWidget(add_trig); trig_layout.addLayout(trig_input)
        self._skill_trig_combo.lineEdit().returnPressed.connect(lambda: self._add_skill_row("trig"))
        self._skill_trig_table = self._make_skill_table(show_kw=False); trig_layout.addWidget(self._skill_trig_table); scroll_layout.addWidget(trig_group)

        # 独立乘区
        iz_label = QLabel("独立乘区组"); iz_label.setObjectName("labelSecondary")
        iz_label.setStyleSheet("font-size: 13px; font-weight: 600; margin-top: 8px;"); scroll_layout.addWidget(iz_label)
        self._skill_indep_container = QVBoxLayout(); self._skill_indep_container.setSpacing(6); scroll_layout.addLayout(self._skill_indep_container)
        self._skill_indep_groups = []
        add_iz_btn = QPushButton("+ 添加独立乘区组"); add_iz_btn.setObjectName("addButton"); add_iz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_iz_btn.clicked.connect(self._add_skill_indep_group); scroll_layout.addWidget(add_iz_btn)
        scroll_layout.addStretch(); scroll.setWidget(scroll_widget); tab_layout.addWidget(scroll)

        self._skill_perm_counter = 0; self._skill_trig_counter = 0

    def _make_skill_table(self, show_kw=True):
        cols = 8 if show_kw else 7
        headers = ["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"] if not show_kw else ["名称", "副名称", "序列号", "数值", "取值", "来源", "关键词关联", "操作"]
        t = QTableWidget(); t.setObjectName("attrTable"); t.setColumnCount(cols)
        t.setHorizontalHeaderLabels(headers); t.verticalHeader().setVisible(False)
        h = t.horizontalHeader(); h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, cols): h.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        if show_kw:
            h.resizeSection(1, 130); h.resizeSection(2, 120); h.resizeSection(3, 140)
            h.resizeSection(4, 70); h.resizeSection(5, 100); h.resizeSection(6, 120); h.resizeSection(7, 100)
        else:
            h.resizeSection(1, 130); h.resizeSection(2, 120); h.resizeSection(3, 140)
            h.resizeSection(4, 70); h.resizeSection(5, 100); h.resizeSection(6, 100)
        return t

    def _add_skill_row(self, kind):
        if kind == "perm":
            combo, val, src, etype, prefix, table = self._skill_perm_combo, self._skill_perm_value, self._skill_perm_source, "常驻", "常驻", self._skill_perm_table
            self._skill_perm_counter += 1
        else:
            combo, val, src, etype, prefix, table = self._skill_trig_combo, self._skill_trig_value, self._skill_trig_source, "触发", "触发", self._skill_trig_table
            self._skill_trig_counter += 1
        name = combo.currentText().strip()
        if not name: return
        self._add_skill_table_row(table, name, val.value(), src.currentText(), etype, prefix)
        combo.lineEdit().clear(); val.setValue(0)

    def _add_skill_table_row(self, table, name, value, source, eff_type, seq_prefix, sub_name_text="", keywords="", show_kw=True):
        from WWDmgCalc import _make_sub_name_cell
        ri = table.rowCount(); table.insertRow(ri); table.setRowHeight(ri, 42)
        ne = QLineEdit(name); ne.setObjectName("nameEdit"); ne.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 0, ne)
        sn = QLineEdit(sub_name_text); sn.setObjectName("nameEdit"); sn.setAlignment(Qt.AlignmentFlag.AlignCenter); sn.setPlaceholderText("（备注）")
        table.setCellWidget(ri, 1, _make_sub_name_cell(sn, lambda: name))
        seq = QLabel(f"{seq_prefix}{ri + 1}"); seq.setObjectName("seqLabel"); seq.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 2, seq)
        vs = QDoubleSpinBox(); vs.setObjectName("itemValueSpin"); vs.setRange(0, 99999); vs.setDecimals(4); vs.setValue(value); vs.setFixedWidth(120); vs.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 3, vs)
        ul = QLabel("百分比"); ul.setObjectName("unitLabel"); ul.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 4, ul)
        sl = QLabel(source); sl.setObjectName("seqLabel"); sl.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 5, sl)
        ops_col = 7 if show_kw else 6
        ops = QWidget(); ol = QHBoxLayout(ops); ol.setContentsMargins(2, 0, 2, 0); ol.setSpacing(3)
        db = QPushButton("删除"); db.setObjectName("itemDeleteBtn"); db.setFixedSize(55, 28); db.setCursor(Qt.CursorShape.PointingHandCursor)
        def _del():
            s = self.sender()
            for r in range(table.rowCount()):
                ow = table.cellWidget(r, ops_col)
                if ow and s in ow.findChildren(QPushButton): table.removeRow(r); return
        db.clicked.connect(_del); ol.addWidget(db); table.setCellWidget(ri, ops_col, ops)

    def _collect_skill_table(self, table, eff_type):
        from WWDmgCalc import _get_sub_name_text
        result = []
        for row in range(table.rowCount()):
            ne = table.cellWidget(row, 0); sn = table.cellWidget(row, 1)
            vs = table.cellWidget(row, 3); sl = table.cellWidget(row, 5)
            if ne and vs:
                result.append({
                    "name": ne.text().strip(), "value": vs.value(), "type": eff_type,
                    "source": sl.text() if sl else "技能效果",
                    "sub_name": _get_sub_name_text(sn),
                })
        return result

    def _add_skill_indep_group(self):
        gb = _IndepZoneGroupBox("", [])
        gb.del_group_btn.clicked.connect(lambda _checked=False, g=gb: self._remove_skill_indep_group(g))
        self._skill_indep_container.addWidget(gb); self._skill_indep_groups.append(gb)

    def _remove_skill_indep_group(self, gb):
        if gb in self._skill_indep_groups:
            self._skill_indep_groups.remove(gb)
            self._skill_indep_container.removeWidget(gb)
            gb.hide(); gb.setParent(None); gb.deleteLater()

    # ── 页面4: 计算结果 ──

    def _build_calc_tab(self):
        """页面4: 计算结果（嵌入主程序 ResultPage）"""
        layout = QVBoxLayout(self.tab_calc)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._preset_result_page)
        layout.addWidget(scroll)

    def _build_result_list_tab(self):
        """页面5: 结果列表（嵌入主程序 ResultListPage）"""
        layout = QVBoxLayout(self.tab_result_list)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._preset_result_list)
        layout.addWidget(scroll)

    def _sync_adapters(self):
        """将预设数据同步到适配器，供 ResultPage/ResultListPage 计算使用"""
        self._adapter_char_base.update(
            self.base_hp.value(), self.base_atk.value(), self.base_def.value())
        # 从 ResonanceBuffPage 读取共鸣链效果（仅已启用的链）
        items = self._resonance_page.get_items()
        chain_data = [
            {"effects": it["effects"], "indep_zones": it.get("indep_zones", [])}
            for it in items if it.get("enabled", True)
        ]
        self._adapter_entries.update_from_chain_data(chain_data)
        self._adapter_indep.update_from_chain_data(chain_data)
        # 追加技能增益效果
        skill_effects = (
            self._collect_skill_table(self._skill_perm_table, "常驻")
            + self._collect_skill_table(self._skill_trig_table, "触发")
        )
        for se in skill_effects:
            name = se.get("name", "")
            if not name: continue
            self._adapter_entries._entries.append((
                name, se.get("value", 0.0), False,
                se.get("source", "技能效果"), f"技能{se.get('type', '')}", se.get("sub_name", ""),
            ))
        # 追加技能增益独立乘区
        for iz in self._skill_indep_groups:
            d = iz.to_dict()
            if d.get("values"):
                self._adapter_indep._groups.append(d)

        self._adapters_dirty = False

    def _on_tab_changed(self, index):
        """切换到计算/结果页时同步数据并触发计算"""
        widget = self.tabs.widget(index)
        if widget in (self.tab_calc, self.tab_result_list):
            self._sync_adapters()
            if widget is self.tab_calc:
                self._preset_result_page.compute()

    def to_dict(self):
        rp = self._preset_result_page
        return {
            "name": self.char_name.text().strip(),
            "element": self.char_element.currentText(),
            "effect": self.char_effect.currentText(),
            "base_hp": self.base_hp.value(),
            "base_atk": self.base_atk.value(),
            "base_def": self.base_def.value(),
            "multiplier": {
                "base_mult": rp.base_mult.value(),
                "mult_increase": rp.mult_increase.value(),
                "mult_boosts": [s.value() for s in rp.mult_boosts],
            },
            "resonance_chain": [
                {
                    "effects": it["effects"],
                    "indep_zones": it.get("indep_zones", []),
                    "intro": it.get("intro", ""),
                }
                for it in self._resonance_page.get_items()
            ],
            "skill_buff": {
                "effects": (
                    self._collect_skill_table(self._skill_perm_table, "常驻")
                    + self._collect_skill_table(self._skill_trig_table, "触发")
                ),
                "indep_zones": [iz.to_dict() for iz in self._skill_indep_groups],
            },
            "result_list": self._preset_result_list.collect_data(),
        }

    def load_data(self, data):
        self.char_name.setText(data.get("name", ""))
        elem = data.get("element", "")
        if elem:
            idx = self.char_element.findText(elem)
            if idx >= 0:
                self.char_element.setCurrentIndex(idx)
        eff = data.get("effect", "(无)")
        idx = self.char_effect.findText(eff)
        if idx >= 0:
            self.char_effect.setCurrentIndex(idx)
        self.base_hp.setValue(data.get("base_hp", 1))
        self.base_atk.setValue(data.get("base_atk", 1))
        self.base_def.setValue(data.get("base_def", 1))
        # 倍率写入 ResultPage
        rp = self._preset_result_page
        mult = data.get("multiplier", {})
        rp.base_mult.setValue(mult.get("base_mult", 100.0))
        rp.mult_increase.setValue(mult.get("mult_increase", 0.0))
        for _i, _v in enumerate(mult.get("mult_boosts", [0, 0, 0])):
            if _i < len(rp.mult_boosts):
                rp.mult_boosts[_i].setValue(_v)
        chains = data.get("resonance_chain", [])
        items = self._resonance_page.get_items()
        for i, it in enumerate(items):
            if i < len(chains):
                ch = chains[i]
                it["effects"] = ch.get("effects", [])
                it["indep_zones"] = ch.get("indep_zones", [])
                it["intro"] = ch.get("intro", "")
            else:
                it["effects"] = []
                it["indep_zones"] = []
                it["intro"] = ""
        self._resonance_page._refresh_cards()
        # 恢复技能增益
        skill = data.get("skill_buff", {})
        self._skill_perm_table.setRowCount(0); self._skill_trig_table.setRowCount(0)
        self._skill_perm_counter = 0; self._skill_trig_counter = 0
        for eff in skill.get("effects", []):
            et = eff.get("type", "常驻")
            if et == "触发":
                self._skill_trig_counter += 1
                self._add_skill_table_row(self._skill_trig_table, eff.get("name", ""), eff.get("value", 0.0), eff.get("source", "技能效果"), "触发", "触发", eff.get("sub_name", ""), show_kw=False)
            else:
                self._skill_perm_counter += 1
                self._add_skill_table_row(self._skill_perm_table, eff.get("name", ""), eff.get("value", 0.0), eff.get("source", "技能效果"), "常驻", "常驻", eff.get("sub_name", ""), show_kw=False)
        # 恢复技能增益独立乘区
        for gb in list(self._skill_indep_groups):
            self._skill_indep_container.removeWidget(gb); gb.hide(); gb.setParent(None); gb.deleteLater()
        self._skill_indep_groups.clear()
        for iz_data in skill.get("indep_zones", []):
            gb = _IndepZoneGroupBox(iz_data.get("group_name", ""), iz_data.get("values", []))
            gb.del_group_btn.clicked.connect(lambda _checked=False, g=gb: self._remove_skill_indep_group(g))
            self._skill_indep_container.addWidget(gb); self._skill_indep_groups.append(gb)
        # 恢复结果列表
        rl_data = data.get("result_list", [])
        if rl_data:
            self._preset_result_list.apply_data(rl_data)
        self._adapters_dirty = True


# ═══════════════════════════════════════════════════════════════
# 武器预设窗口（分页式）
# ═══════════════════════════════════════════════════════════════

class _WeaponPresetWindow(QDialog):
    """武器预设窗口 —— 2 页分页设计"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("武器预设")
        self.setMinimumSize(1000, 700)
        self.resize(1050, 750)
        _fit_to_screen(self, 1050)

        QTimer.singleShot(0, lambda: self._center())

        # 继承主程序主题
        self._apply_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        back_btn = QPushButton("← 返回总界面")
        back_btn.setObjectName("backButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedWidth(140)
        main_layout.addWidget(back_btn)
        self.back_clicked = back_btn.clicked

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        # ── 页面1: 基本内容 ──
        self.tab_basic = QWidget()
        self._build_basic_tab()
        self.tabs.addTab(self.tab_basic, "基本内容")

        # ── 页面2: 阶段等级 ──
        self.tab_refine = QWidget()
        self._ref_data = []
        self._ref_cards = []
        # 初始化 5 个等阶数据
        for _i in range(5):
            self._ref_data.append({"effects": [], "indep_zones": [], "resonance_desc": ""})
        self._build_refine_tab()
        self.tabs.addTab(self.tab_refine, "阶段等级")

        # 查看文本描述 + 保存按钮
        save_row = QHBoxLayout()
        save_row.addStretch()
        desc_btn = QPushButton("查看文本描述")
        desc_btn.setObjectName("backButton")
        desc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        desc_btn.clicked.connect(self._show_text_description)
        save_row.addWidget(desc_btn)
        save_btn = QPushButton("💾 保存武器预设")
        save_btn.setObjectName("presetSaveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_row.addWidget(save_btn)
        main_layout.addLayout(save_row)
        self.save_clicked = save_btn.clicked

    def _show_text_description(self):
        """生成当前武器预设的文本描述并展示"""
        lines = []
        lines.append("═" * 50)
        lines.append("【武器预设】")
        name = self.weapon_name.text().strip() or "(未命名)"
        lines.append(f"名称: {name}")
        lines.append(f"基础攻击力: {self.weapon_base_atk.value():.0f}")
        bonus_type, bonus_value = self._get_selected_bonus()
        if bonus_type:
            lines.append(f"附加属性: {bonus_type} +{bonus_value:.1f}%")
        else:
            lines.append("附加属性: (无)")
        lines.append("")

        for i, cd in enumerate(self._ref_data):
            ri = i + 1
            desc_text = cd.get("resonance_desc", "")
            lines.append(f"── 等阶 {ri} ──")
            if desc_text:
                lines.append(f"  谐振描述: {desc_text}")
            effects = cd.get("effects", [])
            if effects:
                lines.append(f"  效果 ({len(effects)} 条):")
                for eff in effects:
                    kw = f" [关键词: {eff.get('keywords', '')}]" if eff.get('keywords', '') else ""
                    lines.append(f"    {eff.get('type', '常驻')}: {eff.get('name', '')} +{eff.get('value', 0):.1f}%  (来源: {eff.get('source', '')}){kw}")
            else:
                lines.append("  效果: (无)")
            indep_zones = cd.get("indep_zones", [])
            if indep_zones:
                lines.append(f"  独立乘区 ({len(indep_zones)} 组):")
                for iz in indep_zones:
                    lines.append(f"    组名: {iz.get('group_name', '')}")
                    for v in iz.get("values", []):
                        hidden = " [隐藏]" if v.get("hidden", False) else ""
                        lines.append(f"      {v.get('name', '')} = {v.get('value', 0):.1f}%{hidden}")
            else:
                lines.append("  独立乘区: (无)")
            lines.append("")
        lines.append("═" * 50)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"文本描述 - {name}")
        dlg.setMinimumSize(550, 500)
        dlg.resize(600, 600)
        dl = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText("\n".join(lines))
        dl.addWidget(te)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("backButton")
        close_btn.clicked.connect(dlg.accept)
        dl.addWidget(close_btn)
        dlg.exec()

    def reject(self):
        reply = QMessageBox.question(
            self, "退出武器预设", "确定要退出武器预设窗口吗？\n未保存的更改将丢失。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            super().reject()

    def _center(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def _apply_theme(self):
        """继承主程序主题"""
        try:
            from theme_system import THEMES, build_stylesheet
            w = self.parent()
            while w is not None:
                if hasattr(w, 'current_theme') and w.current_theme in THEMES:
                    self.setStyleSheet(build_stylesheet(w.current_theme))
                    return
                w = w.parent()
            self.setStyleSheet(build_stylesheet("dark"))
        except Exception:
            pass

    # ── 页面1: 基本内容 ──

    def _build_basic_tab(self):
        layout = QVBoxLayout(self.tab_basic)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 基本信息
        basic = QGroupBox("基本信息")
        basic_form = QFormLayout(basic)
        basic_form.setSpacing(6)
        self.preset_name_edit = QLineEdit()
        self.preset_name_edit.setPlaceholderText("预设文件名称")
        basic_form.addRow("预设名称:", self.preset_name_edit)
        self.author_edit = QLineEdit()
        self.author_edit.hide()
        self.weapon_name = QLineEdit()
        self.weapon_name.setPlaceholderText("武器名称")
        basic_form.addRow("武器名称:", self.weapon_name)
        self.weapon_base_atk = QDoubleSpinBox()
        self.weapon_base_atk.setRange(0, 10000)
        self.weapon_base_atk.setDecimals(0)
        basic_form.addRow("基础攻击力:", self.weapon_base_atk)
        layout.addWidget(basic)

        # 附加属性
        bonus = QGroupBox("附加属性（仅勾选一项）")
        bonus_layout = QVBoxLayout(bonus)
        self._bonus_checkboxes = []
        for btype in WEAPON_BONUS_TYPES:
            row = QHBoxLayout()
            row.setSpacing(8)
            cb = QCheckBox(btype)
            spin = QDoubleSpinBox()
            spin.setRange(0, 500)
            spin.setDecimals(4)
            spin.setEnabled(False)
            spin.setVisible(False)
            unit = QLabel("%")
            unit.setVisible(False)
            cb.toggled.connect(lambda checked, c=cb, s=spin, u=unit:
                               self._on_bonus_toggled(c, checked, s, u))
            row.addWidget(cb)
            row.addWidget(spin)
            row.addWidget(unit)
            row.addStretch()
            bonus_layout.addLayout(row)
            self._bonus_checkboxes.append((cb, spin, unit))
        layout.addWidget(bonus)

        # 访问官方维基按钮
        wiki_btn = QPushButton("访问官方维基")
        wiki_btn.setObjectName("backButton")
        wiki_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wiki_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://wiki.kurobbs.com/mc/home")))
        layout.addWidget(wiki_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

    def _on_bonus_toggled(self, checked_cb, checked, spin, unit):
        if checked:
            for cb, s, u in self._bonus_checkboxes:
                if cb is not checked_cb:
                    cb.setChecked(False)
                    s.setVisible(False)
                    s.setEnabled(False)
                    u.setVisible(False)
            spin.setVisible(True)
            spin.setEnabled(True)
            unit.setVisible(True)
        else:
            spin.setVisible(False)
            spin.setEnabled(False)
            unit.setVisible(False)

    # ── 页面2: 阶段等级 ──

    def _build_refine_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        for i in range(1, 6):
            card = _CompactCard(f"等阶 {i}")
            card.set_info("暂无效果")
            idx = i
            card.set_expand_callback(lambda ii=idx: self._open_refine_edit(ii))
            self._ref_cards.append(card)
            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(container)
        tab_layout = QVBoxLayout(self.tab_refine)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

    def _open_refine_edit(self, ref_idx):
        cd = self._ref_data[ref_idx - 1]
        dlg = _EditDialog(
            f"等阶 {ref_idx} - 编辑效果", default_source="武器谐振", parent=self,
            intro_tab_label="武器谐振介绍",
            intro_title=f"编辑 等阶 {ref_idx} 的介绍信息：",
            intro_text=cd.get("resonance_desc", ""),
            intro_placeholder="在此输入武器谐振的介绍文本...")
        dlg.set_effects(cd["effects"])
        dlg.set_indep_zones(cd["indep_zones"])

        if dlg.exec() == QDialog.DialogCode.Accepted:
            cd["effects"] = dlg.get_effects()
            cd["indep_zones"] = dlg.get_indep_zones()
            cd["resonance_desc"] = dlg.get_intro_text()
            self._update_refine_summary(ref_idx - 1)

    def _update_refine_summary(self, ref_idx):
        cd = self._ref_data[ref_idx]
        eff_count = len(cd["effects"])
        iz_count = len(cd["indep_zones"])
        desc = cd.get("resonance_desc", "")
        if eff_count == 0 and iz_count == 0 and not desc:
            text = "暂无效果"
        else:
            parts = []
            if desc:
                parts.append(desc[:30] + ("..." if len(desc) > 30 else ""))
            if eff_count > 0:
                parts.append(f"{eff_count} 条效果")
            if iz_count > 0:
                parts.append(f"{iz_count} 组独立乘区")
            text = ", ".join(parts)
        self._ref_cards[ref_idx].set_info(text)

    def _get_selected_bonus(self):
        for cb, spin, unit in self._bonus_checkboxes:
            if cb.isChecked():
                return cb.text(), spin.value()
        return "", 0.0

    def to_dict(self):
        bonus_type, bonus_value = self._get_selected_bonus()
        return {
            "name": self.weapon_name.text().strip(),
            "base_atk": self.weapon_base_atk.value(),
            "bonus_type": bonus_type,
            "bonus_value": bonus_value,
            "refinement": [
                {
                    "resonance_desc": cd.get("resonance_desc", ""),
                    "effects": cd["effects"],
                    "indep_zones": cd["indep_zones"],
                }
                for cd in self._ref_data
            ],
        }

    def load_data(self, data):
        self.weapon_name.setText(data.get("name", ""))
        self.weapon_base_atk.setValue(data.get("base_atk", 0))
        bt = data.get("bonus_type", "")
        bv = data.get("bonus_value", 0.0)
        if bt:
            for cb, spin, unit in self._bonus_checkboxes:
                if cb.text() == bt:
                    cb.setChecked(True)
                    spin.setValue(bv)
                    break
        refs = data.get("refinement", [])
        for i, cd in enumerate(self._ref_data):
            if i < len(refs):
                ref = refs[i]
                cd["resonance_desc"] = ref.get("resonance_desc", "")
                cd["effects"] = ref.get("effects", [])
                cd["indep_zones"] = ref.get("indep_zones", [])
            else:
                cd["resonance_desc"] = ""
                cd["effects"] = []
                cd["indep_zones"] = []
            self._update_refine_summary(i)


# ═══════════════════════════════════════════════════════════════
# 角色增益预设窗口（抄综合填写常驻+触发双表格）
# ═══════════════════════════════════════════════════════════════

class _CharacterBuffWindow(QDialog):
    """角色增益预设 —— 3 页分页式（介绍 + 通用增益 + 特定增益）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("角色增益预设")
        self.setMinimumSize(1050, 650)
        self.resize(1100, 700)
        _fit_to_screen(self, 1100)
        QTimer.singleShot(0, lambda: self._center())
        self._apply_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        top_row = QHBoxLayout()
        back_btn = QPushButton("← 返回总界面")
        back_btn.setObjectName("backButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedWidth(140)
        top_row.addWidget(back_btn)
        self.back_clicked = back_btn.clicked
        top_row.addStretch()
        main_layout.addLayout(top_row)

        self._tabs = QTabWidget()
        main_layout.addWidget(self._tabs, stretch=1)

        self._build_intro_tab()
        self._build_general_tab()
        self._build_specific_tab()

        save_row = QHBoxLayout(); save_row.addStretch()
        desc_btn = QPushButton("查看文本描述"); desc_btn.setObjectName("backButton"); desc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        desc_btn.clicked.connect(self._show_text_description); save_row.addWidget(desc_btn)
        save_btn = QPushButton("💾 保存角色增益预设"); save_btn.setObjectName("presetSaveBtn"); save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_row.addWidget(save_btn); main_layout.addLayout(save_row)
        self.save_clicked = save_btn.clicked

    def _center(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def _apply_theme(self):
        try:
            from theme_system import ThemeSystem
            from PyQt6.QtWidgets import QApplication
            ts = ThemeSystem(); dark = getattr(QApplication.instance(), '_dark_mode', True)
            self.setStyleSheet(ts.apply_theme(dark))
        except Exception: pass

    # ═══ Tab 1: 角色增益介绍 ═══

    def _build_intro_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("预设名称:"))
        self.preset_name_edit = QLineEdit()
        self.preset_name_edit.setPlaceholderText("预设文件名称")
        name_row.addWidget(self.preset_name_edit, stretch=1)
        layout.addLayout(name_row)

        self.author_edit = QLineEdit()
        self.author_edit.hide()

        name_row2 = QHBoxLayout()
        name_row2.addWidget(QLabel("增益名称:"))
        self.buff_name = QLineEdit()
        self.buff_name.setPlaceholderText("例如：守岸人增益、维里奈增益")
        name_row2.addWidget(self.buff_name, stretch=1)
        layout.addLayout(name_row2)

        lbl = QLabel("编辑角色增益的介绍信息：")
        lbl.setObjectName("sectionTitle")
        lbl.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(lbl)

        self._intro_edit = QTextEdit()
        self._intro_edit.setObjectName("nameEdit")
        self._intro_edit.setPlaceholderText("在此输入角色增益的介绍文本...")
        layout.addWidget(self._intro_edit, stretch=1)

        self._tabs.addTab(tab, "角色增益介绍")

    # ═══ Tab 2: 通用增益 ═══

    def _build_general_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("通用增益")
        title.setObjectName("sectionTitle")
        tab_layout.addWidget(title)
        desc = QLabel("管理常驻效果和触发效果，并添加独立乘区组")
        desc.setObjectName("labelSecondary"); desc.setWordWrap(True)
        tab_layout.addWidget(desc)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_widget = QWidget(); scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(4, 4, 4, 4); scroll_layout.setSpacing(12)

        SearchCombo, WEAPON_RESONANCE_ATTRS = _get_search_combo()

        # 常驻效果
        perm_group = QGroupBox("常驻效果"); perm_group.setMinimumHeight(500)
        perm_layout = QVBoxLayout(perm_group)
        perm_input = QHBoxLayout()
        self._perm_combo = SearchCombo(WEAPON_RESONANCE_ATTRS); self._perm_combo.lineEdit().setPlaceholderText("输入搜索...")
        perm_input.addWidget(self._perm_combo, stretch=3)
        self._perm_value = QDoubleSpinBox(); self._perm_value.setRange(0, 99999); self._perm_value.setDecimals(4); self._perm_value.setFixedWidth(100)
        perm_input.addWidget(self._perm_value); perm_input.addWidget(QLabel("%"))
        self._perm_source = QComboBox(); self._perm_source.addItems(SOURCES); self._perm_source.setCurrentText("角色效果"); self._perm_source.setMinimumWidth(100)
        perm_input.addWidget(self._perm_source)
        add_perm = QPushButton("添加"); add_perm.setObjectName("addButton"); add_perm.setFixedWidth(50); add_perm.setCursor(Qt.CursorShape.PointingHandCursor)
        add_perm.clicked.connect(lambda: self._add_row("perm")); perm_input.addWidget(add_perm); perm_layout.addLayout(perm_input)
        self._perm_combo.lineEdit().returnPressed.connect(lambda: self._add_row("perm"))
        self._perm_table = self._make_table(show_kw=False); perm_layout.addWidget(self._perm_table); scroll_layout.addWidget(perm_group)

        # 触发效果
        trig_group = QGroupBox("触发效果"); trig_group.setMinimumHeight(500)
        trig_layout = QVBoxLayout(trig_group)
        trig_input = QHBoxLayout()
        self._trig_combo = SearchCombo(WEAPON_RESONANCE_ATTRS); self._trig_combo.lineEdit().setPlaceholderText("输入搜索...")
        trig_input.addWidget(self._trig_combo, stretch=3)
        self._trig_value = QDoubleSpinBox(); self._trig_value.setRange(0, 99999); self._trig_value.setDecimals(4); self._trig_value.setFixedWidth(100)
        trig_input.addWidget(self._trig_value); trig_input.addWidget(QLabel("%"))
        self._trig_source = QComboBox(); self._trig_source.addItems(SOURCES); self._trig_source.setCurrentText("角色效果"); self._trig_source.setMinimumWidth(100)
        trig_input.addWidget(self._trig_source)
        add_trig = QPushButton("添加"); add_trig.setObjectName("addButton"); add_trig.setFixedWidth(50); add_trig.setCursor(Qt.CursorShape.PointingHandCursor)
        add_trig.clicked.connect(lambda: self._add_row("trig")); trig_input.addWidget(add_trig); trig_layout.addLayout(trig_input)
        self._trig_combo.lineEdit().returnPressed.connect(lambda: self._add_row("trig"))
        self._trig_table = self._make_table(show_kw=False); trig_layout.addWidget(self._trig_table); scroll_layout.addWidget(trig_group)

        # 独立乘区
        iz_label = QLabel("独立乘区组"); iz_label.setObjectName("labelSecondary")
        iz_label.setStyleSheet("font-size: 13px; font-weight: 600; margin-top: 8px;"); scroll_layout.addWidget(iz_label)
        self._indep_container = QVBoxLayout(); self._indep_container.setSpacing(6); scroll_layout.addLayout(self._indep_container)
        self._indep_groups = []
        add_iz_btn = QPushButton("+ 添加独立乘区组"); add_iz_btn.setObjectName("addButton"); add_iz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_iz_btn.clicked.connect(self._add_indep_group); scroll_layout.addWidget(add_iz_btn)
        scroll_layout.addStretch(); scroll.setWidget(scroll_widget); tab_layout.addWidget(scroll)
        self._tabs.addTab(tab, "通用增益")

        self._perm_counter = 0; self._trig_counter = 0

    # ═══ Tab 3: 特定增益 ═══

    def _build_specific_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("特定增益")
        title.setObjectName("sectionTitle"); layout.addWidget(title)
        desc = QLabel("设置特定增益规则，选择效果后指定目标关键词卡片")
        desc.setObjectName("labelSecondary"); desc.setWordWrap(True); layout.addWidget(desc)

        SearchCombo, WEAPON_RESONANCE_ATTRS = _get_search_combo()
        spec_group = QGroupBox("特定增益"); spec_group.setMinimumHeight(300)
        spec_layout = QVBoxLayout(spec_group)
        spec_input = QHBoxLayout()
        self._spec_combo = SearchCombo(WEAPON_RESONANCE_ATTRS); self._spec_combo.lineEdit().setPlaceholderText("输入搜索...")
        spec_input.addWidget(self._spec_combo, stretch=3)
        self._spec_value = QDoubleSpinBox(); self._spec_value.setRange(0, 99999); self._spec_value.setDecimals(4); self._spec_value.setFixedWidth(100)
        spec_input.addWidget(self._spec_value); spec_input.addWidget(QLabel("%"))
        self._spec_source = QComboBox(); self._spec_source.addItems(SOURCES); self._spec_source.setCurrentText("角色效果"); self._spec_source.setMinimumWidth(100)
        spec_input.addWidget(self._spec_source)
        add_spec = QPushButton("添加"); add_spec.setObjectName("addButton"); add_spec.setFixedWidth(50); add_spec.setCursor(Qt.CursorShape.PointingHandCursor)
        add_spec.clicked.connect(lambda: self._add_row("spec")); spec_input.addWidget(add_spec); spec_layout.addLayout(spec_input)
        self._spec_combo.lineEdit().returnPressed.connect(lambda: self._add_row("spec"))
        self._spec_table = self._make_table(); spec_layout.addWidget(self._spec_table)
        layout.addWidget(spec_group)
        self._tabs.addTab(tab, "特定增益")
        self._spec_counter = 0

    # ═══ 表格/行/关键词/独立乘区 ═══

    def _make_table(self, show_kw=True):
        cols = 8 if show_kw else 7
        headers = ["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"] if not show_kw else ["名称", "副名称", "序列号", "数值", "取值", "来源", "关键词关联", "操作"]
        t = QTableWidget(); t.setObjectName("attrTable"); t.setColumnCount(cols)
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        h = t.horizontalHeader(); h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, cols): h.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        if show_kw:
            h.resizeSection(1, 130); h.resizeSection(2, 120); h.resizeSection(3, 140)
            h.resizeSection(4, 70); h.resizeSection(5, 100); h.resizeSection(6, 120); h.resizeSection(7, 100)
        else:
            h.resizeSection(1, 130); h.resizeSection(2, 120); h.resizeSection(3, 140)
            h.resizeSection(4, 70); h.resizeSection(5, 100); h.resizeSection(6, 100)
        return t

    def _add_row(self, kind):
        if kind == "perm":
            combo, val, src, etype, prefix, table = self._perm_combo, self._perm_value, self._perm_source, "常驻", "常驻", self._perm_table
            self._perm_counter += 1
        elif kind == "trig":
            combo, val, src, etype, prefix, table = self._trig_combo, self._trig_value, self._trig_source, "触发", "触发", self._trig_table
            self._trig_counter += 1
        else:
            combo, val, src, etype, prefix, table = self._spec_combo, self._spec_value, self._spec_source, "特定", "特定", self._spec_table
            self._spec_counter += 1
        name = combo.currentText().strip()
        if not name: return
        self._add_table_row(table, name, val.value(), src.currentText(), etype, prefix, show_kw=(kind == "spec"))
        combo.lineEdit().clear(); val.setValue(0)

    def _add_table_row(self, table, name, value, source, eff_type, seq_prefix, sub_name_text="", keywords="", show_kw=True):
        from WWDmgCalc import _make_sub_name_cell
        ri = table.rowCount(); table.insertRow(ri); table.setRowHeight(ri, 42)
        ne = QLineEdit(name); ne.setObjectName("nameEdit"); ne.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 0, ne)
        sn = QLineEdit(sub_name_text); sn.setObjectName("nameEdit"); sn.setAlignment(Qt.AlignmentFlag.AlignCenter); sn.setPlaceholderText("（备注）")
        table.setCellWidget(ri, 1, _make_sub_name_cell(sn, lambda: name))
        seq = QLabel(f"{seq_prefix}{ri + 1}"); seq.setObjectName("seqLabel"); seq.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 2, seq)
        vs = QDoubleSpinBox(); vs.setObjectName("itemValueSpin"); vs.setRange(0, 99999); vs.setDecimals(4); vs.setValue(value); vs.setFixedWidth(120); vs.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 3, vs)
        ul = QLabel("百分比"); ul.setObjectName("unitLabel"); ul.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 4, ul)
        sl = QLabel(source); sl.setObjectName("seqLabel"); sl.setAlignment(Qt.AlignmentFlag.AlignCenter); table.setCellWidget(ri, 5, sl)
        if show_kw:
            kb = QPushButton(keywords if keywords else "点击编辑"); kb.setObjectName("itemLockBtn"); kb.setFixedSize(110, 35); kb.setCursor(Qt.CursorShape.PointingHandCursor)
            kb.clicked.connect(lambda _, r=ri, t=table: self._edit_keywords(r, t)); table.setCellWidget(ri, 6, kb)
        ops_col = 7 if show_kw else 6
        ops = QWidget(); ol = QHBoxLayout(ops); ol.setContentsMargins(2, 0, 2, 0); ol.setSpacing(3)
        db = QPushButton("删除"); db.setObjectName("itemDeleteBtn"); db.setFixedSize(55, 28); db.setCursor(Qt.CursorShape.PointingHandCursor)
        def _del():
            s = self.sender()
            for r in range(table.rowCount()):
                ow = table.cellWidget(r, ops_col)
                if ow and s in ow.findChildren(QPushButton): table.removeRow(r); return
        db.clicked.connect(_del); ol.addWidget(db); table.setCellWidget(ri, ops_col, ops)

    def _edit_keywords(self, ri, table):
        kb = table.cellWidget(ri, 6)
        if not kb: return
        ck = kb.text() if kb.text() != "点击编辑" else ""
        cl = [k.strip() for k in ck.split(",") if k.strip()] if ck else []
        dlg = QDialog(self); dlg.setWindowTitle("编辑关键词关联"); dlg.setMinimumSize(400, 350); dlg.resize(450, 400)
        dl = QVBoxLayout(dlg); dl.setSpacing(10); dl.setContentsMargins(12, 12, 12, 12)
        dl.addWidget(QLabel("关键词关联")); dl.addWidget(QLabel("输入关键词后点击添加，留空则增益全部卡片"))
        ir = QHBoxLayout(); ki = QLineEdit(); ki.setPlaceholderText("输入关键词..."); ki.setObjectName("nameEdit"); ir.addWidget(ki, stretch=1)
        ab = QPushButton("添加"); ab.setObjectName("addButton"); ab.setFixedWidth(50); ab.setCursor(Qt.CursorShape.PointingHandCursor); ir.addWidget(ab); dl.addLayout(ir)
        kwl = QListWidget(); kwl.setObjectName("attrList")
        for kw in cl: kwl.addItem(kw)
        dl.addWidget(kwl, stretch=1)
        dkb = QPushButton("删除选中"); dkb.setObjectName("itemDeleteBtn"); dkb.setCursor(Qt.CursorShape.PointingHandCursor); dl.addWidget(dkb)
        def ak(): t = ki.text().strip(); t and t not in [kwl.item(i).text() for i in range(kwl.count())] and (kwl.addItem(t), ki.clear())
        ab.clicked.connect(ak); ki.returnPressed.connect(ak)
        def dk():
            for it in reversed(kwl.selectedItems()): kwl.takeItem(kwl.row(it))
        dkb.clicked.connect(dk)
        def ok(): kwb = ", ".join(kwl.item(i).text() for i in range(kwl.count())); kb.setText(kwb if kwb else "点击编辑"); dlg.close()
        br = QHBoxLayout(); br.addStretch(); ob = QPushButton("确定"); ob.setObjectName("addButton"); ob.setFixedWidth(80); ob.setCursor(Qt.CursorShape.PointingHandCursor); ob.clicked.connect(ok); br.addWidget(ob); dl.addLayout(br)
        dlg.exec()

    def _add_indep_group(self):
        gb = _IndepZoneGroupBox("", [])
        gb.del_group_btn.clicked.connect(lambda _checked=False, g=gb: self._remove_indep_group(g))
        self._indep_container.addWidget(gb); self._indep_groups.append(gb)

    def _remove_indep_group(self, gb):
        if gb in self._indep_groups:
            self._indep_groups.remove(gb); self._indep_container.removeWidget(gb)
            gb.hide(); gb.setParent(None); gb.deleteLater()

    # ═══ 数据访问 ═══

    def _collect_table(self, table, eff_type):
        from WWDmgCalc import _get_sub_name_text
        has_kw = table.columnCount() == 8
        effects = []
        for row in range(table.rowCount()):
            ne = table.cellWidget(row, 0); sn = table.cellWidget(row, 1); vs = table.cellWidget(row, 3); sl = table.cellWidget(row, 5)
            if ne and vs:
                eff = {"name": ne.text().strip(), "value": vs.value(), "type": eff_type,
                       "source": sl.text() if sl else "", "sub_name": _get_sub_name_text(sn)}
                if has_kw:
                    kb = table.cellWidget(row, 6)
                    eff["keywords"] = kb.text() if kb and kb.text() != "点击编辑" else ""
                effects.append(eff)
        return effects

    def to_dict(self):
        effects = self._collect_table(self._perm_table, "常驻")
        effects += self._collect_table(self._trig_table, "触发")
        effects += self._collect_table(self._spec_table, "特定")
        return {
            "name": self.buff_name.text().strip(),
            "intro": self._intro_edit.toPlainText() if self._intro_edit else "",
            "effects": effects,
            "indep_zones": [iz.to_dict() for iz in self._indep_groups],
        }

    def load_data(self, data):
        self.buff_name.setText(data.get("name", ""))
        if self._intro_edit:
            self._intro_edit.setPlainText(data.get("intro", ""))
        self._perm_table.setRowCount(0); self._trig_table.setRowCount(0); self._spec_table.setRowCount(0)
        self._perm_counter = 0; self._trig_counter = 0; self._spec_counter = 0
        for eff in data.get("effects", []):
            et = eff.get("type", "常驻")
            if et == "触发":
                self._trig_counter += 1
                self._add_table_row(self._trig_table, eff.get("name", ""), eff.get("value", 0.0), eff.get("source", ""), "触发", "触发", eff.get("sub_name", ""), show_kw=False)
            elif et == "特定":
                self._spec_counter += 1
                self._add_table_row(self._spec_table, eff.get("name", ""), eff.get("value", 0.0), eff.get("source", ""), "特定", "特定", eff.get("sub_name", ""), eff.get("keywords", ""), show_kw=True)
            else:
                self._perm_counter += 1
                self._add_table_row(self._perm_table, eff.get("name", ""), eff.get("value", 0.0), eff.get("source", ""), "常驻", "常驻", eff.get("sub_name", ""), show_kw=False)
        for iz_data in data.get("indep_zones", []):
            gb = _IndepZoneGroupBox(iz_data.get("group_name", ""), iz_data.get("values", []))
            gb.del_group_btn.clicked.connect(lambda _checked=False, g=gb: self._remove_indep_group(g))
            self._indep_container.addWidget(gb); self._indep_groups.append(gb)

    def reject(self):
        reply = QMessageBox.question(self, "退出角色增益预设", "确定要退出角色增益预设窗口吗？\n未保存的更改将丢失。",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: super().reject()

    def _show_text_description(self):
        lines = ["═" * 50, "【角色增益预设】", f"名称: {self.buff_name.text().strip() or '(未命名)'}", ""]
        if self._intro_edit:
            intro = self._intro_edit.toPlainText().strip()
            if intro: lines.append(f"介绍: {intro}"); lines.append("")
        for label, table in [("常驻效果", self._perm_table), ("触发效果", self._trig_table), ("特定增益", self._spec_table)]:
            count = table.rowCount()
            if count > 0:
                lines.append(f"── {label} ({count} 条) ──")
                for row in range(count):
                    ne = table.cellWidget(row, 0); vs = table.cellWidget(row, 3); sl = table.cellWidget(row, 5)
                    if ne and vs:
                        label_text = f"  {ne.text().strip()} +{vs.value():.1f}%  (来源: {sl.text() if sl else ''})"
                        if table.columnCount() == 8:
                            kb = table.cellWidget(row, 6)
                            kt = kb.text() if kb and kb.text() != "点击编辑" else ""
                            if kt: label_text += f" [关键词: {kt}]"
                        lines.append(label_text)
            else: lines.append(f"── {label} ──\n  (无)")
            lines.append("")
        indep = self._indep_groups
        if indep:
            lines.append(f"── 独立乘区 ({len(indep)} 组) ──")
            for iz in indep:
                d = iz.to_dict()
                lines.append(f"  组名: {d.get('group_name', '')}")
                for v in d.get("values", []):
                    h = " [隐藏]" if v.get("hidden", False) else ""
                    lines.append(f"    {v.get('name', '')} = {v.get('value', 0):.1f}%{h}")
            lines.append("")
        lines.append("═" * 50)
        dlg = QDialog(self); dlg.setWindowTitle("文本描述"); dlg.setMinimumSize(500, 450); dlg.resize(550, 500)
        dl = QVBoxLayout(dlg); te = QTextEdit(); te.setReadOnly(True); te.setPlainText("\n".join(lines)); dl.addWidget(te)
        cb = QPushButton("关闭"); cb.setObjectName("backButton"); cb.clicked.connect(dlg.accept); dl.addWidget(cb); dlg.exec()


# ═══════════════════════════════════════════════════════════════
# 声骸套装编辑器
# ═══════════════════════════════════════════════════════════════

class _EchoSetEditor(QDialog):
    """声骸套装预设编辑窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("声骸套装预设")
        self.setMinimumSize(1000, 650)
        self.resize(1050, 700)
        _fit_to_screen(self, 1050)

        QTimer.singleShot(0, lambda: self._center())
        self._apply_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        widget = QWidget()
        self._root = QVBoxLayout(widget)
        self._root.setSpacing(12)
        self._root.setContentsMargins(16, 16, 16, 24)

        title = QLabel("声骸套装预设")
        title.setObjectName("sectionTitle")
        self._root.addWidget(title)

        info = QGroupBox("套装信息")
        info_form = QFormLayout(info)
        info_form.setSpacing(6)
        self.preset_name_edit = QLineEdit()
        self.preset_name_edit.setPlaceholderText("预设文件名称")
        info_form.addRow("预设名称:", self.preset_name_edit)
        self.author_edit = QLineEdit()
        self.author_edit.hide()
        self.set_name = QLineEdit()
        self.set_name.setPlaceholderText("声骸套装名称")
        info_form.addRow("套装名称:", self.set_name)
        sc_row = QHBoxLayout()
        sc_row.addWidget(QLabel("套装阶段数:"))
        self.stage_count_spin = QSpinBox()
        self.stage_count_spin.setRange(1, 5)
        self.stage_count_spin.setValue(2)
        self.stage_count_spin.valueChanged.connect(self._on_stage_count_changed)
        sc_row.addWidget(self.stage_count_spin)
        sc_row.addStretch()
        info_form.addRow(sc_row)
        self._root.addWidget(info)

        stage_label = QLabel("阶段效果")
        stage_label.setObjectName("labelSecondary")
        stage_label.setStyleSheet("font-size: 15px; font-weight: 700; margin-top: 8px;")
        self._root.addWidget(stage_label)

        self._stage_data = []
        self._stage_cards = []
        self._stage_container = QVBoxLayout()
        self._stage_container.setSpacing(8)
        self._root.addLayout(self._stage_container)

        first_label = QLabel("首位声骸增益效果")
        first_label.setObjectName("labelSecondary")
        first_label.setStyleSheet("font-size: 15px; font-weight: 700; margin-top: 8px;")
        self._root.addWidget(first_label)

        self._first_data = {"effects": [], "indep_zones": [], "name": "", "intro": ""}
        self._first_card = _CompactCard("首位声骸增益")
        self._first_card.set_info("暂无效果")
        self._first_card.set_expand_callback(self._open_first_edit)
        self._root.addWidget(self._first_card)

        self._root.addSpacing(10)
        btn_row = QHBoxLayout()
        desc_btn = QPushButton("查看文本描述")
        desc_btn.setObjectName("backButton")
        desc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        desc_btn.clicked.connect(self._show_text_description)
        btn_row.addWidget(desc_btn)
        save_btn = QPushButton("💾 保存声骸套装预设")
        save_btn.setObjectName("presetSaveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(save_btn)
        self._root.addLayout(btn_row)
        self.save_clicked = save_btn.clicked

        self._root.addStretch()

        scroll.setWidget(widget)
        main_layout.addWidget(scroll)

        self._on_stage_count_changed(2)

    def _show_text_description(self):
        """生成当前声骸套装预设的文本描述并展示"""
        lines = []
        lines.append("═" * 50)
        lines.append("【声骸套装预设】")
        name = self.set_name.text().strip() or "(未命名)"
        lines.append(f"名称: {name}")
        lines.append("")

        for i, cd in enumerate(self._stage_data):
            rc = cd.get("required_count", i + 1)
            lines.append(f"── {rc} 件套效果 ──")
            desc_text = cd.get("desc", "")
            if desc_text:
                lines.append(f"  描述: {desc_text}")
            effects = cd.get("effects", [])
            if effects:
                lines.append(f"  效果 ({len(effects)} 条):")
                for eff in effects:
                    kw = f" [关键词: {eff.get('keywords', '')}]" if eff.get('keywords', '') else ""
                    lines.append(f"    {eff.get('type', '常驻')}: {eff.get('name', '')} +{eff.get('value', 0):.1f}%  (来源: {eff.get('source', '')}){kw}")
            else:
                lines.append("  效果: (无)")
            lines.append("")

        lines.append("── 首位声骸增益 ──")
        fb_name = self._first_data.get("name", "")
        if fb_name:
            lines.append(f"  名称: {fb_name}")
        fb_intro = self._first_data.get("intro", "")
        if fb_intro:
            lines.append(f"  介绍: {fb_intro}")
        fb_effects = self._first_data.get("effects", [])
        if fb_effects:
            lines.append(f"  效果 ({len(fb_effects)} 条):")
            for eff in fb_effects:
                kw = f" [关键词: {eff.get('keywords', '')}]" if eff.get('keywords', '') else ""
                lines.append(f"    {eff.get('type', '常驻')}: {eff.get('name', '')} +{eff.get('value', 0):.1f}%  (来源: {eff.get('source', '')}){kw}")
        else:
            lines.append("  效果: (无)")
        fb_indep = self._first_data.get("indep_zones", [])
        if fb_indep:
            lines.append(f"  独立乘区 ({len(fb_indep)} 组):")
            for iz in fb_indep:
                lines.append(f"    组名: {iz.get('group_name', '')}")
                for v in iz.get("values", []):
                    hidden = " [隐藏]" if v.get("hidden", False) else ""
                    lines.append(f"      {v.get('name', '')} = {v.get('value', 0):.1f}%{hidden}")
        else:
            lines.append("  独立乘区: (无)")
        lines.append("")
        lines.append("═" * 50)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"文本描述 - {name}")
        dlg.setMinimumSize(550, 500)
        dlg.resize(600, 600)
        dl = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText("\n".join(lines))
        dl.addWidget(te)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("backButton")
        close_btn.clicked.connect(dlg.accept)
        dl.addWidget(close_btn)
        dlg.exec()

    def reject(self):
        reply = QMessageBox.question(
            self, "退出声骸套装预设", "确定要退出声骸套装预设窗口吗？\n未保存的更改将丢失。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            super().reject()

    def _center(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def _apply_theme(self):
        """继承主程序主题"""
        try:
            from theme_system import THEMES, build_stylesheet
            w = self.parent()
            while w is not None:
                if hasattr(w, 'current_theme') and w.current_theme in THEMES:
                    self.setStyleSheet(build_stylesheet(w.current_theme))
                    return
                w = w.parent()
            self.setStyleSheet(build_stylesheet("dark"))
        except Exception:
            pass

    def _on_stage_count_changed(self, count):
        while len(self._stage_data) > count:
            self._stage_data.pop()
            card = self._stage_cards.pop()
            self._stage_container.removeWidget(card)
            card.deleteLater()
        while len(self._stage_data) < count:
            idx = len(self._stage_data) + 1
            cd = {"effects": [], "required_count": idx, "desc": ""}
            self._stage_data.append(cd)

            card = _CompactCard(f"{idx} 件套效果")
            card.set_info("暂无效果")
            stage_idx = idx
            card.set_expand_callback(lambda ii=stage_idx: self._open_stage_edit(ii))
            self._stage_cards.append(card)
            self._stage_container.addWidget(card)
            self._update_stage_summary(len(self._stage_data) - 1)

    def _open_stage_edit(self, stage_idx):
        idx = stage_idx - 1
        if idx < 0 or idx >= len(self._stage_data):
            return
        cd = self._stage_data[idx] 
        # 所需同套数量控件
        count_spin = QSpinBox()
        count_spin.setRange(1, 5)
        count_spin.setValue(cd.get("required_count", stage_idx))
        count_spin.setSuffix(" 件套")
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("所需同套数量:"))
        count_row.addWidget(count_spin)
        count_row.addStretch()

        dlg = _EditDialog(
            f"{stage_idx} 件套效果 - 编辑", default_source="合鸣效果", parent=self,
            intro_tab_label=f"{stage_idx}件套说明",
            intro_title=f"编辑 {stage_idx} 件套效果的介绍信息：",
            intro_text=cd.get("desc", ""),
            intro_placeholder="在此输入套装效果的介绍文本...",
            intro_extra=count_row)
        dlg.set_effects(cd["effects"])

        if dlg.exec() == QDialog.DialogCode.Accepted:
            cd["effects"] = dlg.get_effects()
            cd["desc"] = dlg.get_intro_text()
            cd["required_count"] = count_spin.value()
            self._update_stage_summary(stage_idx - 1)

    def _update_stage_summary(self, idx):
        cd = self._stage_data[idx]
        eff_count = len(cd["effects"])
        req = cd.get("required_count", idx + 1)
        if eff_count == 0:
            text = f"所需 {req} 件，暂无效果"
        else:
            text = f"所需 {req} 件，{eff_count} 条效果"
        self._stage_cards[idx].set_info(text)

    def _open_first_edit(self):
        # 首位声骸名称输入
        first_name_edit = QLineEdit(self._first_data.get("name", ""))
        first_name_edit.setPlaceholderText("首位声骸名称（例如：无归的谬误）")
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("首位声骸名称:"))
        name_row.addWidget(first_name_edit, stretch=1)
        dlg = _EditDialog("首位声骸增益 - 编辑", default_source="合鸣效果", parent=self,
                          intro_tab_label="首位声骸介绍",
                          intro_title="编辑首位声骸的介绍信息：",
                          intro_text=self._first_data.get("intro", ""),
                          intro_placeholder="在此输入首位声骸的介绍文本...",
                          intro_extra=name_row)
        dlg.set_effects(self._first_data["effects"])
        dlg.set_indep_zones(self._first_data["indep_zones"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._first_data["name"] = first_name_edit.text().strip()
            self._first_data["effects"] = dlg.get_effects()
            self._first_data["indep_zones"] = dlg.get_indep_zones()
            self._first_data["intro"] = dlg.get_intro_text()
            eff_count = len(self._first_data["effects"])
            iz_count = len(self._first_data["indep_zones"])
            name = self._first_data.get("name", "")
            if eff_count == 0 and iz_count == 0 and not name:
                self._first_card.set_info("暂无效果")
            else:
                parts = []
                if name:
                    parts.append(name)
                if eff_count > 0:
                    parts.append(f"{eff_count} 条效果")
                if iz_count > 0:
                    parts.append(f"{iz_count} 组独立乘区")
                self._first_card.set_info(", ".join(parts))

    def to_dict(self):
        return {
            "name": self.set_name.text().strip(),
            "stages": [
                {
                    "required_count": cd.get("required_count", i + 1),
                    "effects": cd["effects"],
                    "desc": cd.get("desc", ""),
                }
                for i, cd in enumerate(self._stage_data)
            ],
            "first_echo_bonus": {
                "name": self._first_data.get("name", ""),
                "intro": self._first_data.get("intro", ""),
                "effects": self._first_data["effects"],
                "indep_zones": self._first_data["indep_zones"],
            },
        }

    def load_data(self, data):
        self.set_name.setText(data.get("name", ""))
        stages = data.get("stages", [])
        if stages:
            self.stage_count_spin.blockSignals(True)
            self.stage_count_spin.setValue(len(stages))
            self.stage_count_spin.blockSignals(False)
            for i, cd in enumerate(self._stage_data):
                if i < len(stages):
                    s = stages[i]
                    cd["required_count"] = s.get("required_count", i + 1)
                    cd["effects"] = s.get("effects", [])
                    cd["desc"] = s.get("desc", "")
                    self._update_stage_summary(i)
        first = data.get("first_echo_bonus", {})
        if first:
            self._first_data["name"] = first.get("name", "")
            self._first_data["intro"] = first.get("intro", "")
            self._first_data["effects"] = first.get("effects", [])
            self._first_data["indep_zones"] = first.get("indep_zones", [])
            eff_count = len(self._first_data["effects"])
            iz_count = len(self._first_data["indep_zones"])
            if eff_count > 0 or iz_count > 0:
                parts = []
                if eff_count > 0:
                    parts.append(f"{eff_count} 条效果")
                if iz_count > 0:
                    parts.append(f"{iz_count} 组独立乘区")
                self._first_card.set_info(", ".join(parts))


# ═══════════════════════════════════════════════════════════════
# 预设构建器主对话框（总界面）
# ═══════════════════════════════════════════════════════════════

class PresetBuilderDialog(QDialog):
    """预设构建器 —— 总界面 + 三类预设窗口 + 编辑已有预设"""

    _PAGE_MAIN = 0
    _PAGE_EDIT = 1

    def __init__(self, parent=None, edit_preset_data=None, edit_preset_path=None):
        super().__init__(parent)
        self.setWindowTitle("预设构建器")
        self.setMinimumSize(1000, 800)
        self.resize(1000, 800)
        _fit_to_screen(self, 1000)
        self._edit_preset_path = edit_preset_path
        self._animating = False
        self._auto_update_enabled = True  # 自动更新开关记忆

        QTimer.singleShot(0, lambda: self._center())

        # 继承主程序主题
        self._apply_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()

        # 页面 0：总界面
        self.main_page = self._build_main_page()
        self.stack.addWidget(self.main_page)

        # 页面 1：编辑已有预设
        self.edit_page = self._build_edit_page()
        self.stack.addWidget(self.edit_page)

        main_layout.addWidget(self.stack)

        if edit_preset_data:
            self._load_data(edit_preset_data)

    # ── 滑动动画 ──

    def _slide_to(self, page_index):
        """带上下滑动动画切换页面"""
        if self._animating:
            return
        if page_index == self.stack.currentIndex():
            return
        self._animating = True

        # 新页面在下方 → 往上滑入（下拉展开）；新页面在上方 → 往下滑入（收起）
        direction = 1 if page_index > self.stack.currentIndex() else -1
        h = self.stack.height()
        w = self.stack.width()

        # 新页面初始位置：下方或上方
        self.stack.widget(page_index).setGeometry(0, h * direction, w, h)
        self.stack.widget(page_index).show()

        from_rect = self.stack.currentWidget().geometry()

        # 当前页面滑出（往上或往下）
        anim_out = QPropertyAnimation(self.stack.currentWidget(), b"geometry")
        anim_out.setDuration(280)
        anim_out.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim_out.setStartValue(from_rect)
        anim_out.setEndValue(from_rect.adjusted(0, -h * direction, 0, -h * direction))

        # 新页面滑入
        target_widget = self.stack.widget(page_index)
        anim_in = QPropertyAnimation(target_widget, b"geometry")
        anim_in.setDuration(280)
        anim_in.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim_in.setStartValue(target_widget.geometry())
        anim_in.setEndValue(from_rect)

        def _on_finished():
            self.stack.setCurrentIndex(page_index)
            target_widget.setGeometry(from_rect)
            self._animating = False

        anim_out.finished.connect(_on_finished)
        anim_out.start()
        anim_in.start()
        self._anim_out = anim_out
        self._anim_in = anim_in

    def wheelEvent(self, event):
        """滚轮上下切换主页面 ↔ 编辑已有预设页面"""
        if self._animating:
            return
        delta = event.angleDelta().y()
        cur = self.stack.currentIndex()
        if delta < 0 and cur == self._PAGE_MAIN:
            # 主页面向下滚 → 切换到编辑页
            self._slide_to(self._PAGE_EDIT)
            return
        elif delta > 0 and cur == self._PAGE_EDIT:
            # 编辑页向上滚 → 仅在滚动条已在顶部时切换回主页面
            scroll = self.edit_page.findChild(QScrollArea)
            if scroll and scroll.verticalScrollBar().value() == 0:
                self._slide_to(self._PAGE_MAIN)
                return
        super().wheelEvent(event)

    def _center(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def _apply_theme(self):
        """继承主程序主题"""
        try:
            from theme_system import THEMES, build_stylesheet
            w = self.parent()
            while w is not None:
                if hasattr(w, 'current_theme') and w.current_theme in THEMES:
                    self.setStyleSheet(build_stylesheet(w.current_theme))
                    return
                w = w.parent()
            self.setStyleSheet(build_stylesheet("dark"))
        except Exception:
            pass

    # ── 页面构建 ──

    def _build_main_page(self):
        page = QWidget()
        page.setObjectName("presetMainPage")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(30)

        layout.addStretch(2)

        title = QLabel("预设构建器")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("选择需要构建的预设类型。三类预设相互独立，可单独使用也可组合。")
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(24)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for icon, t, desc, callback in [
            ("🎭", "角色预设", "设定角色基础属性、元素、效应\n以及 0~6 阶共鸣链效果",
             lambda: self._new_character()),
            ("⚔", "武器预设", "设定武器基础攻击力、附加属性\n以及 1~5 阶阶段等级效果",
             lambda: self._new_weapon()),
            ("🔮", "声骸套装预设", "设定声骸套装各阶段效果\n以及首位声骸增益",
             lambda: self._new_echo_set()),
            ("💠", "角色增益预设", "设定队友提供的额外增益效果\n（常驻 / 触发）",
             lambda: self._new_character_buff()),
        ]:
            card = QPushButton()
            card.setObjectName("presetEntryCard")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setMinimumSize(220, 260)
            card.clicked.connect(callback)

            cl = QVBoxLayout(card)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.setSpacing(12)
            cl.setContentsMargins(7, 8, 7, 8)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 42px; border: none; background: transparent;")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(icon_label)

            title_label = QLabel(t)
            title_label.setObjectName("accentLabel")
            title_label.setStyleSheet("font-size: 16px; font-weight: 700; border: none; background: transparent;")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(title_label)

            desc_label = QLabel(desc)
            desc_label.setObjectName("labelSecondary")
            desc_label.setStyleSheet("font-size: 11px; border: none; background: transparent;")
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setWordWrap(True)
            cl.addWidget(desc_label)

            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)
        layout.addSpacing(20)

        load_btn = QPushButton("📂 加载已有预设进行编辑")
        load_btn.setObjectName("backButton")
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.setMinimumWidth(280)
        load_btn.clicked.connect(lambda: self._slide_to(self._PAGE_EDIT))
        layout.addWidget(load_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(3)

        return page

    def _build_edit_page(self):
        """页面 2：编辑已有预设 —— 与主界面同样的模板布局"""
        page = QWidget()
        page.setObjectName("presetMainPage")

        # 可滚动容器
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        layout.addStretch(2)

        # 第一行：标题
        title = QLabel("编辑已有预设")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 第二行：副标题
        subtitle = QLabel("选择预设类型，查看并编辑已保存的预设。")
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # 第三行：三个预设分类卡片
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(24)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for icon, cat_key, cat_label in [
            ("🎭", "character", "角色预设"),
            ("⚔", "weapon", "武器预设"),
            ("🔮", "echo_set", "声骸套装预设"),
            ("💠", "character_buff", "角色增益预设"),
        ]:
            card = QPushButton()
            card.setObjectName("presetEntryCard")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setMinimumSize(220, 260)
            card.clicked.connect(lambda _, c=cat_key: self._select_edit_category(c))

            cl = QVBoxLayout(card)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.setSpacing(12)
            cl.setContentsMargins(7, 8, 7, 8)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 42px; border: none; background: transparent;")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(icon_label)

            title_label = QLabel(cat_label)
            title_label.setObjectName("accentLabel")
            title_label.setStyleSheet("font-size: 16px; font-weight: 700; border: none; background: transparent;")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(title_label)

            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)
        layout.addSpacing(16)

        # 预设列表（初始隐藏，点击卡片后显示）
        self._edit_list_area = QWidget()
        self._edit_list_area.setVisible(False)
        list_layout = QVBoxLayout(self._edit_list_area)
        list_layout.setContentsMargins(40, 0, 40, 0)
        list_layout.setSpacing(8)

        self._edit_list_label = QLabel("")
        self._edit_list_label.setObjectName("labelSecondary")
        self._edit_list_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        self._edit_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        list_layout.addWidget(self._edit_list_label)

        self._edit_search = QLineEdit()
        self._edit_search.setPlaceholderText("搜索预设名称...")
        self._edit_search.setObjectName("nameEdit")
        self._edit_search.setClearButtonEnabled(True)
        self._edit_search.textChanged.connect(self._filter_edit_list)
        self._edit_search.setVisible(False)
        list_layout.addWidget(self._edit_search)

        self._edit_list = QListWidget()
        self._edit_list.setMinimumHeight(160)
        self._edit_list.setMaximumHeight(260)
        self._edit_list.setStyleSheet(
            "QListWidget { border: 1px solid rgba(255,255,255,0.08); "
            "border-radius: 6px; font-size: 13px; }"
            "QListWidget::item { padding: 6px 8px; }"
            "QListWidget::item:selected { background: rgba(233,69,96,0.25); }")
        self._edit_list.itemDoubleClicked.connect(self._on_edit_preset_selected)
        self._edit_list.installEventFilter(self)
        list_layout.addWidget(self._edit_list)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        del_btn = QPushButton("删除预设")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFixedWidth(90)
        del_btn.setStyleSheet(
            "QPushButton { padding: 3px 8px; color: #ef9a9a; "
            "background: rgba(198,40,40,0.18); border: 1px solid rgba(198,40,40,0.35); "
            "border-radius: 4px; }"
            "QPushButton:hover { background: rgba(198,40,40,0.28); }")
        del_btn.clicked.connect(self._on_delete_preset)
        btn_row.addWidget(del_btn)
        edit_btn = QPushButton("打开编辑")
        edit_btn.setObjectName("presetSaveBtn")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setFixedWidth(90)
        edit_btn.setStyleSheet("QPushButton { padding: 3px 8px; }")
        edit_btn.clicked.connect(self._on_edit_preset_selected)
        btn_row.addWidget(edit_btn)
        list_layout.addLayout(btn_row)

        layout.addWidget(self._edit_list_area)

        # 第四行：返回创建预设
        back_btn = QPushButton("← 返回创建预设")
        back_btn.setObjectName("backButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setMinimumWidth(280)
        back_btn.clicked.connect(lambda: self._slide_to(self._PAGE_MAIN))
        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(3)

        scroll.setWidget(inner)
        scroll.installEventFilter(self)
        self._edit_scroll = scroll
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        return page

    # ── 编辑已有预设逻辑 ──

    def _select_edit_category(self, cat_key):
        """选中分类后，显示该分类下的预设列表"""
        self._edit_category = cat_key
        self._edit_presets = PresetManager.list_presets()
        self._edit_cat_presets = [p for p in self._edit_presets if p["category"] == cat_key]
        cat_names = {"character": "角色", "weapon": "武器", "echo_set": "声骸套装", "character_buff": "角色增益"}

        self._edit_list.clear()
        self._edit_search.clear()
        self._edit_search.setVisible(True)
        self._edit_list_area.setVisible(True)
        self._edit_list_label.setText(f"── {cat_names.get(cat_key, '')}预设列表 ──")

        self._populate_edit_list(self._edit_cat_presets)

    def _filter_edit_list(self, text):
        """搜索过滤编辑列表中的预设"""
        if not hasattr(self, '_edit_cat_presets'):
            return
        if not text.strip():
            self._populate_edit_list(self._edit_cat_presets)
            return
        keyword = text.strip().lower()
        filtered = [p for p in self._edit_cat_presets if keyword in p["name"].lower()]
        self._populate_edit_list(filtered)

    def _populate_edit_list(self, presets):
        """用给定的预设列表填充编辑列表"""
        self._edit_list.clear()
        if not presets:
            item = QListWidgetItem("（无匹配预设）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._edit_list.addItem(item)
            return
        for p in presets:
            source_mark = "【官】" if p["source"] == "official" else "【户】"
            text = f"{source_mark} {p['name']}  ({p.get('mtime', '')})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, p)
            if p["source"] == "official":
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self._edit_list.addItem(item)

    def _on_edit_preset_selected(self):
        """双击或点击「打开编辑」按钮 → 加载预设进入编辑"""
        item = self._edit_list.currentItem()
        if not item:
            return
        preset_info = item.data(Qt.ItemDataRole.UserRole)
        if not preset_info:
            return

        data, err = PresetManager.load_preset(preset_info["path"])
        if err:
            QMessageBox.warning(self, "加载失败", err)
            self._edit_preset_path = None
            return

        self._edit_preset_path = preset_info["path"]
        self._edit_preset_source = preset_info.get("source", "user")
        self.setWindowTitle(f"预设构建器 - 编辑: {preset_info['name']}")

        category = data.get("category", "")
        try:
            if category == "character":
                self._open_character()
            elif category == "weapon":
                self._open_weapon()
            elif category == "echo_set":
                self._open_echo_set()
            elif category == "character_buff":
                self._open_character_buff()
        finally:
            self._edit_preset_path = None

    def _new_character(self):
        """新建角色预设（清除编辑路径）"""
        self._edit_preset_path = None
        self._open_character()

    def _new_weapon(self):
        """新建武器预设（清除编辑路径）"""
        self._edit_preset_path = None
        self._open_weapon()

    def _new_echo_set(self):
        """新建声骸套装预设（清除编辑路径）"""
        self._edit_preset_path = None
        self._open_echo_set()

    def _new_character_buff(self):
        """新建角色增益预设（清除编辑路径）"""
        self._edit_preset_path = None
        self._open_character_buff()

    def eventFilter(self, obj, event):
        """拦截编辑预设列表的 Delete 键，以及编辑页滚动区域的滚轮切换"""
        # Delete 键删除预设
        if obj is self._edit_list and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                self._on_delete_preset()
                return True
        # 编辑页滚动区域：滚动到顶部时向上滚 → 切换回主页面
        if obj is getattr(self, '_edit_scroll', None) and event.type() == QEvent.Type.Wheel:
            if self._animating:
                return False
            delta = event.angleDelta().y()
            if delta > 0 and obj.verticalScrollBar().value() == 0:
                self._slide_to(self._PAGE_MAIN)
                return True
        return super().eventFilter(obj, event)

    def _on_delete_preset(self):
        """删除选中的预设，删除后自动选择下一个"""
        item = self._edit_list.currentItem()
        if not item:
            return
        preset_info = item.data(Qt.ItemDataRole.UserRole)
        if not preset_info:
            return

        # 记住当前索引，删除后自动选下一个
        current_row = self._edit_list.row(item)

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除预设「{preset_info['name']}」吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            os.remove(preset_info["path"])
        except OSError as e:
            QMessageBox.warning(self, "删除失败", f"无法删除文件:\n{e}")
            return

        # 刷新当前分类列表
        cat = preset_info.get("category", "")
        if cat:
            self._select_edit_category(cat)

        # 自动选择下一个（或上一个）
        count = self._edit_list.count()
        if count > 0:
            # 过滤掉无预设占位项
            valid_count = sum(
                1 for i in range(count)
                if self._edit_list.item(i).flags() & Qt.ItemFlag.ItemIsSelectable
            )
            if valid_count > 0:
                next_row = min(current_row, valid_count - 1)
                self._edit_list.setCurrentRow(next_row)

    # ── 打开编辑器 ──

    def _open_character(self):
        """打开角色预设分页窗口"""
        dlg = _CharacterPresetWindow(self)
        dlg.back_clicked.connect(dlg.reject)
        dlg.save_clicked.connect(lambda: self._save_from_window(dlg, "character"))
        if self._edit_preset_path:
            data, _ = PresetManager.load_preset(self._edit_preset_path)
            dlg.preset_name_edit.setText(data.get("name", ""))
            dlg.author_edit.setText(data.get("author", ""))
            dlg.author_edit.setText(data.get("author", ""))
            dlg.author_edit.setText(data.get("author", ""))
            dlg.author_edit.setText(data.get("author", ""))
            if data and "character" in data:
                dlg.load_data(data["character"])
        dlg.exec()

    def _open_weapon(self):
        """打开武器预设分页窗口"""
        dlg = _WeaponPresetWindow(self)
        dlg.back_clicked.connect(dlg.reject)
        dlg.save_clicked.connect(lambda: self._save_from_window(dlg, "weapon"))
        if self._edit_preset_path:
            data, _ = PresetManager.load_preset(self._edit_preset_path)
            dlg.preset_name_edit.setText(data.get("name", ""))
            if data and "weapon" in data:
                dlg.load_data(data["weapon"])
        dlg.exec()

    def _open_echo_set(self):
        """打开声骸套装预设窗口"""
        dlg = _EchoSetEditor(self)
        dlg.save_clicked.connect(lambda: self._validate_echo_save(dlg))
        if self._edit_preset_path:
            data, _ = PresetManager.load_preset(self._edit_preset_path)
            dlg.preset_name_edit.setText(data.get("name", ""))
            if data and "echo_set" in data:
                dlg.load_data(data["echo_set"])
        dlg.exec()

    def _open_character_buff(self):
        """打开角色增益预设窗口"""
        dlg = _CharacterBuffWindow(self)
        dlg.back_clicked.connect(dlg.reject)
        dlg.save_clicked.connect(lambda: self._save_from_window(dlg, "character_buff"))
        if self._edit_preset_path:
            data, _ = PresetManager.load_preset(self._edit_preset_path)
            dlg.preset_name_edit.setText(data.get("name", ""))
            if data and "character_buff" in data:
                dlg.load_data(data["character_buff"])
        dlg.exec()

    def _validate_echo_save(self, dlg):
        """声骸套装保存前验证：名称不能为空"""
        name = dlg.set_name.text().strip()
        if not name:
            QMessageBox.warning(self, "保存失败", "请先填写声骸套装名称后再保存。")
            return
        self._save_from_window(dlg, "echo_set")

    # ── 保存 ──

    def _save_from_window(self, window, category):
        """从分页窗口保存预设"""
        data = window.to_dict()
        cat_names = {"character": "角色", "weapon": "武器", "echo_set": "套装", "character_buff": "增益"}
        default_name = data.get("name", "") or f"未命名{cat_names.get(category, '')}"

        # 从窗口读取预设名称（优先使用用户填写的）
        user_name = window.preset_name_edit.text().strip() if hasattr(window, 'preset_name_edit') else ""

        # 校验文件名非法字符
        illegal_chars = r'\/:*?"<>|'
        if user_name and any(c in user_name for c in illegal_chars):
            QMessageBox.warning(
                self, "名称无效",
                f"预设文件名称不能包含以下字符：\n{' '.join(illegal_chars)}\n\n"
                f"请修改后重试。")
            if hasattr(window, 'preset_name_edit'):
                window.preset_name_edit.setFocus()
                window.preset_name_edit.selectAll()
            return

        author = window.author_edit.text().strip() if hasattr(window, 'author_edit') else ""
        preset = {
            "version": 1,
            "type": "preset",
            "name": default_name,
            "author": author,
            "category": category,
            category: data,
        }

        def _fill_internal_name(final_name):
            """如果内部名称为空，用预设名称填充"""
            if not data.get("name", ""):
                base = final_name
                if base.endswith("-预设"):
                    base = base[:-3]
                data["name"] = base
                preset[category] = data

        if self._edit_preset_path:
            # 编辑模式：使用窗口中的预设名称
            raw_name = user_name if user_name else os.path.splitext(os.path.basename(self._edit_preset_path))[0]
            # 清洗非法字符仅用于文件名对比和保存（/ 等符号文件名不支持，但 preset["name"] 保留原样）
            safe_name = "".join(c for c in raw_name if c not in r'\/:*?"<>|') or raw_name
            old_name = os.path.splitext(os.path.basename(self._edit_preset_path))[0]
            preset["name"] = raw_name  # 保留原始名称（含 / 等符号）用于显示
            _fill_internal_name(raw_name)

            if safe_name != old_name:
                # 重命名：保存新文件，删除旧文件
                path, err = PresetManager.save_preset(preset, raw_name, source=self._edit_preset_source, overwrite=False)
                if err:
                    QMessageBox.warning(self, "保存失败", err)
                    return
                try:
                    os.remove(self._edit_preset_path)
                except OSError:
                    pass
                self._edit_preset_path = path
            else:
                # 名称未变（或仅非法字符差异）：直接覆盖
                path, err = PresetManager.save_preset(preset, raw_name, source=self._edit_preset_source, overwrite=True)
                if err:
                    QMessageBox.warning(self, "保存失败", err)
                    return
            QMessageBox.information(self, "保存成功", f"预设已保存到:\n{path}")
            window.accept()
            # 刷新编辑列表
            if hasattr(self, '_edit_category'):
                self._select_edit_category(self._edit_category)
            return

        # 新建模式：以窗口中的预设名称为默认
        name, ok = QInputDialog.getText(
            self, "保存预设", "预设名称:", text=user_name if user_name else f"{default_name}-预设")
        if not ok or not name.strip():
            return
        final_name = name.strip()
        preset["name"] = final_name
        _fill_internal_name(final_name)
        path, err = PresetManager.save_preset(preset, final_name)
        if err:
            QMessageBox.warning(self, "保存失败", err)
            return
        QMessageBox.information(self, "保存成功", f"预设已保存到:\n{path}")
        window.accept()

    def _load_data(self, data):
        """加载已有预设数据（编辑模式）"""
        pass
