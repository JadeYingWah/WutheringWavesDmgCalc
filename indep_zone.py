# -*- coding: utf-8 -*-
# 独立乘区页（从 WWDmgCalc.py 拆分）

__all__ = ["IndepZonePage"]

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QDoubleSpinBox, QCheckBox, QFrame,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt


class IndepZonePage(QWidget):
    """独立乘区：多个独立乘区组，组内加法、组间乘法"""

    def __init__(self):
        super().__init__()
        self._groups = []  # [{name_edit, rows:[(ne,vs),..], frame, result_label}, ...]
        self._on_change_cb = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("独立乘区")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        desc = QLabel("每个独立乘区组内部各数值相加后以 (1 + 合计/100) 计算；\n"
                      "各组之间为乘法关系。")
        desc.setObjectName("labelSecondary")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 总结果
        result_container = QHBoxLayout()
        result_container.addStretch()
        self._result_label = QLabel("独立乘区 = 1.0000000000")
        self._result_label.setObjectName("resultValue")
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_container.addWidget(self._result_label)
        result_container.addStretch()
        layout.addLayout(result_container)

        # 组容器
        self._groups_layout = QVBoxLayout()
        self._groups_layout.setSpacing(10)
        layout.addLayout(self._groups_layout)

        # 添加组按钮
        add_group_btn = QPushButton("添加独立乘区组")
        add_group_btn.setObjectName("itemAddBtn")
        add_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_group_btn.clicked.connect(lambda: self._add_group())
        layout.addWidget(add_group_btn)

        layout.addStretch()

    def _add_group(self, name="", values=None):
        """添加一个独立乘区组。values: [(name, value%), ...]"""
        if values is None:
            values = []

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setObjectName("indepGroupFrame")

        group_layout = QVBoxLayout(frame)
        group_layout.setSpacing(4)

        # 顶部：组名 + 一键隐藏 + 删除组
        top_row = QHBoxLayout()
        name_edit = QLineEdit(name)
        name_edit.setObjectName("nameEdit")
        name_edit.setPlaceholderText("乘区组名称")
        name_edit.setMinimumWidth(120)
        name_edit.setMaximumWidth(200)
        name_edit.textChanged.connect(lambda _: self._notify_change())
        top_row.addWidget(name_edit)
        top_row.addStretch()

        hide_all_btn = QPushButton("一键隐藏")
        hide_all_btn.setObjectName("backButton")
        hide_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        hide_all_btn.setToolTip("隐藏/显示当前组内所有数值")
        top_row.addWidget(hide_all_btn)

        del_group_btn = QPushButton("删除组")
        del_group_btn.setObjectName("backButton")
        del_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_group_btn.clicked.connect(lambda: self._remove_group(frame))
        top_row.addWidget(del_group_btn)
        group_layout.addLayout(top_row)

        # 数值行容器
        rows_layout = QVBoxLayout()
        rows_layout.setSpacing(3)
        group_layout.addLayout(rows_layout)

        # 添加数值按钮
        add_val_btn = QPushButton("添加数值")
        add_val_btn.setObjectName("backButton")
        add_val_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        group_layout.addWidget(add_val_btn)

        # 组结果
        result_lbl = QLabel("该乘区总数值 = 1.0000000000")
        result_lbl.setObjectName("labelSecondary")
        group_layout.addWidget(result_lbl)

        group_data = {
            "name_edit": name_edit,
            "rows": [],
            "frame": frame,
            "rows_layout": rows_layout,
            "result_label": result_lbl,
        }

        # 连接添加数值按钮
        add_val_btn.clicked.connect(lambda: self._add_value_row(group_data))

        # 一键隐藏/显示当前组内所有数值
        def toggle_hide_all():
            if not group_data["rows"]:
                return
            all_hidden = all(cb.isChecked() for _, _, cb in group_data["rows"])
            new_state = not all_hidden
            # 临时阻断 _on_change_cb，避免每个 checkbox 单独触发重算
            old_cb = self._on_change_cb
            self._on_change_cb = None
            for _, _, cb in group_data["rows"]:
                if cb.isChecked() != new_state:
                    cb.setChecked(new_state)  # toggled 信号自动处理 _dim_row
            self._on_change_cb = old_cb
            hide_all_btn.setText("取消隐藏" if new_state else "一键隐藏")
            self._notify_change()
        hide_all_btn.clicked.connect(toggle_hide_all)

        # 恢复已有数值（兼容 2 元素和 3 元素 tuple）
        for item in values:
            if len(item) == 3:
                vname, vval, vhidden = item
            else:
                vname, vval = item
                vhidden = False
            self._add_value_row(group_data, vname, vval, vhidden)

        self._groups.append(group_data)
        self._groups_layout.addWidget(frame)
        self.recalc()

    def _add_value_row(self, group_data, name="", value=0.0, hidden=False):
        row_widget = QWidget()
        row_widget.setObjectName("indepValueRow")
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        name_edit = QLineEdit(name)
        name_edit.setObjectName("nameEdit")
        name_edit.setPlaceholderText("名称")
        name_edit.setMinimumWidth(100)
        name_edit.setMaximumWidth(150)
        name_edit.textChanged.connect(lambda _: self._notify_change())
        row_layout.addWidget(name_edit)

        value_spin = QDoubleSpinBox()
        value_spin.setRange(0, 99999)
        value_spin.setDecimals(4)
        value_spin.setValue(value)
        value_spin.setSuffix("%")
        value_spin.valueChanged.connect(lambda _: self._notify_change())
        row_layout.addWidget(value_spin)

        hide_cb = QCheckBox("隐藏")
        hide_cb.setObjectName("smallCheckbox")
        hide_cb.setChecked(hidden)
        hide_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        hide_cb.setToolTip("勾选后该数值不参与独立乘区计算")
        hide_cb.toggled.connect(lambda checked: self._on_row_hidden_toggled(row_widget, checked))
        row_layout.addWidget(hide_cb)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("backButton")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self._remove_value_row(group_data, row_widget))
        row_layout.addWidget(del_btn)

        row_layout.addStretch()

        group_data["rows"].append((name_edit, value_spin, hide_cb))
        group_data["rows_layout"].addWidget(row_widget)
        if hidden:
            self._dim_row(row_widget, True)
        self._notify_change()

    def _on_row_hidden_toggled(self, row_widget, checked):
        """行隐藏复选框切换：变灰 + 重算 + 同步一键隐藏按钮"""
        self._dim_row(row_widget, checked)
        # 同步该组的"一键隐藏"按钮文字
        gd = self._find_group_for_row(row_widget)
        if gd and gd["rows"]:
            all_hidden = all(cb.isChecked() for _, _, cb in gd["rows"])
            self._sync_hide_all_btn(gd, all_hidden)
        self._notify_change()

    def _find_group_for_row(self, row_widget):
        """找到 row_widget 所属的 group_data"""
        for gd in self._groups:
            for ne, vs, cb in gd["rows"]:
                if ne.parent() is row_widget or ne.parent().parent() is row_widget:
                    return gd
                # ne.parent() could be row_widget; or the outer widget wrapping
                w = ne.parent()
                while w:
                    if w is row_widget:
                        return gd
                    w = w.parent()
        return None

    def _sync_hide_all_btn(self, group_data, all_hidden):
        """根据全隐藏状态更新组内一键隐藏按钮文字"""
        frame = group_data["frame"]
        for child in frame.findChildren(QPushButton):
            if child.text() in ("一键隐藏", "取消隐藏"):
                child.setText("取消隐藏" if all_hidden else "一键隐藏")
                break

    def _dim_row(self, row_widget, dim):
        """将整行变灰或恢复（直接作用于 row_widget，不穿透子控件）"""
        try:
            from PyQt6.QtWidgets import QGraphicsOpacityEffect
            opacity = 0.35 if dim else 1.0
            if dim:
                eff = row_widget.graphicsEffect()
                if eff is None:
                    eff = QGraphicsOpacityEffect()
                    row_widget.setGraphicsEffect(eff)
                eff.setOpacity(opacity)
            else:
                # 恢复：移除效果即可
                row_widget.setGraphicsEffect(None)
        except Exception:
            pass

    def _remove_value_row(self, group_data, row_widget):
        for i, (ne, vs, cb) in enumerate(group_data["rows"]):
            pw = ne.parent()
            if pw is row_widget:
                group_data["rows"].pop(i)
                break
        else:
            idx = group_data["rows_layout"].indexOf(row_widget)
            if 0 <= idx < len(group_data["rows"]):
                group_data["rows"].pop(idx)
        group_data["rows_layout"].removeWidget(row_widget)
        row_widget.deleteLater()
        self._notify_change()

    def _remove_group(self, frame):
        for i, gd in enumerate(self._groups):
            if gd["frame"] is frame:
                self._groups.pop(i)
                break
        self._groups_layout.removeWidget(frame)
        frame.deleteLater()
        self._notify_change()

    def _notify_change(self):
        self.recalc()
        if self._on_change_cb:
            self._on_change_cb()

    def recalc(self):
        zone = 1.0
        self._group_factors = []
        for gd in self._groups:
            total = sum(vs.value() for _, vs, cb in gd["rows"] if not cb.isChecked())
            group_factor = 1.0 + total / 100.0
            gd["result_label"].setText(f"该乘区总数值 = {group_factor:.10f}")
            name = gd["name_edit"].text()
            self._group_factors.append((name, group_factor))
            zone *= group_factor
        self.independent_zone = zone
        self._result_label.setText(f"独立乘区 = {zone:.10f}")

    @property
    def group_factors(self):
        if not self._groups:
            return []
        return self._group_factors

    def collect_data(self):
        return [
            {
                "name": gd["name_edit"].text(),
                "values": [(ne.text(), vs.value(), cb.isChecked()) for ne, vs, cb in gd["rows"]],
            }
            for gd in self._groups
        ]

    def apply_data(self, data):
        # 清除旧组（先隐藏再标记删除）
        while self._groups:
            gd = self._groups.pop()
            frame = gd["frame"]
            self._groups_layout.removeWidget(frame)
            frame.hide()
            frame.setParent(None)
            frame.deleteLater()
        # 恢复（兼容旧格式：2 元素和 3 元素 tuple）
        for g in (data or []):
            values = []
            for item in g.get("values", []):
                if len(item) == 3:
                    vname, vval, vhidden = item
                else:
                    vname, vval = item
                    vhidden = False
                values.append((vname, vval, vhidden))
            self._add_group(g.get("name", ""), values)


