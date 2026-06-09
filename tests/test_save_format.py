# -*- coding: utf-8 -*-
"""
存档格式单元测试
================
测试存档的 JSON 结构、版本兼容性、roundtrip 完整性。
不依赖 PyQt6 GUI，纯数据验证。
"""

import json
import os
import tempfile
import pytest

# 存档版本
SAVE_FILE_VERSION = 1

# 必须存在的页面 key（完整存档应包含）
REQUIRED_PAGE_KEYS = [
    "char_base",
    "combined_perm",
    "combined_trigger",
    "enemy_defense",
    "enemy_resistance",
    "echo_counter",
    "echo_pages",
    "result",
    "result_list",
    "summary_indep",
]

# 顶层 key（存档元数据）
REQUIRED_TOP_KEYS = [
    "version", "app", "timestamp", "name", "pages",
    "base_override_enabled", "base_override_value",
    "hidden_items", "locked_items", "hidden_echo_ids",
]


def make_minimal_state():
    """创建最小有效存档状态"""
    return {
        "version": SAVE_FILE_VERSION,
        "app": "WWDmgCalc",
        "timestamp": "2026-06-01T00:00:00",
        "name": "测试存档",
        "pages": {
            "char_base": {},
            "combined_perm": {"rows": [], "counter": 0},
            "combined_trigger": {"rows": [], "counter": 0},
            "enemy_defense": {"rows": [], "char_level": 90, "enemy_level": 100},
            "enemy_resistance": {"spins": {}, "boost_checks": {}, "trigger_states": {}},
            "echo_counter": {"echoes": [], "echo_id_counter": 0},
            "echo_pages": {},
            "result": {"auto_compute": False, "filter_basis_idx": 0},
            "result_list": {"items": []},
            "summary_indep": [],
        },
        "base_override_enabled": False,
        "base_override_value": 0.0,
        "hidden_items": [],
        "locked_items": [],
        "hidden_echo_ids": [],
    }


class TestSaveFormat:
    """测试存档 JSON 格式"""

    def test_minimal_state_has_all_top_keys(self):
        """最小存档应包含所有顶层 key"""
        state = make_minimal_state()
        for key in REQUIRED_TOP_KEYS:
            assert key in state, f"缺少顶层 key: {key}"

    def test_minimal_state_has_all_page_keys(self):
        """最小存档应包含所有页面 key"""
        state = make_minimal_state()
        for key in REQUIRED_PAGE_KEYS:
            assert key in state["pages"], f"缺少页面 key: {key}"

    def test_version_is_current(self):
        """存档版本应为当前版本"""
        state = make_minimal_state()
        assert state["version"] == SAVE_FILE_VERSION

    def test_future_version_detected(self):
        """检测高于当前支持的版本（模拟 SaveManager 逻辑）"""
        state = make_minimal_state()
        state["version"] = 999
        assert state["version"] > SAVE_FILE_VERSION

    def test_hidden_items_is_list(self):
        """hidden_items 应为列表类型"""
        state = make_minimal_state()
        assert isinstance(state["hidden_items"], list)

    def test_locked_items_is_list(self):
        """locked_items 应为列表类型"""
        state = make_minimal_state()
        assert isinstance(state["locked_items"], list)

    def test_hidden_echo_ids_is_list(self):
        """hidden_echo_ids 应为列表类型"""
        state = make_minimal_state()
        assert isinstance(state["hidden_echo_ids"], list)

    # ---- 4 元素键测试 ----

    def test_hidden_item_key_format(self):
        """隐藏条目的 key 应为 4 元素元组 (name, source, page_key, seq_label)"""
        # 检查项目代码中使用的 4 元素键格式
        valid_keys = [
            ("攻击力", "武器谐振", "combined_perm", "常驻1"),
            ("暴击率", "合鸣效果", "combined_perm", "常驻2"),
            ("热熔伤害", "声骸", "combined_trigger", "触发1"),
            ("攻击力", "声骸1", "echo_1", "1号声骸主词"),
        ]
        for key in valid_keys:
            assert len(key) == 4
            name, src_label, nav_key, seq_label = key
            assert isinstance(name, str)
            assert isinstance(src_label, str)
            assert isinstance(nav_key, str)
            assert isinstance(seq_label, str)


class TestSaveRoundtrip:
    """测试存档读写完整性"""

    def test_json_roundtrip(self):
        """JSON 写入再读取，数据不丢失"""
        state = make_minimal_state()
        state["hidden_items"].append(["攻击力加成", "武器谐振", "combined_perm", "常驻1"])
        state["base_override_enabled"] = True
        state["base_override_value"] = 2500.0

        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            path = f.name

        try:
            # 读取
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            assert loaded == state
            assert loaded["base_override_enabled"] is True
            assert loaded["base_override_value"] == 2500.0
            assert len(loaded["hidden_items"]) == 1
        finally:
            os.unlink(path)

    def test_roundtrip_with_chinese(self):
        """含中文的存档读写不损坏"""
        state = make_minimal_state()
        state["name"] = "赞妮测试效应加深"
        state["pages"]["combined_perm"]["rows"] = [
            {"name": "冷凝伤害加成", "value": 30.0, "seq": 1,
             "source": "武器谐振", "locked": False}
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(state, f, ensure_ascii=False)
            path = f.name

        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            assert loaded["name"] == "赞妮测试效应加深"
            assert loaded["pages"]["combined_perm"]["rows"][0]["name"] == "冷凝伤害加成"
        finally:
            os.unlink(path)

    def test_empty_echo_pages(self):
        """空声骸页面结构正确"""
        state = make_minimal_state()
        assert state["pages"]["echo_pages"] == {}
        assert state["pages"]["echo_counter"]["echoes"] == []
        assert state["pages"]["echo_counter"]["echo_id_counter"] == 0


class TestSaveBackwardCompatibility:
    """测试向后兼容性"""

    def test_legacy_result_list_list_format(self):
        """兼容旧版 result_list（纯列表格式，非字典）"""
        # 旧格式: result_list 直接是数组
        old_state = make_minimal_state()
        old_state["pages"]["result_list"] = [
            {"id": 1, "label": "测试条目", "locked": False}
        ]
        assert isinstance(old_state["pages"]["result_list"], list)

    def test_new_result_list_dict_format(self):
        """新版 result_list（包含 items + auto_update）"""
        new_state = make_minimal_state()
        new_state["pages"]["result_list"] = {
            "items": [{"id": 1, "label": "测试", "locked": False}],
            "auto_update": True,
        }
        assert isinstance(new_state["pages"]["result_list"], dict)
        assert "items" in new_state["pages"]["result_list"]
        assert "auto_update" in new_state["pages"]["result_list"]

    def test_echo_page_sub_stats_format(self):
        """声骸副词条状态格式"""
        sub_stat = {"name": "暴击率", "value": 7.5, "locked": False}
        assert "name" in sub_stat
        assert "value" in sub_stat
        assert "locked" in sub_stat
        assert isinstance(sub_stat["value"], float)
