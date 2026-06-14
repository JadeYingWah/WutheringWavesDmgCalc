# -*- coding: utf-8 -*-
# 使用预设窗口 —— 来源选择 → 分类选择 + 多选预设 + 详情预览

__all__ = ["PresetLoaderDialog"]

import os

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QScrollArea, QFrame, QGroupBox, QCheckBox,
    QMessageBox, QSplitter, QSizePolicy, QStackedWidget,
    QSpinBox, QComboBox, QFormLayout, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QTimer

from preset_manager import PresetManager


# ── 选择上限 ──
_CATEGORY_LIMITS = {"character": 1, "weapon": 1, "echo_set": 5, "character_buff": 5}
_CATEGORY_LABELS = {"character": "角色", "weapon": "武器", "echo_set": "声骸套装", "character_buff": "角色增益"}


# ═══════════════════════════════════════════════════════════════
# 预设详情预览
# ═══════════════════════════════════════════════════════════════

class _PresetPreview(QScrollArea):
    """右侧预设详情预览"""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        widget = QWidget()
        self._layout = QVBoxLayout(widget)
        self._layout.setSpacing(8)

        self._title_label = QLabel("选择预设查看详情")
        self._title_label.setObjectName("sectionTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        self._layout.addWidget(self._title_label)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setSpacing(8)
        self._layout.addWidget(self._content_widget)

        self._layout.addStretch()
        self.setWidget(widget)

    def show_preset(self, preset_info):
        data, err = PresetManager.load_preset(preset_info["path"])
        if err:
            self._title_label.setText(f"加载失败: {err}")
            return

        self._clear_content()
        self._title_label.setText(data.get("name") or preset_info["name"])

        source_tag = "官方预设" if preset_info["source"] == "official" else "用户预设"
        author = data.get("author", "")
        author_part = f"  |  作者: {author}" if author else ""
        info = QLabel(f"来源: {source_tag}  |  修改: {preset_info.get('mtime', '')}"
                      f"  |  类别: {data.get('category', '综合')}{author_part}")
        info.setObjectName("labelSecondary")
        info.setStyleSheet("font-size: 11px;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        self._content_layout.addWidget(info)

        char = data.get("character", {})
        if char and char.get("name"):
            self._add_section("🎭 角色", self._fmt_char(char))

        weap = data.get("weapon", {})
        if weap and weap.get("name"):
            self._add_section("⚔ 武器", self._fmt_weapon(weap))

        echo = data.get("echo_set", {})
        if echo and echo.get("name"):
            self._add_section("🔮 声骸套装", self._fmt_echo(echo))

        buff = data.get("character_buff", {})
        if buff and buff.get("name"):
            self._add_section("💠 角色增益", self._fmt_buff(buff))

        self._content_layout.addStretch()

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _add_section(self, title, text):
        gb = QGroupBox(title)
        gl = QVBoxLayout(gb)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 12px;")
        lbl.setTextFormat(Qt.TextFormat.PlainText)
        gl.addWidget(lbl)
        self._content_layout.addWidget(gb)

    def _fmt_char(self, c):
        lines = [
            f"元素: {c.get('element', '')}  效应: {c.get('effect', '(无)')}",
            f"基础生命: {c.get('base_hp', 0):.0f}  "
            f"攻击: {c.get('base_atk', 0):.0f}  "
            f"防御: {c.get('base_def', 0):.0f}",
        ]
        mult = c.get("multiplier", {})
        if mult:
            bm = mult.get("base_mult", 100)
            mi = mult.get("mult_increase", 0)
            mb = mult.get("mult_boosts", [0, 0, 0])
            lines.append(f"倍率: 基础{bm}% + 增加{mi}%  提升:{'/'.join(f'{b}%' for b in mb)}")
        lines.append("")
        chains = c.get("resonance_chain", [])
        for i, ch in enumerate(chains):
            effs = ch.get("effects", [])
            izs = ch.get("indep_zones", [])
            if effs or izs:
                lines.append(f"── {i + 1} 链 ──")
                for e in effs:
                    h = " [隐藏]" if e.get("default_hidden") else ""
                    lines.append(f"  [{e.get('type','')}] {e.get('name','')} = {e.get('value',0):.4f}%"
                                 f"  ({e.get('source','')}){h}")
                    if e.get("sub_name"):
                        lines.append(f"    副名称: {e['sub_name']}")
                for iz in izs:
                    lines.append(f"  独立乘区组: {iz.get('group_name','')}")
                    for v in iz.get("values", []):
                        h = " [隐藏]" if v.get("hidden") else ""
                        lines.append(f"    {v.get('name','')} = {v.get('value',0):.4f}%{h}")
        return "\n".join(lines)

    def _fmt_weapon(self, w):
        lines = [f"基础攻击力: {w.get('base_atk', 0):.0f}"]
        bt = w.get("bonus_type", "")
        if bt:
            lines.append(f"附加属性: {bt} +{w.get('bonus_value', 0):.4f}%")
        lines.append("")
        refs = w.get("refinement", [])
        for i, ref in enumerate(refs):
            effs = ref.get("effects", [])
            izs = ref.get("indep_zones", [])
            desc = ref.get("resonance_desc", "")
            if desc or effs or izs:
                lines.append(f"── 精炼 {i + 1} 阶 ──")
                if desc:
                    lines.append(f"  谐振: {desc}")
                for e in effs:
                    h = " [隐藏]" if e.get("default_hidden") else ""
                    lines.append(f"  [{e.get('type','')}] {e.get('name','')} = {e.get('value',0):.4f}%"
                                 f"  ({e.get('source','')}){h}")
                    if e.get("sub_name"):
                        lines.append(f"    副名称: {e['sub_name']}")
                for iz in izs:
                    lines.append(f"  独立乘区组: {iz.get('group_name','')}")
                    for v in iz.get("values", []):
                        h = " [隐藏]" if v.get("hidden") else ""
                        lines.append(f"    {v.get('name','')} = {v.get('value',0):.4f}%{h}")
        return "\n".join(lines)

    def _fmt_echo(self, e):
        lines = []
        for s in e.get("stages", []):
            req = s.get("required_count", 0)
            lines.append(f"── {req} 件套效果 ──")
            for eff in s.get("effects", []):
                h = " [隐藏]" if eff.get("default_hidden") else ""
                lines.append(f"  [{eff.get('type','')}] {eff.get('name','')} = {eff.get('value',0):.4f}%"
                             f"  ({eff.get('source','')}){h}")
                if eff.get("sub_name"):
                    lines.append(f"    副名称: {eff['sub_name']}")
        fb = e.get("first_echo_bonus", {})
        if fb.get("effects") or fb.get("indep_zones"):
            lines.append("── 首位声骸增益 ──")
            for eff in fb.get("effects", []):
                h = " [隐藏]" if eff.get("default_hidden") else ""
                lines.append(f"  [{eff.get('type','')}] {eff.get('name','')} = {eff.get('value',0):.4f}%"
                             f"  ({eff.get('source','')}){h}")
                if eff.get("sub_name"):
                    lines.append(f"    副名称: {eff['sub_name']}")
            for iz in fb.get("indep_zones", []):
                lines.append(f"  独立乘区组: {iz.get('group_name','')}")
                for v in iz.get("values", []):
                    h = " [隐藏]" if v.get("hidden") else ""
                    lines.append(f"    {v.get('name','')} = {v.get('value',0):.4f}%{h}")
        return "\n".join(lines)

    def _fmt_buff(self, b):
        lines = []
        effects = b.get("effects", [])
        perm_count = sum(1 for e in effects if e.get("type") != "触发")
        trig_count = sum(1 for e in effects if e.get("type") == "触发")
        lines.append(f"常驻: {perm_count} 条  触发: {trig_count} 条")
        lines.append("")
        for e in effects:
            lines.append(f"  [{e.get('type','')}] {e.get('name','')} = {e.get('value',0):.4f}%"
                         f"  ({e.get('source','')})")
            if e.get("sub_name"):
                lines.append(f"    副名称: {e['sub_name']}")
            if e.get("keywords"):
                lines.append(f"    关键词: {e['keywords']}")
        return "\n".join(lines)

    def clear(self):
        self._title_label.setText("选择预设查看详情")
        self._clear_content()


# ═══════════════════════════════════════════════════════════════
# 使用预设主对话框
# ═══════════════════════════════════════════════════════════════

class PresetLoaderDialog(QDialog):
    """使用预设窗口 —— 来源选择 → 分类 + 多选 + 预览"""

    def __init__(self, parent=None, main_screen=None):
        super().__init__(parent)
        self.setWindowTitle("使用预设")
        self.setMinimumSize(900, 620)
        self.resize(960, 660)
        self._main_screen = main_screen
        # 已选预设: {"character": [path, ...], "weapon": [...], "echo_set": [...]}
        self._selected = {"character": [], "weapon": [], "echo_set": [], "character_buff": []}

        QTimer.singleShot(0, lambda: self._center())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()

        # 页面 1：分类 + 预设列表 + 预览
        self._page_browse = self._build_browse_page()
        self.stack.addWidget(self._page_browse)

        main_layout.addWidget(self.stack)

        # 直接进入混合浏览模式
        self._current_source = None
        self._browse_title.setText("使用预设")
        # 默认选中第一个有预设的分类
        all_presets = PresetManager.list_presets()
        for cat in ["character", "weapon", "echo_set", "character_buff"]:
            if any(p["category"] == cat for p in all_presets):
                self._select_category(cat)
                break

    def reject(self):
        """ESC：直接关闭窗口"""
        super().reject()

    def _center(self):
        if self.parent():
            geo = self.parent().geometry()
            self.move(geo.center() - self.rect().center())
        else:
            from PyQt6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen().availableGeometry()
            self.move(screen.center() - self.rect().center())

    # ── 页面 0：来源选择 ──

    def _build_source_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 顶栏
        top = QHBoxLayout()
        title = QLabel("使用预设")
        title.setObjectName("sectionTitle")
        top.addWidget(title)
        top.addStretch()

        update_btn = QPushButton("🔄 更新官方预设")
        update_btn.setObjectName("backButton")
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.clicked.connect(lambda: self._update_official())
        top.addWidget(update_btn)

        builder_btn = QPushButton("🔧 预设构建器")
        builder_btn.setObjectName("backButton")
        builder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        builder_btn.clicked.connect(self._open_builder)
        top.addWidget(builder_btn)
        layout.addLayout(top)

        # 两张来源卡片
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(32)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for icon, label, source in [
            ("🏛", "官方预设", "official"),
            ("👤", "我的预设", "user"),
        ]:
            card = QPushButton()
            card.setObjectName("presetEntryCard")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setMinimumSize(260, 280)
            card.clicked.connect(lambda _, s=source: self._enter_source(s))

            cl = QVBoxLayout(card)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.setSpacing(14)
            cl.setContentsMargins(20, 28, 20, 28)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 52px; border: none; background: transparent;")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(icon_label)

            title_label = QLabel(label)
            title_label.setObjectName("accentLabel")
            title_label.setStyleSheet("font-size: 18px; font-weight: 700; border: none; background: transparent;")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(title_label)

            cards_layout.addWidget(card)

        layout.addStretch(1)
        layout.addLayout(cards_layout)
        layout.addStretch(2)

        # 底部按钮
        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("backButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)
        layout.addLayout(bottom)

        return page

    # ── 页面 1：分类 + 预设列表 + 预览 ──

    def _build_browse_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 顶栏
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)

        back_btn = QPushButton("← 返回")
        back_btn.setObjectName("backButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedWidth(80)
        back_btn.clicked.connect(self.reject)
        top.addWidget(back_btn)

        self._browse_title = QLabel("")
        self._browse_title.setObjectName("sectionTitle")
        top.addWidget(self._browse_title)

        top.addStretch()
        layout.addLayout(top)

        # 副标题（独立一行，居中）
        self._browse_hint = QLabel("单击查看详细，双击选择预设。")
        self._browse_hint.setObjectName("labelSecondary")
        self._browse_hint.setStyleSheet("font-size: 12px;")
        self._browse_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._browse_hint)

        # 三张分类卡片
        cat_row = QHBoxLayout()
        cat_row.setSpacing(16)
        cat_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._cat_buttons = {}
        for icon, cat_key, cat_label in [
            ("🎭", "character", "角色"),
            ("⚔", "weapon", "武器"),
            ("🔮", "echo_set", "声骸套装"),
            ("💠", "character_buff", "角色增益"),
        ]:
            btn = QPushButton()
            btn.setObjectName("presetEntryCard")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(160, 100)
            btn.clicked.connect(lambda _, c=cat_key: self._select_category(c))

            cl = QVBoxLayout(btn)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.setSpacing(6)
            cl.setContentsMargins(8, 8, 8, 8)

            il = QLabel(icon)
            il.setStyleSheet("font-size: 28px; border: none; background: transparent;")
            il.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(il)

            tl = QLabel(f"{cat_label} (0/{_CATEGORY_LIMITS[cat_key]})")
            tl.setObjectName("accentLabel")
            tl.setStyleSheet("font-size: 12px; font-weight: 600; border: none; background: transparent;")
            tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(tl)

            cat_row.addWidget(btn)
            self._cat_buttons[cat_key] = (btn, tl)

        layout.addLayout(cat_row)

        # 来源过滤：全部 / 官方 / 个人
        src_row = QHBoxLayout()
        src_row.setContentsMargins(0, 4, 0, 0)
        src_row.setSpacing(8)
        src_row.addWidget(QLabel("来源:"))
        self._src_btns = {}
        for sk, sl in [("all", "全部"), ("official", "官方"), ("user", "个人")]:
            sb = QPushButton(sl)
            sb.setObjectName("backButton")
            sb.setCursor(Qt.CursorShape.PointingHandCursor)
            sb.setCheckable(True)
            sb.setFixedWidth(60)
            sb.clicked.connect(lambda _, s=sk: self._set_source_filter(s))
            src_row.addWidget(sb)
            self._src_btns[sk] = sb
        self._src_btns["all"].setChecked(True)
        self._current_source_filter = "all"
        src_row.addStretch()
        layout.addLayout(src_row)

        # 搜索框
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 4, 0, 0)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("输入关键词搜索预设...")
        self._search_input.setObjectName("nameEdit")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search_input)
        layout.addLayout(search_row)

        # 中间：预设列表 + 预览
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background: transparent; width: 2px; }")

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)

        self._preset_list = QListWidget()
        self._preset_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._preset_list.setMinimumWidth(240)
        self._preset_list.setStyleSheet(
            "QListWidget { border: 1px solid rgba(255,255,255,0.08); "
            "border-radius: 6px; font-size: 13px; outline: none; }"
            "QListWidget::item { padding: 7px 10px; margin: 1px 3px; "
            "border-radius: 4px; }"
            "QListWidget::item:hover { background: rgba(255,255,255,0.06); }"
            "QListWidget::item:selected { background: rgba(255,255,255,0.10); "
            "border: 1px solid rgba(255,255,255,0.15); }")
        self._preset_list.currentItemChanged.connect(self._on_item_selected)
        self._preset_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        ll.addWidget(self._preset_list)
        splitter.addWidget(left)

        self._preview = _PresetPreview()
        splitter.addWidget(self._preview)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)

        layout.addWidget(splitter, stretch=1)

        # 底部：已选信息 + 应用按钮
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self._sel_info = QLabel("已选中: 0/1 角色  0/1 武器  0/5 声骸套装  0/5 角色增益")
        self._sel_info.setObjectName("labelSecondary")
        self._sel_info.setStyleSheet("font-size: 13px;")
        bottom.addWidget(self._sel_info)
        bottom.addStretch()

        self._apply_btn = QPushButton("应用预设")
        self._apply_btn.setObjectName("presetSaveBtn")
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.setFixedWidth(120)
        self._apply_btn.clicked.connect(self._apply_preset)
        self._apply_btn.setEnabled(False)
        bottom.addWidget(self._apply_btn)

        layout.addLayout(bottom)

        # 当前浏览的来源和分类
        self._current_source = None
        self._current_category = None

        return page

    # ── 来源选择 ──

    def _enter_source(self, source):
        self._current_source = None  # both sources
        self._browse_title.setText("使用预设")
        self.stack.setCurrentIndex(1)
        # 默认选中第一个有预设的分类
        all_presets = PresetManager.list_presets()
        for cat in ["character", "weapon", "echo_set", "character_buff"]:
            if any(p["category"] == cat for p in all_presets):
                self._select_category(cat)
                return
        self._current_category = None
        self._preset_list.clear()
        self._preview.clear()

    # ── 分类选择 ──

    def _select_category(self, cat_key):
        self._current_category = cat_key
        # 选中按钮高亮
        for ck, (btn, tl) in self._cat_buttons.items():
            if ck == cat_key:
                btn.setStyleSheet("QPushButton{border:2px solid #89b4fa;background:#2a2a3c;border-radius:8px;}")
            else:
                btn.setStyleSheet("QPushButton{border:1px solid #45475a;background:#1e1e2e;border-radius:8px;}")
        self._refresh_preset_list()
        self._update_sel_info()

    def _set_source_filter(self, sk):
        self._current_source_filter = sk
        for s, b in self._src_btns.items():
            b.setChecked(s == sk)
            b.setStyleSheet("background:#5050e0;color:white;" if s == sk else "")
        self._refresh_preset_list()

    def _refresh_preset_list(self):
        self._preset_list.blockSignals(True)
        self._preset_list.clear()

        all_presets = PresetManager.list_presets()
        cat_presets = [p for p in all_presets
                       if p["category"] == self._current_category
                       and (self._current_source_filter == "all" or p["source"] == self._current_source_filter)]

        # 搜索过滤
        search_text = self._search_input.text().strip().lower() if hasattr(self, '_search_input') else ""
        if search_text:
            cat_presets = [p for p in cat_presets if search_text in p["name"].lower()]

        if not cat_presets:
            item = QListWidgetItem("（该分类下暂无预设）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._preset_list.addItem(item)
            self._preset_list.blockSignals(False)
            return

        cat = self._current_category
        selected_paths = set(self._selected.get(cat, []))

        for p in cat_presets:
            is_sel = p["path"] in selected_paths
            text = f"✓ {p['name']}" if is_sel else f"   {p['name']}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, p)
            if is_sel:
                item.setSelected(True)
            if self._current_source == "official":
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            self._preset_list.addItem(item)

        self._preset_list.blockSignals(False)

    def _on_search_changed(self):
        """搜索框文本变化时重新过滤预设列表"""
        self._refresh_preset_list()

    def _update_item_text(self):
        """更新列表项文本和样式，标记已选中的预设（带来源标签）"""
        from PyQt6.QtGui import QColor
        cat = self._current_category
        if not cat:
            return
        selected_paths = set(self._selected.get(cat, []))
        for i in range(self._preset_list.count()):
            item = self._preset_list.item(i)
            info = item.data(Qt.ItemDataRole.UserRole)
            if not info:
                continue
            src = "[官]" if info["source"] == "official" else "[我]"
            name = src + " " + info["name"]
            if info["path"] in selected_paths:
                item.setText(f"✓ {name}")
                item.setBackground(QColor(80, 112, 232, 70))
                item.setForeground(QColor(224, 228, 255))
            else:
                item.setText(f"   {name}")
                item.setBackground(QColor(0, 0, 0, 0))
                item.setForeground(QColor(200, 204, 216))

    # ── 交互：单击预览，双击选中/取消 ──

    def _on_item_selected(self, current, previous):
        """单击：仅预览，不改变选中状态"""
        if current and current.data(Qt.ItemDataRole.UserRole):
            self._preview.show_preset(current.data(Qt.ItemDataRole.UserRole))
        else:
            self._preview.clear()

    def _on_item_double_clicked(self, item):
        """双击：切换选中/取消（跨来源）"""
        info = item.data(Qt.ItemDataRole.UserRole)
        if not info:
            return
        cat = self._current_category
        if not cat:
            return

        path = info["path"]
        selected = self._selected.get(cat, [])
        limit = _CATEGORY_LIMITS[cat]

        if path in selected:
            selected.remove(path)
        else:
            if len(selected) >= limit:
                selected.pop(0)
            selected.append(path)

        self._selected[cat] = selected
        self._update_item_text()
        self._update_sel_info()

    def _update_sel_info(self):
        parts = []
        for cat in ["character", "weapon", "echo_set", "character_buff"]:
            n = len(self._selected.get(cat, []))
            lim = _CATEGORY_LIMITS[cat]
            parts.append(f"{n}/{lim} {_CATEGORY_LABELS[cat]}")
            if cat in self._cat_buttons:
                _, tl = self._cat_buttons[cat]
                tl.setText(f"{_CATEGORY_LABELS[cat]} ({n}/{lim})")
        self._sel_info.setText(f"已选中: {'  '.join(parts)}")

        total = sum(len(v) for v in self._selected.values())
        self._apply_btn.setEnabled(total > 0)

    # ── 应用预设 ──

    def _apply_preset(self):
        if not self._main_screen:
            QMessageBox.warning(self, "错误", "未连接到主界面，无法应用预设。")
            return

        total = sum(len(v) for v in self._selected.values())
        if total == 0:
            QMessageBox.information(self, "未选择", "请至少选择一个预设。")
            return

        # 收集所有选中预设的数据
        all_data = []
        char_name = None
        weapon_name = None
        echo_names = []  # (name, has_first_bonus)
        buff_names = []
        for cat in ["character", "weapon", "echo_set", "character_buff"]:
            for path in self._selected.get(cat, []):
                data, err = PresetManager.load_preset(path)
                if err:
                    QMessageBox.warning(self, "加载失败", f"无法读取预设:\n{err}")
                    continue
                all_data.append(data)
                if cat == "character" and "character" in data:
                    char_name = data["character"].get("name", "未命名角色")
                elif cat == "weapon" and "weapon" in data:
                    weapon_name = data["weapon"].get("name", "未命名武器")
                elif cat == "echo_set" and "echo_set" in data:
                    es = data["echo_set"]
                    ename = es.get("name", "未命名套装")
                    has_fb = bool(es.get("first_echo_bonus", {}).get("effects") or
                                  es.get("first_echo_bonus", {}).get("indep_zones"))
                    echo_names.append({"name": ename, "has_fb": has_fb,
                                       "stages": es.get("stages", []),
                                       "data": data})
                elif cat == "character_buff" and "character_buff" in data:
                    buff_names.append(data["character_buff"].get("name", "未命名增益"))

        if not all_data:
            return

        # ── 配置对话框 ──
        dlg = QDialog(self)
        dlg.setWindowTitle("配置预设应用")
        dlg.setMinimumWidth(460)
        lay_dlg = QVBoxLayout(dlg)
        lay_dlg.setSpacing(14)
        lay_dlg.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)

        chain_spin = None
        refine_spin = None
        echo_combo = None
        echo_pieces = []

        if char_name:
            chain_spin = QSpinBox()
            chain_spin.setRange(0, 6)
            chain_spin.setValue(6)
            chain_spin.setSuffix(" 链")
            chain_spin.setToolTip("0=不开启任何共鸣链，N=开启1~N链")
            form.addRow(f"共鸣链 ({char_name}):", chain_spin)

        if weapon_name:
            refine_spin = QSpinBox()
            refine_spin.setRange(1, 5)
            refine_spin.setValue(1)
            refine_spin.setSuffix(" 阶")
            refine_spin.setToolTip("选择使用哪一阶的武器精炼数据")
            form.addRow(f"武器等阶 ({weapon_name}):", refine_spin)

        lay_dlg.addLayout(form)

        # ── 声骸套装件数分配 ──
        if echo_names:
            stage_gb = QGroupBox("声骸套装（分配件数给各套装，总计不超过 5 件）")
            stage_gb.setStyleSheet("QGroupBox{font-weight:bold;padding-top:14px;}")
            stage_lay = QVBoxLayout(stage_gb)
            stage_lay.setSpacing(6)

            for ed in echo_names:
                sname = ed["name"]
                row = QHBoxLayout()
                row.addWidget(QLabel(sname))
                spin = QSpinBox()
                spin.setRange(0, 5)
                max_pieces = min(5, max([st.get("required_count", 0) for st in ed["stages"]]) if ed["stages"] else 5)
                spin.setValue(max_pieces)
                spin.setFixedWidth(55)
                row.addWidget(spin)
                preview = QLabel()
                preview.setStyleSheet("color:#6c7086;font-size:11px;")
                preview.setWordWrap(True)
                row.addWidget(preview, 1)
                stage_lay.addLayout(row)
                echo_pieces.append((spin, ed, preview))

            total_label = QLabel()
            total_label.setStyleSheet("color:#e74c3c;font-size:12px;font-weight:bold;padding-top:4px;")
            stage_lay.addWidget(total_label)

            echo_combo = QComboBox()
            for ed in echo_names:
                suffix = " (有效果)" if ed["has_fb"] else " (无效果)"
                echo_combo.addItem(ed["name"] + suffix)
            echo_combo.setToolTip("只有被选中的声骸套装的首位声骸增益会生效")
            echo_row = QHBoxLayout()
            echo_row.addWidget(QLabel("首位声骸增益:"))
            echo_row.addWidget(echo_combo, 1)
            stage_lay.addLayout(echo_row)

            def _update_pieces():
                t = 0
                for sp, ed, prev in echo_pieces:
                    n = sp.value()
                    t += n
                    stages = sorted(ed["stages"], key=lambda s: s.get("required_count", 1))
                    if stages:
                        parts = []
                        for st in stages:
                            rc = st.get("required_count", 1)
                            parts.append(f"{rc}件{'<font color="#a6e3a1">✓</font>' if rc <= n else '<font color="#f38ba8">✗</font>'}")
                        prev.setText("生效: " + " + ".join(parts))
                    else:
                        prev.setText("无阶段")
                total_label.setText(f"已分配 {t}/5 件" + ("  ⚠ 超过上限！" if t > 5 else ""))
                try:
                    ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
                    if ok_btn:
                        ok_btn.setEnabled(t <= 5)
                except Exception:
                    pass

            for sp, ed, prev in echo_pieces:
                sp.valueChanged.connect(_update_pieces)

            _update_pieces()
            lay_dlg.addWidget(stage_gb)

        # 角色增益提示
        if buff_names:
            buff_label = QLabel(f"角色增益: {', '.join(buff_names)} (共 {len(buff_names)} 个)")
            buff_label.setStyleSheet("color: #888; font-size: 12px;")
            buff_label.setWordWrap(True)
            lay_dlg.addWidget(buff_label)

        # 按钮
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay_dlg.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # ── 合并为一个预设数据 ──
        # 角色/武器默认只有一份直接覆盖；角色增益和声骸套装需要累积
        merged = {"version": 1, "type": "preset", "name": "合并预设"}
        for d in all_data:
            for key in ["character", "weapon", "echo_set", "character_buff"]:
                if key not in d or not d[key]:
                    continue
                if key in ("character", "weapon"):
                    merged[key] = d[key]
                elif key == "character_buff":
                    if key not in merged:
                        merged[key] = {"name": "", "effects": [], "indep_zones": []}
                    merged[key]["effects"].extend(d[key].get("effects", []))
                    merged[key]["indep_zones"].extend(d[key].get("indep_zones", []))
                    if d[key].get("name"):
                        merged[key]["name"] = d[key]["name"]
                elif key == "echo_set":
                    es = d[key]
                    pieces = 0
                    for sp3, ed3, pv3 in echo_pieces:
                        if ed3["data"] is d:
                            pieces = sp3.value()
                            break
                    active = [st for st in es.get("stages", [])
                              if st.get("required_count", 1) <= pieces]
                    if active:
                        if key not in merged:
                            merged[key] = {"name": "", "stages": [], "first_echo_bonus": {}}
                        merged[key]["stages"].extend(active)
                        if es.get("first_echo_bonus"):
                            merged[key]["first_echo_bonus"] = es["first_echo_bonus"]
                        if es.get("name"):
                            merged[key]["name"] = es["name"]

        # ── 根据用户选择过滤数据 ──

        # 共鸣链：只保留 1~N 链（数组索引 0~N-1 对应 1~N 链）
        if chain_spin and "character" in merged:
            n_chain = chain_spin.value()
            chains = merged["character"].get("resonance_chain", [])
            if n_chain == 0:
                merged["character"]["resonance_chain"] = []
            else:
                merged["character"]["resonance_chain"] = chains[:n_chain]

        # 武器等阶：仅保留选中等阶的数据
        if refine_spin and "weapon" in merged:
            n_ref = refine_spin.value()
            refs = merged["weapon"].get("refinement", [])
            if 0 < n_ref <= len(refs):
                merged["weapon"]["refinement"] = [refs[n_ref - 1]]
            else:
                merged["weapon"]["refinement"] = []

        # 首位声骸增益：仅保留选中的那个（不覆盖已累积的阶段效果）
        if echo_combo and "echo_set" in merged:
            sel_idx = echo_combo.currentIndex()
            echo_idx = 0
            for d in all_data:
                if "echo_set" in d and d["echo_set"]:
                    if echo_idx == sel_idx:
                        merged["echo_set"]["first_echo_bonus"] = d["echo_set"].get("first_echo_bonus", {})
                        break
                    echo_idx += 1
            else:
                merged["echo_set"].pop("first_echo_bonus", None)

        try:
            PresetManager.apply_preset(merged, self._main_screen)
        except Exception as e:
            QMessageBox.warning(self, "应用失败", f"应用预设时发生错误:\n{e}")
            return

        QMessageBox.information(
            self, "应用成功",
            "预设已成功应用。")
        self.accept()

    # ── 其他 ──

    def _update_official(self):
        PresetManager.update_official_presets(self)
        if self._current_category:
            self._refresh_preset_list()

    def _open_builder(self):
        from preset_builder import PresetBuilderDialog
        dlg = PresetBuilderDialog(self)
        dlg.exec()
        if self._current_category:
            self._refresh_preset_list()
