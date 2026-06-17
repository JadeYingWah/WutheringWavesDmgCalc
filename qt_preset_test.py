# -*- coding: utf-8 -*-
"""
预设应用后主程序完整性测试
==========================
覆盖历史 bug：_trigger_states / _timing_override / _summary_pages /
navigate_requested 丢失、序列号错位、防御页属性消失、存档字段缺失。
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

_app = QApplication.instance() or QApplication(sys.argv)
RESULTS = []

def log(step, ok, detail=""):
    s = "PASS" if ok else "FAIL"
    line = f'  [{s}] {step}' + (f' ({detail})' if detail else '')
    print(line)
    RESULTS.append((step, ok, detail))


def run():
    from WWDmgCalc import DmgCalculator, SaveManager
    from preset_manager import PresetManager
    
    win = DmgCalculator()
    ms = win.main_screen
    
    # ═══════ 1. 预置状态检查 ═══════
    print("=== 1. 预置状态检查 ===")
    
    log("MainScreen 存在", ms is not None)
    log("防御页属性", hasattr(ms.page_enemy_defense, '_def_tables'))
    log("防御页7表", len(ms.page_enemy_defense._def_tables) == 7 if hasattr(ms.page_enemy_defense, '_def_tables') else False)
    log("抗性页属性", hasattr(ms.page_enemy_resistance, '_res_mult'))
    log("def_multiplier 存在", hasattr(ms.page_enemy_defense, 'def_multiplier'))
    log("_disabled_items 存在", hasattr(ms.page_enemy_defense, '_disabled_items'))
    log("_timing_filters 存在", hasattr(ms.page_enemy_defense, '_timing_filters'))
    log("_view_skill 存在", hasattr(ms.page_enemy_defense, '_view_skill'))
    log("_view_chips 7个", len(ms.page_enemy_defense._view_chips) == 7 if hasattr(ms.page_enemy_defense, '_view_chips') else False)
    log("_timing_override SummaryBasePage", hasattr(ms.page_summary_bonus, '_timing_override'))
    
    # ═══════ 2. 加载角色预设 ═══════
    print("\n=== 2. 加载角色预设 ===")
    
    char_preset_path = os.path.join(
        os.path.dirname(__file__), 'presets', 'official', 'character',
        '漂泊者-气动.json'
    )
    weapon_preset_path = os.path.join(
        os.path.dirname(__file__), 'presets', 'official', 'weapon',
        '血誓盟约.json'
    )
    
    char_data = None
    if os.path.exists(char_preset_path):
        with open(char_preset_path, 'r', encoding='utf-8') as f:
            char_data = json.load(f)
        log("角色预设加载", True, char_preset_path)
    else:
        log("角色预设加载", False, "文件未找到，跳过")
    
    if char_data:
        try:
            PresetManager.apply_preset(char_data, ms)
            log("apply_preset 无异常", True)
        except Exception as e:
            log("apply_preset 无异常", False, str(e))
    
    # ═══════ 3. 应用后页面完整性 ═══════
    print("\n=== 3. 应用预设后页面完整性 ===")
    
    log("防御页 _def_tables 仍存在", hasattr(ms.page_enemy_defense, '_def_tables'))
    log("防御页 7 表仍完整", len(ms.page_enemy_defense._def_tables) == 7 if hasattr(ms.page_enemy_defense, '_def_tables') else False)
    log("抗性页 _res_mult 仍存在", hasattr(ms.page_enemy_resistance, '_res_mult'))
    log("抗性页 get_resistance_multiplier 可调用", callable(getattr(ms.page_enemy_resistance, 'get_resistance_multiplier', None)))
    log("防御页 get_defense_zone 可调用", callable(getattr(ms.page_enemy_defense, 'get_defense_zone', None)))
    
    # 导航映射
    log("navigate_requested 防御页", ms.page_enemy_defense.navigate_requested is not None)
    log("navigate_requested 抗性页", ms.page_enemy_resistance.navigate_requested is not None)
    
    # CombinedEntryPage._summary_pages
    sp = getattr(ms.page_combined_perm, '_summary_pages', {})
    log("_summary_pages 含防御页", 'enemy_defense' in sp)
    log("_summary_pages 含抗性页", 'enemy_resistance' in sp)
    
    # ═══════ 4. 各页面 recalc 不崩溃 ═══════
    print("\n=== 4. 各页面 recalc ===")
    
    for key, label in [
        ("summary_base", "基础乘区"), ("summary_bonus", "加成乘区"),
        ("summary_deepen", "加深乘区"), ("summary_crit", "暴击乘区"),
    ]:
        try:
            ms._scrolls[key].widget().recalc()
            log(f"{label} recalc", True)
        except Exception as e:
            log(f"{label} recalc", False, str(e))
    
    try:
        ms.page_enemy_defense.recalc()
        log("防御页 recalc", True)
    except Exception as e:
        log("防御页 recalc", False, str(e))
    
    try:
        ms.page_enemy_resistance._recalc()
        log("抗性页 recalc", True)
    except Exception as e:
        log("抗性页 recalc", False, str(e))
    
    # ═══════ 5. 计算结果 compute ═══════
    print("\n=== 5. 计算结果 compute ===")
    
    try:
        ms.page_result.compute()
        last = getattr(ms.page_result, '_last_computed', {})
        html = last.get('process_html', '')
        log("compute 无异常", True)
        log("process_html 非空", len(html) > 100, f'{len(html)} chars')
    except Exception as e:
        log("compute 无异常", False, str(e))
    
    # ═══════ 6. 存档/导出 ═══════
    print("\n=== 6. 存档收集 ===")
    
    try:
        state = SaveManager.collect_full_state(ms)
        pages = state.get("pages", {})
        ed = pages.get("enemy_defense", {})
        log("collect_full_state 无异常", True)
        log("防御页存档含 char_level", "char_level" in ed)
        log("防御页存档含 disabled_items", "disabled_items" in ed)
        log("防御页存档含 timing_filters", "timing_filters" in ed)
        log("防御页存档含 view_skill", "view_skill" in ed)
        log("防御页存档无 _trigger_states", "_trigger_states" not in ed)
    except Exception as e:
        log("collect_full_state 无异常", False, str(e))
    
    # ═══════ 7. 序列号对齐 ═══════
    print("\n=== 7. 序列号对齐 ===")
    
    try:
        # 加一个防御词条，验证 seq 一致性
        page = ms.page_combined_perm
        page._counter += 1
        page._add_row_with_source("忽视防御", 10.0, page._counter, "测试")
        items = page.collect_data()
        seq = items[-1][4] if items else ""
        
        ed = ms.page_enemy_defense
        ed.recalc()
        matched = False
        for key, d in ed._def_tables.items():
            for r in range(d["table"].rowCount()):
                sq = d["table"].item(r, 3)
                if sq and sq.text() == seq:
                    matched = True
                    break
        log("预设后序列号对齐", matched, f'seq={seq}')
        
        # 清理
        if page._rows:
            page._delete_combined_row("忽视防御", "测试", page._rows[-1], page._counter)
    except Exception as e:
        log("序列号测试不崩溃", False, str(e))
    
    # ═══════ 8. 高亮跳转不崩溃 ═══════
    print("\n=== 8. 高亮跳转 ===")
    
    try:
        ms.page_enemy_defense.highlight_item("无视防御", "综合常驻数值", "combined_perm", "常驻1")
        log("防御页 highlight_item", True)
    except Exception as e:
        log("防御页 highlight_item", False, str(e))
    
    try:
        ms.page_enemy_resistance.highlight_item("冷凝抗性无视", "综合常驻数值", "combined_perm", "常驻1")
        log("抗性页 highlight_item", True)
    except Exception as e:
        log("抗性页 highlight_item", False, str(e))
    
    # ═══════ 总结 ═══════
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    print(f"\n{'='*50}")
    print(f"结果: {passed} PASS, {failed} FAIL (共 {len(RESULTS)} 项)")
    print(f"{'='*50}")
    
    win.close()
    QApplication.quit()

QTimer.singleShot(500, run)
sys.exit(_app.exec())
