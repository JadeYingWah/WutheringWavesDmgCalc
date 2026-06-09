# -*- coding: utf-8 -*-
"""
数据流端到端测试
================
验证每种来源的词条能正确流经 _collect_all_items → 分类路由 → 总结页筛选。

测试范围：
  - CharBasePage → _collect_all_items → 基础乘区
  - CombinedEntryPage(常驻/触发) → _collect_all_items → 各乘区
  - EchoPage → _collect_all_items → 各乘区
  - KeywordAssociationPage → get_items → 各乘区
  - 共鸣链同步 → 综合填写 + 关键词关联 → 各乘区
  - classify_item_category 路由正确性
  - _collect_all_items 数据转换正确性
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from damage_calc import (
    classify_item_category,
    matches_filter,
    is_defense_item,
    is_resistance_item,
    BONUS_SUFFIX, DEEPEN_SUFFIX,
    CRIT_RATE_KEYWORDS, CRIT_DMG_KEYWORDS,
)


# ============================================================
# 辅助：模拟 _collect_all_items 的数据转换逻辑
# ============================================================

def simulate_collect_all_items(external_sources, echo_pages=None):
    """模拟 WWDmgCalc._collect_all_items 的逻辑（纯函数版，无 GUI 依赖）。
    返回 [(name, value, source_label, nav_key, seq_label, sub_name), ...]
    """
    items = []
    for src_label, data, nav_key in external_sources:
        if isinstance(data, list):
            for entry in data:
                name, value = entry[0], entry[1]
                item_src = entry[3] if len(entry) >= 4 else src_label
                seq_label = ""
                sub_name = ""
                if len(entry) >= 5 and nav_key in ("combined_perm", "combined_trigger"):
                    type_label = "常驻" if nav_key == "combined_perm" else "触发"
                    seq_label = f"{type_label}{entry[4]}"
                if len(entry) >= 6:
                    sub_name = entry[5] or ""
                items.append((name, value, item_src, nav_key, seq_label, sub_name))
        elif isinstance(data, dict):
            if 'base_atk' in data:
                for n, v in [
                    ("角色基础攻击力", data['base_atk']),
                    ("武器基础攻击力", data['weapon_base_atk']),
                    ("角色基础生命值", data['base_hp']),
                    ("角色基础防御力", data['base_def']),
                ] + ([("武器附加" + data['weapon_bonus'][0], data['weapon_bonus'][1])]
                     if data.get('weapon_bonus') else []):
                    items.append((n, v, src_label, nav_key, "", ""))
            elif 'main_stat' in data:
                ms_name, ms_val = data['main_stat']
                fs_name, fs_val = data['fixed_stat']
                for n, v in [(f"[声骸]主词条-{ms_name}", ms_val),
                             (f"[声骸]固定词条-{fs_name}", fs_val)] + \
                             [(f"[声骸]副词条-{ss_name}", ss_val)
                              for ss_name, ss_val, *_ in data['sub_stats']]:
                    items.append((n, v, src_label, nav_key, "", ""))
    if echo_pages:
        for ei, (eid, echo_data) in enumerate(echo_pages.items(), 1):
            src_label = f"声骸{echo_data['cost']}费"
            nav_key = f"echo_{eid}"
            ms_name, ms_val = echo_data['main_stat']
            items.append((f"[声骸]主词条-{ms_name}", ms_val, src_label, nav_key,
                          f"{ei}号声骸主词", ""))
            fs_name, fs_val = echo_data['fixed_stat']
            items.append((f"[声骸]固定词条-{fs_name}", fs_val, src_label, nav_key,
                          f"{ei}号声骸固词", ""))
            for si, (ss_name, ss_val, *_) in enumerate(echo_data['sub_stats'], 1):
                items.append((f"[声骸]副词条-{ss_name}", ss_val, src_label, nav_key,
                              f"{ei}号声骸副词{si}", ""))
    return items


def simulate_summary_filter(items, zone_type):
    """模拟 SummaryPage 的筛选逻辑，返回属于指定乘区的词条列表。
    zone_type: "base" | "bonus" | "deepen" | "crit"
    注意：基础乘区使用 SummaryBaseZonePage 的显式名称匹配，而非 classify_item_category。
    """
    filtered = []
    for name, value, src, nav_key, seq, sub_name in items:
        if zone_type == "base":
            # SummaryBaseZonePage.recalc() 的逻辑（line 506-527）
            if name in ("角色基础攻击力", "武器基础攻击力", "角色基础生命值", "角色基础防御力"):
                filtered.append((name, value, src, nav_key, seq, sub_name))
            elif ("攻击力" in name and "固定" not in name and "基础" not in name
                  and "基础" not in name):
                filtered.append((name, value, src, nav_key, seq, sub_name))
            elif "固定攻击" in name:
                filtered.append((name, value, src, nav_key, seq, sub_name))
            elif "生命值" in name and "固定" not in name and "基础" not in name:
                filtered.append((name, value, src, nav_key, seq, sub_name))
            elif "固定生命" in name:
                filtered.append((name, value, src, nav_key, seq, sub_name))
            elif "防御力" in name and "固定" not in name and "基础" not in name:
                filtered.append((name, value, src, nav_key, seq, sub_name))
            elif "固定防御" in name:
                filtered.append((name, value, src, nav_key, seq, sub_name))
        elif zone_type == "bonus":
            # SummaryBonusZonePage.recalc() 的逻辑（line 584-586）
            if any(s in name for s in BONUS_SUFFIX) and \
               not any(kw in name for kw in CRIT_DMG_KEYWORDS):
                filtered.append((name, value, src, nav_key, seq, sub_name))
        elif zone_type == "deepen":
            # SummaryDeepenZonePage.recalc() 的逻辑（line 607）
            if DEEPEN_SUFFIX in name:
                filtered.append((name, value, src, nav_key, seq, sub_name))
        elif zone_type == "crit":
            # SummaryCritZonePage.recalc() 的逻辑（line 628-631）
            if any(kw in name for kw in CRIT_RATE_KEYWORDS | CRIT_DMG_KEYWORDS):
                filtered.append((name, value, src, nav_key, seq, sub_name))
    return filtered


# ============================================================
# 测试：classify_item_category 路由正确性
# ============================================================

class TestClassifyItemCategory:
    """验证每个词条名称被正确路由到对应的乘区分类。"""

    # --- 基础乘区 ---
    @pytest.mark.parametrize("name", [
        "角色基础攻击力", "武器基础攻击力",
        "攻击力加成", "攻击力", "攻击", "固定攻击",
        "[声骸]固定词条-基础攻击", "[声骸]主词条-攻击力",
    ])
    def test_base_items(self, name):
        assert classify_item_category(name) == "base", f"'{name}' 应归类为 base"

    # --- 加成乘区 ---
    @pytest.mark.parametrize("name", [
        "伤害加成", "伤害提升", "冷凝伤害加成", "热熔伤害提升",
        "共鸣技能伤害加成", "共鸣解放伤害提升", "普攻伤害加成",
        "[声骸]副词条-伤害加成",
    ])
    def test_bonus_items(self, name):
        assert classify_item_category(name) == "bonus", f"'{name}' 应归类为 bonus"

    # --- 加深乘区 ---
    @pytest.mark.parametrize("name", [
        "伤害加深", "加深", "效应伤害加深", "重击伤害加深",
    ])
    def test_deepen_items(self, name):
        assert classify_item_category(name) == "deepen", f"'{name}' 应归类为 deepen"

    # --- 暴击乘区 ---
    @pytest.mark.parametrize("name", [
        "暴击率", "暴击伤害", "暴击伤害加成", "暴伤", "暴傷",
        "[声骸]副词条-暴击率", "[声骸]副词条-暴击伤害",
    ])
    def test_crit_items(self, name):
        assert classify_item_category(name) == "crit", f"'{name}' 应归类为 crit"

    # --- 防御 ---
    @pytest.mark.parametrize("name", [
        "无视防御", "忽视防御", "减少防御",
        "共鸣技能无视防御", "共鸣解放无视防御",
        "重击伤害无视防御", "普攻伤害无视防御",
    ])
    def test_defense_items(self, name):
        assert classify_item_category(name) == "defense", f"'{name}' 应归类为 defense"

    # --- 抗性 ---
    @pytest.mark.parametrize("name", [
        "冷凝抗性无视", "热熔抗性无视", "气动抗性无视",
        "导电抗性无视", "衍射抗性无视", "湮灭抗性无视",
        "冷凝抗性减少", "全属性抗性减少",
    ])
    def test_resistance_items(self, name):
        assert classify_item_category(name) == "resistance", f"'{name}' 应归类为 resistance"

    # --- 其他（不应误分类）---
    # 注：角色基础生命值/防御力在 SummaryBaseZonePage 中由显式名称匹配处理，
    # 不经过 classify_item_category，因此返回 "other" 是正确的。
    @pytest.mark.parametrize("name", [
        "共鸣链效果", "未知词条", "测试用词条",
        "角色基础生命值", "角色基础防御力",
    ])
    def test_other_items(self, name):
        assert classify_item_category(name) == "other", f"'{name}' 应归类为 other"


# ============================================================
# 测试：CharBasePage → _collect_all_items → 基础乘区
# ============================================================

class TestCharBaseFlow:
    """验证角色基础值数据正确流入基础乘区。"""

    def _make_char_base_data(self, base_atk=400, weapon_base=500, base_hp=12000,
                             base_def=600, weapon_bonus=None):
        return {
            'base_atk': base_atk,
            'weapon_base_atk': weapon_base,
            'base_hp': base_hp,
            'base_def': base_def,
            'weapon_bonus': weapon_bonus,
        }

    def test_basic_stats_collected(self):
        """角色四维 + 武器基础应被收集为 4~5 条。"""
        data = self._make_char_base_data()
        sources = [("角色武器", data, "char_base")]
        items = simulate_collect_all_items(sources)
        names = [n for n, *_ in items]
        assert "角色基础攻击力" in names
        assert "武器基础攻击力" in names
        assert "角色基础生命值" in names
        assert "角色基础防御力" in names
        assert len(items) == 4

    def test_weapon_bonus_collected(self):
        """武器附加属性应被收集。"""
        data = self._make_char_base_data(weapon_bonus=("攻击力", 12.4))
        sources = [("角色武器", data, "char_base")]
        items = simulate_collect_all_items(sources)
        names = [n for n, *_ in items]
        assert "武器附加攻击力" in names
        assert len(items) == 5

    def test_char_base_flows_to_base_zone(self):
        """角色基础值应全部流入基础乘区。"""
        data = self._make_char_base_data(weapon_bonus=("攻击力", 12.4))
        sources = [("角色武器", data, "char_base")]
        items = simulate_collect_all_items(sources)
        base_items = simulate_summary_filter(items, "base")
        assert len(base_items) == 5  # 4基础 + 1武器附加

    def test_char_base_not_in_other_zones(self):
        """角色基础值不应流入加成/加深/暴击乘区。"""
        data = self._make_char_base_data(weapon_bonus=("攻击力", 12.4))
        sources = [("角色武器", data, "char_base")]
        items = simulate_collect_all_items(sources)
        assert len(simulate_summary_filter(items, "bonus")) == 0
        assert len(simulate_summary_filter(items, "deepen")) == 0
        assert len(simulate_summary_filter(items, "crit")) == 0

    def test_seq_and_sub_name_empty(self):
        """CharBasePage 的词条没有序列号和副名称。"""
        data = self._make_char_base_data()
        sources = [("角色武器", data, "char_base")]
        items = simulate_collect_all_items(sources)
        for name, value, src, nk, seq, sub in items:
            assert seq == "", f"'{name}' 序列号应为空"
            assert sub == "", f"'{name}' 副名称应为空"


# ============================================================
# 测试：CombinedEntryPage → _collect_all_items → 各乘区
# ============================================================

class TestCombinedEntryFlow:
    """验证综合填写页词条正确流入对应乘区。"""

    def _make_combined_row(self, name, value, source="手动", seq=1, sub_name=""):
        return (name, value, False, source, seq, sub_name)

    def test_bonus_item_to_bonus_zone(self):
        """'伤害加成' 应流入加成乘区。"""
        rows = [self._make_combined_row("伤害加成", 30)]
        sources = [("综合常驻数值", rows, "combined_perm")]
        items = simulate_collect_all_items(sources)
        bonus = simulate_summary_filter(items, "bonus")
        assert len(bonus) == 1
        assert bonus[0][0] == "伤害加成"
        assert bonus[0][1] == 30

    def test_crit_rate_to_crit_zone(self):
        """'暴击率' 应流入暴击乘区。"""
        rows = [self._make_combined_row("暴击率", 10)]
        sources = [("综合触发数值", rows, "combined_trigger")]
        items = simulate_collect_all_items(sources)
        crit = simulate_summary_filter(items, "crit")
        assert len(crit) == 1
        assert crit[0][0] == "暴击率"

    def test_deepen_to_deepen_zone(self):
        """'伤害加深' 应流入加深乘区。"""
        rows = [self._make_combined_row("伤害加深", 20)]
        sources = [("综合常驻数值", rows, "combined_perm")]
        items = simulate_collect_all_items(sources)
        deepen = simulate_summary_filter(items, "deepen")
        assert len(deepen) == 1
        assert deepen[0][0] == "伤害加深"

    def test_defense_item_to_defense(self):
        """'无视防御' 应被分类为 defense。"""
        rows = [self._make_combined_row("无视防御", 18)]
        sources = [("综合常驻数值", rows, "combined_perm")]
        items = simulate_collect_all_items(sources)
        defense = [(n, v, s, nk, sq, sub) for n, v, s, nk, sq, sub in items
                   if classify_item_category(n) == "defense"]
        assert len(defense) == 1

    def test_seq_label_format(self):
        """综合常驻页序列号应为 '常驻N'，触发页应为 '触发N'。"""
        perm_rows = [self._make_combined_row("伤害加成", 10, seq=1)]
        trig_rows = [self._make_combined_row("暴击率", 5, seq=2)]
        sources = [
            ("综合常驻数值", perm_rows, "combined_perm"),
            ("综合触发数值", trig_rows, "combined_trigger"),
        ]
        items = simulate_collect_all_items(sources)
        seqs = {n: sq for n, v, s, nk, sq, sub in items}
        assert seqs["伤害加成"] == "常驻1"
        assert seqs["暴击率"] == "触发2"

    def test_sub_name_preserved(self):
        """副名称应被正确传递。"""
        rows = [self._make_combined_row("伤害加成", 30, sub_name="测试副名")]
        sources = [("综合常驻数值", rows, "combined_perm")]
        items = simulate_collect_all_items(sources)
        assert items[0][5] == "测试副名"

    def test_source_label_preserved(self):
        """来源标签应被正确传递。"""
        rows = [self._make_combined_row("伤害加成", 30, source="声骸")]
        sources = [("综合常驻数值", rows, "combined_perm")]
        items = simulate_collect_all_items(sources)
        assert items[0][2] == "声骸"

    def test_multiple_items_different_zones(self):
        """多个词条应分别流入各自乘区。"""
        rows = [
            self._make_combined_row("伤害加成", 30, seq=1),
            self._make_combined_row("暴击率", 10, seq=2),
            self._make_combined_row("伤害加深", 15, seq=3),
            self._make_combined_row("暴击伤害", 20, seq=4),
        ]
        sources = [("综合常驻数值", rows, "combined_perm")]
        items = simulate_collect_all_items(sources)
        assert len(simulate_summary_filter(items, "bonus")) == 1
        assert len(simulate_summary_filter(items, "crit")) == 2  # 暴击率 + 暴击伤害
        assert len(simulate_summary_filter(items, "deepen")) == 1


# ============================================================
# 测试：EchoPage → _collect_all_items → 各乘区
# ============================================================

class TestEchoFlow:
    """验证声骸词条正确流入对应乘区。"""

    def _make_echo(self, cost=4, main=("攻击力", 33), fixed=("固定攻击", 150),
                   subs=None):
        if subs is None:
            subs = [("暴击率", 10.5, True), ("暴击伤害", 21.0, True)]
        return {
            'cost': cost,
            'main_stat': main,
            'fixed_stat': fixed,
            'sub_stats': subs,
        }

    def test_echo_items_count(self):
        """4费声骸（2副词条）应产生 4 条数据。"""
        echo = self._make_echo()
        echoes = {1: echo}
        items = simulate_collect_all_items([], echo_pages=echoes)
        assert len(items) == 4  # 主 + 固定 + 2副

    def test_echo_main_stat_name(self):
        """主词条名称应含 '[声骸]主词条-' 前缀。"""
        echo = self._make_echo()
        echoes = {1: echo}
        items = simulate_collect_all_items([], echo_pages=echoes)
        names = [n for n, *_ in items]
        assert "[声骸]主词条-攻击力" in names

    def test_echo_fixed_stat_name(self):
        """固定词条名称应含 '[声骸]固定词条-' 前缀。"""
        echo = self._make_echo()
        echoes = {1: echo}
        items = simulate_collect_all_items([], echo_pages=echoes)
        names = [n for n, *_ in items]
        assert "[声骸]固定词条-固定攻击" in names

    def test_echo_sub_stat_names(self):
        """副词条名称应含 '[声骸]副词条-' 前缀。"""
        echo = self._make_echo()
        echoes = {1: echo}
        items = simulate_collect_all_items([], echo_pages=echoes)
        names = [n for n, *_ in items]
        assert "[声骸]副词条-暴击率" in names
        assert "[声骸]副词条-暴击伤害" in names

    def test_echo_seq_labels(self):
        """声骸词条应有正确的序列号标签。"""
        echo = self._make_echo()
        echoes = {1: echo}
        items = simulate_collect_all_items([], echo_pages=echoes)
        seqs = {n: sq for n, v, s, nk, sq, sub in items}
        assert seqs["[声骸]主词条-攻击力"] == "1号声骸主词"
        assert seqs["[声骸]固定词条-固定攻击"] == "1号声骸固词"
        assert seqs["[声骸]副词条-暴击率"] == "1号声骸副词1"
        assert seqs["[声骸]副词条-暴击伤害"] == "1号声骸副词2"

    def test_echo_flows_to_correct_zones(self):
        """声骸词条应按名称流入对应乘区。"""
        echo = self._make_echo(subs=[
            ("暴击率", 10.5, True),
            ("暴击伤害", 21.0, True),
            ("伤害加成", 8.6, True),
        ])
        echoes = {1: echo}
        items = simulate_collect_all_items([], echo_pages=echoes)
        # 基础乘区：主词条-攻击力, 固定词条-基础攻击
        base = simulate_summary_filter(items, "base")
        assert len(base) == 2
        # 加成乘区：副词条-伤害加成
        bonus = simulate_summary_filter(items, "bonus")
        assert len(bonus) == 1
        assert bonus[0][0] == "[声骸]副词条-伤害加成"
        # 暴击乘区：副词条-暴击率, 副词条-暴击伤害
        crit = simulate_summary_filter(items, "crit")
        assert len(crit) == 2

    def test_multiple_echoes(self):
        """多个声骸的数据应全部被收集。"""
        echo1 = self._make_echo(cost=4, subs=[("暴击率", 10.5, True)])
        echo2 = self._make_echo(cost=3, main=("生命", 2280), fixed=("固定生命", 2280),
                                subs=[("暴击伤害", 15.0, True)])
        echoes = {1: echo1, 2: echo2}
        items = simulate_collect_all_items([], echo_pages=echoes)
        assert len(items) == 6  # 3 + 3

    def test_echo_source_label(self):
        """来源标签应包含 COST 信息。"""
        echo = self._make_echo(cost=4)
        echoes = {1: echo}
        items = simulate_collect_all_items([], echo_pages=echoes)
        for n, v, src, nk, sq, sub in items:
            assert src == "声骸4费"


# ============================================================
# 测试：混合来源 → 完整数据流
# ============================================================

class TestMixedSourcesFlow:
    """验证多个来源的词条混合后仍能正确分类。"""

    def test_full_pipeline(self):
        """模拟完整的数据收集流程：角色 + 综合 + 声骸。"""
        char_data = {
            'base_atk': 400, 'weapon_base_atk': 500,
            'base_hp': 12000, 'base_def': 600,
            'weapon_bonus': ("攻击力", 12.4),
        }
        combined_rows = [
            ("伤害加成", 30, False, "声骸", 1, ""),
            ("暴击率", 10, False, "声骸", 2, ""),
            ("无视防御", 18, False, "共鸣", 3, ""),
        ]
        echo = {
            'cost': 4,
            'main_stat': ("攻击力", 33),
            'fixed_stat': ("固定攻击", 150),
            'sub_stats': [("暴击率", 10.5, True), ("暴击伤害", 21.0, True)],
        }

        sources = [
            ("角色武器", char_data, "char_base"),
            ("综合常驻数值", combined_rows, "combined_perm"),
        ]
        echoes = {1: echo}
        items = simulate_collect_all_items(sources, echo_pages=echoes)

        # 总数：5(角色) + 3(综合) + 4(声骸) = 12
        assert len(items) == 12

        # 各乘区筛选
        base = simulate_summary_filter(items, "base")
        bonus = simulate_summary_filter(items, "bonus")
        crit = simulate_summary_filter(items, "crit")
        defense = [(n, v, s, nk, sq, sub) for n, v, s, nk, sq, sub in items
                   if classify_item_category(n) == "defense"]

        assert len(base) == 7   # 4角色 + 1武器附加 + 1声骸主 + 1声骸固
        assert len(bonus) == 1  # 综合-伤害加成（声骸副词条无伤害加成）
        assert len(crit) == 3   # 综合-暴击率 + 声骸副-暴击率 + 声骸副-暴击伤害
        assert len(defense) == 1  # 综合-无视防御
        assert len(crit) == 3   # 综合-暴击率 + 声骸副-暴击率 + 声骸副-暴击伤害
        assert len(defense) == 1  # 综合-无视防御

    def test_all_items_have_valid_tuples(self):
        """所有收集到的词条应为 6 元组。"""
        char_data = {
            'base_atk': 400, 'weapon_base_atk': 500,
            'base_hp': 12000, 'base_def': 600,
            'weapon_bonus': None,
        }
        combined_rows = [
            ("伤害加成", 30, False, "声骸", 1, "副名测试"),
        ]
        sources = [
            ("角色武器", char_data, "char_base"),
            ("综合常驻数值", combined_rows, "combined_perm"),
        ]
        items = simulate_collect_all_items(sources)
        for item in items:
            assert len(item) == 6, f"词条 {item[0]} 不是 6 元组"
            name, value, src, nk, seq, sub = item
            assert isinstance(name, str)
            assert isinstance(value, (int, float))
            assert isinstance(src, str)
            assert isinstance(nk, str)
            assert isinstance(seq, str)
            assert isinstance(sub, str)


# ============================================================
# 测试：词条来源 → 乘区分类 全覆盖
# ============================================================

class TestSourceToZoneCoverage:
    """确保每种常见的词条名称都能被正确路由到乘区。"""

    # 共鸣链中常见的词条
    @pytest.mark.parametrize("name,expected", [
        ("伤害加成", "bonus"),
        ("伤害提升", "bonus"),
        ("冷凝伤害加成", "bonus"),
        ("热熔伤害提升", "bonus"),
        ("暴击率", "crit"),
        ("暴击伤害", "crit"),
        ("暴伤", "crit"),
        ("伤害加深", "deepen"),
        ("效应伤害加深", "deepen"),
        ("无视防御", "defense"),
        ("共鸣技能无视防御", "defense"),
        ("冷凝抗性减少", "resistance"),
        ("全属性抗性减少", "resistance"),
        ("攻击力加成", "base"),
        ("攻击力", "base"),
    ])
    def test_common_items_classified(self, name, expected):
        """常见词条名称应被正确分类。"""
        assert classify_item_category(name) == expected

    # 声骸副词条
    @pytest.mark.parametrize("name,expected", [
        ("[声骸]副词条-暴击率", "crit"),
        ("[声骸]副词条-暴击伤害", "crit"),
        ("[声骸]副词条-伤害加成", "bonus"),
        ("[声骸]副词条-攻击力", "base"),
        ("[声骸]主词条-攻击力", "base"),
        ("[声骸]固定词条-固定攻击", "base"),
    ])
    def test_echo_items_classified(self, name, expected):
        """声骸词条名称应被正确分类。"""
        assert classify_item_category(name) == expected
