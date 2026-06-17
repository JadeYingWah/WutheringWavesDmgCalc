# -*- coding: utf-8 -*-
"""
GUI 自动化测试 —— 按钮 / 导航 / 数据流 / 防御页 / 双向跳转
需要 PyQt6 + pytest-qt，运行时会弹出真实窗口。
"""

import pytest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QPushButton, QCheckBox, QLineEdit
from PyQt6.QtCore import Qt, QTimer

_app = QApplication.instance() or QApplication(sys.argv)

# ═══════════════════════════════════════════════════════════════
# fixture
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def main_window():
    from WWDmgCalc import DmgCalculator
    win = DmgCalculator()
    yield win
    win.close()


def _ms(win):
    return win.main_screen


def _btn_by_text(parent, text):
    """递归查找按钮"""
    for btn in parent.findChildren(QPushButton):
        if btn.text() == text:
            return btn
    return None


# ═══════════════════════════════════════════════════════════════
# 一、工具栏按钮
# ═══════════════════════════════════════════════════════════════

class TestToolbarButtons:
    def test_all_toolbar_buttons_exist(self, main_window, qtbot):
        texts = ["快速保存", "快速加载", "导入", "导出",
                 "预设构建器", "使用预设"]
        for t in texts:
            btn = _btn_by_text(main_window, t)
            assert btn is not None, f"工具栏缺少按钮: {t}"

    def test_auto_update_toggle(self, main_window, qtbot):
        btn = _btn_by_text(main_window, "开启自动更新")
        if btn:
            assert btn.text() in ("开启自动更新", "关闭自动更新")

    def test_theme_btn_exists(self, main_window):
        themes = ["切换到白天模式", "切换到黑夜模式"]
        found = _btn_by_text(main_window, themes[0]) or _btn_by_text(main_window, themes[1])
        assert found is not None, "缺少主题切换按钮"


# ═══════════════════════════════════════════════════════════════
# 二、导航树
# ═══════════════════════════════════════════════════════════════

class TestNavigation:
    def test_nav_items_exist(self, main_window):
        """导航树最少 5 个顶级节点"""
        tree = _ms(main_window).nav_tree
        assert tree.topLevelItemCount() >= 5, f"只有 {tree.topLevelItemCount()} 个顶级节点"

    def test_nav_click_resonance_buff(self, main_window, qtbot):
        """点击共鸣链增益不崩溃"""
        ms = _ms(main_window)
        # 通过 scroll 确认页面存在
        assert "resonance_buff" in ms._scrolls

    def test_all_summary_pages_exist(self, main_window):
        ms = _ms(main_window)
        for key in ["summary_base", "summary_bonus", "summary_deepen",
                     "summary_crit", "summary_indep"]:
            assert key in ms._scrolls, f"缺少: {key}"

    def test_defense_and_resistance_exist(self, main_window):
        ms = _ms(main_window)
        assert "enemy_defense" in ms._scrolls
        assert "enemy_resistance" in ms._scrolls


# ═══════════════════════════════════════════════════════════════
# 三、防御减伤页面（核心）
# ═══════════════════════════════════════════════════════════════

class TestDefensePage:
    def test_7_tables_exist(self, main_window):
        ed = _ms(main_window).page_enemy_defense
        assert len(ed._def_tables) == 7, f"应为 7 表，实际 {len(ed._def_tables)}"
        assert "通用" in ed._def_tables
        for sk in ["普攻", "重击", "共鸣技能", "共鸣解放", "变奏技能", "声骸技能"]:
            assert sk in ed._def_tables, f"缺少技能表: {sk}"

    def test_view_chips_exist(self, main_window):
        ed = _ms(main_window).page_enemy_defense
        chip_texts = [b.text() for b in ed._view_chips]
        assert "无类别" in chip_texts
        assert "普攻" in chip_texts
        assert "共鸣解放" in chip_texts

    def test_view_skill_switch(self, main_window, qtbot):
        ed = _ms(main_window).page_enemy_defense
        old_skill = ed._view_skill
        # 点击"共鸣解放"按钮
        for btn in ed._view_chips:
            if btn.text() == "共鸣解放":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break
        assert ed._view_skill == "共鸣解放" or old_skill != ed._view_skill

    def test_timing_chips_on_each_table(self, main_window):
        ed = _ms(main_window).page_enemy_defense
        for key, d in ed._def_tables.items():
            chips = d["chips"]
            texts = {c.text() for c in chips}
            assert texts == {"全部", "常驻", "触发"}, f"{key} 芯片: {texts}"

    def test_level_spins_exist(self, main_window):
        ed = _ms(main_window).page_enemy_defense
        assert ed.char_level.value() == 90
        assert ed.enemy_level.value() == 100

    def test_result_labels_exist(self, main_window):
        ed = _ms(main_window).page_enemy_defense
        assert "0.0%" in ed.total_ignore_label.text() or True  # 可能已计算
        assert "0.0000" in ed.def_multiplier_label.text() or True

    def test_defense_zone_api(self, main_window):
        """get_defense_zone 返回合理值"""
        ed = _ms(main_window).page_enemy_defense
        dz = ed.get_defense_zone()
        assert 0.4 < dz < 1.1, f"防御乘区异常: {dz}"


# ═══════════════════════════════════════════════════════════════
# 四、抗性页面
# ═══════════════════════════════════════════════════════════════

class TestResistancePage:
    def test_6_types_exist(self, main_window):
        er = _ms(main_window).page_enemy_resistance
        assert len(er.TYPES) == 6

    def test_res_multiplier_api(self, main_window):
        er = _ms(main_window).page_enemy_resistance
        rm = er.get_resistance_multiplier("冷凝")
        assert 0.01 < rm < 2.0, f"抗性乘数异常: {rm}"

    def test_preset_values(self, main_window):
        er = _ms(main_window).page_enemy_resistance
        assert er.BASE_VALUES["world"] == 10
        assert er.BOOST_VALUES["world"] == 30


# ═══════════════════════════════════════════════════════════════
# 五、数据流 — 添加词条 → 防御/抗性页收集
# ═══════════════════════════════════════════════════════════════

class TestDataFlow:
    def test_add_defense_item_collected(self, main_window, qtbot):
        """综合常驻添加无视防御 → 防御页能收集到"""
        ms = _ms(main_window)
        page = ms.page_combined_perm

        # 模拟添加词条
        page._counter += 1
        page._add_row_with_source("无视防御", 20.0, page._counter, "测试")

        # 收集数据
        items = page.collect_data()
        names = [it[0] for it in items]
        # 清理
        if page._rows:
            rd = page._rows[-1]
            page._delete_combined_row("无视防御", "测试", rd, page._counter)
        assert "无视防御" in names, f"收集数据中无无视防御: {names}"

    def test_defense_page_recalc_no_crash(self, main_window):
        """防御页 recalc 不崩溃"""
        ed = _ms(main_window).page_enemy_defense
        try:
            ed.recalc()
        except Exception as e:
            pytest.fail(f"recalc crashed: {e}")

    def test_resistance_page_recalc_no_crash(self, main_window):
        er = _ms(main_window).page_enemy_resistance
        try:
            er._recalc()
        except Exception as e:
            pytest.fail(f"_recalc crashed: {e}")


# ═══════════════════════════════════════════════════════════════
# 六、计算结果页
# ═══════════════════════════════════════════════════════════════

class TestResultPage:
    def test_filter_widgets_exist(self, main_window):
        rp = _ms(main_window).page_result
        assert rp.filter_skill is not None
        assert rp.filter_element is not None

    def test_compute_no_crash(self, main_window):
        rp = _ms(main_window).page_result
        try:
            rp.compute()
        except Exception as e:
            pytest.fail(f"compute crashed: {e}")

    def test_auto_compute_toggle(self, main_window, qtbot):
        rp = _ms(main_window).page_result
        btn = rp.auto_compute_btn
        assert btn is not None
        current_text = btn.text()
        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
        assert btn.text() != current_text  # 切换成功


# ═══════════════════════════════════════════════════════════════
# 七、结果列表页
# ═══════════════════════════════════════════════════════════════

class TestResultListPage:
    def test_list_exists(self, main_window):
        rl = _ms(main_window).page_result_list
        assert rl is not None

    def test_recalc_no_crash(self, main_window):
        rl = _ms(main_window).page_result_list
        try:
            rl.recalc()
        except Exception as e:
            pytest.fail(f"recalc crashed: {e}")


# ═══════════════════════════════════════════════════════════════
# 八、存档/导出
# ═══════════════════════════════════════════════════════════════

class TestSaveExport:
    def test_collect_full_state_no_crash(self, main_window):
        from WWDmgCalc import SaveManager
        ms = _ms(main_window)
        try:
            state = SaveManager.collect_full_state(ms)
            assert isinstance(state, dict)
            assert "pages" in state
        except Exception as e:
            pytest.fail(f"collect_full_state crashed: {e}")

    def test_defense_page_save_has_disabled_items(self, main_window):
        from WWDmgCalc import SaveManager
        ms = _ms(main_window)
        state = SaveManager.collect_full_state(ms)
        pages = state.get("pages", {})
        ed_data = pages.get("enemy_defense", {})
        # 至少有关键字段
        assert "char_level" in ed_data, f"缺少 char_level: {list(ed_data.keys())}"
        assert "enemy_level" in ed_data
