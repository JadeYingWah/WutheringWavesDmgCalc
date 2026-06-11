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
from PyQt6.QtCore import Qt, QEvent, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

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
                seq = f"共鸣链{chain_idx}-{eff_i + 1}"
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
    """表格化效果编辑器"""

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
    """独立乘区组"""

    def __init__(self, group_name="", values=None):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("indepGroupFrame")
        self._value_widgets = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.addWidget(QLabel("组名:"))
        self.group_name_edit = QLineEdit(group_name)
        self.group_name_edit.setPlaceholderText("乘区组名称")
        top.addWidget(self.group_name_edit, stretch=1)

        self.del_group_btn = QPushButton("删除组")
        self.del_group_btn.setObjectName("itemDeleteBtn")
        self.del_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        top.addWidget(self.del_group_btn)
        layout.addLayout(top)

        self._values_layout = QVBoxLayout()
        self._values_layout.setSpacing(3)
        layout.addLayout(self._values_layout)

        add_btn = QPushButton("+ 添加数值")
        add_btn.setObjectName("addButton")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(lambda: self._add_value_row())
        layout.addWidget(add_btn)

        if values:
            for v in values:
                if isinstance(v, dict):
                    self._add_value_row(v.get("name", ""), v.get("value", 0.0), v.get("hidden", False))
                elif len(v) >= 3:
                    self._add_value_row(v[0], v[1], v[2])
                elif len(v) >= 2:
                    self._add_value_row(v[0], v[1], False)

    def _add_value_row(self, name="", value=0.0, hidden=False):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 2, 0, 2)
        rl.setSpacing(6)

        ne = QLineEdit(name)
        ne.setPlaceholderText("名称")
        ne.setMinimumWidth(80)
        rl.addWidget(ne, stretch=2)

        vs = QDoubleSpinBox()
        vs.setRange(0, 99999)
        vs.setDecimals(4)
        vs.setValue(value)
        vs.setSuffix("%")
        rl.addWidget(vs)

        hc = QCheckBox("隐藏")
        hc.setChecked(hidden)
        hc.setCursor(Qt.CursorShape.PointingHandCursor)
        rl.addWidget(hc)

        db = QPushButton("✕")
        db.setObjectName("itemDeleteBtn")
        db.setFixedSize(22, 22)
        db.setCursor(Qt.CursorShape.PointingHandCursor)
        db.clicked.connect(lambda: self._remove_value_row(row))
        rl.addWidget(db)

        self._values_layout.addWidget(row)
        self._value_widgets.append((ne, vs, hc, row))

    def _remove_value_row(self, row_widget):
        for i, (_, _, _, rw) in enumerate(self._value_widgets):
            if rw is row_widget:
                self._value_widgets.pop(i)
                self._values_layout.removeWidget(row_widget)
                row_widget.deleteLater()
                break

    def to_dict(self):
        return {
            "group_name": self.group_name_edit.text().strip(),
            "values": [
                {"name": ne.text().strip(), "value": vs.value(), "hidden": hc.isChecked()}
                for ne, vs, hc, _ in self._value_widgets
            ],
        }


# ═══════════════════════════════════════════════════════════════
# 展开编辑弹窗
# ═══════════════════════════════════════════════════════════════

class _EditDialog(QDialog):
    """卡片展开后的编辑弹窗"""

    def __init__(self, title, default_source="其他效果", show_type=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(950, 600)
        self.resize(1000, 650)

        QTimer.singleShot(0, lambda: self._center())

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel(title)
        lbl.setObjectName("sectionTitle")
        layout.addWidget(lbl)

        self.effect_table = _EffectTableWidget(default_source=default_source, show_type=show_type)
        layout.addWidget(self.effect_table, stretch=3)

        iz_label = QLabel("独立乘区组")
        iz_label.setObjectName("labelSecondary")
        iz_label.setStyleSheet("font-size: 13px; font-weight: 600;")
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

    def _add_indep_group(self):
        gb = _IndepZoneGroupBox("", [])
        gb.del_group_btn.clicked.connect(lambda: self._remove_indep_group(gb))
        self._indep_container.addWidget(gb)
        self._indep_groups.append(gb)

    def _remove_indep_group(self, gb):
        if gb in self._indep_groups:
            self._indep_groups.remove(gb)
            self._indep_container.removeWidget(gb)
            gb.deleteLater()

    def get_effects(self):
        return self.effect_table.to_list()

    def get_indep_zones(self):
        return [iz.to_dict() for iz in self._indep_groups]

    def set_effects(self, effects):
        self.effect_table.from_list(effects)

    def set_indep_zones(self, zones):
        for iz_data in zones:
            gb = _IndepZoneGroupBox(iz_data.get("group_name", ""), iz_data.get("values", []))
            gb.del_group_btn.clicked.connect(lambda g=gb: self._remove_indep_group(gb))
            self._indep_container.addWidget(gb)
            self._indep_groups.append(gb)


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

        # 分页标签
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        # ── 页面1: 基本内容 ──
        self.tab_basic = QWidget()
        self._build_basic_tab()
        self.tabs.addTab(self.tab_basic, "基本内容")

        # ── 页面2: 共鸣链 ──
        self.tab_chain = QWidget()
        self._chain_data = []  # [{"effects": [], "indep_zones": []}, ...] x 7
        self._chain_cards = []
        self._build_chain_tab()
        self.tabs.addTab(self.tab_chain, "共鸣链")

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

        # ── 页面4: 结果列表 ──
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

        # 保存按钮
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("💾 保存角色预设")
        save_btn.setObjectName("presetSaveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_row.addWidget(save_btn)
        main_layout.addLayout(save_row)
        self.save_clicked = save_btn.clicked

        # 初始化 7 个共鸣链数据
        for i in range(7):
            self._chain_data.append({"effects": [], "indep_zones": []})

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
        self.char_name = QLineEdit()
        self.char_name.setPlaceholderText("角色名称")
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

        # 倍率设置
        mult_group = QGroupBox("倍率设置")
        mult_form = QFormLayout(mult_group)
        mult_form.setSpacing(4)
        self.mult_base = QDoubleSpinBox()
        self.mult_base.setRange(0, 99999)
        self.mult_base.setDecimals(4)
        self.mult_base.setValue(100.0)
        mult_form.addRow("基础倍率(%):", self.mult_base)
        self.mult_increase = QDoubleSpinBox()
        self.mult_increase.setRange(0, 99999)
        self.mult_increase.setDecimals(4)
        self.mult_increase.setValue(0.0)
        mult_form.addRow("倍率增加(%):", self.mult_increase)
        self.mult_boosts = []
        for _i in range(3):
            spin = QDoubleSpinBox()
            spin.setRange(0, 99999)
            spin.setDecimals(4)
            spin.setValue(0.0)
            self.mult_boosts.append(spin)
            mult_form.addRow(f"倍率提升{_i + 1}(%):", spin)
        layout.addWidget(mult_group)

        # 基础数值/倍率变更时触发自动计算
        for sp in (self.base_hp, self.base_atk, self.base_def,
                   self.mult_base, self.mult_increase, *self.mult_boosts):
            sp.valueChanged.connect(self._on_preset_data_changed)

        layout.addStretch()

    # ── 页面2: 共鸣链 ──

    def _build_chain_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        for i in range(7):
            card = _CompactCard(f"{i} 链")
            card.set_info("暂无效果")
            idx = i
            card.set_expand_callback(lambda ii=idx: self._open_chain_edit(ii))
            self._chain_cards.append(card)
            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(container)
        tab_layout = QVBoxLayout(self.tab_chain)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

    def _open_chain_edit(self, chain_idx):
        cd = self._chain_data[chain_idx]
        dlg = _EditDialog(f"{chain_idx} 链 - 编辑效果", default_source="共鸣链效果", show_type=True, parent=self)
        dlg.set_effects(cd["effects"])
        dlg.set_indep_zones(cd["indep_zones"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cd["effects"] = dlg.get_effects()
            cd["indep_zones"] = dlg.get_indep_zones()
            self._update_chain_summary(chain_idx)
            self._adapters_dirty = True

    def _update_chain_summary(self, chain_idx):
        cd = self._chain_data[chain_idx]
        eff_count = len(cd["effects"])
        iz_count = len(cd["indep_zones"])
        if eff_count == 0 and iz_count == 0:
            text = "暂无效果"
        else:
            parts = []
            if eff_count > 0:
                parts.append(f"{eff_count} 条效果")
            if iz_count > 0:
                parts.append(f"{iz_count} 组独立乘区")
            text = ", ".join(parts)
        self._chain_cards[chain_idx].set_info(text)

    # ── 页面3: 结果列表 ──

    def _build_calc_tab(self):
        """页面3: 计算结果（嵌入主程序 ResultPage）"""
        layout = QVBoxLayout(self.tab_calc)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._preset_result_page)
        layout.addWidget(scroll)

    def _build_result_list_tab(self):
        """页面4: 结果列表（嵌入主程序 ResultListPage）"""
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
        self._adapter_entries.update_from_chain_data(self._chain_data)
        self._adapter_indep.update_from_chain_data(self._chain_data)
        # 同步倍率到 ResultPage
        rp = self._preset_result_page
        rp.base_mult.setValue(self.mult_base.value())
        rp.mult_increase.setValue(self.mult_increase.value())
        for i, s in enumerate(self.mult_boosts):
            if i < len(rp.mult_boosts):
                rp.mult_boosts[i].setValue(s.value())
        self._adapters_dirty = False

    def _on_tab_changed(self, index):
        """切换到计算/结果页时同步数据并触发计算"""
        widget = self.tabs.widget(index)
        if widget in (self.tab_calc, self.tab_result_list):
            self._sync_adapters()
            if widget is self.tab_calc:
                self._preset_result_page.compute()

    def to_dict(self):
        return {
            "name": self.char_name.text().strip(),
            "element": self.char_element.currentText(),
            "effect": self.char_effect.currentText(),
            "base_hp": self.base_hp.value(),
            "base_atk": self.base_atk.value(),
            "base_def": self.base_def.value(),
            "multiplier": {
                "base_mult": self.mult_base.value(),
                "mult_increase": self.mult_increase.value(),
                "mult_boosts": [s.value() for s in self.mult_boosts],
            },
            "resonance_chain": [
                {
                    "effects": cd["effects"],
                    "indep_zones": cd["indep_zones"],
                }
                for cd in self._chain_data
            ],
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
        mult = data.get("multiplier", {})
        self.mult_base.setValue(mult.get("base_mult", 100.0))
        self.mult_increase.setValue(mult.get("mult_increase", 0.0))
        for _i, _v in enumerate(mult.get("mult_boosts", [0, 0, 0])):
            if _i < len(self.mult_boosts):
                self.mult_boosts[_i].setValue(_v)
        chains = data.get("resonance_chain", [])
        for i, cd in enumerate(self._chain_data):
            if i < len(chains):
                ch = chains[i]
                cd["effects"] = ch.get("effects", [])
                cd["indep_zones"] = ch.get("indep_zones", [])
                self._update_chain_summary(i)
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
        self._build_refine_tab()
        self.tabs.addTab(self.tab_refine, "阶段等级")

        # 保存按钮
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("💾 保存武器预设")
        save_btn.setObjectName("presetSaveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_row.addWidget(save_btn)
        main_layout.addLayout(save_row)
        self.save_clicked = save_btn.clicked

        # 初始化 5 个等阶数据
        for i in range(5):
            self._ref_data.append({"effects": [], "indep_zones": [], "resonance_desc": ""})

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
        dlg = _EditDialog(f"等阶 {ref_idx} - 编辑效果", default_source="武器谐振", show_type=True, parent=self)
        dlg.set_effects(cd["effects"])
        dlg.set_indep_zones(cd["indep_zones"])

        # 添加谐振描述输入
        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel("谐振描述:"))
        desc_edit = QLineEdit(cd.get("resonance_desc", ""))
        desc_edit.setPlaceholderText("（可选）谐振效果的文字描述")
        desc_row.addWidget(desc_edit, stretch=1)
        dlg.layout().insertLayout(1, desc_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            cd["effects"] = dlg.get_effects()
            cd["indep_zones"] = dlg.get_indep_zones()
            cd["resonance_desc"] = desc_edit.text().strip()
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
                self._update_refine_summary(i)


# ═══════════════════════════════════════════════════════════════
# 声骸套装编辑器（保持原有设计）
# ═══════════════════════════════════════════════════════════════

class _EchoSetEditor(QDialog):
    """声骸套装预设编辑窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("声骸套装预设")
        self.setMinimumSize(900, 650)
        self.resize(950, 700)

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

        self._first_data = {"effects": [], "indep_zones": []}
        self._first_card = _CompactCard("首位声骸增益")
        self._first_card.set_info("暂无效果")
        self._first_card.set_expand_callback(self._open_first_edit)
        self._root.addWidget(self._first_card)

        self._root.addSpacing(10)
        save_btn = QPushButton("💾 保存声骸套装预设")
        save_btn.setObjectName("presetSaveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._root.addWidget(save_btn)
        self.save_clicked = save_btn.clicked

        self._root.addStretch()

        scroll.setWidget(widget)
        main_layout.addWidget(scroll)

        self._on_stage_count_changed(2)

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
            cd = {"effects": [], "required_count": idx}
            self._stage_data.append(cd)

            card = _CompactCard(f"{idx} 件套效果")
            card.set_info("暂无效果")
            stage_idx = idx
            card.set_expand_callback(lambda ii=stage_idx: self._open_stage_edit(ii))
            self._stage_cards.append(card)
            self._stage_container.addWidget(card)
            self._update_stage_summary(len(self._stage_data) - 1)

    def _open_stage_edit(self, stage_idx):
        cd = self._stage_data[stage_idx - 1]
        dlg = _EditDialog(f"{stage_idx} 件套效果 - 编辑", default_source="合鸣效果", show_type=True, parent=self)
        dlg.set_effects(cd["effects"])

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("所需同套数量:"))
        count_spin = QSpinBox()
        count_spin.setRange(1, 5)
        count_spin.setValue(cd.get("required_count", stage_idx))
        count_row.addWidget(count_spin)
        count_row.addStretch()
        dlg.layout().insertLayout(1, count_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            cd["effects"] = dlg.get_effects()
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
        dlg = _EditDialog("首位声骸增益 - 编辑", default_source="合鸣效果", show_type=True, parent=self)
        dlg.set_effects(self._first_data["effects"])
        dlg.set_indep_zones(self._first_data["indep_zones"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._first_data["effects"] = dlg.get_effects()
            self._first_data["indep_zones"] = dlg.get_indep_zones()
            eff_count = len(self._first_data["effects"])
            iz_count = len(self._first_data["indep_zones"])
            if eff_count == 0 and iz_count == 0:
                self._first_card.set_info("暂无效果")
            else:
                parts = []
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
                }
                for i, cd in enumerate(self._stage_data)
            ],
            "first_echo_bonus": {
                "effects": self._first_data["effects"],
                "indep_zones": self._first_data["indep_zones"],
            },
        }

    def load_data(self, data):
        self.set_name.setText(data.get("name", ""))
        stages = data.get("stages", [])
        if stages:
            self.stage_count_spin.setValue(len(stages))
            for i, cd in enumerate(self._stage_data):
                if i < len(stages):
                    s = stages[i]
                    cd["required_count"] = s.get("required_count", i + 1)
                    cd["effects"] = s.get("effects", [])
                    self._update_stage_summary(i)
        first = data.get("first_echo_bonus", {})
        if first:
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
        self.setMinimumSize(880, 720)
        self.resize(920, 760)
        self._edit_preset_path = edit_preset_path
        self._animating = False

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
            ("🎭", "角色预设", "设定角色基础属性、元素、效应\n以及 0~6 阶共鸣链效果", self._open_character),
            ("⚔", "武器预设", "设定武器基础攻击力、附加属性\n以及 1~5 阶阶段等级效果", self._open_weapon),
            ("🔮", "声骸套装预设", "设定声骸套装各阶段效果\n以及首位声骸增益", self._open_echo_set),
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
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        return page

    # ── 编辑已有预设逻辑 ──

    def _select_edit_category(self, cat_key):
        """选中分类后，显示该分类下的预设列表"""
        self._edit_presets = PresetManager.list_presets()
        cat_presets = [p for p in self._edit_presets if p["category"] == cat_key]
        cat_names = {"character": "角色", "weapon": "武器", "echo_set": "声骸套装"}

        self._edit_list.clear()
        self._edit_list_area.setVisible(True)
        self._edit_list_label.setText(f"── {cat_names.get(cat_key, '')}预设列表 ──")

        if not cat_presets:
            item = QListWidgetItem("（暂无该类型预设）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._edit_list.addItem(item)
            return

        for p in cat_presets:
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
            return

        self._edit_preset_path = preset_info["path"]
        self.setWindowTitle(f"预设构建器 - 编辑: {preset_info['name']}")

        category = data.get("category", "")
        if category == "character":
            self._open_character()
        elif category == "weapon":
            self._open_weapon()
        elif category == "echo_set":
            self._open_echo_set()

    def eventFilter(self, obj, event):
        """拦截编辑预设列表的 Delete 键"""
        if obj is self._edit_list and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                self._on_delete_preset()
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
            if data and "weapon" in data:
                dlg.load_data(data["weapon"])
        dlg.exec()

    def _open_echo_set(self):
        """打开声骸套装预设窗口"""
        dlg = _EchoSetEditor(self)
        dlg.save_clicked.connect(lambda: self._save_from_window(dlg, "echo_set"))
        if self._edit_preset_path:
            data, _ = PresetManager.load_preset(self._edit_preset_path)
            if data and "echo_set" in data:
                dlg.load_data(data["echo_set"])
        dlg.exec()

    # ── 保存 ──

    def _save_from_window(self, window, category):
        """从分页窗口保存预设"""
        data = window.to_dict()
        default_name = data.get("name", "") or f"未命名{'角色' if category == 'character' else '武器'}"

        preset = {
            "version": 1,
            "type": "preset",
            "name": default_name,
            "category": category,
            category: data,
        }

        if self._edit_preset_path:
            preset["name"] = os.path.splitext(os.path.basename(self._edit_preset_path))[0]
            path, err = PresetManager.save_preset(preset, preset["name"], overwrite=True)
            if err:
                QMessageBox.warning(self, "保存失败", err)
                return
            QMessageBox.information(self, "保存成功", f"预设已保存到:\n{path}")
            window.accept()
            return

        name, ok = QInputDialog.getText(
            self, "保存预设", "预设名称:", text=f"{default_name}-预设")
        if not ok or not name.strip():
            return
        preset["name"] = name.strip()
        path, err = PresetManager.save_preset(preset, name.strip())
        if err:
            QMessageBox.warning(self, "保存失败", err)
            return
        QMessageBox.information(self, "保存成功", f"预设已保存到:\n{path}")
        window.accept()

    def _load_data(self, data):
        """加载已有预设数据（编辑模式）"""
        pass
