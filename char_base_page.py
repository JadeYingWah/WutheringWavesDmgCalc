# -*- coding: utf-8 -*-
# 角色与武器基础属性页（从 WWDmgCalc.py 拆分）

__all__ = ["CharBasePage"]

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QCheckBox, QGroupBox, QFormLayout,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

WEAPON_BONUS_TYPES = ["生命值", "攻击力", "防御力", "暴击率", "暴击伤害", "共鸣效率"]


class CharBasePage(QWidget):
    """角色与武器基础属性页. 等级/三维/武器攻击力/武器附加属性."""
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("角色基础数值")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        char_group = QGroupBox("角色属性")
        char_form = QFormLayout(char_group)

        self.hp_spin = QDoubleSpinBox()
        self.hp_spin.setRange(1, 100000)
        self.hp_spin.setDecimals(0)
        self.hp_spin.setValue(1)
        char_form.addRow("基础生命值:", self.hp_spin)

        self.atk_spin = QDoubleSpinBox()
        self.atk_spin.setRange(1, 10000)
        self.atk_spin.setDecimals(0)
        self.atk_spin.setValue(1)
        char_form.addRow("基础攻击力:", self.atk_spin)

        self.def_spin = QDoubleSpinBox()
        self.def_spin.setRange(1, 10000)
        self.def_spin.setDecimals(0)
        self.def_spin.setValue(1)
        char_form.addRow("基础防御力:", self.def_spin)

        layout.addWidget(char_group)

        weapon_group = QGroupBox("武器")
        weapon_form = QFormLayout(weapon_group)

        self.weapon_base_atk = QDoubleSpinBox()
        self.weapon_base_atk.setRange(0, 10000)
        self.weapon_base_atk.setDecimals(0)
        weapon_form.addRow("基础攻击力:", self.weapon_base_atk)

        weapon_form.addRow(QLabel(""))
        weapon_form.addRow(QLabel("附加属性（仅勾选一项）:"))

        self.checkbox_group = []
        for name in WEAPON_BONUS_TYPES:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            cb = QCheckBox(name)
            spin = QDoubleSpinBox()
            spin.setRange(0, 500)
            spin.setVisible(False)
            spin.setDecimals(4)

            unit_label = QLabel("百分比")
            unit_label.setObjectName("unitLabel")
            unit_label.setVisible(False)

            cb.toggled.connect(
                lambda checked, s=spin, u=unit_label, c=cb:
                self._on_attr_checked(c, checked, s, u)
            )

            self.checkbox_group.append((cb, spin, unit_label))

            row_layout.addWidget(cb)
            row_layout.addWidget(spin)
            row_layout.addWidget(unit_label)
            row_layout.addStretch()

            weapon_form.addRow(row_widget)

        layout.addWidget(weapon_group)

        wiki_btn = QPushButton("访问官方维基")
        wiki_btn.setObjectName("backButton")
        wiki_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wiki_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://wiki.kurobbs.com/mc/home")))
        layout.addWidget(wiki_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

        self._on_change_cb = None
        # 连接值变更信号
        for spin in [self.hp_spin, self.atk_spin, self.def_spin, self.weapon_base_atk]:
            spin.valueChanged.connect(self._notify_change)
        for cb, spin, ul in self.checkbox_group:
            spin.valueChanged.connect(self._notify_change)

    def _notify_change(self, *_):
        if self._on_change_cb:
            self._on_change_cb()

    def _on_attr_checked(self, checked_cb, checked, spin, unit_label):
        if checked:
            for cb, sp, ul in self.checkbox_group:
                if cb is not checked_cb:
                    cb.setChecked(False)
                    sp.setVisible(False)
                    ul.setVisible(False)
            spin.setVisible(True)
            unit_label.setVisible(True)
        else:
            spin.setVisible(False)
            unit_label.setVisible(False)
        self._notify_change()

    def collect_data(self):
        weapon_attr = None
        for cb, spin, ul in self.checkbox_group:
            if cb.isChecked():
                weapon_attr = (cb.text(), spin.value())
                break

        return {
            'base_hp': self.hp_spin.value(),
            'base_atk': self.atk_spin.value(),
            'base_def': self.def_spin.value(),
            'weapon_base_atk': self.weapon_base_atk.value(),
            'weapon_bonus': weapon_attr,
        }

