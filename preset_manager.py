# -*- coding: utf-8 -*-
# 预设管理器 —— 预设核心逻辑（list/load/validate/apply/export/update_official）
#
# 预设 JSON 结构:
# {
#   "version": 1, "type": "preset", "name": "...", "author": "...",
#   "character": { "name", "element", "effect", "base_hp", "base_atk", "base_def",
#                  "multiplier": { "base_mult", "mult_increase", "mult_boosts": [...] },
#                  "resonance_chain": [ { "effects": [...], "indep_zones": [...] }, ... ] },
#   "weapon": { "name", "base_atk", "bonus_type", "bonus_value",
#               "refinement": [ { "resonance_desc", "effects": [...], "indep_zones": [...] }, ... ] },
#   "echo_set": { "name", "stages": [ { "required_count", "effects": [...] }, ... ],
#                  "first_echo_bonus": { "effects": [...], "indep_zones": [...] } }
# }

__all__ = ["PresetManager", "PRESETS_DIR"]

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QProgressDialog
from PyQt6.QtCore import Qt, QTimer

# ── 项目根目录定位 ──
if getattr(sys, 'frozen', False):
    # 打包后: WWDmgCalc.exe 在 WWDmgCalc/ 子目录，presets/ 在上级
    _APP_DIR = os.path.dirname(os.path.dirname(sys.executable))
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

PRESETS_DIR = os.path.join(_APP_DIR, "presets")
OFFICIAL_DIR = os.path.join(PRESETS_DIR, "official")
USER_DIR = os.path.join(PRESETS_DIR, "user")

# 四个类别子目录
CATEGORY_DIRS = ["character", "weapon", "echo_set", "character_buff"]

# 类别中文名（用于列表显示）
CATEGORY_LABELS = {
    "character": "角色", "weapon": "武器",
    "echo_set": "套装", "character_buff": "增益"}

# GitHub 仓库配置（项目上传后可修改）
GITHUB_REPO_OWNER = "JadeYingWah"
GITHUB_REPO_NAME = "WutheringWavesDmgCalc"
# 下载源列表（自动按顺序重试）
GITHUB_RAW_URLS = [
    f"https://raw.githubusercontent.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/main/presets/official",
    f"https://raw.gitmirror.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/main/presets/official",
    f"https://cdn.jsdelivr.net/gh/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}@main/presets/official",
]


class PresetManager:
    """预设管理器：列出、加载、验证、应用、导出、更新官方预设"""

    # ═══════════════════════════════════════════════════════════════
    # 目录与文件操作
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def ensure_dirs():
        """确保预设目录结构存在（含三个类别子目录）"""
        for base in (OFFICIAL_DIR, USER_DIR):
            for cat in CATEGORY_DIRS:
                os.makedirs(os.path.join(base, cat), exist_ok=True)

    @staticmethod
    def list_presets():
        """列出 official 和 user 目录下三个类别子目录中的所有预设。

        Returns:
            list[dict]: [{"name", "path", "source", "category", "mtime"}, ...]
        """
        PresetManager.ensure_dirs()
        result = []

        for source, base_dir in [("official", OFFICIAL_DIR), ("user", USER_DIR)]:
            for cat in CATEGORY_DIRS:
                cat_dir = os.path.join(base_dir, cat)
                if not os.path.isdir(cat_dir):
                    continue
                for fname in sorted(os.listdir(cat_dir)):
                    if not fname.endswith(".json"):
                        continue
                    fpath = os.path.join(cat_dir, fname)
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                        # 优先读取 JSON 内存储的 name（可含 / 等文件名非法字符）
                        name = os.path.splitext(fname)[0]
                        try:
                            with open(fpath, "r", encoding="utf-8") as _f:
                                _d = json.loads(_f.read())
                                if _d.get("name"):
                                    name = _d["name"]
                            author = _d.get("author", "")
                        except Exception:
                            author = ""
                        result.append({
                            "name": name,
                            "path": fpath,
                            "source": source,
                            "category": cat,
                            "mtime": mtime.strftime("%Y-%m-%d %H:%M"),
                            "author": author,
                        })
                    except OSError:
                        continue

        # 官方在前，用户在后；同来源按类别再按名称
        result.sort(key=lambda x: (0 if x["source"] == "official" else 1,
                                     CATEGORY_DIRS.index(x.get("category", "")),
                                     x["name"]))
        return result

    # ═══════════════════════════════════════════════════════════════
    # 加载与验证
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def load_preset(path):
        """读取 JSON 预设文件并验证格式。

        Returns:
            (data: dict | None, error: str | None)
        """
        if not os.path.exists(path):
            return None, f"文件不存在: {path}"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return None, f"JSON 格式错误: {e}"
        except Exception as e:
            return None, f"读取文件失败: {e}"

        # ── 兼容旧版本预设：内部名称为空时自动补齐 ──
        PresetManager._migrate_empty_names(data)

        valid, err = PresetManager.validate_preset(data)
        if not valid:
            return None, err
        return data, None

    @staticmethod
    def _migrate_empty_names(data):
        """兼容旧版本预设：如果内部名称（character/weapon/echo_set.name）
        为空，则从顶层 preset.name 自动填充。"""
        preset_name = data.get("name", "")
        for cat_key, fallback in [("character", "角色"), ("weapon", "武器"), ("echo_set", "套装"), ("character_buff", "增益")]:
            cat_data = data.get(cat_key)
            if isinstance(cat_data, dict) and not cat_data.get("name", ""):
                # 从预设名称提取基础名："绯雪-预设" → "绯雪"
                if preset_name and preset_name.endswith("-预设"):
                    base = preset_name[:-3]
                elif preset_name:
                    base = preset_name
                else:
                    base = f"未命名{fallback}"
                cat_data["name"] = base

    @staticmethod
    def validate_preset(data):
        """验证预设 JSON 结构。

        Returns:
            (valid: bool, error: str | None)
        """
        if not isinstance(data, dict):
            return False, "预设根结构无效（不是 JSON 对象）"
        if data.get("type") != "preset":
            return False, "不是有效的预设文件（缺少 type=preset）"
        version = data.get("version", 0)
        if version > 1:
            return False, f"预设版本 {version} 高于当前支持版本 1"

        # 至少需要一个模块
        has_char = "character" in data and data["character"]
        has_weapon = "weapon" in data and data["weapon"]
        has_echo = "echo_set" in data and data["echo_set"]
        has_buff = "character_buff" in data and data["character_buff"]
        if not (has_char or has_weapon or has_echo or has_buff):
            return False, "预设至少需要包含角色、武器、声骸套装或角色增益之一"

        # 验证角色（可选）
        if has_char:
            c = data["character"]
            if not isinstance(c, dict):
                return False, "character 必须是对象"
            if "name" not in c or not c["name"]:
                return False, "角色必须填写名称"
            if "multiplier" in c and not isinstance(c["multiplier"], dict):
                return False, "character.multiplier 必须是对象"

        # 验证武器（可选）
        if has_weapon:
            w = data["weapon"]
            if not isinstance(w, dict):
                return False, "weapon 必须是对象"
            if "name" not in w or not w["name"]:
                return False, "武器必须填写名称"

        # 验证声骸套装（可选）
        if has_echo:
            e = data["echo_set"]
            if not isinstance(e, dict):
                return False, "echo_set 必须是对象"
            if "name" not in e or not e["name"]:
                return False, "声骸套装必须填写名称"

        # 验证角色增益（可选）
        if has_buff:
            b = data["character_buff"]
            if not isinstance(b, dict):
                return False, "character_buff 必须是对象"
            if "name" not in b or not b["name"]:
                return False, "角色增益必须填写名称"

        return True, None

    @staticmethod
    def save_preset(data, name, source="user", overwrite=False):
        """保存预设到指定目录。

        Args:
            data: 预设数据字典（含 category 字段决定存入哪个子目录）
            name: 预设名称（将用作文件名）
            source: "user" 或 "official"
            overwrite: True 时直接覆盖同名文件（编辑已有预设时使用）
        Returns:
            (path: str | None, error: str | None)
        """
        PresetManager.ensure_dirs()
        base_dir = OFFICIAL_DIR if source == "official" else USER_DIR

        # 根据类别选择子目录
        category = data.get("category", "character")
        if category not in CATEGORY_DIRS:
            category = "character"
        target_dir = os.path.join(base_dir, category)

        # 检查文件名非法字符
        _INVALID_CHARS = r'\/:*?"<>|'
        _bad = [c for c in name if c in _INVALID_CHARS]
        if _bad:
            return None, f"预设名称不能包含以下字符：{' '.join(sorted(set(_bad)))}"
        safe_name = name.strip()
        if not safe_name:
            return None, "预设名称不能为空"

        fpath = os.path.join(target_dir, f"{safe_name}.json")

        # 同名检测：新建时自动追加 .副本，编辑时直接覆盖
        if not overwrite and os.path.exists(fpath):
            while os.path.exists(fpath):
                safe_name = f"{safe_name}.副本"
                fpath = os.path.join(target_dir, f"{safe_name}.json")
            data["name"] = safe_name
        try:
            os.makedirs(target_dir, exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return None, f"保存失败: {e}"
        return fpath, None

    # ═══════════════════════════════════════════════════════════════
    # 应用预设到计算器
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def apply_preset(data, main_screen):
        """将预设数据应用到计算器各页面。

        Args:
            data: 已验证的预设数据字典
            main_screen: MainScreen 实例
        """
        # ── 导入必要引用（延迟导入避免循环依赖） ──
        from WWDmgCalc import HIDDEN_ITEMS, _APP_DIR as _a

        # ── 0. 清除旧的独立乘区组（避免重复叠加） ──
        main_screen.page_indep_zone.remove_all_groups()

        # ── 1. 应用角色基础属性 ──
        char_data = data.get("character", {})
        if char_data:
            cb = main_screen.page_char_base
            cb.hp_spin.setValue(char_data.get("base_hp", 1))
            cb.atk_spin.setValue(char_data.get("base_atk", 1))
            cb.def_spin.setValue(char_data.get("base_def", 1))

            # 应用倍率设置
            multiplier = char_data.get("multiplier", {})
            if multiplier:
                rp = main_screen.page_result
                rp.base_mult.setValue(multiplier.get("base_mult", 100.0))
                rp.mult_increase.setValue(multiplier.get("mult_increase", 0.0))
                for _i, _v in enumerate(multiplier.get("mult_boosts", [0, 0, 0])):
                    if _i < len(rp.mult_boosts):
                        rp.mult_boosts[_i].setValue(_v)

            # 应用共鸣链效果 —— 先填充共鸣链页面，再由页面同步到综合填写/关键词关联
            chains = char_data.get("resonance_chain", [])
            rb = main_screen.page_resonance_buff
            char_name = char_data.get("name", "")
            if char_name:
                rb._prefix = char_name
            # 重置全部6链为关闭状态
            for it in rb._items:
                it["enabled"] = False
                it["effects"] = []
                it["indep_zones"] = []
                it["intro"] = ""
                it["name"] = f"{rb._prefix}的共鸣链{it['id']}" if rb._prefix else f"共鸣链{it['id']}"
            # 用预设数据填充存在的链
            for chain_idx, chain in enumerate(chains):
                if chain_idx >= len(rb._items):
                    break
                item = rb._items[chain_idx]
                item["enabled"] = True
                item["effects"] = chain.get("effects", [])
                item["indep_zones"] = chain.get("indep_zones", [])
                item["intro"] = chain.get("intro", "")
                if rb._prefix:
                    item["name"] = f"{rb._prefix}的共鸣链{chain_idx + 1}"
            rb._refresh_cards()
            # 同步效果到综合填写 + 关键词关联
            for it in rb._items:
                if it.get("enabled") and it.get("effects"):
                    rb._sync_chain_to_pages(it)
            # 同步独立乘区
            for it in rb._items:
                if it.get("enabled"):
                    for iz_data in it.get("indep_zones", []):
                        group_name = iz_data.get("group_name", "")
                        values = iz_data.get("values", [])
                        if not values:
                            continue
                        converted = [(v.get("name", ""), v.get("value", 0.0), v.get("hidden", False))
                                     for v in values]
                        main_screen.page_indep_zone._add_group(group_name, converted)

            # 应用结果列表（预设中保存的计算结果卡片）
            result_list = char_data.get("result_list", [])
            if result_list:
                main_screen.page_result_list.apply_data(result_list)

            # 应用技能增益
            skill_buff = char_data.get("skill_buff", {})
            if skill_buff:
                _apply_effects_and_indep(
                    main_screen,
                    skill_buff.get("effects", []),
                    skill_buff.get("indep_zones", []),
                    tag_prefix=f"{char_data.get('name', '')} 技能增益"
                )

        # ── 2. 应用武器 ──
        weapon_data = data.get("weapon", {})
        if weapon_data:
            cb = main_screen.page_char_base
            cb.weapon_base_atk.setValue(weapon_data.get("base_atk", 0))

            # 武器附加属性
            bonus_type = weapon_data.get("bonus_type", "")
            bonus_value = weapon_data.get("bonus_value", 0.0)
            if bonus_type:
                for cbox, spin, ul in cb.checkbox_group:
                    if cbox.text() == bonus_type:
                        cbox.setChecked(True)
                        spin.setValue(bonus_value)
                        break

            # 应用精炼效果
            refinements = weapon_data.get("refinement", [])
            for ref_idx, ref in enumerate(refinements):
                _apply_effects_and_indep(
                    main_screen,
                    ref.get("effects", []),
                    ref.get("indep_zones", []),
                    tag_prefix=f"{weapon_data.get('name', '')} {ref_idx + 1}阶"
                )

        # ── 3. 应用声骸套装 ──
        echo_data = data.get("echo_set", {})
        if echo_data:
            stages = echo_data.get("stages", [])
            for stage in stages:
                req_count = stage.get("required_count", 1)
                effects = stage.get("effects", [])
                _apply_effects_and_indep(
                    main_screen,
                    effects,
                    [],
                    tag_prefix=f"{echo_data.get('name', '')} {req_count}件套"
                )

            # 首位声骸增益
            first_bonus = echo_data.get("first_echo_bonus", {})
            if first_bonus:
                _apply_effects_and_indep(
                    main_screen,
                    first_bonus.get("effects", []),
                    first_bonus.get("indep_zones", []),
                    tag_prefix=f"{echo_data.get('name', '')} 首位声骸"
                )

        # ── 4. 应用角色增益 ──
        buff_data = data.get("character_buff", {})
        if buff_data:
            _apply_effects_and_indep(
                main_screen,
                buff_data.get("effects", []),
                buff_data.get("indep_zones", []),
                tag_prefix=f"{buff_data.get('name', '')} 增益"
            )

        # ── 5. 触发全局重算 ──
        # 模拟一次完整的数据变更回调
        if hasattr(main_screen.page_combined_perm, '_on_change_cb') and \
           main_screen.page_combined_perm._on_change_cb:
            QTimer.singleShot(50, main_screen.page_combined_perm._on_change_cb)

    # ═══════════════════════════════════════════════════════════════
    # 导出与 GitHub 更新
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def export_temp_preset(preset_path):
        """将预设文件导出到系统临时目录并返回路径。"""
        if not os.path.exists(preset_path):
            return None
        tmp_dir = tempfile.gettempdir()
        fname = os.path.basename(preset_path)
        dest = os.path.join(tmp_dir, fname)
        try:
            shutil.copy2(preset_path, dest)
        except Exception:
            return None
        return dest

    @staticmethod
    def update_official_presets(parent_widget=None):
        """从 GitHub 拉取最新官方预设。

        如果 GitHub 仓库未配置或网络不可用，提示用户。

        Args:
            parent_widget: 父窗口（用于 QProgressDialog / QMessageBox）
        Returns:
            (success: bool, message: str)
        """
        # 检查是否配置了有效的 GitHub 仓库
        if not GITHUB_REPO_OWNER or GITHUB_REPO_OWNER == "YOUR_USERNAME":
            QMessageBox.information(
                parent_widget,
                "暂无官方预设源",
                "项目尚未完善此功能，暂无官方预设可更新。\n\n"
                "官方预设功能将在后续开发中启用。\n"
                "届时可通过此按钮一键从 GitHub 拉取最新预设配置。"
            )
            return False, "GitHub 仓库未配置"

        # 尝试从 GitHub 拉取
        progress = None
        if parent_widget:
            progress = QProgressDialog("正在连接 GitHub...", None, 0, 0, parent_widget)
            progress.setWindowTitle("更新官方预设")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            # 窗口尺寸：增大 2.5 倍，给文字留够空间
            progress.resize(550, 550)
            progress.setMinimumSize(500, 500)
            # 标题文字自动换行，避免撑宽窗口
            label = progress.findChild(QLabel)
            if label:
                label.setWordWrap(True)
            progress.show()

        try:
            import urllib.request
            import urllib.error
            from urllib.parse import quote

            # ── 阶段1：拉取 manifest.json ──
            if progress:
                progress.setLabelText("正在连接预设源...")
                QApplication.processEvents()

            manifest = None
            working_url = None
            last_error = None
            for base_url in GITHUB_RAW_URLS:
                manifest_url = f"{base_url}/manifest.json?_=" + str(int(__import__("time").time()))
                try:
                    req = urllib.request.Request(manifest_url)
                    req.add_header("User-Agent", "WutheringWavesDmgCalc-PresetUpdater/1.0")
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        manifest = json.loads(resp.read().decode("utf-8"))
                    working_url = base_url
                    break
                except urllib.error.HTTPError as e:
                    last_error = e
                    if e.code == 404:
                        break
                    continue
                except Exception as e:
                    last_error = e
                    continue

            if manifest is None:
                if progress:
                    progress.close()
                if isinstance(last_error, urllib.error.HTTPError) and last_error.code == 404:
                    QMessageBox.information(parent_widget, "暂无官方预设",
                        "GitHub 仓库中尚未上传官方预设文件。")
                else:
                    QMessageBox.warning(parent_widget, "网络错误",
                        "无法连接到 GitHub 预设源。\n\n请检查网络连接后重试。")
                return False, "manifest 下载失败"

            if not isinstance(manifest, dict):
                if progress:
                    progress.close()
                QMessageBox.warning(parent_widget, "格式错误", "manifest 格式异常")
                return False, "格式错误"

            # ── 阶段2：统计 + 下载 ──
            # 计算总文件数，切换为有进度的进度条
            PresetManager.ensure_dirs()
            total_files = sum(len(v) for v in manifest.values() if isinstance(v, list))
            downloaded = 0
            failed = 0
            failed_details = []

            if progress and total_files > 0:
                progress.setLabelText(f"准备下载 {total_files} 个预设文件...")
                progress.setMaximum(total_files)
                progress.setValue(0)
                progress.setCancelButtonText("取消")
                QApplication.processEvents()

            for cat in CATEGORY_DIRS:
                file_list = manifest.get(cat, [])
                if not isinstance(file_list, list):
                    continue
                target_dir = os.path.join(OFFICIAL_DIR, cat)
                for fname in file_list:
                    if progress and progress.wasCanceled():
                        break
                    _short = fname[:28] + "..." if len(fname) > 28 else fname
                    if progress:
                        progress.setLabelText(f"[{downloaded + failed + 1}/{total_files}] {cat}/{_short}")
                        QApplication.processEvents()
                    raw_url = f"{working_url}/{cat}/{quote(fname)}"
                    try:
                        req2 = urllib.request.Request(raw_url)
                        req2.add_header("User-Agent", "WutheringWavesDmgCalc-PresetUpdater/1.0")
                        with urllib.request.urlopen(req2, timeout=15) as resp:
                            content = resp.read().decode("utf-8")
                        data = json.loads(content)
                        valid, err_msg = PresetManager.validate_preset(data)
                        if not valid:
                            failed += 1
                            failed_details.append((cat, fname, f"校验失败: {err_msg}"))
                            if progress:
                                progress.setValue(downloaded + failed)
                            continue
                        os.makedirs(target_dir, exist_ok=True)
                        dest = os.path.join(target_dir, fname)
                        with open(dest, "w", encoding="utf-8") as f:
                            f.write(content)
                        downloaded += 1
                    except urllib.error.HTTPError as e:
                        failed += 1
                        failed_details.append((cat, fname, f"HTTP {e.code}"))
                    except urllib.error.URLError as e:
                        failed += 1
                        failed_details.append((cat, fname, f"网络错误"))
                    except Exception as e:
                        failed += 1
                        failed_details.append((cat, fname, str(e)[:80]))
                    if progress:
                        progress.setValue(downloaded + failed)

            if progress:
                progress.setLabelText("同步完成！" if downloaded > 0 else "同步失败")
                progress.setValue(total_files)
                QApplication.processEvents()
                progress.close()

            # 2.5 清理本地旧文件：删除不在 manifest 中的官方预设（防止改名/删除残留）
            try:
                for cat in CATEGORY_DIRS:
                    cat_dir = os.path.join(OFFICIAL_DIR, cat)
                    if not os.path.isdir(cat_dir):
                        continue
                    valid_names = set(manifest.get(cat, []))
                    for fname in os.listdir(cat_dir):
                        if not fname.endswith(".json"):
                            continue
                        if fname == "manifest.json":
                            continue
                        if fname not in valid_names:
                            try:
                                os.remove(os.path.join(cat_dir, fname))
                            except OSError:
                                pass
            except Exception:
                pass

            # 3. 写入错误日志（供侧边栏"错误日志"查看）
            if failed_details:
                try:
                    from error_handler.error_system import _add_log_entry
                    detail_lines = [f"预设同步: {downloaded} 成功, {failed} 失败"]
                    for cat, fname, reason in failed_details:
                        detail_lines.append(f"  [{cat}] {fname}: {reason}")
                    _add_log_entry("WARNING", f"预设同步部分失败 ({failed}/{downloaded+failed})",
                                   "\n".join(detail_lines))
                except Exception:
                    pass

            if downloaded > 0:
                msg = f"成功下载 {downloaded} 个官方预设。"
                if failed:
                    msg += f"\n{failed} 个下载失败（可点击侧边栏「错误日志」查看详情）。"
                QMessageBox.information(parent_widget, "更新完成", msg)
                PresetManager.rebuild_contributors_md()
                return True, f"成功 {downloaded} 个"
            else:
                # 全部失败 → 详细信息写入日志并弹窗
                QMessageBox.warning(parent_widget, "更新失败",
                    "所有预设文件下载失败，请检查网络后重试。\n\n"
                    "可点击侧边栏「错误日志」查看失败详情。")
                return False, "下载全部失败"

        except ImportError:
            if progress:
                progress.close()
            QMessageBox.warning(parent_widget, "缺少依赖", "需要 urllib 模块支持网络请求。")
            return False, "缺少 urllib"
        except Exception as e:
            if progress:
                progress.close()
            QMessageBox.warning(parent_widget, "更新失败", f"发生未知错误:\n{e}")
            return False, str(e)

    # ═══════════════════════════════════════════════════════════════
    # 提交为官方预设（Fork & PR 引导）
    # ═══════════════════════════════════════════════════════════════


    @staticmethod
    @staticmethod
    def rebuild_contributors_md():
        """重建 CONTRIBUTORS.md，合并已有记录 + 预设 JSON author"""
        import datetime
        newline = chr(10)
        contrib_path = os.path.join(_APP_DIR, 'CONTRIBUTORS.md')

        # 读取已有记录（不覆盖已有贡献者）
        existing = {}
        try:
            if os.path.exists(contrib_path):
                with open(contrib_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line.startswith('|'):
                            continue
                        if line.startswith('|-'):
                            continue
                        parts = [p.strip() for p in line.split('|') if p.strip()]
                        if len(parts) >= 3 and parts[0] not in ('贡献者',) and parts[0] != '*(虚位以待)*':
                            existing[parts[0]] = parts[1]  # name -> content
        except Exception:
            pass

        # 扫描当前官方预设的 author 字段
        from_presets = {}
        for cat in CATEGORY_DIRS:
            d = os.path.join(OFFICIAL_DIR, cat)
            if not os.path.isdir(d):
                continue
            for fname in sorted(os.listdir(d)):
                if not fname.endswith('.json'):
                    continue
                try:
                    with open(os.path.join(d, fname), 'r', encoding='utf-8') as f:
                        data = json.loads(f.read())
                    a = data.get('author', '').strip()
                    if a:
                        if a not in from_presets:
                            from_presets[a] = set()
                        from_presets[a].add(f'{cat}/{fname}')
                except Exception:
                    pass

        # 合并：已有记录保留，预设新增追加
        today = datetime.date.today().strftime('%Y-%m-%d')
        md_lines = [
            '# 🎖️ 贡献者名单',
            '',
            '感谢每一位为鸣潮伤害计算器贡献预设的朋友！',
            '',
            '---',
            '',
            '## 贡献列表',
            '',
            '| 贡献者 | 贡献内容 | 贡献时间 |',
            '|--------|---------|----------|',
        ]
        has = False
        for n in sorted(existing.keys()):
            has = True
            md_lines.append(f'| {n} | {existing[n]} | {today} |')
        for n in sorted(from_presets.keys()):
            if n not in existing:
                has = True
                md_lines.append(f'| {n} | {"<br>".join(sorted(from_presets[n]))} | {today} |')
        if not has and not os.path.exists(contrib_path):
            md_lines.append('| *(虚位以待)* | | |')
        md_lines += [
            '',
            '---',
            '',
            '## 如何成为贡献者',
            '',
            '1. 使用「**预设构建器**」制作预设，填写作者名',
            '2. 打开「**官方预设上传工具**」，填入你的 GitHub 用户名',
            '3. 选择预设文件 → 提交投稿',
            '4. 等待审核合并后，你的名字会自动出现在这里',
            '',
            '---',
            '',
            '> 📌 此文件由预设上传工具自动更新，每次投稿合并后贡献者名单自动追加。',
            '',
        ]
        try:
            with open(contrib_path, 'w', encoding='utf-8') as f:
                f.write(newline.join(md_lines))
        except Exception:
            pass

    def submit_as_official(parent_widget, preset_path):
        """引导用户通过 Fork & Pull Request 提交预设为官方预设。"""
        # 先导出到临时目录
        exported = PresetManager.export_temp_preset(preset_path)
        if not exported:
            QMessageBox.warning(parent_widget, "导出失败", "无法导出预设文件。")
            return

        repo_url = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
        msg = QMessageBox(parent_widget)
        msg.setWindowTitle("提交为官方预设")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            "<h3>请按以下步骤将您的预设贡献为官方预设：</h3>"
            "<ol>"
            f"<li>访问项目 GitHub 仓库：<a href='{repo_url}'>{repo_url}</a></li>"
            "<li>Fork 该仓库到您的 GitHub 账号</li>"
            f"<li>将本预设文件 <b>{os.path.basename(preset_path)}</b> 放入 Fork 仓库的 <code>presets/official/</code> 下对应类别目录（character/weapon/echo_set/character_buff）</li>"
            "<li>提交 Pull Request，等待作者审核</li>"
            "</ol>"
            "<p><b>提示：</b>也可以通过项目 QQ 群向作者反馈。</p>"
            "<p>预设文件已保存至临时目录，点击下方按钮可打开该目录。</p>"
        )
        open_btn = msg.addButton("打开临时目录", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() == open_btn:
            tmp_dir = os.path.dirname(exported)
            os.startfile(tmp_dir) if sys.platform == "win32" else os.system(f"open '{tmp_dir}'")


# ═══════════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════════

def _apply_effects_and_indep(main_screen, effects, indep_zones, tag_prefix=""):
    """将效果列表添加到综合填写页面，将独立乘区添加到独立乘区页面。

    Args:
        main_screen: MainScreen 实例
        effects: [{"type": "常驻"/"触发", "name": str, "value": float,
                    "source": str, "sub_name": str, "default_hidden": bool}, ...]
        indep_zones: [{"group_name": str,
                        "values": [{"name": str, "value": float, "hidden": bool}, ...]}, ...]
        tag_prefix: 用于日志/调试的前缀标签
    """
    from WWDmgCalc import HIDDEN_ITEMS

    # ── 应用效果到综合填写 ──
    kw_seq_counter = 0
    for eff in effects:
        eff_type = eff.get("type", "常驻")
        name = eff.get("name", "")
        value = eff.get("value", 0.0)
        source = eff.get("source", "其他效果")
        sub_name = eff.get("sub_name", "")
        default_hidden = eff.get("default_hidden", False)
        keywords = eff.get("keywords", "")

        if not name:
            continue

        # 选择目标页面（与 _sync_chain_to_pages 保持一致：常驻→perm，其余→trigger）
        if eff_type == "常驻":
            page = main_screen.page_combined_perm
        else:
            page = main_screen.page_combined_trigger

        # 使用 _add_row_with_source 添加行
        page._counter += 1
        page._add_row_with_source(name, value, page._counter, source)

        # 设置副名称
        if sub_name and page._rows:
            last = page._rows[-1]
            if 'sub_name_edit' in last:
                last['sub_name_edit'].setText(sub_name)

        # 处理默认隐藏
        if default_hidden and page._rows:
            type_label = "常驻" if page.page_key == "combined_perm" else "触发"
            seq_num = page._counter
            key = (name, source, page.page_key, f"{type_label}{seq_num}")
            HIDDEN_ITEMS.add(key)
            # 更新按钮文字
            last = page._rows[-1]
            last['hide_btn'].setText("隐藏中")
            last['hide_btn'].setObjectName("itemDeleteBtn")
            last['hide_btn'].style().unpolish(last['hide_btn'])
            last['hide_btn'].style().polish(last['hide_btn'])

        # 同步到关键词关联页面
        if keywords:
            kw_seq_counter += 1
            seq_text = f"{tag_prefix}关联{kw_seq_counter}" if tag_prefix else f"关联{kw_seq_counter}"
            main_screen.page_keyword_assoc.add_effect_with_seq(
                name, value, eff_type, source, sub_name, keywords, seq_text)

    # ── 应用独立乘区 ──
    for iz_data in indep_zones:
        group_name = iz_data.get("group_name", "")
        values = iz_data.get("values", [])
        if not values:
            continue
        # 转换为 IndepZonePage._add_group 所需格式
        converted = []
        for v in values:
            converted.append((v.get("name", ""), v.get("value", 0.0), v.get("hidden", False)))
        main_screen.page_indep_zone._add_group(group_name, converted)
