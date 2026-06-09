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
    QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from preset_manager import PresetManager

# 延迟导入避免循环依赖
def _get_search_combo():
    from WWDmgCalc import SearchCombo, WEAPON_RESONANCE_ATTRS
    return SearchCombo, WEAPON_RESONANCE_ATTRS

# ── 常量 ──
ELEMENTS = ["冷凝", "热熔", "气动", "导电", "衍射", "湮灭"]
EFFECTS = ["(无)", "光噪", "风蚀", "虚湮", "聚爆", "霜渐", "电磁"]
SOURCES = ["武器谐振", "合鸣效果", "技能效果", "角色效果", "其他效果", "共鸣链效果"]
WEAPON_BONUS_TYPES = ["生命值", "攻击力", "防御力", "暴击率", "暴击伤害", "共鸣效率"]
EFFECT_TYPES = ["常驻", "触发"]


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
# 结果列表卡片（照抄主程序样式）
# ═══════════════════════════════════════════════════════════════

class _PresetResultCard(QFrame):
    """预设结果卡片 —— 照抄主程序结果卡片样式"""

    def __init__(self, effect_data, idx=0, parent=None):
        super().__init__(parent)
        self.setObjectName("resultCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedWidth(320)
        self._effect = effect_data
        self._idx = idx
        self._locked = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 第一行：效果名称 + 锁定标记
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(effect_data.get("name", "未知效果"))
        name_lbl.setObjectName("resultHeader")
        row1.addWidget(name_lbl, stretch=1)

        eff_type = effect_data.get("type", "常驻")
        type_lbl = QLabel(f"[{eff_type}]")
        type_lbl.setObjectName("labelSecondary")
        row1.addWidget(type_lbl)

        self._lock_mark = QLabel("[锁]")
        self._lock_mark.setObjectName("labelSecondary")
        self._lock_mark.setVisible(False)
        row1.addWidget(self._lock_mark)

        row1.addStretch()
        layout.addLayout(row1)

        # 第二行：效果数值
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        value = effect_data.get("value", 0.0)
        val_lbl = QLabel(f"数值: {value:.4f}%")
        val_lbl.setObjectName("resultValue")
        row2.addWidget(val_lbl)
        row2.addStretch()
        layout.addLayout(row2)

        # 第三行：来源
        row3 = QHBoxLayout()
        row3.setContentsMargins(0, 0, 0, 0)
        source = effect_data.get("source", "其他效果")
        src_lbl = QLabel(f"来源: {source}")
        src_lbl.setObjectName("labelSecondary")
        row3.addWidget(src_lbl)
        row3.addStretch()
        layout.addLayout(row3)

        # 第四行：默认隐藏状态
        row4 = QHBoxLayout()
        row4.setContentsMargins(0, 0, 0, 0)
        hidden = effect_data.get("default_hidden", False)
        status_text = "默认隐藏" if hidden else "可见"
        status_lbl = QLabel(f"状态: {status_text}")
        status_lbl.setObjectName("labelSecondary")
        row4.addWidget(status_lbl)
        row4.addStretch()
        layout.addLayout(row4)

        # 副名称（如果有）
        sub_name = effect_data.get("sub_name", "")
        if sub_name:
            row5 = QHBoxLayout()
            row5.setContentsMargins(0, 0, 0, 0)
            sub_lbl = QLabel(f"副名称: {sub_name}")
            sub_lbl.setStyleSheet("color: #64b5f6; font-size: 12px;")
            row5.addWidget(sub_lbl)
            row5.addStretch()
            layout.addLayout(row5)

        # 第五行：按钮（锁定 / 展开 / 删除）
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)

        self._lock_btn = QPushButton("锁定")
        self._lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lock_btn.setStyleSheet(
            "QPushButton { color: #ffcc80; background: rgba(255,152,0,0.10); "
            "border: 1px solid rgba(255,152,0,0.22); border-radius: 3px; padding: 2px 8px; }"
            "QPushButton:hover { background: rgba(255,152,0,0.18); }")
        self._lock_btn.clicked.connect(self._toggle_lock)
        btn_row.addWidget(self._lock_btn)

        expand_btn = QPushButton("展开")
        expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        expand_btn.setStyleSheet(
            "QPushButton { color: #81c784; background: rgba(76,175,80,0.16); "
            "border: 1px solid rgba(76,175,80,0.30); border-radius: 3px; padding: 2px 8px; }"
            "QPushButton:hover { background: rgba(76,175,80,0.24); }")
        expand_btn.clicked.connect(self._on_expand)
        btn_row.addWidget(expand_btn)

        del_btn = QPushButton("删除")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton { color: #ef9a9a; background: rgba(198,40,40,0.18); "
            "border: 1px solid rgba(198,40,40,0.35); border-radius: 3px; padding: 2px 8px; }"
            "QPushButton:hover { background: rgba(198,40,40,0.28); }")
        del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(del_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 回调
        self._expand_cb = None
        self._delete_cb = None

    def _toggle_lock(self):
        self._locked = not self._locked
        self._lock_mark.setVisible(self._locked)
        self._lock_btn.setText("解锁" if self._locked else "锁定")

    def _on_expand(self):
        if self._expand_cb:
            self._expand_cb(self._idx, self._effect)

    def _on_delete(self):
        if self._delete_cb:
            self._delete_cb(self._idx)

    def set_expand_callback(self, cb):
        self._expand_cb = cb

    def set_delete_callback(self, cb):
        self._delete_cb = cb

    def is_locked(self):
        return self._locked


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

        # 返回按钮
        back_btn = QPushButton("← 返回总界面")
        back_btn.setObjectName("backButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedWidth(140)
        main_layout.addWidget(back_btn)
        self.back_clicked = back_btn.clicked

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

        # ── 页面3: 结果列表 ──
        self.tab_result = QWidget()
        self._result_cards = []
        self._build_result_tab()
        self.tabs.addTab(self.tab_result, "结果列表")

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
            self._refresh_result_list()

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

    def _build_result_tab(self):
        layout = QVBoxLayout(self.tab_result)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("结果列表")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._result_container = QWidget()
        self._result_grid = QGridLayout(self._result_container)
        self._result_grid.setSpacing(12)
        self._result_grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._result_container)
        layout.addWidget(scroll, stretch=1)

        # 初始提示
        self._result_empty_label = QLabel("在「共鸣链」页面添加效果后，这里会显示对应的结果卡片。")
        self._result_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_empty_label.setObjectName("labelSecondary")
        self._result_grid.addWidget(self._result_empty_label, 0, 0, 1, 3)

    def _refresh_result_list(self):
        """根据共鸣链数据刷新结果列表"""
        # 清空旧卡片
        while self._result_grid.count():
            child = self._result_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._result_cards.clear()

        # 收集所有共鸣链效果
        all_effects = []
        for chain_idx, cd in enumerate(self._chain_data):
            for eff in cd["effects"]:
                eff_copy = dict(eff)
                eff_copy["chain"] = f"{chain_idx} 链"
                all_effects.append(eff_copy)

        if not all_effects:
            self._result_empty_label = QLabel("在「共鸣链」页面添加效果后，这里会显示对应的结果卡片。")
            self._result_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_empty_label.setObjectName("labelSecondary")
            self._result_grid.addWidget(self._result_empty_label, 0, 0, 1, 3)
            return

        # 生成卡片（3 列，从左到右排列）
        cols = 3
        for i, eff in enumerate(all_effects):
            card = _PresetResultCard(eff, idx=i)
            card.set_expand_callback(self._on_result_expand)
            card.set_delete_callback(self._on_result_delete)
            self._result_cards.append(card)
            row, col = divmod(i, cols)
            self._result_grid.addWidget(card, row, col,
                                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # 底部弹簧
        last_row = (len(all_effects) - 1) // cols if all_effects else 0
        self._result_grid.setRowStretch(last_row + 1, 1)

    def _on_result_expand(self, idx, _effect):
        """展开结果卡片详情"""
        eff = self._find_effect_by_idx(idx)
        if eff:
            dlg = _EditDialog(f"{eff.get('name', '效果')} - 详情", default_source="共鸣链效果", show_type=True, parent=self)
            dlg.set_effects([eff])
            dlg.exec()

    def _on_result_delete(self, idx):
        """删除结果卡片"""
        eff = self._find_effect_by_idx(idx)
        if eff:
            reply = QMessageBox.question(
                self, "确认删除", f"确定要删除效果「{eff.get('name', '')}」吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self._remove_effect_by_idx(idx)
                self._refresh_result_list()

    def _find_effect_by_idx(self, idx):
        """根据索引查找效果"""
        count = 0
        for _chain_idx, cd in enumerate(self._chain_data):
            for eff in cd["effects"]:
                if count == idx:
                    return eff
                count += 1
        return None

    def _remove_effect_by_idx(self, idx):
        """根据索引删除效果"""
        count = 0
        for chain_idx, cd in enumerate(self._chain_data):
            for i, _eff in enumerate(cd["effects"]):
                if count == idx:
                    cd["effects"].pop(i)
                    self._update_chain_summary(chain_idx)
                    return
                count += 1

    def to_dict(self):
        return {
            "name": self.char_name.text().strip(),
            "element": self.char_element.currentText(),
            "effect": self.char_effect.currentText(),
            "base_hp": self.base_hp.value(),
            "base_atk": self.base_atk.value(),
            "base_def": self.base_def.value(),
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
        chains = data.get("resonance_chain", [])
        for i, cd in enumerate(self._chain_data):
            if i < len(chains):
                ch = chains[i]
                cd["effects"] = ch.get("effects", [])
                cd["indep_zones"] = ch.get("indep_zones", [])
                self._update_chain_summary(i)
        self._refresh_result_list()


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

class _EchoSetEditor(QScrollArea):
    """声骸套装预设编辑"""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        widget = QWidget()
        self._root = QVBoxLayout(widget)
        self._root.setSpacing(12)
        self._root.setContentsMargins(8, 8, 8, 24)

        back_btn = QPushButton("← 返回总界面")
        back_btn.setObjectName("backButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedWidth(140)
        self._root.addWidget(back_btn)
        self.back_clicked = back_btn.clicked

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
        self.setWidget(widget)

        self._on_stage_count_changed(2)

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
    """预设构建器 —— 总界面 + 三类预设窗口"""

    def __init__(self, parent=None, edit_preset_data=None, edit_preset_path=None):
        super().__init__(parent)
        self.setWindowTitle("预设构建器")
        self.setMinimumSize(880, 670)
        self.resize(920, 710)
        self._edit_preset_path = edit_preset_path

        QTimer.singleShot(0, lambda: self._center())

        # 继承主程序主题
        self._apply_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()

        # 页面 0：总界面
        self.main_page = self._build_main_page()
        self.stack.addWidget(self.main_page)

        # 页面 1：声骸套装（保持原有设计）
        self.echo_editor = _EchoSetEditor()
        self.echo_editor.back_clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.echo_editor.save_clicked.connect(lambda: self._save_category("echo_set"))
        self.stack.addWidget(self.echo_editor)

        main_layout.addWidget(self.stack)

        if edit_preset_data:
            self._load_data(edit_preset_data)

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
            cl.setContentsMargins(20, 24, 20, 24)

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
        load_btn.clicked.connect(self._load_preset)
        layout.addWidget(load_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(3)

        return page

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
        """切换到声骸套装编辑页"""
        self.stack.setCurrentIndex(1)

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
            path, err = PresetManager.save_preset(preset, preset["name"])
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

    def _save_category(self, category):
        """保存声骸套装预设"""
        data = self.echo_editor.to_dict()
        default_name = data.get("name", "") or "未命名套装"

        preset = {
            "version": 1,
            "type": "preset",
            "name": default_name,
            "category": category,
            category: data,
        }

        if self._edit_preset_path:
            preset["name"] = os.path.splitext(os.path.basename(self._edit_preset_path))[0]
            path, err = PresetManager.save_preset(preset, preset["name"])
            if err:
                QMessageBox.warning(self, "保存失败", err)
                return
            QMessageBox.information(self, "保存成功", f"预设已保存到:\n{path}")
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

    def _load_preset(self):
        presets = PresetManager.list_presets()
        if not presets:
            QMessageBox.information(self, "无预设", "暂无已保存的预设文件。\n\n请先创建并保存预设。")
            return

        names = [f"[{'官方' if p['source'] == 'official' else '用户'}] {p['name']}"
                 for p in presets]
        item, ok = QInputDialog.getItem(self, "加载预设", "选择要编辑的预设:", names, 0, False)
        if not ok or not item:
            return

        idx = names.index(item)
        preset_info = presets[idx]
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
            self._load_data(data)
            self.stack.setCurrentIndex(1)

    def _load_data(self, data):
        if "echo_set" in data and data["echo_set"]:
            self.echo_editor.load_data(data["echo_set"])
