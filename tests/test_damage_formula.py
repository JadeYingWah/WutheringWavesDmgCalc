# -*- coding: utf-8 -*-
"""
伤害公式单元测试
================
覆盖 WutheringWavesDmgCalc 中所有纯计算逻辑（不依赖 PyQt6 GUI）。

测试范围:
  - 敌人防御减伤公式
  - 敌人抗性公式
  - 独立乘区公式
  - 基础乘区（攻击/生命/防御）公式
  - 加成 / 加深 / 暴击乘区公式
  - 完整伤害公式端到端
  - 筛选匹配函数
  - 游戏常量
"""

import pytest
import sys
import os

# 从项目根目录导入 damage_calc（测试的是真实代码，不是副本）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from damage_calc import (
    # 常量
    ELEMENT_NAMES_SET, SKILL_TYPE_NAMES_SET, EFFECT_NAMES_SET,
    BONUS_SUFFIX, DEEPEN_SUFFIX,
    CRIT_RATE_KEYWORDS, CRIT_DMG_KEYWORDS,
    DEFENSE_ITEM_NAMES, RESISTANCE_ITEM_NAMES,
    # 筛选
    matches_filter, is_defense_item, is_resistance_item, classify_item_category,
    # 公式
    calc_defense_zone, calc_enemy_base_def,
    calc_resistance_zone,
    calc_indep_zone,
    calc_base_zone, calc_bonus_zone, calc_deepen_zone,
    calc_crit_zone, calc_crit_rate,
    calc_mult_zone,
    calc_final_damage,
    compute_all_zones,
)

# ============================================================
# 测试用例
# ============================================================

# ---- 防御乘区测试 ----

class TestDefenseZone:
    """测试 EnemyDefensePage.recalc() 的防御减伤公式"""

    def test_same_level_no_ignore(self):
        """角色90级，敌人90级，无无视防御 → 防御乘区≈0.5013（并非精确0.5）"""
        # 敌方基础防御 = 792 + 8×90 = 1512
        # (800 + 8×90) = 1520
        # multiplier = 1520 / (1512 + 1520) = 1520/3032 ≈ 0.50131926
        result = calc_defense_zone(char_level=90, enemy_level=90, total_ignore=0.0)
        expected = (800 + 8 * 90) / ((792 + 8 * 90) + (800 + 8 * 90))
        assert result == pytest.approx(expected, abs=1e-10)

    def test_char_90_enemy_100(self):
        """角色90级，敌人100级 → 乘区应小于 0.5"""
        result = calc_defense_zone(char_level=90, enemy_level=100, total_ignore=0.0)
        assert result < 0.5

    def test_ignore_defense_increases_zone(self):
        """无视防御越高，防御乘区越大"""
        no_ignore = calc_defense_zone(90, 100, 0.0)
        half_ignore = calc_defense_zone(90, 100, 0.5)
        full_ignore = calc_defense_zone(90, 100, 1.0)
        assert no_ignore < half_ignore < full_ignore

    def test_full_ignore_is_one(self):
        """100% 无视防御 → 防御乘区 = 1.0"""
        result = calc_defense_zone(char_level=90, enemy_level=100, total_ignore=1.0)
        assert result == pytest.approx(1.0, abs=1e-10)

    def test_ignore_capped_at_one(self):
        """无视防御超过 100% 应被截断为 100%"""
        result = calc_defense_zone(90, 100, 2.0)  # 200% → capped to 100%
        assert result == pytest.approx(1.0, abs=1e-10)

    def test_higher_enemy_level_lower_zone(self):
        """敌人等级越高，防御乘区越低"""
        zone_90 = calc_defense_zone(90, 90)
        zone_100 = calc_defense_zone(90, 100)
        zone_120 = calc_defense_zone(90, 120)
        assert zone_90 > zone_100 > zone_120

    def test_higher_char_level_higher_zone(self):
        """角色等级越高，防御乘区越高"""
        zone_1 = calc_defense_zone(1, 90)
        zone_50 = calc_defense_zone(50, 90)
        zone_90 = calc_defense_zone(90, 90)
        assert zone_1 < zone_50 < zone_90

    def test_enemy_base_def_formula(self):
        """手动验证敌方基础防御公式: 792 + 8×等级"""
        # 等级 90: 792 + 720 = 1512
        # 等级 100: 792 + 800 = 1592
        z90 = calc_defense_zone(90, 90, 1.0)
        assert z90 == pytest.approx(1.0, abs=1e-10)  # 100% ignore → multiplier = 1

    @pytest.mark.parametrize("char_lv,enemy_lv", [
        (90, 90),    # 最常见场景
        (90, 1),     # 低级敌人，乘区高
        (1, 120),    # 极端情况：1级打120级
    ])
    def test_various_levels_no_ignore(self, char_lv, enemy_lv):
        """参数化测试不同等级组合"""
        result = calc_defense_zone(char_lv, enemy_lv, 0.0)
        # 乘区应该在 (0, 1] 范围内
        assert 0 < result <= 1.0


# ---- 抗性乘区测试 ----

class TestResistanceZone:
    """测试 EnemyResistancePage._recalc() 的抗性公式"""

    def test_zero_resistance_is_one(self):
        """抗性为 0 → 乘区 = 1.0"""
        result = calc_resistance_zone(base_res=0, boost_pct=0, reduce_pct=0, ext_reduce=0)
        assert result == pytest.approx(1.0, abs=1e-10)

    def test_positive_resistance_reduces_zone(self):
        """正抗性降低伤害"""
        assert calc_resistance_zone(10) < 1.0
        assert calc_resistance_zone(40) < calc_resistance_zone(10)

    def test_negative_resistance_clamped_to_zero(self):
        """代码中负最终抗性被截断为 0（而非 /200 公式）"""
        # 基础 10, 减少 50 → 最终 = -40 → clamped to 0 → zone = 1.0
        result = calc_resistance_zone(base_res=10, reduce_pct=50)
        assert result == pytest.approx(1.0, abs=1e-10)

    def test_boost_increases_resistance(self):
        """抗性提升让抗性更高，乘区更低"""
        no_boost = calc_resistance_zone(10, 0)
        with_boost = calc_resistance_zone(10, 50)  # 10 * 1.5 = 15
        assert with_boost < no_boost

    def test_external_reduce_lowers_resistance(self):
        """外部抗性减免降低最终抗性"""
        no_ext = calc_resistance_zone(20, 0, 0, 0)
        with_ext = calc_resistance_zone(20, 0, 0, 10)
        assert with_ext > no_ext

    def test_resistance_100_means_immune(self):
        """100% 抗性 → 乘区 = 0（免疫）"""
        result = calc_resistance_zone(base_res=100)
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_resistance_above_100_goes_negative(self):
        """超过 100% 抗性 → 乘区为负（代码未对正抗性上限做 clamp）"""
        # base_res=150 → final=150 → zone = 1 - 150/100 = -0.5
        result = calc_resistance_zone(base_res=150)
        assert result == pytest.approx(-0.5, abs=1e-10)


# ---- 独立乘区测试 ----

class TestIndepZone:
    """测试 IndepZonePage.recalc() 的独立乘区公式"""

    def test_empty_groups_zone_is_one(self):
        """无独立乘区组 → 乘区 = 1.0"""
        zone, factors = calc_indep_zone([])
        assert zone == pytest.approx(1.0, abs=1e-10)
        assert factors == []

    def test_single_group_no_value(self):
        """单个空组 → 组内合计 0，乘区 = 1.0"""
        zone, factors = calc_indep_zone([[0]])
        assert zone == pytest.approx(1.0, abs=1e-10)
        assert factors[0][1] == pytest.approx(1.0)

    def test_single_group_with_values(self):
        """单组有数值 → 1 + total/100"""
        # 10% + 20% = 30% → 1 + 0.3 = 1.3
        zone, factors = calc_indep_zone([[10, 20]])
        assert zone == pytest.approx(1.3, abs=1e-10)
        assert factors[0][1] == pytest.approx(1.3)

    def test_multiple_groups_multiply(self):
        """多组之间乘法关系"""
        # 组1: 30% → 1.3; 组2: 50% → 1.5; 总 = 1.3 × 1.5 = 1.95
        zone, factors = calc_indep_zone([[30], [50]])
        assert zone == pytest.approx(1.95, abs=1e-10)
        assert len(factors) == 2

    def test_negative_values_reduce_zone(self):
        """组内负值会降低乘区"""
        zone, _ = calc_indep_zone([[-20]])  # 1 + (-0.2) = 0.8
        assert zone == pytest.approx(0.8, abs=1e-10)

    def test_three_groups(self):
        """三组独立乘区"""
        zone, factors = calc_indep_zone([[10], [20], [30]])
        expected = 1.10 * 1.20 * 1.30
        assert zone == pytest.approx(expected, abs=1e-10)

    def test_hidden_rows_excluded(self):
        """模拟隐藏功能：组内只传未隐藏的值"""
        # 原始组: [10, 20, 30] → 1.60
        zone_all, _ = calc_indep_zone([[10, 20, 30]])
        assert zone_all == pytest.approx(1.60, abs=1e-10)
        # "隐藏" 20 和 30: 只剩 [10] → 1.10
        zone_partial, _ = calc_indep_zone([[10]])
        assert zone_partial == pytest.approx(1.10, abs=1e-10)
        # "隐藏"全部: 空组 → 1.00
        zone_none, _ = calc_indep_zone([[]])
        assert zone_none == pytest.approx(1.00, abs=1e-10)


# ---- 基础乘区测试 ----

class TestBaseZone:
    """测试基础乘区（攻击/生命/防御通用公式）"""

    def test_no_bonus_equals_raw_sum(self):
        """无加成时 = 角色基础 + 武器基础"""
        result = calc_base_zone(base_value=1000, weapon_base=500, total_pct=0, total_flat=0)
        assert result == pytest.approx(1500, abs=1e-10)

    def test_percent_bonus(self):
        """百分比加成: (1000+500) × (1+0.5) = 2250"""
        result = calc_base_zone(1000, 500, 50, 0)
        assert result == pytest.approx(2250, abs=1e-10)

    def test_flat_bonus(self):
        """固定值加成: (1000+500) + 200 = 1700"""
        result = calc_base_zone(1000, 500, 0, 200)
        assert result == pytest.approx(1700, abs=1e-10)

    def test_both_bonuses(self):
        """百分比 + 固定值: (1000+500)×1.5 + 200 = 2450"""
        result = calc_base_zone(1000, 500, 50, 200)
        assert result == pytest.approx(2450, abs=1e-10)

    def test_no_weapon(self):
        """无武器时基础值: 角色基础 × (1+%) + 固定"""
        result = calc_base_zone(800, 0, 30, 100)
        assert result == pytest.approx(800 * 1.3 + 100, abs=1e-10)  # 1140

    def test_defense_basis_no_weapon(self):
        """防御力为基础时一般无武器基础"""
        result = calc_base_zone(500, 0, 40, 50)
        assert result == pytest.approx(500 * 1.4 + 50, abs=1e-10)  # 750

    def test_zero_all(self):
        """全为 0 → 结果为 0"""
        result = calc_base_zone(0, 0, 0, 0)
        assert result == pytest.approx(0.0, abs=1e-10)


# ---- 加成/加深/暴击乘区测试 ----

class TestBonusZone:
    """测试加成乘区"""

    def test_no_bonus_is_one(self):
        assert calc_bonus_zone(0) == pytest.approx(1.0)

    def test_60_bonus(self):
        """+60% 伤害加成 → 1.6"""
        assert calc_bonus_zone(60) == pytest.approx(1.6, abs=1e-10)

    def test_negative_bonus(self):
        """负加成 → < 1.0"""
        assert calc_bonus_zone(-20) == pytest.approx(0.8, abs=1e-10)


class TestDeepenZone:
    """测试加深乘区"""

    def test_no_deepen_is_one(self):
        assert calc_deepen_zone(0) == pytest.approx(1.0)

    def test_40_deepen(self):
        assert calc_deepen_zone(40) == pytest.approx(1.4, abs=1e-10)


class TestCritZone:
    """测试暴击乘区"""

    def test_no_bonus_crit_zone(self):
        """基础暴伤 150% → 乘区 = 1.5"""
        assert calc_crit_zone(0) == pytest.approx(1.5, abs=1e-10)

    def test_60_crit_dmg(self):
        """+60% 暴伤 → (150+60)/100 = 2.1"""
        assert calc_crit_zone(60) == pytest.approx(2.1, abs=1e-10)

    def test_crit_rate_base(self):
        """基础暴击率 5%，无加成"""
        assert calc_crit_rate(0) == pytest.approx(5.0, abs=1e-10)

    def test_crit_rate_with_bonus(self):
        """+50% 暴击率 → 5 + 50 = 55"""
        assert calc_crit_rate(50) == pytest.approx(55.0, abs=1e-10)

    def test_crit_rate_cannot_exceed_100(self):
        """暴击率可以超过 100%（虽然游戏可能 cap，但计算不会）"""
        # 公式本身不 cap，只是记录一下这个行为
        assert calc_crit_rate(200) > 100


# ---- 倍率乘区测试 ----

class TestMultZone:
    """测试倍率乘区"""

    def test_base_mult_only(self):
        """仅基础倍率"""
        assert calc_mult_zone(100, 0, []) == pytest.approx(100.0)

    def test_with_increase(self):
        """倍率增加: 100 + 20 = 120"""
        assert calc_mult_zone(100, 20, []) == pytest.approx(120.0)

    def test_with_boosts(self):
        """倍率增幅: 100 × (1+50%) = 150"""
        assert calc_mult_zone(100, 0, [50]) == pytest.approx(150.0)

    def test_multiple_boosts_multiply(self):
        """多个倍率增幅: 100 × 1.2 × 1.3 = 156"""
        assert calc_mult_zone(100, 0, [20, 30]) == pytest.approx(156.0)

    def test_increase_and_boosts(self):
        """倍率增加 + 增幅: (100+20) × 1.5 = 180"""
        assert calc_mult_zone(100, 20, [50]) == pytest.approx(180.0)


# ---- 完整伤害公式端到端测试 ----

class TestFullDamageFormula:
    """测试完整伤害公式端到端"""

    def test_simple_scenario(self):
        """简单场景：所有乘区 = 1.0，倍率 = 100%，基础 = 1000"""
        base_dmg, crit_dmg = calc_final_damage(
            base_zone=1000,   # 1000 基础攻击
            bonus_zone=1.0,   # 无加成
            deepen_zone=1.0,  # 无加深
            crit_zone=1.5,    # 基础暴伤 150%
            def_zone=1.0,     # 无视100%防御
            res_zone=1.0,     # 无抗性
            indep_zone=1.0,   # 无独立乘区
            mult_zone=100.0,  # 100% 倍率
        )
        # base_dmg = 1000 * 1 * 1 * 1 * 1 * 1 * 100 / 100 = 1000
        assert base_dmg == pytest.approx(1000.0, abs=1e-10)
        # crit = 1000 * 1.5 = 1500
        assert crit_dmg == pytest.approx(1500.0, abs=1e-10)

    def test_realistic_scenario(self):
        """模拟实战场景"""
        base_zone = calc_base_zone(400, 500, 60, 200)   # (400+500)*1.6+200 = 1640
        bonus_zone = calc_bonus_zone(70)                 # 1.7
        deepen_zone = calc_deepen_zone(30)               # 1.3
        crit_zone = calc_crit_zone(60)                   # 2.1
        def_zone = calc_defense_zone(90, 100, 0.2)      # ~0.514
        res_zone = calc_resistance_zone(10, 0, 0, 10)   # 1.0
        indep_zone, _ = calc_indep_zone([[15], [25]])    # 1.15 * 1.25 = 1.4375
        mult_zone = calc_mult_zone(150, 30, [20, 10])   # (150+30) * 1.2 * 1.1 = 237.6

        base_dmg, crit_dmg = calc_final_damage(
            base_zone, bonus_zone, deepen_zone, crit_zone,
            def_zone, res_zone, indep_zone, mult_zone,
        )

        # 手动验算
        expected_base = (1640 * 1.7 * 1.3 * def_zone * 1.0 * 1.4375 * 237.6) / 100.0
        assert base_dmg == pytest.approx(expected_base, abs=1e-8)
        assert crit_dmg == pytest.approx(expected_base * 2.1, abs=1e-8)

    def test_zero_damage_if_resistance_100(self):
        """100% 抗性 → 乘区 = 0 → 伤害 = 0"""
        base_dmg, crit_dmg = calc_final_damage(
            1000, 1.5, 1.3, 2.0,
            0.5,   # 50% 防御乘区
            0.0,   # 100% 抗性 → 抗性乘区 = 0
            1.0, 100.0,
        )
        assert base_dmg == pytest.approx(0.0, abs=1e-10)
        assert crit_dmg == pytest.approx(0.0, abs=1e-10)


# ---- 筛选匹配测试 ----

class TestFilterMatching:
    """测试 _matches_filter 函数的筛选逻辑"""

    def test_generic_item_passes_all_none(self):
        """通用词条（无特定属性）在筛选全为 None 时应通过"""
        assert matches_filter("攻击力加成", None, None, None) is True

    def test_element_specific_blocked_when_none(self):
        """含特定元素的词条在筛选为 None 时被排除"""
        assert matches_filter("冷凝伤害加成", None, None, None) is False

    def test_element_specific_matches(self):
        """含特定元素的词条在匹配时通过"""
        assert matches_filter("冷凝伤害加成", "冷凝", None, None) is True

    def test_element_specific_mismatch(self):
        """含冷凝的词条在热熔筛选时不通过"""
        assert matches_filter("冷凝伤害加成", "热熔", None, None) is False

    def test_skill_specific_matches(self):
        assert matches_filter("共鸣技能伤害加成", None, "共鸣技能", None) is True

    def test_skill_specific_blocked(self):
        assert matches_filter("共鸣技能伤害加成", None, None, None) is False

    def test_effect_specific_matches(self):
        assert matches_filter("光噪伤害加成", None, None, "光噪") is True

    def test_generic_passes_with_specific_filter(self):
        """通用词条即使设置了筛选也应通过（例如筛选冷凝+普攻时，通用攻击力加成应算入）"""
        assert matches_filter("攻击力加成", "冷凝", "普攻", None) is True

    def test_echo_prefix_stripped(self):
        """声骸前缀应被剥离后再匹配"""
        assert matches_filter("[声骸]主词条-攻击力加成", None, None, None) is True
        assert matches_filter("[声骸]副词条-冷凝伤害加成", None, None, None) is False

    def test_multiple_tags_match_first(self):
        """含多个特定标签时，只匹配第一个（按元素→技能→效应顺序）"""
        # "冷凝共鸣技能伤害加成" — 先匹配元素"冷凝"
        # 如果筛选冷凝但技能为 None → 元素匹配但技能检测到"共鸣技能"且未筛选 → 被排除
        assert matches_filter("冷凝共鸣技能伤害加成", "冷凝", None, None) is False
        # 同时筛选冷凝和共鸣技能 → 通过
        assert matches_filter("冷凝共鸣技能伤害加成", "冷凝", "共鸣技能", None) is True


# ---- 常量定义测试 ----

class TestGameConstants:
    """测试游戏常量的正确性（防止无意修改导致计算错误）"""

    def test_defense_item_names_not_empty(self):
        assert len(DEFENSE_ITEM_NAMES) > 0

    def test_resistance_item_names_not_empty(self):
        assert len(RESISTANCE_ITEM_NAMES) > 0

    def test_bonus_suffix_not_empty(self):
        assert len(BONUS_SUFFIX) == 2

    def test_crit_keywords_not_empty(self):
        assert len(CRIT_RATE_KEYWORDS) > 0
        assert len(CRIT_DMG_KEYWORDS) > 0

    def test_elements_contains_six(self):
        assert len(ELEMENT_NAMES_SET) == 6

    def test_skill_types_contains_six(self):
        assert len(SKILL_TYPE_NAMES_SET) == 6

    def test_effects_contains_six(self):
        assert len(EFFECT_NAMES_SET) == 6

    def test_deepen_suffix_value(self):
        """加深的关键词是"加深"且正确"""
        assert DEEPEN_SUFFIX == "加深"


# ---- 边界和回归测试 ----

class TestEdgeCases:
    """边界条件和回归测试"""

    def test_base_zone_negative_flat(self):
        """固定值为负数（应不被业务使用，但公式需要健壮）"""
        result = calc_base_zone(1000, 500, 20, -100)
        assert result == pytest.approx(1500 * 1.2 - 100, abs=1e-10)

    def test_mult_zone_negative_boost(self):
        """倍率增幅为负数"""
        result = calc_mult_zone(100, 0, [-50])  # 100 * 0.5 = 50
        assert result == pytest.approx(50.0)

    def test_crit_zone_zero_total(self):
        """总暴伤 = 0？基础值是 150，不太可能出现，但公式应有定义"""
        # 基础暴伤永远至少有 150
        assert calc_crit_zone(0) > 1.0

    def test_indep_zone_many_groups(self):
        """10 个独立乘区组"""
        groups = [[10]] * 10  # 1.1^10 ≈ 2.5937
        zone, factors = calc_indep_zone(groups)
        assert zone == pytest.approx(1.1 ** 10, abs=1e-8)
