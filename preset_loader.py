# -*- coding: utf-8 -*-
# 使用预设窗口 —— 列表 + 详情预览 + 选择性应用 + 更新官方预设

__all__ = ["PresetLoaderDialog"]

import os

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QScrollArea, QFrame, QGroupBox, QCheckBox,
    QMessageBox, QSplitter, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer

from preset_manager import PresetManager


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
        self._title_label.setText(preset_info["name"])

        source_tag = "官方预设" if preset_info["source"] == "official" else "用户预设"
        info = QLabel(f"来源: {source_tag}  |  修改: {preset_info.get('mtime', '')}"
                      f"  |  类别: {data.get('category', '综合')}")
        info.setObjectName("labelSecondary")
        info.setStyleSheet("font-size: 11px;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

        self._content_layout.addStretch()

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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
            "",
        ]
        chains = c.get("resonance_chain", [])
        for i, ch in enumerate(chains):
            effs = ch.get("effects", [])
            izs = ch.get("indep_zones", [])
            if effs or izs:
                lines.append(f"── {i} 链 ──")
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

    def clear(self):
        self._title_label.setText("选择预设查看详情")
        self._clear_content()


# ═══════════════════════════════════════════════════════════════
# 使用预设主对话框
# ═══════════════════════════════════════════════════════════════

class PresetLoaderDialog(QDialog):
    """使用预设窗口 —— 列表 + 详情 + 选择性应用"""

    def __init__(self, parent=None, main_screen=None):
        super().__init__(parent)
        self.setWindowTitle("使用预设")
        self.setMinimumSize(800, 560)
        self.resize(880, 600)
        self._main_screen = main_screen

        QTimer.singleShot(0, lambda: self._center())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # ── 顶栏 ──
        top = QHBoxLayout()
        top_title = QLabel("选择预设")
        top_title.setObjectName("sectionTitle")
        top.addWidget(top_title)
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
        main_layout.addLayout(top)

        # ── 中间：左右分栏 ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)

        self.preset_list = QListWidget()
        self.preset_list.setMinimumWidth(240)
        self.preset_list.currentItemChanged.connect(self._on_preset_selected)
        ll.addWidget(self.preset_list)
        splitter.addWidget(left)

        self.preview = _PresetPreview()
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)

        main_layout.addWidget(splitter, stretch=1)

        # ── 底部：选择性应用勾选框 + 按钮 ──
        bottom = QHBoxLayout()
        bottom.setSpacing(16)

        bottom.addWidget(QLabel("应用内容:"))
        self.cb_char = QCheckBox("角色")
        self.cb_char.setChecked(True)
        self.cb_char.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom.addWidget(self.cb_char)

        self.cb_weapon = QCheckBox("武器")
        self.cb_weapon.setChecked(True)
        self.cb_weapon.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom.addWidget(self.cb_weapon)

        self.cb_echo = QCheckBox("声骸套装")
        self.cb_echo.setChecked(True)
        self.cb_echo.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom.addWidget(self.cb_echo)

        bottom.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("backButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        self.apply_btn = QPushButton("应用预设")
        self.apply_btn.setObjectName("presetSaveBtn")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self._apply_preset)
        self.apply_btn.setEnabled(False)
        bottom.addWidget(self.apply_btn)

        main_layout.addLayout(bottom)

        self._refresh_list()

    def _center(self):
        if self.parent():
            geo = self.parent().geometry()
            self.move(geo.center() - self.rect().center())
        else:
            from PyQt6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen().availableGeometry()
            self.move(screen.center() - self.rect().center())

    def _refresh_list(self):
        self.preset_list.clear()
        self._presets = PresetManager.list_presets()
        if not self._presets:
            item = QListWidgetItem("（暂无预设文件）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.preset_list.addItem(item)
            return

        for p in self._presets:
            source_mark = "【官】" if p["source"] == "official" else "【户】"
            cat = p.get("category", "")
            cat_label = {"character": "角色", "weapon": "武器", "echo_set": "套装"}.get(cat, "")
            cat_str = f" [{cat_label}]" if cat_label else ""
            text = f"{source_mark}{cat_str} {p['name']}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, p)
            if p["source"] == "official":
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.preset_list.addItem(item)

    def _on_preset_selected(self, current, previous):
        if current and current.data(Qt.ItemDataRole.UserRole):
            preset_info = current.data(Qt.ItemDataRole.UserRole)
            self.preview.show_preset(preset_info)
            self.apply_btn.setEnabled(True)

            # 根据预设类别自动勾选对应复选框
            cat = preset_info.get("category", "")
            has_char = (cat == "character")
            has_weap = (cat == "weapon")
            has_echo = (cat == "echo_set")
            self.cb_char.setChecked(has_char)
            self.cb_char.setEnabled(has_char)
            self.cb_weapon.setChecked(has_weap)
            self.cb_weapon.setEnabled(has_weap)
            self.cb_echo.setChecked(has_echo)
            self.cb_echo.setEnabled(has_echo)
        else:
            self.preview.clear()
            self.apply_btn.setEnabled(False)

    def _apply_preset(self):
        current = self.preset_list.currentItem()
        if not current:
            return
        preset_info = current.data(Qt.ItemDataRole.UserRole)
        if not preset_info:
            return

        if not self._main_screen:
            QMessageBox.warning(self, "错误", "未连接到主界面，无法应用预设。")
            return

        data, err = PresetManager.load_preset(preset_info["path"])
        if err:
            QMessageBox.warning(self, "加载失败", f"无法读取预设文件:\n{err}")
            return

        # 按用户勾选过滤
        parts = []
        if self.cb_char.isChecked():
            parts.append("角色")
        if self.cb_weapon.isChecked():
            parts.append("武器")
        if self.cb_echo.isChecked():
            parts.append("声骸套装")

        if not parts:
            QMessageBox.information(self, "未选择", "请至少勾选一项要应用的内容。")
            return

        msg = (f"将应用预设「{preset_info['name']}」的以下内容到当前计算器：\n\n"
               f"  • {'  • '.join(parts)}\n\n"
               "预设数据将追加到现有数据中（不会清空已有数据）。\n是否继续？")
        reply = QMessageBox.question(
            self, "确认应用", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 构建只包含用户勾选部分的数据
        filtered = {"version": data.get("version", 1), "type": "preset", "name": data.get("name", "")}
        if self.cb_char.isChecked() and "character" in data:
            filtered["character"] = data["character"]
        if self.cb_weapon.isChecked() and "weapon" in data:
            filtered["weapon"] = data["weapon"]
        if self.cb_echo.isChecked() and "echo_set" in data:
            filtered["echo_set"] = data["echo_set"]

        try:
            PresetManager.apply_preset(filtered, self._main_screen)
        except Exception as e:
            QMessageBox.warning(self, "应用失败", f"应用预设时发生错误:\n{e}")
            return

        QMessageBox.information(
            self, "应用成功",
            f"预设「{preset_info['name']}」已成功应用。\n\n"
            "共鸣链/精炼/套装的所有阶段效果均已添加，\n"
            "标记为「默认隐藏」的效果已在隐藏状态中。")
        self.accept()

    def _update_official(self):
        PresetManager.update_official_presets(self)
        self._refresh_list()

    def _open_builder(self):
        from preset_builder import PresetBuilderDialog
        dlg = PresetBuilderDialog(self)
        dlg.exec()
        self._refresh_list()
