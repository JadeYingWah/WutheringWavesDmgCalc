# -*- coding: utf-8 -*-
"""
共鸣链同步链路测试
==================
测试共鸣链增益 → 综合填写 → 关键词关联 的数据同步。

需要 PyQt6 环境（创建 QApplication + 真实 widget）。
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QLineEdit

# 确保 QApplication 存在
_app = QApplication.instance() or QApplication(sys.argv)


def _get_kw_names(ms):
    """从关键词关联页的 _table 中提取所有名称"""
    names = []
    for row in range(ms.page_keyword_assoc._table.rowCount()):
        w = ms.page_keyword_assoc._table.cellWidget(row, 0)
        if w and hasattr(w, 'text'):
            names.append(w.text())
    return names


def _get_kw_sub_name(ms, name):
    """从关键词关联页查找指定名称行的副名称"""
    for row in range(ms.page_keyword_assoc._table.rowCount()):
        w = ms.page_keyword_assoc._table.cellWidget(row, 0)
        if w and hasattr(w, 'text') and w.text() == name:
            sub_widget = ms.page_keyword_assoc._table.cellWidget(row, 1)
            if sub_widget is None:
                return ""
            if isinstance(sub_widget, QLineEdit):
                return sub_widget.text()
            le = sub_widget.findChild(QLineEdit)
            return le.text() if le else ""
    return None


def _get_kw_seq(ms, name):
    """从关键词关联页查找指定名称行的序列号"""
    for row in range(ms.page_keyword_assoc._table.rowCount()):
        w = ms.page_keyword_assoc._table.cellWidget(row, 0)
        if w and hasattr(w, 'text') and w.text() == name:
            seq = ms.page_keyword_assoc._table.cellWidget(row, 2)
            return seq.text() if seq and hasattr(seq, 'text') else ""
    return None


@pytest.fixture(scope="module")
def main_window():
    """创建主窗口实例（module 级别复用）"""
    from WWDmgCalc import DmgCalculator
    win = DmgCalculator()
    yield win
    win.close()


@pytest.fixture
def chain_item():
    """返回一个空白共鸣链 item 模板"""
    return {
        "id": 1,
        "name": "测试角色的共鸣链1",
        "enabled": False,
        "effects": [],
    }


@pytest.fixture(autouse=True)
def cleanup_rows(main_window, chain_item):
    """每个测试后清理同步产生的行"""
    yield
    ms = main_window.main_screen
    chain_num = chain_item["id"]
    ms.page_combined_perm.remove_effects_by_source_and_names("共鸣链效果", set(), chain_num=chain_num)
    ms.page_combined_trigger.remove_effects_by_source_and_names("共鸣链效果", set(), chain_num=chain_num)
    ms.page_keyword_assoc.remove_effects_by_chain(chain_num)


# ==================== 基础同步 ====================

class TestSyncBasics:
    """共鸣链基础同步到综合填写和关键词关联"""

    def test_save_effect_appears_in_combined_perm(self, main_window, chain_item):
        """常驻效果保存后出现在综合常驻数值页"""
        ms = main_window.main_screen
        chain_item["effects"] = [
            {"name": "攻击力加成", "value": 12.0, "type": "常驻", "source": "共鸣链效果", "sub_name": ""}
        ]
        chain_item["enabled"] = True
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        names = [rd['name_edit'].text() for rd in ms.page_combined_perm._rows]
        assert "攻击力加成" in names

    def test_save_effect_appears_in_combined_trigger(self, main_window, chain_item):
        """触发效果保存后出现在综合触发数值页"""
        ms = main_window.main_screen
        chain_item["effects"] = [
            {"name": "冷凝伤害加成", "value": 15.0, "type": "触发", "source": "共鸣链效果", "sub_name": ""}
        ]
        chain_item["enabled"] = True
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        names = [rd['name_edit'].text() for rd in ms.page_combined_trigger._rows]
        assert "冷凝伤害加成" in names

    def test_save_effect_appears_in_keyword_assoc(self, main_window, chain_item):
        """效果保存后出现在关键词关联页"""
        ms = main_window.main_screen
        chain_item["effects"] = [
            {"name": "攻击力加成", "value": 12.0, "type": "常驻", "source": "共鸣链效果", "sub_name": "测试备注"}
        ]
        chain_item["enabled"] = True
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        assert "攻击力加成" in _get_kw_names(ms)

    def test_disabled_chain_not_synced(self, main_window, chain_item):
        """关闭状态的共鸣链不会同步效果"""
        ms = main_window.main_screen
        chain_item["effects"] = [
            {"name": "不应出现", "value": 99.0, "type": "常驻", "source": "共鸣链效果", "sub_name": ""}
        ]
        chain_item["enabled"] = False
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        names = [rd['name_edit'].text() for rd in ms.page_combined_perm._rows]
        assert "不应出现" not in names


# ==================== 副名称同步 ====================

class TestSubNameSync:
    """副名称在同步过程中不丢失"""

    def test_sub_name_synced_to_combined(self, main_window, chain_item):
        """副名称同步到综合填写页"""
        ms = main_window.main_screen
        chain_item["effects"] = [
            {"name": "攻击力加成", "value": 12.0, "type": "常驻", "source": "共鸣链效果", "sub_name": "守岸人延奏"}
        ]
        chain_item["enabled"] = True
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        for rd in ms.page_combined_perm._rows:
            if rd['name_edit'].text() == "攻击力加成":
                assert rd['sub_name_edit'].text() == "守岸人延奏"
                return
        pytest.fail("未找到攻击力加成行")

    def test_sub_name_synced_to_keyword_assoc(self, main_window, chain_item):
        """副名称同步到关键词关联页"""
        ms = main_window.main_screen
        chain_item["effects"] = [
            {"name": "攻击力加成", "value": 12.0, "type": "常驻", "source": "共鸣链效果", "sub_name": "测试备注"}
        ]
        chain_item["enabled"] = True
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        sub = _get_kw_sub_name(ms, "攻击力加成")
        assert sub is not None
        assert sub == "测试备注"


# ==================== 增量同步 ====================

class TestIncrementalSync:
    """增删效果后重新同步"""

    def test_remove_effect_synced(self, main_window, chain_item):
        """删除效果后综合填写页同步移除"""
        ms = main_window.main_screen
        chain_item["effects"] = [
            {"name": "攻击力加成", "value": 12.0, "type": "常驻", "source": "共鸣链效果", "sub_name": ""},
            {"name": "防御力加成", "value": 8.0, "type": "常驻", "source": "共鸣链效果", "sub_name": ""},
        ]
        chain_item["enabled"] = True
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        # 移除一个效果后重新同步
        chain_item["effects"] = [
            {"name": "攻击力加成", "value": 12.0, "type": "常驻", "source": "共鸣链效果", "sub_name": ""},
        ]
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        names = [rd['name_edit'].text() for rd in ms.page_combined_perm._rows]
        assert "攻击力加成" in names
        assert "防御力加成" not in names

    def test_value_change_synced(self, main_window, chain_item):
        """修改数值后同步更新"""
        ms = main_window.main_screen
        chain_item["effects"] = [
            {"name": "攻击力加成", "value": 12.0, "type": "常驻", "source": "共鸣链效果", "sub_name": ""}
        ]
        chain_item["enabled"] = True
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        chain_item["effects"] = [
            {"name": "攻击力加成", "value": 25.0, "type": "常驻", "source": "共鸣链效果", "sub_name": ""}
        ]
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        for rd in ms.page_combined_perm._rows:
            if rd['name_edit'].text() == "攻击力加成":
                assert rd['value_spin'].value() == 25.0
                return
        pytest.fail("未找到攻击力加成行")


# ==================== 序列号格式 ====================

class TestSequenceFormat:
    """关键词关联页的序列号格式"""

    def test_chain_effect_seq_format(self, main_window, chain_item):
        """共鸣链效果序列号格式为「共鸣链X关联Y」"""
        ms = main_window.main_screen
        chain_item["effects"] = [
            {"name": "攻击力加成", "value": 12.0, "type": "常驻", "source": "共鸣链效果", "sub_name": ""}
        ]
        chain_item["enabled"] = True
        ms.page_resonance_buff._sync_chain_to_pages(chain_item)

        seq = _get_kw_seq(ms, "攻击力加成")
        assert seq is not None
        assert seq.startswith("共鸣链1关联")
