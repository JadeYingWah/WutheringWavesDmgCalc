# -*- coding: utf-8 -*-
# 抗性数值页（从 WWDmgCalc.py 拆分）

__all__ = ["EnemyResistancePage"]

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QCheckBox, QDoubleSpinBox,
    QGroupBox, QScrollArea, QApplication,
    QHeaderView, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRect

import damage_calc

# ── 从主编注入（不再本地复制，消除 ~50 行冗余） ──
_cell_center = None
_fix_table_height = None
_CombinedEntryPage = None
_PropTable = None
_place_highlight_overlay = None

def inject_deps(combined_entry_cls, cell_center_fn, fix_table_height_fn, prop_table_cls, place_hl_fn):
    global _cell_center, _fix_table_height, _CombinedEntryPage, _PropTable, _place_highlight_overlay
    _cell_center = cell_center_fn
    _fix_table_height = fix_table_height_fn
    _CombinedEntryPage = combined_entry_cls
    _PropTable = prop_table_cls
    _place_highlight_overlay = place_hl_fn


class EnemyResistancePage(QWidget):
    """敌人抗性页. 6 元素抗性 + 预设 + 外部抗性来源叠加."""
    TYPES = ["冷凝抗性", "热熔抗性", "气动抗性", "导电抗性", "衍射抗性", "湮灭抗性"]
    navigate_requested = None

    def __init__(self):
        super().__init__()
        self._on_change_cb = None
        self._res_mult = {}  # {rtype: zone_value}
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ---- 标题 ----
        title = QLabel("抗性数值")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        desc = QLabel("敌人抗性由基础抗性、抗性提升、抗性减少共同决定。预设按钮可快速填充世界、深塔、全息抗性数据，也可手动调整各属性数值。")
        desc.setObjectName("labelSecondary")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ---- 预设按钮 ----
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        world_btn = QPushButton("世界抗性")
        world_btn.setObjectName("backButton")
        world_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        world_btn.clicked.connect(lambda: self._apply_preset("world"))
        preset_row.addWidget(world_btn)

        tower_btn = QPushButton("深塔抗性")
        tower_btn.setObjectName("backButton")
        tower_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tower_btn.clicked.connect(lambda: self._apply_preset("tower"))
        preset_row.addWidget(tower_btn)

        holo_btn = QPushButton("全息抗性")
        holo_btn.setObjectName("backButton")
        holo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        holo_btn.clicked.connect(lambda: self._apply_preset("holo"))
        preset_row.addWidget(holo_btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        # ---- 抗性提升标识 ----
        boost_row = QHBoxLayout()
        boost_row.setSpacing(8)
        boost_label = QLabel("抗性提升标识：")
        boost_label.setObjectName("labelSecondary")
        boost_row.addWidget(boost_label)
        self._boost_checks = {}  # {type_name: QCheckBox}
        for t in self.TYPES:
            cb = QCheckBox(t)
            cb.setObjectName("smallCheckbox")
            cb.stateChanged.connect(self._apply_boost_markers)
            self._boost_checks[t] = cb
            boost_row.addWidget(cb)
        boost_row.addStretch()
        layout.addLayout(boost_row)

        # ---- 属性表格 ----
        self.table = QTableWidget()
        self.table.setObjectName("attrTable")
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["抗性类型", "基础抗性 %", "抗性提升 %", "抗性减少 %", "最终抗性", "抗性乘区"]
        )
        self.table.setRowCount(len(self.TYPES))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        hdr = self.table.horizontalHeader()
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 6):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)

        self._spins = {}  # {(row, col): QDoubleSpinBox}

        for i, rtype in enumerate(self.TYPES):
            item = QTableWidgetItem(rtype)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, item)

            for col in range(1, 4):
                spin = QDoubleSpinBox()
                spin.setRange(0, 999)
                spin.setDecimals(4)
                spin.setValue(0)
                spin.valueChanged.connect(self._recalc)
                w = QWidget()
                wl = QHBoxLayout(w)
                wl.setContentsMargins(0, 0, 0, 0)
                wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                wl.addWidget(spin)
                self.table.setCellWidget(i, col, w)
                self._spins[(i, col)] = spin

            # 抗性乘区列占位
            self.table.setItem(i, 5, QTableWidgetItem(""))

        layout.addWidget(self.table)

        # ---- 抗性减伤·常驻 ----
        perm_label = QLabel("抗性减伤 · 常驻")
        perm_label.setObjectName("groupBoxTitle")
        layout.addWidget(perm_label)
        self.perm_table = self._make_def_table(
            ["启用", "属性名称", "副名称", "序列号", "数值", "来源"],
            proportions=[0.08, 0.20, 0.12, 0.10, 0.18, 0.22]
        )
        layout.addWidget(self.perm_table)

        # ---- 抗性减伤·触发 ----
        trig_header = QHBoxLayout()
        trig_label = QLabel("抗性减伤 · 触发")
        trig_label.setObjectName("groupBoxTitle")
        trig_header.addWidget(trig_label)
        trig_header.addStretch()
        all_btn = QPushButton("全选")
        all_btn.setObjectName("backButton")
        all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        all_btn.clicked.connect(self._trigger_select_all)
        trig_header.addWidget(all_btn)
        none_btn = QPushButton("全不选")
        none_btn.setObjectName("backButton")
        none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        none_btn.clicked.connect(self._trigger_select_none)
        trig_header.addWidget(none_btn)
        layout.addLayout(trig_header)

        self.trig_table = self._make_def_table(
            ["启用", "属性名称", "副名称", "序列号", "数值", "来源"],
            proportions=[0.08, 0.20, 0.12, 0.10, 0.18, 0.22]
        )
        layout.addWidget(self.trig_table)

        layout.addStretch()

        # 外部来源
        self._external_sources = []
        self._trigger_states = {}
        self._current_preset = None

        self._recalc()

    # ========== 表格工厂 ==========
    def _make_def_table(self, headers, proportions=None):
        if proportions is None:
            proportions = [1.0 / len(headers)] * len(headers)
        table = _PropTable(proportions)
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

    # ========== 外部来源 ==========
    def set_external_sources(self, sources):
        self._external_sources = sources
        self._trigger_states.clear()
        self._recalc()

    def _make_item_key(self, name, src_label, seq_label=""):
        return f"{name}___{src_label}___{seq_label}"

    def _trigger_select_all(self):
        for cb in self._trig_checkbox_widgets:
            self._trigger_states[cb._item_key] = True
            cb.setChecked(True)
        self._recalc()

    def _trigger_select_none(self):
        for cb in self._trig_checkbox_widgets:
            self._trigger_states[cb._item_key] = False
            cb.setChecked(False)
        self._recalc()

    def _on_item_toggled(self, key, checked):
        self._trigger_states[key] = checked
        self._recalc()

    def _on_source_clicked(self, nav_key, seq_label=""):
        if self.navigate_requested:
            self.navigate_requested(nav_key)
        if seq_label:
            QTimer.singleShot(350, lambda: self._do_highlight_in_source(nav_key, seq_label))

    def _do_highlight_in_source(self, nav_key, seq_label):
        try:
            ms = self.window().main_screen if self.window() else None
            if not ms:
                return
            QApplication.processEvents()
            for key in ["combined_perm", "combined_trigger"]:
                scroll = ms._scrolls.get(key)
                if not scroll: continue
                pw = scroll.widget()
                if not isinstance(pw, _CombinedEntryPage): continue
                type_label = "常驻" if key == "combined_perm" else "触发"
                for r in range(len(pw._rows)):
                    try:
                        row_data = pw.collect_data()[r]
                        row_seq = row_data[4] if len(row_data) > 4 else ""
                        if row_seq == seq_label:
                            pw._highlight_row(r, scroll)
                            return
                    except (IndexError, AttributeError):
                        continue
        except Exception:
            pass

    def highlight_item(self, name, src_label, nav_key, seq_label=""):
        """按序列号在表格中定位并高亮（seq_label 在列3）"""
        for table in [self.perm_table, self.trig_table]:
            for r in range(table.rowCount()):
                item = table.item(r, 3)
                if item and item.text() == seq_label:
                    scroll = None
                    p = table.parent()
                    while p:
                        if isinstance(p, QScrollArea):
                            scroll = p; break
                        p = p.parent()
                    if scroll:
                        self._scroll_and_highlight(table, r, scroll)
                    else:
                        table.scrollTo(table.model().index(r, 0))
                        QTimer.singleShot(200, lambda tb=table, row=r:
                                          self._show_highlight_overlay(tb, row))
                    return

    def _scroll_and_highlight(self, table, row, scroll):
        QApplication.processEvents()
        # 几何计算：行 Y = 表头 + 累积行高
        hdr_h = table.horizontalHeader().height() if table.horizontalHeader().isVisible() else 0
        row_y = hdr_h + sum(table.rowHeight(i) for i in range(row))
        table_origin = table.mapTo(scroll.widget(), QPoint(0, 0))
        target_y = table_origin.y() + row_y
        vp_h = scroll.viewport().height()
        desired = max(0, target_y - vp_h // 5)
        sb = scroll.verticalScrollBar()
        old_pos = sb.value()
        if abs(desired - old_pos) < 2:
            QTimer.singleShot(80, lambda: self._show_highlight_overlay(table, row))
            return
        anim = QPropertyAnimation(sb, b"value")
        anim.setDuration(450)
        anim.setStartValue(old_pos)
        anim.setEndValue(min(desired, sb.maximum()))
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.finished.connect(lambda tb=table, r=row:
            QTimer.singleShot(80, lambda: self._show_highlight_overlay(tb, r)))
        scroll._scroll_anim = anim
        anim.start()

    def _show_highlight_overlay(self, table, row):
        QApplication.processEvents()
        vp = table.viewport()
        idx = table.model().index(row, 0)
        rect = table.visualRect(idx)
        if rect.y() < 0 or rect.y() > vp.height():
            return
        row_rect = QRect(0, rect.y(), vp.width(), table.rowHeight(row))
        _place_highlight_overlay(vp, row_rect, "background-color: #ffeb3b;")

    # ========== 构建外部来源 UI ==========
    def _build_ext_ui(self, perm_items, trig_items):
        def _centered(text):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            return item

        # 常驻
        self.perm_table.setRowCount(0)
        self._perm_checkbox_widgets = []
        for item_tuple in perm_items:
            name, value, src_label, nav_key = item_tuple[:4]
            sub_name = item_tuple[5] if len(item_tuple) > 5 else ""
            seq_label = item_tuple[4] if len(item_tuple) > 4 else ""
            key = self._make_item_key(name, src_label, seq_label)
            if key not in self._trigger_states:
                self._trigger_states[key] = True
            r = self.perm_table.rowCount()
            self.perm_table.insertRow(r)
            cb = QCheckBox()
            cb.setChecked(self._trigger_states[key])
            cb._item_key = key
            cb.toggled.connect(lambda chk, k=key: self._on_item_toggled(k, chk))
            self._perm_checkbox_widgets.append(cb)
            _cell_center(self.perm_table, r, 0, cb)
            self.perm_table.setItem(r, 1, _centered(name))
            # 副名称：带 ... 编辑按钮的 QLineEdit
            from PyQt6.QtWidgets import QLineEdit, QPushButton, QHBoxLayout, QWidget
            sub_widget = QWidget()
            sub_lay = QHBoxLayout(sub_widget)
            sub_lay.setContentsMargins(0, 0, 0, 0)
            sub_lay.setSpacing(2)
            sub_edit = QLineEdit(sub_name)
            sub_edit.setObjectName("nameEdit")
            sub_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_edit.setPlaceholderText("（备注）")
            sub_lay.addWidget(sub_edit, stretch=1)
            exp_btn = QPushButton("...")
            exp_btn.setFixedWidth(24)
            exp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            exp_btn.clicked.connect(lambda _, le=sub_edit: _make_sub_name_editor(le))
            sub_lay.addWidget(exp_btn)
            _cell_center(self.perm_table, r, 2, sub_widget)
            self.perm_table.setItem(r, 3, _centered(seq_label))
            self.perm_table.setItem(r, 4, _centered(f"{value:.1f}%"))
            src_btn = QPushButton(src_label)
            src_btn.setObjectName("backButton")
            src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            src_btn.clicked.connect(lambda _, nk=nav_key, sq=seq_label:
                                    self._on_source_clicked(nk, sq))
            _cell_center(self.perm_table, r, 5, src_btn)

        # 触发
        self.trig_table.setRowCount(0)
        self._trig_checkbox_widgets = []
        for item_tuple in trig_items:
            name, value, src_label, nav_key = item_tuple[:4]
            sub_name = item_tuple[5] if len(item_tuple) > 5 else ""
            seq_label = item_tuple[4] if len(item_tuple) > 4 else ""
            key = self._make_item_key(name, src_label, seq_label)
            if key not in self._trigger_states:
                self._trigger_states[key] = True
            r = self.trig_table.rowCount()
            self.trig_table.insertRow(r)
            cb = QCheckBox()
            cb.setChecked(self._trigger_states[key])
            cb._item_key = key
            cb.toggled.connect(lambda chk, k=key: self._on_item_toggled(k, chk))
            self._trig_checkbox_widgets.append(cb)
            _cell_center(self.trig_table, r, 0, cb)
            self.trig_table.setItem(r, 1, _centered(name))
            from PyQt6.QtWidgets import QLineEdit, QPushButton, QHBoxLayout, QWidget
            sub_widget = QWidget()
            sub_lay = QHBoxLayout(sub_widget)
            sub_lay.setContentsMargins(0, 0, 0, 0)
            sub_lay.setSpacing(2)
            sub_edit = QLineEdit(sub_name)
            sub_edit.setObjectName("nameEdit")
            sub_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_edit.setPlaceholderText("（备注）")
            sub_lay.addWidget(sub_edit, stretch=1)
            exp_btn = QPushButton("...")
            exp_btn.setFixedWidth(24)
            exp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            exp_btn.clicked.connect(lambda _, le=sub_edit: _make_sub_name_editor(le))
            sub_lay.addWidget(exp_btn)
            _cell_center(self.trig_table, r, 2, sub_widget)
            self.trig_table.setItem(r, 3, _centered(seq_label))
            self.trig_table.setItem(r, 4, _centered(f"{value:.1f}%"))
            src_btn = QPushButton(src_label)
            src_btn.setObjectName("backButton")
            src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            src_btn.clicked.connect(lambda _, nk=nav_key, sq=seq_label:
                                    self._on_source_clicked(nk, sq))
            _cell_center(self.trig_table, r, 5, src_btn)


    # ========== 计算 ==========
    def _recalc(self, *_):
        # 计算每类抗性的基础最终值（来自表格）
        table_final = {}
        for i, rtype in enumerate(self.TYPES):
            base = self._spins[(i, 1)].value()
            boost = self._spins[(i, 2)].value()
            reduce = self._spins[(i, 3)].value()
            final = (base * (1 + boost / 100.0)) - reduce
            table_final[rtype] = final

        # 从外部来源收集每类抗性的减免值
        ext_reduce = {t: 0.0 for t in self.TYPES}
        perm_out = []
        trig_out = []

        for src_label, page, nav_key, category in self._external_sources:
            for item_data in page.collect_data():
                name = item_data[0]; value = item_data[1]
                if not damage_calc.is_resistance_item(name):
                    continue
                seq_label = item_data[4] if len(item_data) > 4 and item_data[4] else ""
                key = self._make_item_key(name, src_label, seq_label)
                active = self._trigger_states.get(key, True)
                if name == "全属性抗性减少":
                    targets = list(self.TYPES)
                else:
                    matched_type = None
                    for t in self.TYPES:
                        if name.startswith(t):
                            matched_type = t
                            break
                    targets = [matched_type] if matched_type else []
                if category == "常驻":
                    if active:
                        for t in targets:
                            ext_reduce[t] += value
                    sub_name = item_data[5] if len(item_data) > 5 else ""
                    perm_out.append((name, value, src_label, nav_key, seq_label, sub_name))
                else:
                    if active:
                        for t in targets:
                            ext_reduce[t] += value
                    sub_name = item_data[5] if len(item_data) > 5 else ""
                    trig_out.append((name, value, src_label, nav_key, seq_label, sub_name))

        # 更新表格：最终抗性 和 抗性乘区（委托 damage_calc 计算）
        for i, rtype in enumerate(self.TYPES):
            final_res = table_final[rtype] - ext_reduce[rtype]
            res_mult = damage_calc.calc_resistance_zone(
                table_final[rtype], 0, 0, ext_reduce[rtype]
            )
            self._res_mult[rtype] = res_mult

            # 最终抗性列
            fres = QTableWidgetItem(f"{final_res:.1f}%")
            fres.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 4, fres)

            # 抗性乘区列
            mul = QTableWidgetItem(f"{res_mult:.10f}")
            mul.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 5, mul)

        self._build_ext_ui(perm_out, trig_out)
        if self._on_change_cb:
            self._on_change_cb()

    # ========== 预设 ==========
    BASE_VALUES = {"world": 10, "tower": 20, "holo": 10}
    BOOST_VALUES = {"world": 30, "tower": 40, "holo": 70}

    def _apply_preset(self, preset):
        self._current_preset = preset
        base = self.BASE_VALUES[preset]
        boost = self.BOOST_VALUES[preset]
        for i, t in enumerate(self.TYPES):
            if self._boost_checks[t].isChecked():
                self._spins[(i, 1)].setValue(base + boost)
            else:
                self._spins[(i, 1)].setValue(base)
            self._spins[(i, 2)].setValue(0)
            self._spins[(i, 3)].setValue(0)
        self._recalc()

    def _apply_boost_markers(self):
        if self._current_preset:
            self._apply_preset(self._current_preset)

    def get_resistance_multiplier(self, element_name=None):
        """抗性乘数；优先用 _res_mult 缓存避免 widget 时序问题。"""
        if not hasattr(self, "_res_mult") or not self._res_mult:
            self._recalc()
        m = dict(self._res_mult) if hasattr(self, "_res_mult") and self._res_mult else {}
        if not m:
            return 1.0
        if element_name and element_name != "(无)":
            k = element_name + "抗性"
            if k in m:
                return m[k]
        return min(m.values())




