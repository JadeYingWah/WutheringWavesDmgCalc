# -*- coding: utf-8 -*-
# 数值总结页（从 WWDmgCalc.py 拆分）
# 包含: SummaryBasePage / SummaryBaseZonePage / SummaryBonusZonePage /
#       SummaryDeepenZonePage / SummaryCritZonePage

__all__ = [
    "SummaryBasePage", "SummaryBaseZonePage",
    "SummaryBonusZonePage", "SummaryDeepenZonePage", "SummaryCritZonePage",
]

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QScrollArea, QApplication,
    QGraphicsOpacityEffect, QGroupBox, QFormLayout,
    QHeaderView, QDoubleSpinBox, QLineEdit,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRect

import damage_calc

# 从主编导入共享工具（运行时注入）
_fix_table_height = None
_place_highlight_overlay = None
from shared_state import HIDDEN_ITEMS, LOCKED_SUMMARY_ITEMS
_CombinedEntryPage = None
_collect_all_items = None
_PropTable = None
_cell_center = None
_CONSTANT_ATTRS = set()
_make_sub_name_cell = None


def inject_dependencies(fix_table_height_fn, place_hl_fn, combined_cls, collect_fn, prop_table_cls, cell_center_fn, constant_attrs, make_sub_name_cell_fn=None):
    """由主编在 import 后调用，注入共享依赖"""
    global _fix_table_height, _place_highlight_overlay
    global _CombinedEntryPage, _collect_all_items
    global _PropTable, _cell_center, _CONSTANT_ATTRS, _make_sub_name_cell
    _fix_table_height = fix_table_height_fn
    _place_highlight_overlay = place_hl_fn
    # HIDDEN_ITEMS / LOCKED_SUMMARY_ITEMS now from shared_state — skip injection
    _CombinedEntryPage = combined_cls
    _collect_all_items = collect_fn
    _PropTable = prop_table_cls
    _cell_center = cell_center_fn
    _CONSTANT_ATTRS = constant_attrs
    _make_sub_name_cell = make_sub_name_cell_fn


def set_make_sub_name_cell(fn):
    """延迟注入 _make_sub_name_cell（用于函数定义在 inject 之后的情况）"""
    global _make_sub_name_cell
    _make_sub_name_cell = fn


class SummaryBasePage(QWidget):
    """数值总结页基类. 汇总展示某一乘区的所有来源条目, 行可点击跳转."""
    def __init__(self, title_text, desc_text=""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(title_text)
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        if desc_text:
            desc = QLabel(desc_text)
            desc.setObjectName("labelSecondary")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        self._content_layout = QVBoxLayout()
        layout.addLayout(self._content_layout)
        layout.addStretch()

        self._external_sources = []
        self._echo_pages = {}
        self._filter_chips = {}   # group_name -> [chip_widget, ...]
        self._active_filters = {} # group_name -> "全部" | "无" | specific_value
        self._filtered_table = None
        self._filtered_all_items = []
        self._filter_refill_fn = None

    def set_external_sources(self, sources):
        self._external_sources = sources
        self.recalc()

    def set_echo_sources(self, echo_pages_dict):
        self._echo_pages = echo_pages_dict or {}
        self.recalc()

    def recalc(self):
        raise NotImplementedError

    def _build_filter_bar(self, groups):
        """Build filter chip buttons. groups: [(label, options_list), ...]
        Each option is a string. First option should be "全部".
        Returns a QWidget containing all filter rows."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        for group_label, options in groups:
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl = QLabel(group_label + ":")
            lbl.setObjectName("labelSecondary")
            lbl.setFixedWidth(70)
            row.addWidget(lbl)

            chips = []
            for opt in options:
                btn = QPushButton(opt)
                btn.setCheckable(True)
                btn.setFixedHeight(24)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    "QPushButton { border: 1px solid #555; border-radius: 12px; "
                    "padding: 1px 10px; font-size: 11px; background: transparent; } "
                    "QPushButton:hover { border-color: #888; } "
                    "QPushButton:checked { background: #3a6a9a; color: #fff; border-color: #5a9aca; }")
                if opt == "全部":
                    btn.setChecked(True)
                btn.clicked.connect(
                    lambda checked, g=group_label, o=opt, cl=chips:
                    self._on_filter_chip_clicked(g, o, cl))
                chips.append(btn)
                row.addWidget(btn)
            row.addStretch()
            layout.addLayout(row)
            self._filter_chips[group_label] = chips
            self._active_filters[group_label] = "全部"

        return container

    def _on_filter_chip_clicked(self, group_name, value, chips):
        """Handle filter chip click.
        
        时效类型单独设置 _timing_override，其他走通用 _active_filters。
        """
        for c in chips:
            c.blockSignals(True)
            c.setChecked(c.text() == value)
            c.blockSignals(False)
        if group_name == "时效类型":
            self._timing_override = value if value != "全部" else None
        else:
            self._active_filters[group_name] = value
        self._refilter_table()

    def _matches_filter(self, name):
        """混合逻辑：「无」强制 AND（必须不含该组任意值），
        具体值之间 OR，所有组「全部」时显示全部。"""
        values = self._active_filters

        # 全部「全部」→ 显示全部
        if all(v == "全部" for v in values.values()):
            return True

        # 第一轮：「无」是强制 AND —— 条目必须通过所有「无」组
        for group, value in values.items():
            if value == "无":
                if group in self._filter_chips:
                    for c in self._filter_chips[group]:
                        opt = c.text()
                        if opt not in ("全部", "无") and opt in name:
                            return False  # 含有该组属性 → 不通过

        # 第二轮：具体值和「全部」是 OR —— 条目匹配任一即通过
        has_specific = any(v != "全部" and v != "无" for v in values.values())
        if has_specific:
            for group, value in values.items():
                if value == "全部":
                    for c in self._filter_chips.get(group, []):
                        opt = c.text()
                        if opt not in ("全部", "无") and opt in name:
                            return True
                elif value != "无" and value in name:
                    return True
            return False

        # 只有「全部」和「无」（无具体值）：通过了「无」的条目 + 匹配任意「全部」组
        for group, value in values.items():
            if value == "全部":
                for c in self._filter_chips.get(group, []):
                    opt = c.text()
                    if opt not in ("全部", "无") and opt in name:
                        return True
        return False

    def _refilter_table(self):
        """Re-apply filters and refill the table. Items are 6-tuples."""
        if self._filtered_table is None:
            return
        filtered = [it for it in self._filtered_all_items
                    if self._matches_filter(it[0]) and self._matches_timing(it[3])]
        self._filtered_table.setRowCount(0)
        if self._filter_refill_fn:
            self._filter_refill_fn(self._filtered_table, filtered, self._navigate)

    def _matches_timing(self, nav_key):
        if self._timing_override is None:
            return True
        if self._timing_override == "常驻" and nav_key != "combined_perm":
            return False
        if self._timing_override == "触发" and nav_key != "combined_trigger":
            return False
        return True

    def _make_result_group(self, title, rows):
        """rows: [(label, value_str), ...]"""
        group = QGroupBox(title)
        form = QFormLayout(group)
        for label_text, value_text in rows:
            lbl = QLabel(value_text)
            lbl.setObjectName("resultValue")
            form.addRow(f"{label_text}:", lbl)
        return group

    def _make_source_table(self, headers, proportions=None):
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
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        table.verticalHeader().setDefaultSectionSize(50)
        hdr = table.horizontalHeader()
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        return table

    def _fill_source_table(self, table, items, nav_callback):
        """items: 6-tuples (name, value, source_label, nav_key, seq_label, sub_name)
        统一 7 列表格：名称 | 副名称 | 序列号 | 数值 | 取值 | 来源 | 操作"""
        if table.columnCount() < 7:
            table.setColumnCount(7)
            table.setHorizontalHeaderLabels(["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"])
        if isinstance(table, _PropTable):
            # PropTable 每次 resize 按比例重算列宽，比例即唯一真相来源
            #          名称   副名称  序列号  数值   取值   来源   操作
            table._proportions = [0.14, 0.20, 0.07, 0.14, 0.06, 0.10, 0.18]
        hdr = table.horizontalHeader()

        table.setRowCount(0)
        for item in items:
            name, value = item[0], item[1]
            src_label = item[2] if len(item) > 2 else ""
            nav_key = item[3] if len(item) > 3 else ""
            seq_label = item[4] if len(item) > 4 else ""
            sub_name = item[5] if len(item) > 5 else ""
            r = table.rowCount()
            table.insertRow(r)
            table.setRowHeight(r, 42)
            key = (name, nav_key, seq_label)
            is_hidden = key in HIDDEN_ITEMS
            is_const = name in _CONSTANT_ATTRS or "固定" in name

            # 名称
            ni = QTableWidgetItem(name)
            ni.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(r, 0, ni)

            # 副名称（与综合填写实时互联，双向同步）
            sub_edit = QLineEdit()
            sub_edit.setObjectName("subNameEdit")
            sub_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_edit.setPlaceholderText("（备注）")
            sub_edit.setStyleSheet("font-size: 13px;")
            if sub_name:
                sub_edit.setText(sub_name)
            sub_edit.editingFinished.connect(
                lambda n=name, sl=src_label, nk=nav_key, sq=seq_label, se=sub_edit:
                self._on_summary_sub_name_changed(n, sl, nk, sq, se))
            # textChanged 轻量同步到综合填写（不触发重算）
            sub_edit.textChanged.connect(
                lambda t, n=name, sl=src_label, nk=nav_key, sq=seq_label:
                self._push_sub_name_to_source(n, sl, nk, sq, t))
            if _make_sub_name_cell:
                table.setCellWidget(r, 1, _make_sub_name_cell(sub_edit, lambda: name))
            else:
                table.setCellWidget(r, 1, sub_edit)

            # 序列号（常驻/触发 + 序号）
            si = QTableWidgetItem(seq_label)
            si.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(r, 2, si)

            # 数值 —— 可编辑（锁定后禁用）
            vs = QDoubleSpinBox()
            vs.setObjectName("itemValueSpin")
            vs.setRange(0, 9999)
            vs.setDecimals(4)
            vs.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vs.setValue(value)
            vs.setFixedWidth(100)
            vs.valueChanged.connect(
                lambda v, n=name, sl=src_label, nk=nav_key, sq=seq_label:
                self._on_summary_value_changed(n, v, sl, nk, sq))
            _cell_center(table, r, 3, vs)

            # 取值（常数/百分比）
            ui = QTableWidgetItem("常数" if is_const else "百分比")
            ui.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(r, 4, ui)

            # 来源
            src_btn = QPushButton(src_label)
            src_btn.setObjectName("backButton")
            src_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            src_btn.clicked.connect(lambda _, nk=nav_key, n=name, sl=src_label, sq=seq_label:
                                    self._navigate(nk, n, sl, sq))
            _cell_center(table, r, 5, src_btn)

            # 操作列：隐藏 | 锁定 | 删除
            ops_widget = QWidget()
            ops_layout = QHBoxLayout(ops_widget)
            ops_layout.setContentsMargins(2, 0, 2, 0)
            ops_layout.setSpacing(3)

            hide_btn = QPushButton("隐藏中" if is_hidden else "隐藏")
            hide_btn.setObjectName("itemDeleteBtn" if is_hidden else "itemLockBtn")
            hide_btn.setFixedSize(48, 28)
            hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            hide_btn.clicked.connect(
                lambda _, n=name, sl=src_label, nk=nav_key, btn=hide_btn, sq=seq_label:
                self._toggle_hide_item(n, sl, nk, btn, sq))
            ops_layout.addWidget(hide_btn)

            del_btn = QPushButton("删除")
            del_btn.setObjectName("itemDeleteBtn")
            del_btn.setFixedSize(48, 28)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(
                lambda _, n=name, sl=src_label, nk=nav_key, sq=seq_label:
                self._delete_summary_item(n, sl, nk, sq))
            ops_layout.addWidget(del_btn)

            table.setCellWidget(r, 6, ops_widget)

        _fix_table_height(table)

    def _on_summary_value_changed(self, name, new_value, src_label, nav_key, seq_label=""):
        """数值总结页数值变更时，同步回对应的来源页面并触发全局重算。"""
        for _, page, nk in self._external_sources:
            if nk == nav_key:
                data = page.collect_data()
                if isinstance(data, list):
                    for i, rd in enumerate(page._rows):
                        # 有序列号时精确匹配（CombinedEntryPage），否则回退名称匹配
                        if seq_label:
                            rd_seq = self._row_seq(page, i)
                            if not (rd['name_edit'].text() == name and rd_seq == seq_label):
                                continue
                        elif rd['name_edit'].text() != name:
                            continue
                        # 先静默更新源页面数值，避免 setValue 立即触发嵌套重算
                        rd['value_spin'].blockSignals(True)
                        rd['value_spin'].setValue(new_value)
                        rd['value_spin'].blockSignals(False)
                        # 延迟触发一次回调链
                        if page._on_change_cb:
                            QTimer.singleShot(0, page._on_change_cb)
                        return
                elif isinstance(data, dict) and 'base_atk' in data:
                    pass
                break

    @staticmethod
    def _row_seq(page, idx):
        """根据页面类型和行索引生成序列标签（如'常驻3'）。"""
        if hasattr(page, 'page_key') and page.page_key in ("combined_perm", "combined_trigger"):
            type_label = "常驻" if page.page_key == "combined_perm" else "触发"
            return f"{type_label}{idx + 1}"
        return ""

    def _push_sub_name_to_source(self, name, src_label, nav_key, seq_label, text):
        """轻量同步：仅将副名称文本推送到综合填写页（不触发重算）。"""
        for _, page, nk in self._external_sources:
            if not isinstance(page, _CombinedEntryPage):
                continue
            for i, rd in enumerate(page._rows):
                type_label = "常驻" if page.page_key == "combined_perm" else "触发"
                rd_seq = f"{type_label}{i + 1}"
                if (rd['name_edit'].text() == name and
                        rd.get('source', '') == src_label and
                        rd_seq == seq_label and
                        'sub_name_edit' in rd):
                    rd['sub_name_edit'].blockSignals(True)
                    rd['sub_name_edit'].setText(text)
                    rd['sub_name_edit'].blockSignals(False)
                    return

    def _on_summary_sub_name_changed(self, name, src_label, nav_key, seq_label, sub_edit):
        """副名称在总结页被编辑后，同步回 CombinedEntryPage 并触发全局重算。"""
        new_sub = sub_edit.text().strip()
        for _, page, nk in self._external_sources:
            if not isinstance(page, _CombinedEntryPage):
                continue
            for i, rd in enumerate(page._rows):
                type_label = "常驻" if page.page_key == "combined_perm" else "触发"
                rd_seq = f"{type_label}{i + 1}"
                if (rd['name_edit'].text() == name and
                        rd.get('source', '') == src_label and
                        rd_seq == seq_label):
                    rd['sub_name_edit'].blockSignals(True)
                    rd['sub_name_edit'].setText(new_sub)
                    rd['sub_name_edit'].blockSignals(False)
                    if page._on_change_cb:
                        QTimer.singleShot(0, page._on_change_cb)
                    return

    def _toggle_hide_item(self, name, src_label, nav_key, btn, seq_label=""):
        """切换词条的隐藏/显示状态并触发全局重算。"""
        key = (name, nav_key, seq_label)
        key = (name, nav_key, seq_label)
        if key in HIDDEN_ITEMS:
            HIDDEN_ITEMS.discard(key)
            btn.setText("隐藏")
            btn.setObjectName("itemLockBtn")
        else:
            HIDDEN_ITEMS.add(key)
            btn.setText("隐藏中")
            btn.setObjectName("itemDeleteBtn")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        # 同步 CombinedEntryPage 中对应行的隐藏按钮状态
        for _, page, _ in self._external_sources:
            if isinstance(page, _CombinedEntryPage):
                for ri, rd in enumerate(page._rows):
                    type_label = "常驻" if page.page_key == "combined_perm" else "触发"


        # 强制刷新所有总结页 + 重算
        window = self.window()
        if window and hasattr(window, 'main_screen'):
            ms = window.main_screen
            for sp in [ms.page_summary_base, ms.page_summary_bonus,
                       ms.page_summary_deepen, ms.page_summary_crit]:
                sp.recalc()
            ms.page_result.compute()
            ms.page_result_list.recalc(force=True)


    def _delete_summary_item(self, name, src_label, nav_key, seq_label=""):
        """从数值总结中删除词条（同时删除来源页面中的对应条目）。"""
        key = (name, nav_key, seq_label)
        HIDDEN_ITEMS.discard(key)
        for _, page, nk in self._external_sources:
            if nk == nav_key:
                data = page.collect_data()
                if isinstance(data, list):
                    for i, rd in enumerate(list(page._rows)):
                        if seq_label:
                            rd_seq = self._row_seq(page, i)
                            if not (rd['name_edit'].text() == name and rd_seq == seq_label):
                                continue
                        elif rd['name_edit'].text() != name:
                            continue
                        rd['locked'] = False
                        # 暂挂回调，避免 _delete_row 触发嵌套重算
                        saved_cb = page._on_change_cb
                        page._on_change_cb = None
                        try:
                            page._delete_row(rd)
                        finally:
                            page._on_change_cb = saved_cb
                        break
                break
        # 触发全局重算（来源回调已含 summary recalc，无需额外 self.recalc）
        for _, page, _ in self._external_sources:
            if page._on_change_cb:
                page._on_change_cb()

    def highlight_item(self, name, src_label, nav_key, seq_label=""):
        """找到匹配行：优先按序列号匹配，再验证名称。"""
        all_tables = self.findChildren(QTableWidget)
        for t in all_tables:
            # 第一轮：优先用序列号匹配（列2，唯一键）
            if seq_label:
                for r in range(t.rowCount()):
                    seq_item = t.item(r, 2)
                    if seq_item and seq_item.text() == seq_label:
                        name_item = t.item(r, 0)
                        if name_item and name_item.text() == name:
                            self._highlight_table_row(t, r)
                            return
            # 第二轮回退：只用名称匹配
            for r in range(t.rowCount()):
                name_item = t.item(r, 0)
                if name_item and name_item.text() == name:
                    self._highlight_table_row(t, r)
                    return

    def _highlight_table_row(self, t, r):
        """平滑滚动到行 + 黄色叠层"""
        scroll = None
        p = t.parent()
        while p:
            if isinstance(p, QScrollArea):
                scroll = p
                break
            p = p.parent()
        if scroll:
            self._scroll_and_highlight(t, r, scroll)
        else:
            t.scrollTo(t.model().index(r, 0))
            QTimer.singleShot(200, lambda tb=t, row=r:
                              self._show_highlight_overlay(tb, row))

    def _scroll_and_highlight(self, table, row, scroll):
        """平滑滚动 QScrollArea 使目标行靠近顶部，再放叠层。"""
        QApplication.processEvents()
        # 表格内部滚动
        idx = table.model().index(row, 0)
        table.scrollTo(idx)
        QApplication.processEvents()

        # 计算目标行在 scroll 内容中的 y 坐标
        row_y_in_table = table.rowViewportPosition(row)
        table_origin = table.mapTo(scroll.widget(), QPoint(0, 0))
        target_y = table_origin.y() + row_y_in_table

        # 目标滚动值：让目标行显示在 viewport 上方约 1/5 处
        vp_h = scroll.viewport().height()
        desired = max(0, target_y - vp_h // 5)
        sb = scroll.verticalScrollBar()

        # 平滑动画滚动
        anim = QPropertyAnimation(sb, b"value")
        anim.setDuration(450)
        anim.setStartValue(sb.value())
        anim.setEndValue(desired)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.finished.connect(lambda tb=table, r=row:
            QTimer.singleShot(80, lambda tb=tb, r=r:
                self._show_highlight_overlay(tb, r)))
        # 防止动画被 GC 回收
        scroll._scroll_anim = anim
        anim.start()

    def _show_highlight_overlay(self, table, row):
        """在指定表格行上放置黄色叠层，两轮渐入渐出（共 2s）。"""
        try:
            QApplication.processEvents()
            vp = table.viewport()
            idx = table.model().index(row, 0)
            rect = table.visualRect(idx)
            if rect.y() < 0 or rect.y() > vp.height():
                return
            row_rect = QRect(0, rect.y(), vp.width(), table.rowHeight(row))
            _place_highlight_overlay(vp, row_rect, "background-color: #ffeb3b;")
        except RuntimeError:
            pass  # 表格已被销毁（全局重算等）

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                lyt = item.layout()
                self._clear_layout(lyt)
                lyt.setParent(None)
                lyt.deleteLater()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())


# ==================== 数值总结页面 ====================

class SummaryBaseZonePage(SummaryBasePage):
    """基础乘区 —— 分攻击力/生命值/防御力三区，每区含百分比与固定值"""

    def __init__(self):
        super().__init__("基础乘区", "攻击力 / 生命值 / 防御力 的百分比与固定值加成汇总")

    def recalc(self):
        self._clear_content()
        items = _collect_all_items(self._external_sources, self._echo_pages)

        bases = {"攻击力": 0.0, "生命值": 0.0, "防御力": 0.0}
        weapon_bases = {"攻击力": 0.0, "生命值": 0.0, "防御力": 0.0}
        pct_items = {"攻击力": [], "生命值": [], "防御力": []}
        flat_items = {"攻击力": [], "生命值": [], "防御力": []}

        for it in items:
            name = it[0]; value = it[1]
            if name == "角色基础攻击力":
                bases["攻击力"] = value
            elif name == "武器基础攻击力":
                weapon_bases["攻击力"] = value
            elif name == "角色基础生命值":
                bases["生命值"] = value
            elif name == "角色基础防御力":
                bases["防御力"] = value
            elif "攻击力" in name and "固定" not in name and "基础" not in name:
                pct_items["攻击力"].append(it)
            elif "固定攻击" in name:
                flat_items["攻击力"].append(it)
            elif "生命值" in name and "固定" not in name and "基础" not in name:
                pct_items["生命值"].append(it)
            elif "固定生命" in name:
                flat_items["生命值"].append(it)
            elif "防御力" in name and "固定" not in name and "基础" not in name:
                pct_items["防御力"].append(it)
            elif "固定防御" in name:
                flat_items["防御力"].append(it)

        for stat in ["攻击力", "生命值", "防御力"]:
            base_val = bases[stat]
            w_base = weapon_bases[stat]
            pct = pct_items[stat]
            flat = flat_items[stat]
            total_pct = sum(it[1] for it in pct)
            total_flat = sum(it[1] for it in flat)
            if stat == "攻击力":
                total = (base_val + w_base) * (1.0 + total_pct / 100.0) + total_flat
            else:
                total = base_val * (1.0 + total_pct / 100.0) + total_flat

            if not pct and not flat and base_val == 0 and (stat != "攻击力" or w_base == 0):
                continue

            all_rows = pct + flat  # 直接合并，每项已是完整 5 元组含 seq_label

            title_lbl = QLabel(f"▎{stat}")
            title_lbl.setObjectName("sectionTitle")
            self._content_layout.addWidget(title_lbl)

            t = self._make_source_table(["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"],
                                        [0.22, 0.10, 0.07, 0.14, 0.07, 0.12, 0.10])
            self._fill_source_table(t, all_rows, self._navigate)
            self._content_layout.addWidget(t)

            if stat == "攻击力":
                result_group = self._make_result_group(f"{stat}计算结果", [
                    ("角色基础攻击力", f"{base_val:.0f}"),
                    ("武器基础攻击力", f"{w_base:.0f}"),
                    ("攻击力%合计", f"{total_pct:.1f}%"),
                    ("固定攻击力合计", f"{total_flat:.1f}"),
                    ("攻击力总值", f"{total:.10f}"),
                ])
            else:
                result_group = self._make_result_group(f"{stat}计算结果", [
                    (f"角色基础{stat}", f"{base_val:.0f}"),
                    (f"{stat}%合计", f"{total_pct:.1f}%"),
                    (f"固定{stat}合计", f"{total_flat:.1f}"),
                    (f"{stat}总值", f"{total:.10f}"),
                ])
            self._content_layout.addWidget(result_group)



class SummaryBonusZonePage(SummaryBasePage):
    """加成乘区"""

    def __init__(self):
        super().__init__("加成乘区", "所有伤害加成与伤害提升属性汇总 (全属性/元素/技能类别)")

    def recalc(self):
        self._clear_content()
        items = _collect_all_items(self._external_sources, self._echo_pages)

        bonus_items = [it for it in items
                      if any(s in it[0] for s in damage_calc.BONUS_SUFFIX)
                      and not any(kw in it[0] for kw in damage_calc.CRIT_DMG_KEYWORDS)]

        # 筛选芯片：元素属性 + 技能类型
        filter_bar = self._build_filter_bar([
            ("时效类型", ["全部", "常驻", "触发"]),
            ("元素属性", ["全部", "无"] + damage_calc.ELEMENTS[1:]),
            ("技能类型", ["全部", "无"] + list(damage_calc.SKILL_TYPE_NAMES_SET)),
        ])
        self._content_layout.addWidget(filter_bar)

        label = QLabel("伤害加成 / 伤害提升 词条")
        self._content_layout.addWidget(label)
        t = self._make_source_table(["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"],
                                    [0.22, 0.10, 0.07, 0.14, 0.07, 0.12, 0.10])
        self._filtered_table = t
        self._filtered_all_items = bonus_items
        self._filter_refill_fn = self._fill_source_table
        self._refilter_table()
        self._content_layout.addWidget(t)



class SummaryDeepenZonePage(SummaryBasePage):
    """加深乘区"""

    def __init__(self):
        super().__init__("加深乘区", "所有伤害加深属性汇总 (全属性/元素/技能类别/效应)")

    def recalc(self):
        self._clear_content()
        items = _collect_all_items(self._external_sources, self._echo_pages)

        deepen_items = [it for it in items if damage_calc.DEEPEN_SUFFIX in it[0]]

        # 筛选芯片：元素属性 + 技能类型 + 效应类型
        filter_bar = self._build_filter_bar([
            ("时效类型", ["全部", "常驻", "触发"]),
            ("元素属性", ["全部", "无"] + damage_calc.ELEMENTS[1:]),
            ("技能类型", ["全部", "无"] + list(damage_calc.SKILL_TYPE_NAMES_SET)),
            ("效应类型", ["全部", "无"] + damage_calc.EFFECTS[1:]),
        ])
        self._content_layout.addWidget(filter_bar)

        label = QLabel("伤害加深 词条")
        self._content_layout.addWidget(label)
        t = self._make_source_table(["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"],
                                    [0.22, 0.10, 0.07, 0.14, 0.07, 0.12, 0.10])
        self._filtered_table = t
        self._filtered_all_items = deepen_items
        self._filter_refill_fn = self._fill_source_table
        self._refilter_table()
        self._content_layout.addWidget(t)



class SummaryCritZonePage(SummaryBasePage):
    """暴击乘区 — 基础暴击率 5%, 基础暴击伤害 150%"""

    def __init__(self):
        super().__init__("暴击乘区", "暴击率与暴击伤害汇总 (基础暴击率 5%, 基础暴击伤害 150%)")

    def recalc(self):
        self._clear_content()
        items = _collect_all_items(self._external_sources, self._echo_pages)

        rate_items = [it for it in items
                      if any(kw in it[0] for kw in damage_calc.CRIT_RATE_KEYWORDS) and not any(kw in it[0] for kw in damage_calc.CRIT_DMG_KEYWORDS)]
        dmg_items = [it for it in items
                     if any(kw in it[0] for kw in damage_calc.CRIT_DMG_KEYWORDS)]

        total_rate_sources = sum(it[1] for it in rate_items)
        total_dmg_sources = sum(it[1] for it in dmg_items)
        total_rate = 5.0 + total_rate_sources
        total_dmg = 150.0 + total_dmg_sources

        # 时效筛选
        filter_bar = self._build_filter_bar([
            ("时效类型", ["全部", "常驻", "触发"]),
        ])
        self._content_layout.addWidget(filter_bar)

        self._content_layout.addWidget(QLabel("暴击率 词条 (基础 5%)"))
        t1 = self._make_source_table(["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"],
                                     [0.22, 0.10, 0.07, 0.14, 0.07, 0.12, 0.10])
        self._filtered_table = t1
        self._filtered_all_items = rate_items
        self._filter_refill_fn = self._fill_source_table
        self._refilter_table()
        self._content_layout.addWidget(t1)

        # 暴击率计算过程
        rate_calc = self._make_result_group("暴击率计算过程", [
            ("角色基础暴击率", "5.0%"),
            ("来源暴击率合计", f"{total_rate_sources:.1f}%"),
            ("最终暴击率", f"{total_rate:.1f}%"),
        ])
        self._content_layout.addWidget(rate_calc)

        self._content_layout.addWidget(QLabel("暴击伤害 词条 (基础 150%)"))
        t2 = self._make_source_table(["名称", "副名称", "序列号", "数值", "取值", "来源", "操作"],
                                     [0.22, 0.10, 0.07, 0.14, 0.07, 0.12, 0.10])
        self._fill_source_table(t2, dmg_items, self._navigate)
        self._content_layout.addWidget(t2)

        # 暴击伤害计算过程
        dmg_calc = self._make_result_group("暴击伤害计算过程", [
            ("角色基础暴击伤害", "150.0%"),
            ("来源暴击伤害合计", f"{total_dmg_sources:.1f}%"),
            ("最终暴击伤害", f"{total_dmg:.1f}%"),
        ])
        self._content_layout.addWidget(dmg_calc)

        result_group = self._make_result_group("计算结果", [
            ("暴击率合计", f"{total_rate:.1f}%"),
            ("暴击伤害合计", f"{total_dmg:.1f}%"),
            ("期望暴击乘区", f"{(1.0 + min(total_rate, 100.0) / 100.0 * (total_dmg / 100.0 - 1.0)):.10f}"),
        ])
        self._content_layout.addWidget(result_group)



# ==================== 独立乘区页面 ====================

