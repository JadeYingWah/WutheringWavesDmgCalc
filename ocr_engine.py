# -*- coding: utf-8 -*-
# OCR 图文识别引擎（从 WWDmgCalc.py 拆分）
# 包含：RapidOCR 适配器 / 声骸解析 / 倍率解析 / OCRWorker / 图像预处理

__all__ = [
    "_OCR_STAT_ALIASES", "_SORTED_ALIASES", "_ALL_STAT_NAMES",
    "_RapidOCRAdapter", "OCRWorker",
    "_qimage_to_temp_file", "_is_fullscreen_image",
    "_crop_to_mult_region", "_crop_to_echo_region",
    "_add_image_padding", "_extract_cost_via_crop",
    "_match_stat_name", "_parse_ocr_results",
    "_parse_dmg_formula", "_parse_dmg_mult_ocr_results",
    "_SKILL_CATEGORIES",
]

import sys
import os
import re
import tempfile
import difflib
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal, QObject

# 引用 error_handler 的 logger
from error_handler.error_system import _logger

_ocr_instance = None
_ocr_error = None

# 所有可识别的词条名称集合（从 OCR_STAT_ALIASES 的 canonical key 提取，用于模糊匹配）
_ALL_STAT_NAMES = None  # lazy init below

# ── OCR 生僻字字符修正表 ──
# RapidOCR 默认移动端模型字符集有限（约 6600 字），游戏中生僻字可能
# 被识别成形近或音近的常见字。此表按 OCR 误读结果 → 正确字符。
# 仅修正游戏中实际出现的高频生僻字，避免过度泛化造成误伤。
# ── OCR 生僻字修正系统 ──
# 两层策略：
#   1. 精确词条修正表 _OCR_TERM_FIX — 已知的高频 OCR 误读 → 正确词条
#   2. 游戏词库模糊匹配 — 对 OCR 输出做字典比对，自动纠正生僻字
# RapidOCR 默认移动端模型字符集有限（约 6600 字），不在词表中的字
# 无法被识别。词库模糊匹配可弥补这一缺陷。

# ═══════════════════════════════════════════════════════════════
# 一、精确词条修正表（已知高频误读 → 正确）
# ═══════════════════════════════════════════════════════════════
_OCR_TERM_FIX = [
    # ── 元素/伤害类型 ──
    ("烟灭", "湮灭"), ("淹灭", "湮灭"), ("理灭", "湮灭"),
    ("衔射", "衍射"), ("行射", "衍射"),
    ("冷疑", "冷凝"), ("冷宁", "冷凝"),
    ("热溶", "热熔"), ("热容", "热熔"), ("热格", "热熔"),
    ("气幼", "气动"), ("导雷", "导电"), ("寻电", "导电"),
    # ── 词条名 ──
    ("共呜效率", "共鸣效率"), ("共呜", "共鸣"),
    ("重去", "重击"), ("重市", "重击"),
    ("增监", "增益"), ("增溢", "增益"), ("增兰", "增益"),
    ("常往", "常驻"), ("常仕", "常驻"), ("常注", "常驻"),
    ("触友", "触发"), ("触法", "触发"),
    ("技自", "技能"), ("技施", "技能"),
    ("治广", "治疗"), ("冶疗", "治疗"),
    ("效辛", "效率"), ("效卒", "效率"),
    ("伤言", "伤害"), ("伤喜", "伤害"),
    ("暴去", "暴击"), ("暴市", "暴击"),
    # ── 角色名 ──
    ("秋秋", "秧秧"), ("映映", "秧秧"),
    ("今夕", "今汐"),
    ("织霞", "炽霞"), ("只霞", "炽霞"),
    ("白止", "白芷"),
    ("可菜塔", "柯莱塔"),
    ("坎持蓄拉", "坎特蕾拉"), ("次特蕾拉", "坎特蕾拉"),
    ("佛洛洛", "弗洛洛"), ("费洛洛", "弗洛洛"),
    ("非比", "菲比"),
    ("灵阳", "凌阳"),
    ("忘炎", "忌炎"),
    ("签心", "鉴心"), ("览心", "鉴心"),
    ("开支", "折枝"),
    ("可丁", "珂莱塔"),
    ("守库人", "守岸人"), ("守岩人", "守岸人"),
    ("洛可司", "洛可可"), ("络可可", "洛可可"),
    # ── 声骸名 ──
    ("噪鹛", "噪鹃"),
    ("车刀镰", "车刃镰"),
    ("角藏", "角赢"),
    ("振锋", "振铎"),
    ("残猿", "戏猿"),
    ("奏论", "奏谕"),
    ("蹈光", "踏光"),
    ("游磷", "游鳞"),
    ("呼梭", "呼棱"),
    ("呜泣", "鸣泣"),
    ("具渊", "冥渊"),
    ("饶夔", "骁夔"),
    ("聚城", "聚械"),
    # ── 武器名 ──
    ("水夜", "永夜"),
    ("诸万", "诸方"),
    ("时利", "时和"),
    ("停往", "停驻"),
    ("核溶", "核熔"),
    ("令州", "今州"),
    ("原火", "源火"),
    ("箱华", "霜华"),
    ("渊水", "渊冰"),
    ("心恨", "心痕"),
    ("苍磷", "苍鳞"),
    ("暗欧", "暗殴"),
    ("喊锋", "藏锋"),
    ("慢师", "偃师"),
    ("龙洲", "龙渊"),
    ("星乐", "星烁"),
    ("日冤", "日冕"),
    # ── 通用词/技能名 ──
    ("永动", "涌动"),
    ("畏缩", "畏缩"),
    ("热噪", "热噪"),
    ("熔毁", "熔毁"),
    # ── 游戏专有术语（ocr_training_data.txt） ──
    ("协秦", "协奏"), ("协凑", "协奏"),
    ("谐度", "谐度"), ("失谱", "失谐"),
    ("抗打", "抗打断"), ("凝沸", "凝滞"),
    ("共呜链", "共鸣链"), ("声核", "声骸"),
    ("终瑞", "终瑞"), ("偏谐", "偏谐"),
    ("疾霆", "疾霆"), ("穿林", "穿林"),
    # ── 角色名补充（ocr_training_data.txt） ──
    ("吟林", "吟霖"), ("吟淋", "吟霖"),
    ("灯订", "灯灯"), ("丁灯", "灯灯"),
    ("釉胡", "釉瑚"), ("油瑚", "釉瑚"),
    ("千关", "千咲"), ("千笑", "千咲"),
    ("桃祁", "桃祈"), ("桃折", "桃祈"),
    ("丹理", "丹瑾"), ("丹懂", "丹瑾"),
    ("露茜", "露西"),
    ("赞姬", "赞妮"), ("赞妣", "赞妮"),
    ("仇沅", "仇远"), ("仇元", "仇远"),
    ("夏宝", "夏空"),
    ("尤娜", "尤诺"),
    ("春药", "椿"), ("桩", "椿"),
    ("卡提希娅", "卡提希娅"),
    ("布兰", "布兰特"),
    ("绯雷", "绯雪"),
    ("卜买", "卜灵"),
    ("渊伍", "渊武"),
    ("西格", "西格莉卡"),
    ("嘉贝", "嘉贝莉娜"),
    ("莫特", "莫特斐"), ("莫特飞", "莫特斐"),
    ("奥古斯", "奥古斯塔"),
    # ── 武器名补充（ocr_training_data.txt） ──
    ("时和岁念", "时和岁稔"),
    ("浩境磷光", "浩境粼光"),
    ("苍磷千嶂", "苍鳞千嶂"),
    ("千古状流", "千古洑流"), ("千古伏流", "千古洑流"),
    ("赫亦流明", "赫奕流明"), ("赫奔流明", "赫奕流明"),
    ("不死航路", "不灭航路"),
    ("海的呢喃", "海的呢喃"),
    ("制傀之手", "掣傀之手"),
    ("漪兰浮录", "漪澜浮录"), ("漪澜浮绿", "漪澜浮录"),
    ("琼枝冰消", "琼枝冰绡"),
    ("异向空灵", "异响空灵"), ("异响空买", "异响空灵"),
    ("重破刀-41型", "重破刃-41型"),
    ("风流的寓", "风流的寓言诗"),
    ("叙别的罗", "叙别的罗曼史"),
    ("停论喷流", "悖论喷流"), ("倍论喷流", "悖论喷流"),
    ("无眠烈", "无眠烈火"),
    ("酩酊的英雄", "酩酊的英雄志"),
    ("袍泽之", "袍泽之固"),
    ("虚饰的华", "虚饰的华尔兹"),
    ("核溶星盘", "核熔星盘"),
    ("钧天正", "钧天正音"),
    # ── 共鸣链/技能名（ocr_training_data.txt） ──
    ("每明如朔", "晦明如朔"),
    ("临渊死", "临渊死寂"),
    ("万象崩", "万象崩落于风间"),
    ("界限崩", "界限崩折于刹那"),
    ("生灭交", "生灭交错于来路"),
    ("流光乍", "流光乍隐于长夜"),
    ("虚相陷", "虚相陷落于掌中"),
    ("风止息于", "风止息于无明界"),
    # ── PP-OCRv5 特有混淆（v5 字库更大但形近字仍会混淆） ──
    ("唤取", "换取"), ("换能", "换能"),
    ("骈臻", "骈臻"), ("辐辕", "辐辏"),
    ("幕刃", "幕刃"), ("斩魔", "斩魔"),
    ("哀声", "哀声"), ("邃夜", "邃夜"),
    ("骤雨", "骤雨"), ("狂岚", "狂岚"),
    ("残响", "残响"), ("唤声", "唤声"),
    ("灭音", "灭音"), ("瞬刻", "瞬刻"),
    ("震声", "震声"), ("绞息", "绞息"),
    ("碧霄", "碧霄"), ("苍息", "苍息"),
    # ── UI 元素干扰修正（v5 检测到更多 UI 字符） ──
    ("更换声骸", "更换"),
    ("+ 25", "+25"), ("+25%", "+25"),
]

# ═══════════════════════════════════════════════════════════════
# 二、OCR 常见字符混淆矩阵
# ── 用于模糊匹配时计算字符相似度 ──
# 格式: OCR误读字符 → {候选正确字符, ...}
# ═══════════════════════════════════════════════════════════════
_CHAR_CONFUSION = {
    # ── 偏旁部首混淆（基于 ocr_training_data.txt 生僻字集） ──
    "拆": {"拆", "折", "抃", "拚", "扦"},
    "折": {"拆", "折", "抃", "浙", "哲"},
    "抃": {"拆", "折", "抃", "拼"},
    # 氵 ↔ 冫 ↔ ？
    "湮": {"烟", "淹", "湮", "理", "潭"},
    "衍": {"行", "衔", "衍", "街"},
    "凝": {"疑", "宁", "凝", "淩", "凌"},
    "澜": {"兰", "栏", "澜", "拦"},
    "漪": {"奇", "倚", "漪", "椅"},
    "淬": {"卒", "碎", "淬", "翠"},
    "瀚": {"翰", "汗", "瀚", "旱"},
    "沅": {"元", "阮", "沅", "玩"},
    "澧": {"礼", "澧", "豊"},
    # 火 ↔ ？
    "熔": {"溶", "容", "熔", "格", "榕"},
    "炽": {"织", "只", "炽", "帜", "职"},
    "烬": {"尽", "进", "烬", "近"},
    # 口 ↔ 日
    "鸣": {"呜", "鸣"},
    "吟": {"今", "令", "吟", "铃", "玲"},
    "啸": {"萧", "潇", "啸", "肃"},
    # 禾 ↔ 木
    "秧": {"映", "秋", "秧", "殃", "英"},
    # 氵
    "汐": {"夕", "汐", "砂"},
    # 王/玉旁
    "珑": {"龙", "尤", "珑", "陇"},
    "珩": {"行", "衔", "珩", "街"},
    "玦": {"决", "块", "玦", "诀"},
    "琮": {"宗", "崇", "琮", "综"},
    "璨": {"粲", "灿", "璨", "餐"},
    "瑾": {"堇", "勤", "瑾", "仅"},
    # 日旁
    "曦": {"嘻", "义", "曦", "稀"},
    "曙": {"暑", "署", "曙", "著"},
    "晦": {"每", "海", "晦", "梅"},
    "暄": {"宣", "宜", "暄", "渲"},
    "晔": {"华", "叶", "晔", "桦"},
    # 金旁
    "铎": {"锋", "铎", "择", "泽"},
    "钧": {"均", "钧", "钓"},
    "鉴": {"签", "览", "鉴", "监", "篮"},
    # 鱼旁
    "鳞": {"磷", "鳞", "麟"},
    # ── 其他结构相似 ──
    "儛": {"舞", "潮", "侮", "梅"},
    "夔": {"饶", "骁", "夔", "莫"},
    "谕": {"论", "谕", "喻", "偷"},
    "掣": {"制", "裂", "掣"},
    "傀": {"鬼", "愧", "傀", "瑰"},
    "酩": {"名", "铭", "酩", "茗"},
    "酊": {"丁", "钉", "酊", "叮"},
    "霁": {"齐", "济", "霁", "挤"},
    "霓": {"尼", "泥", "霓", "呢"},
    "霆": {"廷", "庭", "霆", "挺"},
    "砚": {"见", "现", "砚", "观"},
    "绽": {"定", "淀", "绽", "锭"},
    "壑": {"容", "豁", "壑", "浴"},
    "麓": {"鹿", "路", "麓", "露"},
    "霖": {"林", "淋", "霖", "琳"},
    "帧": {"侦", "贞", "帧", "真"},
    "寰": {"还", "环", "寰", "缓"},
    "朔": {"塑", "溯", "朔"},
    "缥": {"票", "漂", "缥", "飘"},
    "缈": {"秒", "渺", "缈", "妙"},
    "笙": {"生", "声", "笙", "牲"},
    "筱": {"条", "修", "筱", "悠"},
    "敕": {"来", "刺", "敕", "策"},
    "澹": {"詹", "淡", "澹", "檐"},
    "肇": {"户", "启", "肇"},
    "潼": {"童", "同", "潼", "撞"},
    "绡": {"肖", "消", "绡", "销"},
    "洑": {"伏", "犬", "洑", "状"},
    "粼": {"磷", "鳞", "粼", "麟"},
    "燧": {"遂", "隧", "燧", "邃"},
    "鸾": {"亦", "鸾", "变"},
    # ── PP-OCRv5 扩展混淆对（v5 字库 ≥15000，混淆更多发生在形近字之间） ──
    "阖": {"阁", "合", "阖", "阂"},
    "辏": {"秦", "奏", "辏", "凑"},
    "骈": {"并", "拼", "骈", "饼"},
    "臻": {"秦", "至", "臻", "榛"},
    "辐": {"福", "幅", "辐", "副"},
    "飓": {"具", "飓", "俱"},
    "岚": {"风", "岚", "岗"},
    "邃": {"遂", "隧", "邃", "燧"},
    "斩": {"折", "斩", "轨"},
    "骤": {"聚", "骤", "暴"},
    "霄": {"宵", "霄", "销"},
    "绞": {"交", "校", "绞", "效"},
    "隙": {"陈", "希", "隙", "欷"},
    "褶": {"习", "折", "褶", "摺"},
    "冥": {"具", "冥", "寞"},
    "渊": {"渊", "洲", "测"},
    "骁": {"尧", "骁", "饶"},
    "谕": {"论", "偷", "谕", "喻"},
    "璨": {"粲", "餐", "璨", "灿"},
    "瑾": {"仅", "勤", "瑾", "谨"},
    "釉": {"由", "油", "釉", "轴"},
    "瑚": {"胡", "湖", "瑚", "糊"},
    "咲": {"关", "笑", "咲", "关"},
    "洑": {"伏", "犬", "状", "洑"},
    "徙": {"徒", "徙", "从"},
    "祓": {"拔", "祓", "跋"},
    "磔": {"桀", "磔", "碟"},
    "砺": {"厉", "励", "砺", "蛎"},
    "弑": {"杀", "试", "弑", "式"},
    "锢": {"固", "锢", "涸"},
    "铿": {"坚", "铿", "鉴"},
    "锵": {"将", "锵", "枪"},
    "罅": {"乎", "罅", "呼"},
    "啮": {"齿", "啮", "龄"},
    "魇": {"厌", "魔", "魇"},
    "魈": {"肖", "鬼", "魈"},
    "鬣": {"鼠", "猎", "鬣"},
}

# ═══════════════════════════════════════════════════════════════
# 三、游戏词库（所有已知游戏术语，用于模糊匹配纠错）
# ═══════════════════════════════════════════════════════════════
_GAME_TERMS = set()
# 构建词库（合并所有来源）
def _build_game_terms():
    """从所有数据源构建完整游戏词库（含 ocr_training_data.txt 全部术语）。"""
    if _GAME_TERMS:
        return _GAME_TERMS

    # ── 声骸词条名 ──
    _GAME_TERMS.update(_ALL_STAT_NAMES)
    _GAME_TERMS.update(_OCR_STAT_ALIASES.keys())

    # ── 元素 ──
    _GAME_TERMS.update(["冷凝", "热熔", "气动", "导电", "衍射", "湮灭"])

    # ── 技能类型 ──
    _GAME_TERMS.update(["普攻", "重击", "共鸣技能", "共鸣解放", "变奏技能",
                         "声骸技能", "常态攻击", "共鸣回路", "延奏技能",
                         "空中攻击", "闪避", "极限闪避", "弹刀"])

    # ── 异常效应 ──
    _GAME_TERMS.update(["光噪", "风蚀", "虚湮", "聚爆", "霜渐", "电磁"])

    # ── 词条类型 ──
    _GAME_TERMS.update(["常驻", "触发", "治疗", "效率", "伤害",
                         "增益", "攻击", "防御", "生命", "暴击"])

    # ── 从 _OCR_TERM_FIX 提取所有正确词条 ──
    for _, correct in _OCR_TERM_FIX:
        _GAME_TERMS.add(correct)

    # ══════════════════════════════════════════════════════════
    # 角色名（完整，来自 ocr_training_data.txt）
    # ══════════════════════════════════════════════════════════
    _GAME_TERMS.update([
        "漂泊者", "漂泊者·衍射", "漂泊者·湮灭", "漂泊者·气动",
        "今汐", "露西", "赞妮", "菲比", "守岸人", "维里奈",
        "卡提希娅", "夏空", "忌炎", "鉴心", "西格莉卡", "仇远",
        "尤诺", "秧秧", "秋水",
        "珂莱塔", "柯莱塔", "折枝", "凌阳", "绯雪", "散华", "釉瑚", "白芷",
        "椿", "坎特蕾拉", "洛可可", "弗洛洛", "千咲", "丹瑾", "桃祈",
        "长离", "布兰特", "露帕", "安可", "炽霞", "嘉贝莉娜", "莫特斐",
        "吟霖", "卡卡罗", "相里要", "灯灯", "奥古斯塔", "卜灵", "渊武",
    ])

    # ══════════════════════════════════════════════════════════
    # 武器名（完整，来自 ocr_training_data.txt）
    # ══════════════════════════════════════════════════════════
    _GAME_TERMS.update([
        # 5星
        "时和岁稔", "浩境粼光", "苍鳞千嶂", "千古洑流",
        "赫奕流明", "不灭航路", "死与舞", "停驻之烟",
        "悲喜剧", "擎渊怒涛", "诸方玄枢", "海的呢喃",
        "和光回唱", "掣傀之手", "星序协响", "漪澜浮录", "琼枝冰绡",
        # 4星
        "容赦的沉思录", "凋亡频移", "东落", "异响空灵",
        "永夜", "永夜长明", "纹秋", "重破刃-41型",
        "风流的寓言诗", "心之锚", "永续坍缩", "不归孤军",
        "行进序曲", "西升", "飞景", "瞬斩刀-18型",
        "叙别的罗曼史", "悖论喷流", "华彩乐段", "奔雷",
        "无眠烈火", "穿击枪-26型", "飞逝",
        "酩酊的英雄志", "尘云旋臂", "呼啸重音", "袍泽之固",
        "金掌", "钢影拳-21丁型", "骇行",
        "渊海回声", "虚饰的华尔兹", "核熔星盘", "今州守望",
        "奇幻变奏", "异度", "清音", "鸣动仪-25型",
        # 3星
        "钧天正音", "戍关长刃·定军", "暗夜长刃·玄明",
        "源能长刃·测壹", "远行者长刃·辟路",
        "原初长刃·朴石", "教学长刃",
        "戍关迅刀·镇海", "暗夜迅刀·黑闪",
        "源能迅刀·测贰", "远行者迅刀·旅迹",
        "原初迅刀·鸣雨", "教学迅刀",
        "戍关佩枪·平云", "暗夜佩枪·暗星",
        "源能佩枪·测叁", "远行者佩枪·洞察",
        "原初佩枪·穿林", "教学佩枪",
        "戍关臂铠·拔山", "暗夜臂铠·夜芒",
        "源能臂铠·测肆", "远行者臂铠·破障",
        "原初臂铠·磐岩", "教学臂铠",
        "戍关音感仪·留光", "暗夜矩阵·暝光",
        "源能音感仪·测五", "远行者矩阵·探幽",
        "原初音感仪·听浪", "教学音感仪",
        # 别名
        "诸方", "时和", "停驻", "核熔", "干面", "今州",
        "源火", "霜华", "渊冰", "心痕", "苍鳞", "暗殴", "藏锋",
        "偃师", "龙渊", "星烁", "日冕", "血誓盟约", "裁春",
        "尘云", "不归", "浩境", "诸手", "渊海", "千音",
        "静默", "深海", "尘世", "幻饵", "碎磷", "不返", "狂想", "重破",
    ])

    # ══════════════════════════════════════════════════════════
    # 声骸名
    # ══════════════════════════════════════════════════════════
    _GAME_TERMS.update([
        "噪鹃", "车刃镰", "角赢", "振铎", "戏猿", "奏谕",
        "踏光", "游鳞", "呼棱", "鸣泣", "冥渊", "骁夔", "聚械",
        "共眠", "啸叫", "幼岩", "裂变", "破阵", "云闪", "诛罗",
        "抃风儛润", "芙露德莉斯", "审判", "寒岁", "灼热",
        "残象", "声骸", "声骸技能", "声骸异能",
    ])

    # ══════════════════════════════════════════════════════════
    # 合鸣效果/声骸套装名
    # ══════════════════════════════════════════════════════════
    _GAME_TERMS.update([
        "流云逝尽之空", "浮星", "畏缩", "热噪", "熔毁", "涌动",
        "流云", "逝尽", "浮星坠辰", "彻空", "彻空之雷",
        "哀恸", "哀恸之声", "哀声鸷枭",
        "邃夜", "邃夜逐冥", "斩魔", "斩魔之镰",
        "狂岚", "狂岚骤雨", "残响", "残响之石",
        "轻云", "轻云出月", "凝夜", "凝夜之霜",
        "隐士", "隐士之叹", "裂变之雷", "啸叫之岩",
        "幼岩之壳", "破阵之刃", "云闪之鳞", "诛罗之爪",
        "共眠之火", "审判之锤", "寒岁之冰", "灼热之炎",
        "衍射之塔", "湮灭之核", "气动之翼",
    ])

    # ══════════════════════════════════════════════════════════
    # 技能名（漂泊者三条路线 + 战斗系统，来自 ocr_training_data.txt）
    # ══════════════════════════════════════════════════════════
    _GAME_TERMS.update([
        # 漂泊者·衍射
        "化声为型", "浮声千斩", "万物微尘", "回响奏鸣", "震声", "瞬刻",
        # 漂泊者·湮灭
        "灭音", "残响", "临渊死寂", "唤声",
        # 漂泊者·气动
        "抃风儛润", "缥缈无相", "万象归墟", "风蚀",
        "苍息破象", "碧霄断行", "绞息",
        # 共鸣链（漂泊者·衍射）
        "始源纪行", "微物细语", "尘声百面", "连音扫弦", "回声流转", "长路归鸣",
        # 共鸣链（漂泊者·湮灭）
        "弦外知机", "晦明如朔", "声息涌动", "尘声湮灭", "万物寂听", "暗涌潮升",
        # 共鸣链（漂泊者·气动）
        "风止息于无明界", "流光乍隐于长夜", "虚相陷落于掌中",
        "界限崩折于刹那", "生灭交错于来路", "万象崩落于风间",
        # 战斗术语
        "共鸣技能", "共鸣解放", "共鸣回路", "共鸣链",
        "变奏技能", "延奏技能", "常态攻击",
        "协奏", "协同攻击", "牵引", "共振摧毁",
        "偏谐值", "失谐", "谐度破坏", "谐度破坏技", "谐度破坏伤害",
        "凝滞", "抗打断",
    ])

    # ══════════════════════════════════════════════════════════
    # 游戏专有词汇（来自 ocr_training_data.txt）
    # ══════════════════════════════════════════════════════════
    _GAME_TERMS.update([
        "鸣潮", "漂泊者", "共鸣者", "共鸣", "声骸", "残象",
        "岁主", "瑝珑", "今州", "黎那汐塔", "黑海岸",
        "夜归", "天工", "巡宁所", "边庭", "军策府", "华胥研究院",
        "无音区", "共鸣频率", "拉贝尔曲线", "超频", "声痕",
        "今令尹", "鸣钟广场", "雪莲酥",
        "召唤", "变身", "固有技能", "属性加成", "突破",
    ])

    # ══════════════════════════════════════════════════════════
    # 通用游戏术语
    # ══════════════════════════════════════════════════════════
    _GAME_TERMS.update([
        "倍率增加", "倍率提升", "伤害加成", "伤害加深", "伤害提升",
        "抗性", "抗性减少", "抗性无视", "无视防御", "忽视防御",
        "减少防御", "全属性", "共鸣链",
        "谐振", "合鸣", "延奏", "变奏",
        "百分比攻击", "百分比生命", "百分比防御",
        "主力输出", "快速协奏", "生存治疗", "伤害加深",
        "骇破响应", "共鸣解放充能",
        "暴击率", "暴击伤害", "共鸣效率", "治疗效果加成",
        # ── PROJECT_SUMMARY.md 补充：游戏系统术语 ──
        "合鸣效果", "合鸣筛选", "声骸推荐", "声骸列表",
        "装配声骸", "更换声骸", "强化声骸", "卸下声骸",
        "排序", "筛选", "锁定", "解锁", "详情",
        "切换配置", "一键装配", "一键卸下",
        # ── 战斗机制 ──
        "光噪效应", "风蚀效应", "虚湮效应", "聚爆效应", "霜渐效应", "电磁效应",
        "极限闪避", "空中攻击", "弹刀", "闪避反击",
        "协奏值", "共鸣值", "连携技",
        # ── 面板/界面 ──
        "基础属性", "进阶属性", "详细属性",
        "声骸评分", "推荐度", "适用角色",
        "主属性", "副属性", "随机属性",
        # ── 数值描述 ──
        "百分比", "固定值", "基础数值",
        "当前值", "最大值", "最小值",
        # ── 技能效果 ──
        "技能伤害", "持续伤害", "爆发伤害",
        "护盾", "减伤", "增伤", "易伤",
        "回复生命", "回复耐力",
        # ── 声骸相关补充 ──
        "声骸等级", "声骸经验", "声骸突破",
        "调谐", "湮灭回响", "残响石",
        "无音区", "凝滞", "抗打断",
    ])

    return _GAME_TERMS


# ═══════════════════════════════════════════════════════════════
# 字符相似度计算
# ═══════════════════════════════════════════════════════════════
def _char_similar(c1, c2):
    """判断两个字符是否 OCR 层面的相似（相同或来自已知混淆对）。"""
    if c1 == c2:
        return True
    conf = _CHAR_CONFUSION.get(c1)
    if conf and c2 in conf:
        return True
    conf = _CHAR_CONFUSION.get(c2)
    if conf and c1 in conf:
        return True
    return False


def _fuzzy_match_score(ocr_text, dict_term):
    """计算 OCR 文本与词库术语的模糊匹配得分（越高越相似）。
    使用 LCS 思路 + 字符混淆宽容，处理 OCR 的漏字/多字/误字。
    返回 (score, dict_term)。
    """
    if not ocr_text or not dict_term:
        return 0.0
    if ocr_text == dict_term:
        return 1.0

    o_len, d_len = len(ocr_text), len(dict_term)
    if o_len == 0 or d_len == 0:
        return 0.0

    # DP: 最长公共子序列（允许字符混淆宽容）
    dp = [[0] * (d_len + 1) for _ in range(o_len + 1)]
    for i in range(o_len):
        for j in range(d_len):
            if _char_similar(ocr_text[i], dict_term[j]):
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i][j + 1], dp[i + 1][j])

    lcs = dp[o_len][d_len]
    # 得分 = LCS 长度 / 较长字符串的长度（处理 OCR 漏字/多字）
    score = lcs / max(o_len, d_len) if max(o_len, d_len) > 0 else 0.0
    return score


# ═══════════════════════════════════════════════════════════════
# 词库模糊匹配修正
# ═══════════════════════════════════════════════════════════════
_FUZZY_MIN_LEN = 2        # 最短文本才做模糊匹配（过短无意义）
_FUZZY_MIN_SCORE = 0.55   # 最低相似度阈值
_FUZZY_MIN_LEN_RATIO = 0.4  # 长度比下限（OCR 漏字不能太严重）


def _fuzzy_correct(ocr_text, game_terms):
    """对 OCR 文本做词库模糊匹配修正。
    若 OCR 文本与词库中某个术语高度相似但又不完全匹配，则返回纠正后的术语。
    否则返回原文本。
    """
    if not ocr_text or len(ocr_text) < _FUZZY_MIN_LEN:
        return ocr_text

    # 已在词库中，无需修正
    if ocr_text in game_terms:
        return ocr_text

    best_score = 0.0
    best_term = None

    for term in game_terms:
        t_len = len(term)
        o_len = len(ocr_text)
        # 长度比过滤：差异太大直接跳过
        if t_len == 0 or o_len == 0:
            continue
        len_ratio = min(o_len, t_len) / max(o_len, t_len)
        if len_ratio < _FUZZY_MIN_LEN_RATIO:
            continue

        score = _fuzzy_match_score(ocr_text, term)
        if score > best_score:
            best_score = score
            best_term = term

    if best_score >= _FUZZY_MIN_SCORE and best_term is not None:
        return best_term
    return ocr_text


def _apply_ocr_char_fix(text):
    """对 OCR 识别文本做生僻字修正。
    1. 精确词条修正（已知高频误读 → 正确）
    2. 游戏词库模糊匹配（补充模型词表外的生僻字）
    """
    if not text:
        return text

    # 第一层：精确词条修正
    for wrong, correct in _OCR_TERM_FIX:
        if wrong in text:
            text = text.replace(wrong, correct)

    # 第二层：词库模糊匹配
    game_terms = _build_game_terms()
    text = _fuzzy_correct(text, game_terms)

    return text


# 常见的 OCR 混淆映射：OCR 可能把某些字符读错
_OCR_STAT_ALIASES = {
    "攻击力": ["攻击力", "攻擊力", "攻击", "ATK", "atk"],
    "生命值": ["生命值", "生命", "HP", "hp"],
    "防御力": ["防御力", "防御", "DEF", "def"],
    "暴击率": ["暴击率", "暴击", "暴擊率", "暴擊", "Crit Rate", "CRIT Rate"],
    "暴击伤害": ["暴击伤害", "暴擊傷害", "暴伤", "暴傷", "Crit DMG", "CRIT DMG"],
    "治疗效果加成": ["治疗效果加成", "治療效果加成", "治疗加成", "治療加成", "Healing Bonus"],
    "共鸣效率": ["共鸣效率", "共鳴效率", "共鸣", "共鳴", "Energy Regen"],
    "普攻伤害加成": ["普攻伤害加成", "普攻加成", "普通攻击伤害加成"],
    "重击伤害加成": ["重击伤害加成", "重擊傷害加成", "重击加成", "重擊加成"],
    "共鸣技能伤害加成": ["共鸣技能伤害加成", "共鳴技能傷害加成", "共鸣技能加成", "E技能加成"],
    "共鸣解放伤害加成": ["共鸣解放伤害加成", "共鳴解放傷害加成", "共鸣解放加成", "R技能加成"],
    "固定生命": ["固定生命", "固定生命值", "Flat HP"],
    "固定攻击": ["固定攻击", "固定攻擊", "Flat ATK"],
    "固定防御": ["固定防御", "Flat DEF"],
    "冷凝伤害加成": ["冷凝伤害加成", "冷凝加成", "冰伤加成", "Glacio DMG"],
    "热熔伤害加成": ["热熔伤害加成", "熱熔傷害加成", "热熔加成", "火伤加成", "Fusion DMG"],
    "气动伤害加成": ["气动伤害加成", "氣動傷害加成", "气动加成", "风伤加成", "Aero DMG"],
    "导电伤害加成": ["导电伤害加成", "導電傷害加成", "导电加成", "雷伤加成", "Electro DMG"],
    "衍射伤害加成": ["衍射伤害加成", "衍射加成", "光伤加成", "Spectro DMG"],
    "湮灭伤害加成": ["湮灭伤害加成", "湮灭加成", "暗伤加成", "Havoc DMG"],
}

# 跨所有 canonical 按别名长度降序，避免短别名（如"暴击"）抢先匹配长文本（如"暴击伤害"）
_SORTED_ALIASES = sorted(
    [(alias, canonical) for canonical, aliases in _OCR_STAT_ALIASES.items() for alias in aliases],
    key=lambda x: len(x[0]), reverse=True,
)

# 所有可识别的词条名（用于模糊匹配，覆盖主词条+副词条的全部名称）
_ALL_STAT_NAMES = list(_OCR_STAT_ALIASES.keys()) + [
    # 补充 _OCR_STAT_ALIASES 中作为 alias 存在但非 canonical key 的百分比版词条
    "攻击力", "攻击力%", "生命值", "生命值%", "防御力", "防御力%",
    "暴击率", "暴击伤害", "共鸣效率",
    "普攻伤害加成", "重击伤害加成",
    "共鸣技能伤害加成", "共鸣解放伤害加成",
    "冷凝伤害加成", "热熔伤害加成", "气动伤害加成",
    "导电伤害加成", "衍射伤害加成", "湮灭伤害加成",
]


class _RapidOCRAdapter:
    """将 RapidOCR 输出格式适配为 PaddleOCR 兼容格式，存量解析器无需改动。"""
    def __init__(self):
        # PyInstaller 打包后，模块可能被冻结在 PYZ 中，其 __file__ 不指向真实文件，
        # 导致同目录的 config.yaml / ONNX 模型找不到。
        # 将 _MEIPASS 加入 sys.path 首位，让 Python 优先从真实文件系统加载本包。
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', '')
            if meipass and meipass not in sys.path:
                sys.path.insert(0, meipass)
        from rapidocr_onnxruntime import RapidOCR

        # PP-OCRv5 模型（字符集 ≥15000，含生僻字）
        # 策略：mobile 检测（快，4.6 MB）+ server 识别（准，81 MB）
        _model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
        _rec_model = os.path.join(_model_dir, 'ch_PP-OCRv5_rec_server_infer.onnx')
        _det_mobile = os.path.join(_model_dir, 'ch_PP-OCRv5_mobile_det.onnx')
        _det_server = os.path.join(_model_dir, 'ch_PP-OCRv5_server_det.onnx')

        # 优先 mobile 检测（快 10 倍），不存在则用 server，都没有则回退默认
        _rec_path = _rec_model if os.path.exists(_rec_model) else None
        if os.path.exists(_det_mobile):
            _det_path = _det_mobile
            _logger.info("使用 PP-OCRv5 mobile 检测模型（高速）")
        elif os.path.exists(_det_server):
            _det_path = _det_server
            _logger.info("使用 PP-OCRv5 server 检测模型")
        else:
            _det_path = None

        if _rec_path:
            _logger.info("使用 PP-OCRv5 server 识别模型: %s", _rec_path)

        # det_limit_side_len=480：v5 检测模型精度更高，低分辨率即可；
        # 全屏截图已在上游裁剪到目标区域，无需高分辨率检测
        self._ocr = RapidOCR(
            text_score=0.2,
            det_thresh=0.15,
            det_box_thresh=0.25,
            det_model_path=_det_path,
            rec_model_path=_rec_path,
            det_limit_side_len=480,
        )

    def predict(self, image_path):
        """返回与 PaddleOCR predict() 相同格式的结果列表"""
        # 调用时也降低识别阈值，防止低置信度的大字 / 单字符被丢弃
        result, _ = self._ocr(image_path, text_score=0.2, box_thresh=0.25)
        rec_texts, rec_scores, dt_polys = [], [], []
        if result:
            for box, text, conf in result:
                # 生僻字词条修正
                fixed_text = _apply_ocr_char_fix(text)
                rec_texts.append(fixed_text)
                rec_scores.append(conf)
                dt_polys.append(box)
        return [{"rec_texts": rec_texts, "rec_scores": rec_scores, "dt_polys": dt_polys}]


def _get_ocr():
    """延迟初始化 OCR 引擎（使用 RapidOCR + ONNX Runtime）
    返回 (instance, None) 或 (None, error_message)"""
    global _ocr_instance, _ocr_error
    if _ocr_instance is None and _ocr_error is None:
        try:
            _ocr_instance = _RapidOCRAdapter()
        except Exception as e:
            _ocr_error = str(e)
            _logger.warning("RapidOCR 初始化失败: %s", e)
    return _ocr_instance, _ocr_error


def _qimage_to_temp_file(qimage):
    """将 QImage 保存为临时 PNG 文件，返回路径"""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    qimage.save(path, "PNG")
    return path


def _is_fullscreen_image(w, h):
    """判断宽高是否接近常见显示器分辨率（±6% 容差）。
    无法精确匹配时，检查是否超过 1M 像素且接近标准宽高比（16:9/16:10/21:9/3:2）。"""
    _monitor_res = [
        # 16:9
        (1920, 1080), (2560, 1440), (3840, 2160), (1366, 768), (1280, 720),
        # 16:10
        (1920, 1200), (2560, 1600), (2880, 1800), (1680, 1050),
        # 21:9 ultrawide
        (3440, 1440), (2560, 1080), (3840, 1600), (5120, 2160),
        # 3:2
        (3000, 2000), (2256, 1504), (2160, 1440), (2736, 1824),
        # 4:3
        (1600, 1200), (2048, 1536),
    ]
    for mw, mh in _monitor_res:
        if abs(w - mw) <= mw * 0.06 and abs(h - mh) <= mh * 0.06:
            return True
    # 兜底：>1M 像素 + 标准宽高比
    if w * h >= 1000000:
        ratio = w / h
        for std in (16/9, 16/10, 21/9, 3/2, 4/3):
            if abs(ratio - std) < 0.05:
                return True
    return False


def _crop_to_mult_region(input_path):
    """全屏截图 → 裁剪左侧 1/3 区域（技能倍率面板所在位置）。
    返回裁剪后的临时图片路径，非全屏则返回原路径。"""
    from PIL import Image
    import tempfile
    img = Image.open(input_path)
    w, h = img.size
    if not _is_fullscreen_image(w, h):
        return input_path
    # 严格取左侧 1/3：倍率面板在屏幕左 33.3%
    left, top = 0, 0
    right, bottom = w // 3, h
    cropped = img.crop((left, top, right, bottom))
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cropped.save(path, "PNG")
    _logger.info("全屏截图 %d×%d → 倍率识别裁剪左半区 (%d×%d)", w, h, right - left, bottom - top)
    return path


def _crop_to_echo_region(input_path):
    """全屏截图 → 裁剪右上 1/4 区域（声骸卡片所在位置）。
    排除右下技能描述/套装效果/特征码等干扰信息。
    非全屏则返回原路径。"""
    from PIL import Image
    import tempfile
    img = Image.open(input_path)
    w, h = img.size
    if not _is_fullscreen_image(w, h):
        return input_path
    # 严格取右上 1/4：声骸卡片位于屏幕右上半区
    left, top = w // 2, 0
    right, bottom = w, h // 2
    cropped = img.crop((left, top, right, bottom))
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cropped.save(path, "PNG")
    _logger.info("全屏截图 %d×%d → 声骸裁剪右上 1/4 (%d×%d)", w, h, right - left, bottom - top)
    return path


def _add_image_padding(input_path, padding=40):
    """给图片四周加边距，帮助 OCR 检测紧贴边缘的文字。
    padding: 最小边距；实际值 = max(padding, 图片短边 × 5%)，自适应分辨率。"""
    from PIL import Image
    import tempfile
    img = Image.open(input_path)
    w, h = img.size
    padding = max(padding, int(min(w, h) * 0.05))
    corners = [img.getpixel((0, 0)), img.getpixel((w - 1, 0)),
               img.getpixel((0, h - 1)), img.getpixel((w - 1, h - 1))]
    if isinstance(corners[0], int):
        bg = sum(corners) // 4
    else:
        bg = tuple(sum(c[i] for c in corners) // 4 for i in range(len(corners[0])))
    new_w, new_h = w + 2 * padding, h + 2 * padding
    padded = Image.new(img.mode, (new_w, new_h), bg)
    padded.paste(img, (padding, padding))
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    padded.save(path, "PNG")
    return path


def _extract_cost_via_crop(padded_path, cost_bbox):
    """在 COST 标签附近裁剪并做针对性 OCR，提取费用数字 (1/3/4)。
    cost_bbox: (x_min, y_min, x_max, y_max) 为 COST 文字的外接矩形（图像坐标）。
    返回 int 或 None。
    """
    from PIL import Image, ImageFilter, ImageOps
    import tempfile
    try:
        img = Image.open(padded_path)
    except Exception as e:
        _logger.warning("COST 裁剪打开图片失败: %s", e)
        return None
    w, h = img.size

    cx_min, cy_min, cx_max, cy_max = cost_bbox
    cost_h = cy_max - cy_min
    digit_left = cx_max + 5
    digit_right = min(cx_max + 200, w)
    digit_top = max(0, int(cy_min - cost_h * 1.5))
    digit_bottom = min(int(cy_max + cost_h * 1.5), h)

    if digit_right <= digit_left or digit_bottom <= digit_top:
        return None

    crop = img.crop((digit_left, digit_top, digit_right, digit_bottom))
    scale = 3
    crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    gray = crop.convert("L")

    def _ocr_on_preprocessed(preprocessed):
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        preprocessed.save(tmp, "PNG")
        try:
            ocr, _ = _get_ocr()
            if ocr is None:
                return None
            result, _ = ocr._ocr(tmp)
        except Exception as e:
            _logger.warning("COST 区域 OCR 识别失败: %s", e)
            return None
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        if not result:
            return None
        for _, text, _ in result:
            nums = re.findall(r'\d+', text)
            for ns in nums:
                n = int(ns)
                if n in (1, 3, 4):
                    return n
        return None

    # —— 路径 1：Median 去噪 + OTSU 二值化 ——
    g1 = gray.filter(ImageFilter.MedianFilter(3))
    try:
        import cv2
        import numpy as np
        arr = np.array(g1)
        _, arr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        g1 = Image.fromarray(arr)
    except Exception:
        g1 = g1.point(lambda p: 0 if p < 128 else 255)
    dark_px = sum(1 for x in range(g1.width) for y in range(g1.height)
                  if g1.getpixel((x, y)) < 128)
    if dark_px > g1.width * g1.height * 0.7:
        g1 = ImageOps.invert(g1)

    cost_digit = _ocr_on_preprocessed(g1)
    if cost_digit is not None:
        return cost_digit

    # —— 路径 1b：OTSU 失败 → 自适应阈值（光照不均补偿） ——
    try:
        import cv2
        import numpy as np
        arr = np.array(gray.filter(ImageFilter.MedianFilter(3)))
        arr = cv2.adaptiveThreshold(
            arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 3
        )
        ath = Image.fromarray(arr)
        dark_px = sum(1 for x in range(ath.width) for y in range(ath.height)
                      if ath.getpixel((x, y)) < 128)
        if dark_px > ath.width * ath.height * 0.7:
            ath = ImageOps.invert(ath)
        cost_digit = _ocr_on_preprocessed(ath)
        if cost_digit is not None:
            return cost_digit
    except Exception as e:
        _logger.debug("自适应阈值 1b 失败: %s", e)

    # —— 路径 2：跳过 Median 滤波（保留细笔画 "1"），OTSU 二值化 ——
    g2 = gray
    try:
        import cv2
        import numpy as np
        arr = np.array(g2)
        _, arr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        g2 = Image.fromarray(arr)
    except Exception:
        g2 = g2.point(lambda p: 0 if p < 128 else 255)
    dark_px = sum(1 for x in range(g2.width) for y in range(g2.height)
                  if g2.getpixel((x, y)) < 128)
    if dark_px > g2.width * g2.height * 0.7:
        g2 = ImageOps.invert(g2)

    cost_digit = _ocr_on_preprocessed(g2)
    if cost_digit is not None:
        return cost_digit

    # —— 路径 2b：OTSU 失败 → 自适应阈值（无 Median） ——
    try:
        import cv2
        import numpy as np
        arr = np.array(gray)
        arr = cv2.adaptiveThreshold(
            arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 3
        )
        ath = Image.fromarray(arr)
        dark_px = sum(1 for x in range(ath.width) for y in range(ath.height)
                      if ath.getpixel((x, y)) < 128)
        if dark_px > ath.width * ath.height * 0.7:
            ath = ImageOps.invert(ath)
        cost_digit = _ocr_on_preprocessed(ath)
        if cost_digit is not None:
            return cost_digit
    except Exception as e:
        _logger.debug("自适应阈值 2b 失败: %s", e)

    # —— 路径 3：反相后 OCR（尝试亮底暗字场景） ——
    g3 = ImageOps.invert(gray)
    cost_digit = _ocr_on_preprocessed(g3)
    if cost_digit is not None:
        return cost_digit

    return None


def _match_stat_name(ocr_text):
    """对 OCR 文本做模糊匹配，返回 (标准词条名, 置信度) 或 (None, 0)"""
    import difflib
    if not ocr_text:
        return None, 0
    clean = ocr_text.strip()
    # 精确匹配
    for name in _ALL_STAT_NAMES:
        if clean == name:
            return name, 1.0
    # 别名匹配
    for canonical, aliases in _OCR_STAT_ALIASES.items():
        for alias in aliases:
            if alias.lower() in clean.lower():
                return canonical, 0.95
    # difflib 模糊匹配
    best = difflib.get_close_matches(clean, _ALL_STAT_NAMES, n=1, cutoff=0.72)
    if best:
        return best[0], difflib.SequenceMatcher(None, clean, best[0]).ratio()
    return None, 0


def _parse_ocr_results(ocr_results):
    """从 PaddleOCR 3.x predict() 结果中提取声骸信息。

    声骸卡片布局（从上到下逐行扫描）：
      第1行：声骸名称、等级、合鸣标识 → 忽略
      第2行：COST4/3/1 + Z弃置 + C锁定 → 只取 COST
      第3行：主词条（名称 + 数值，有 % 则为百分比）
      第4行：固定词条（固定生命/固定攻击/固定防御 + 数值）
      第5-9行：副词条（名称 + 数值，有 % 则为百分比）
    """
    empty = {"cost": None, "main_stat": None, "fixed_stat": None, "sub_stats": [], "raw_lines": []}
    if not ocr_results:
        return empty

    page = ocr_results[0] if isinstance(ocr_results, list) else ocr_results
    rec_texts = page.get("rec_texts", [])
    rec_scores = page.get("rec_scores", [])
    dt_polys = page.get("dt_polys", [])

    if not rec_texts:
        return empty

    # —— 构建条目列表 ——
    entries = []
    for i, (text, conf) in enumerate(zip(rec_texts, rec_scores)):
        bbox = dt_polys[i] if i < len(dt_polys) else None
        if bbox is not None and len(bbox) >= 4:
            x_center = sum(p[0] for p in bbox) / 4
            y_center = sum(p[1] for p in bbox) / 4
            h = max(p[1] for p in bbox) - min(p[1] for p in bbox)
        else:
            x_center, y_center, h = 0, float(i), 10
        entries.append({"text": text.strip(), "confidence": conf,
                        "x": x_center, "y": y_center, "height": h})

    raw_lines = [e["text"] for e in entries]
    entries.sort(key=lambda e: (e["y"], e["x"]))

    # —— 污染检测：统计已知词条名的出现率 ——
    def _known_stat_hits(entry_list):
        """返回 (命中数, 总数)，命中 = entry 文本匹配已知词条别名或纯数值。"""
        hits = 0
        for e in entry_list:
            t = e["text"].strip()
            if not t:
                continue
            # 纯数字/百分比（含小数）→ 可能是数值
            if re.match(r'^[\d,.]+\s*%?$', t):
                hits += 1
                continue
            # 匹配已知词条别名
            for alias, _ in _SORTED_ALIASES:
                if alias.lower() in t.lower():
                    hits += 1
                    break
            else:
                # COST / +25 / 合鸣 / 声骸技能 / 简述 等 UI 污染
                # PP-OCRv5 检测范围更大，需覆盖更多 UI 标签
                if re.search(r'COST|合鸣|声骸|简述|推荐|筛选|全部|冷却|召唤|装配|'
                             r'伤害加成提升|技能冷却|共鸣回响|鸣式|虚造|更换|'
                             r'切换|详情|强化|卸下|一键|排序|锁定|解锁|'
                             r'\+25|\+\s*25', t, re.IGNORECASE):
                    continue
                # 短文本（≤2字）可能是污染标签
                if len(t) <= 2:
                    hits += 0.5  # 半信
        return (hits, len(entry_list))

    # —— 全屏截图：根据 COST 位置定位右侧声骸卡片区域 ——
    cost_pattern = re.compile(
        r'COST\s*(\d)|费用?\s*(\d)|費\s*(\d)|(\d)\s*[费費]|(\d)\s*cost|COST(\d)|cost(\d)',
        re.IGNORECASE
    )
    # 降低触发阈值：>25 条就可能是全屏截图
    if len(entries) > 25:
        cost_x = None
        for e in entries:
            m = cost_pattern.search(e["text"])
            if m:
                cost_x = e["x"]
                break
        if cost_x is not None:
            all_x = [e["x"] for e in entries]
            img_width = max(all_x) - min(all_x) if all_x else 1000
            # 全屏截图：以 COST 为中心，取右侧 50% 图宽，确保名+值都在范围内
            region_margin = max(img_width * 0.50, 400)
            entries = [e for e in entries if abs(e["x"] - cost_x) < region_margin]

            # —— 污染复检：过滤后仍>15条且命中率<20%，再做更紧的空间裁剪 ——
            if len(entries) > 15:
                hits, total = _known_stat_hits(entries)
                ratio = hits / total if total > 0 else 0
                if ratio < 0.20:
                    # 重污染：收紧到右侧区域（声骸卡片在屏幕右侧）
                    tight_margin = max(img_width * 0.25, 200)
                    entries = [e for e in entries
                               if abs(e["x"] - cost_x) < tight_margin
                               and e["x"] >= cost_x - 80]

    # —— 按 Y 聚类为行 ——
    if entries:
        avg_h = sum(e["height"] for e in entries) / len(entries)
    else:
        avg_h = 14
    line_threshold = max(avg_h * 0.65, 8)

    lines = []  # [[entries in same row], ...]
    for e in entries:
        placed = False
        for line in lines:
            if abs(e["y"] - line[0]["y"]) < line_threshold:
                line.append(e)
                placed = True
                break
        if not placed:
            lines.append([e])

    for line in lines:
        line.sort(key=lambda e: e["x"])

    def _line_text(line):
        return " ".join(e["text"] for e in line)

    lines.sort(key=lambda line: sum(e["y"] for e in line) / len(line))

    # —— 找 COST 行 ——
    cost = None
    cost_line_idx = None
    _cost_label_re = re.compile(r'COST|费用?|費', re.IGNORECASE)

    # 提前定义：后续 COST 候选评分需要用到
    _value_re_early = re.compile(r'([\d,]+\.?\d*)\s*(%|％)?')

    def _quick_stat_name(text):
        """快速词条名匹配（COST 候选评分用，不依赖 _match_stat_name 的模糊匹配）"""
        clean = re.sub(r'^[\s＋+\->↗]+', '', text.strip())
        for alias, canonical in _SORTED_ALIASES:
            if alias.lower() in clean.lower():
                return canonical
        return None

    # 第一遍：收集所有 COST 候选行索引
    _cost_candidates = []  # [(line_idx, cost_value or None), ...]
    for idx, line in enumerate(lines):
        m = cost_pattern.search(_line_text(line))
        if m:
            c = None
            for g in m.groups():
                if g and g.isdigit():
                    c = int(g)
                    break
            if c in (1, 3, 4):
                _cost_candidates.append((idx, c))
            elif _cost_label_re.search(_line_text(line)):
                _cost_candidates.append((idx, None))
        elif _cost_label_re.search(_line_text(line)):
            # 只有 COST 标签，数字在相邻行
            _cost_candidates.append((idx, None))

    if _cost_candidates:
        # 简单规则：同行有 COST+数字 > 同行 COST 无数字 > 无 COST
        # 同行有数字的 COST 最可靠（如 "COST 4"），直接取它
        _with_digit = [(idx, c) for idx, c in _cost_candidates if c is not None]
        if _with_digit:
            # 有同行数字：多个时选周围词条最多的
            if len(_with_digit) == 1:
                cost = _with_digit[0][1]
                cost_line_idx = _with_digit[0][0]
            else:
                _best_idx, _best_cost, _best_score = _with_digit[0][0], _with_digit[0][1], -1
                for cand_idx, cand_cost in _with_digit:
                    _names_found = sum(1 for ahead in range(cand_idx + 1, min(cand_idx + 20, len(lines)))
                                      if _quick_stat_name(_line_text(lines[ahead])))
                    if _names_found > _best_score:
                        _best_score, _best_idx, _best_cost = _names_found, cand_idx, cand_cost
                cost, cost_line_idx = _best_cost, _best_idx
        else:
            # 全都没有同行数字（都是孤立的 "COST" 标签）→ 选周围词条最多的
            _best_idx, _best_cost, _best_score = _cost_candidates[0][0], None, -1
            for cand_idx, _ in _cost_candidates:
                _names_found = sum(1 for ahead in range(cand_idx + 1, min(cand_idx + 20, len(lines)))
                                  if _quick_stat_name(_line_text(lines[ahead])))
                if _names_found > _best_score:
                    _best_score, _best_idx = _names_found, cand_idx
            cost, cost_line_idx = None, _best_idx
    else:
        # 没有候选 —— 走原来的逻辑，扫描全行找 COST 数字
        cost = None
        cost_line_idx = None

    # 如果最佳候选没有直接读到的数字，从附近行提取
    if cost is None:
        # 策略：从最佳 COST 候选行出发，向上下扫描附近行
        # 先尝试直接提取数字 1/3/4，再尝试字符别名恢复（如 "G"→4）
        _scan_center = _best_idx if _cost_candidates else 0
        # 按 Y 距离从近到远检查周围行
        _center_y = sum(e["y"] for e in lines[_scan_center]) / len(lines[_scan_center])
        _nearby = sorted(
            [i for i in range(len(lines)) if i != _scan_center],
            key=lambda i: abs((sum(e["y"] for e in lines[i]) / len(lines[i])) - _center_y)
        )
        # 先尝试直接提取数字
        for adj in _nearby[:5]:
            adj_text = _line_text(lines[adj]).strip()
            nums = re.findall(r'\d+', adj_text)
            for ns in nums:
                n = int(ns)
                if n in (1, 3, 4):
                    cost = n
                    cost_line_idx = _scan_center
                    break
            if cost is not None:
                break
        # 直接提取失败 → 字符别名恢复（处理 OCR 误读）
        if cost is None:
            _digit_aliases = {
                # ——— 1 ———
                "Z": 1, "z": 1, "乙": 1, "l": 1, "I": 1, "|": 1,
                "i": 1, "¡": 1, "¹": 1, "⒈": 1,
                # ——— 3 ———
                "了": 3, "ō": 3, "ヨ": 3, "Ξ": 3,
                # ——— 4 ———
                "乡": 4, "午": 4, "キ": 4,
                "G": 4, "g": 4, "C": 4, "c": 4,  # PP-OCRv5 常见：4 → G/C
            }
            # 优先检查最佳 COST 候选行附近的字符（而非全图扫描）
            _alias_scan = [_scan_center] + _nearby[:6]
            for idx in _alias_scan:
                line = lines[idx]
                for e in line:
                    t = e["text"].strip()
                    if t in _digit_aliases:
                        cost = _digit_aliases[t]
                        cost_line_idx = _scan_center
                        break
                    # 通用单字符匹配
                    if len(t) == 1 and t not in _digit_aliases:
                        if t.isalpha() and t.upper() in ("Z", "I", "L"):
                            cost = 1
                            cost_line_idx = _scan_center
                            break
                if cost is not None:
                    break

    # —— 噪声行预过滤：如果总行数>10且已知词条命中率<30%，剔除明显是UI污染的整行 ——
    if len(lines) > 10:
        line_texts = [_line_text(ln) for ln in lines]
        _noise_kw = (
            r'声骸技能|合鸣效果|简述|推荐|筛选|全部|冷却|召唤|装配|伤害加成提升|'
            r'技能冷却|共鸣回响|鸣式|虚造|装配该|首位|对敌人|造成|伤害。|使用声骸|'
            r'技能。|攻击目标|破空幻|八段|九段|十段|的一段|并造成|'
            r'更换|切换|详情|强化|卸下|一键|排序|锁定|解锁|'
            r'\+25|\+\s*25'
        )
        _noise_re = re.compile(_noise_kw, re.IGNORECASE)
        valid_lines = []
        _cost_line_kept = None  # 记录 COST 行在过滤后的新索引
        for i, lt in enumerate(line_texts):
            if not lt.strip():
                continue
            # COST 行保护：不删除
            if i == cost_line_idx:
                valid_lines.append(i)
                _cost_line_kept = len(valid_lines) - 1
                continue
            # 已知词条名保护：含词条名别名的行不受噪声过滤（如 "攻击 +25"）
            _has_stat_name = any(alias.lower() in lt.lower()
                                for alias, _ in _SORTED_ALIASES)
            if _noise_re.search(lt) and not _has_stat_name:
                continue
            # 纯数字且不是合理的属性值 → 噪声
            clean = re.sub(r'\s*%?\s*$', '', lt.strip())
            if re.match(r'^[\d,]+$', clean) and len(clean) <= 3:
                valid_lines.append(i)
                continue
            valid_lines.append(i)
            # 记录 COST 行在新数组中的位置
            if i == cost_line_idx:
                _cost_line_kept = len(valid_lines) - 1
        # 只有确实过滤掉了行才替换
        if len(valid_lines) < len(lines):
            lines = [lines[i] for i in valid_lines]
            # 修正 cost_line_idx 到过滤后的位置
            if _cost_line_kept is not None:
                cost_line_idx = _cost_line_kept

    # —— 从上到下逐行扫描，收集词条 ——
    value_re = re.compile(r'([\d,]+\.?\d*)\s*(%|％)?')

    def _find_stat_name(text):
        """返回 (canonical_name, is_fixed) 或 (None, False)"""
        # 清理 OCR 常见噪音前缀（全角/半角加号、箭头等）
        clean = re.sub(r'^[\s＋+\->↗]+', '', text.strip())
        for alias, canonical in _SORTED_ALIASES:
            if alias.lower() in clean.lower():
                return (canonical, canonical.startswith("固定"))
        name, score = _match_stat_name(clean)
        if score > 0.55:
            return (name, name.startswith("固定"))
        return (None, False)

    def _extract_value(text):
        """从文本提取 (value_float, is_percent)，没有则 (None, False)"""
        m = value_re.search(text)
        if m:
            try:
                return (float(m.group(1).replace(",", "")), m.group(2) is not None)
            except ValueError:
                pass
        return (None, False)

    stats = []  # [(name, value, is_percent, is_fixed), ...]
    pending_name = None  # 上一行的词条名（等下一行给数值）
    pending_fixed = False

    start = cost_line_idx + 1 if cost_line_idx is not None else 0
    for idx in range(start, len(lines)):
        text = _line_text(lines[idx])

        # 跳过纯 UI 元素（含 PP-OCRv5 误读的 COST 残影字符）
        if re.match(r'^[ZzCcGg棄锁棄鎖鎖\s\.\,\;\:\-\—\+]+$', text):
            continue

        name, is_fixed = _find_stat_name(text)
        val, is_pct = _extract_value(text)

        if name and val is not None:
            # 同行有名称和数值 → 完整词条
            if pending_name:
                stats.append((pending_name, 0.0, False, pending_fixed))
                pending_name = None
            stats.append((name, val, is_pct, is_fixed))
        elif name and val is None:
            # 只有名称没有数值 → 暂存，等下一行
            if pending_name:
                stats.append((pending_name, 0.0, False, pending_fixed))
            pending_name = name
            pending_fixed = is_fixed
        elif not name and val is not None:
            # 只有数值没有名称 → 配给上一行 pending
            if pending_name:
                stats.append((pending_name, val, is_pct, pending_fixed))
                pending_name = None
            # 否则是孤立数值，忽略
        else:
            # 既没有名称也没有数值 → 普通文字，跳过
            pass

    if pending_name:
        stats.append((pending_name, 0.0, False, pending_fixed))

    # —— 根据数值是否带 % 修正歧义名称 ——
    # "生命"/"攻击"/"防御" 可以是百分比（生命值/攻击力/防御力）也可以是固定值
    # 无数值有 % → 百分比版；无 % → 固定值版
    _PCT_TO_FLAT = {"攻击力": "固定攻击", "生命值": "固定生命", "防御力": "固定防御"}
    for i, (name, val, is_pct, is_fixed) in enumerate(stats):
        if name in _PCT_TO_FLAT and not is_pct:
            stats[i] = (_PCT_TO_FLAT[name], val, is_pct, True)

    # —— 按位置分配：stat 0=主词条, stat 1=固定词条, stat 2+=副词条 ——
    # 游戏里固定词条只显示"攻击：150"不带"固定"前缀，靠 OCR 文本不可靠
    main_stat = None
    fixed_stat = None
    sub_stats = []
    stat_pos = 0

    for name, val, is_pct, is_fixed in stats:
        if stat_pos == 0:
            main_stat = {"name": name, "value": val, "is_percent": is_pct}
        elif stat_pos == 1:
            fixed_stat = {"name": name, "value": val}
        else:
            sub_stats.append({"name": name, "value": val, "is_percent": is_pct})
        stat_pos += 1

    # —— 后解析质量验证：主词条或固定词条异常 → 标记为污染 ——
    _valid_main_names = ["暴击率", "暴击伤害", "攻击力", "生命值", "防御力",
                         "治疗效果加成", "共鸣效率"]
    _valid_main_names += [f"{e}伤害加成" for e in ("冷凝", "热熔", "气动", "导电", "衍射", "湮灭")]
    if main_stat and main_stat.get("name", "") not in _valid_main_names:
        # main_stat 名不在已知列表 → 可能是垃圾识别
        main_stat = None
    if fixed_stat and fixed_stat.get("name", "").startswith("固定") and fixed_stat.get("value", 0) <= 0:
        fixed_stat = None

    # —— 固定词条反推/纠正 COST ——
    # 游戏铁律：4c→固定攻击150, 3c→固定攻击100, 1c→固定生命2280
    # 固定词条数值大、易识别，比 OCR 直接读 COST 数字更可靠。
    # 当 COST 未识别 或 COST 与固定词条冲突时，以固定词条为准。
    if fixed_stat:
        fname = fixed_stat.get("name", "")
        fval = fixed_stat.get("value", 0)
        _inferred = None
        if fname == "固定攻击" and abs(fval - 150) < 1:
            _inferred = 4
        elif fname == "固定攻击" and abs(fval - 100) < 1:
            _inferred = 3
        elif fname == "固定生命" and abs(fval - 2280) < 1:
            _inferred = 1
        if _inferred is not None:
            if cost is None:
                cost = _inferred
            elif cost != _inferred:
                cost = _inferred  # 固定词条纠错：以游戏铁律为准

    # 调试：将行文本和解析结果附加到 raw_lines 后方，方便定位问题
    debug_lines = raw_lines[:]
    debug_lines.append("")
    debug_lines.append("--- 逐行解析结果 ---")
    for i in range(start, len(lines)):
        lt = _line_text(lines[i])
        if lt.strip():
            debug_lines.append(f"  Line {i}: [{lt}]")
    debug_lines.append("--- 识别词条 ---")
    debug_lines.append(f"  COST: {cost}")
    debug_lines.append(f"  主词条: {main_stat}")
    debug_lines.append(f"  固定词条: {fixed_stat}")
    for j, s in enumerate(sub_stats[:5]):
        debug_lines.append(f"  副词条{j+1}: {s}")

    return {
        "cost": cost,
        "main_stat": main_stat,
        "fixed_stat": fixed_stat,
        "sub_stats": sub_stats[:5],
        "raw_lines": debug_lines,
    }


# ==================== 伤害倍率图文识别 ====================

_SKILL_CATEGORIES = ["常态攻击", "共鸣技能", "共鸣回路", "共鸣解放", "变奏技能"]


def _parse_dmg_formula(formula):
    """解析伤害倍率公式字符串
    返回 (hits: list[dict], basis: str)
    hits 每项: {"mult": float, "count": int}
    basis: "攻击力" / "防御力" / "生命值"
    """
    text = formula.strip()
    basis = "攻击力"
    if "防御" in text:
        basis = "防御力"
        text = text.replace("防御", "")
    elif "生命" in text:
        basis = "生命值"
        text = text.replace("生命", "")
    text = text.replace("(", "").replace(")", "")
    hits = []
    for comp in text.split("+"):
        comp = comp.strip()
        if not comp:
            continue
        m = re.match(r'([\d,]+\.?\d*)\s*%\s*(?:\*\s*(\d+))?', comp)
        if m:
            mult = float(m.group(1).replace(",", ""))
            count = int(m.group(2)) if m.group(2) else 1
            hits.append({"mult": mult, "count": count})
    return hits, basis


def _parse_dmg_mult_ocr_results(ocr_results):
    """解析游戏伤害倍率界面 OCR 结果，返回 (list[dict], debug_text)。
    debug_text 包含逐行解析和识别倍率，用于 OCR 确认对话框显示。"""
    rec_texts = []
    for page in (ocr_results or []):
        rec_texts.extend(page.get("rec_texts", []))
    if not rec_texts:
        return [], ""

    full_text = "\n".join(rec_texts)
    # 逐行调试文本
    _debug_lines = ["--- 逐行解析结果 ---"]
    for i, t in enumerate(rec_texts):
        t = t.strip()
        if t:
            _debug_lines.append(f"  Line {i}: [{t}]")

    # 技能分类按行跟踪（全屏截图下多个标签同时可见，全局扫描会误判）
    current_skill = None

    # 要跳过的非伤害行关键词（仅对不含百分比公式的行生效）
    _SKIP_KW = ["耐力消耗", "冷却时间", "回复", "协奏能力", "耐力",
                "lv.", "Lv.", "LV.", "等级", "缓存", "轮", "tok", "v4-pro",
                "总结", "优化", "修改", "完成", "识别", "测试", "记录", "更新",
                "文件", "编辑", "查看", "转到", "选择", "资源", "管理器",
                "打开", "大纲", "问题", "输出", "调试", "控制台", "终端",
                "PS C:", "Python", "WWDmgCalc", ".py", ".md", ".png", ".json"]

    # 常态攻击下的子分类
    _SUB_SKILLS = {"普攻": "普攻", "重击": "重击"}

    # 百分比公式
    _PCT_RE = re.compile(
        r'[\d,]+\.?\d*\s*%\s*(?:\*\s*\d+)?'
        r'(?:\s*\+\s*[\d,]+\.?\d*\s*%\s*(?:\*\s*\d+)?)*'
    )

    results = []
    current_sub_skill = None  # 追踪子分类（普攻/重击）
    prev_line = ""  # 上一行文本（用于名称换行回溯）

    # ── 预处理：合并跨行倍率（上行以 + 结尾时合并下一行） ──
    _pure_formula_re = re.compile(r'^[\d,]+\.?\d*\s*%')
    _trailing_plus_re = re.compile(r'[\d,]+\.?\d*\s*%\+$')
    _sys_terms = {'共鸣技能', '常态攻击', '共鸣解放', '共鸣回路', '变奏技能', '普攻', '重击',
                  '技能介绍', '技能详情', '战术性调整', 'Lv.6', '1秒'}
    merged_texts = []
    for lineno in range(len(rec_texts)):
        cur = rec_texts[lineno].strip()
        prev = merged_texts[-1] if merged_texts else ""
        # 1. 单字中文碎片（如 "害"）→ 拼到最近的非公式行
        if (merged_texts and len(cur) <= 2 and '\u4e00' <= cur[0] <= '\u9fff'
                and cur not in _sys_terms):
            insert_idx = len(merged_texts) - 1
            while insert_idx >= 0 and _pure_formula_re.match(merged_texts[insert_idx]):
                insert_idx -= 1
            if insert_idx >= 0:
                merged_texts[insert_idx] = merged_texts[insert_idx] + cur
            else:
                merged_texts.append(cur)
        # 2. 倍率跨行合并：上行以 + 结尾 + 下行纯倍率
        elif (merged_texts and
              _pure_formula_re.match(cur) and
              _trailing_plus_re.search(prev)):
            merged_texts[-1] = prev + cur
        else:
            merged_texts.append(cur)

    for line in merged_texts:
        line = line.strip()
        if not line:
            continue
        # 跳过非伤害行（但如果行内包含百分比公式则不跳过，如"治疗量 2090+77%攻击"）
        has_formula = bool(_PCT_RE.search(line))
        if not has_formula and any(kw in line for kw in _SKIP_KW):
            continue
        # 子分类行（普攻/重击）——切换子分类状态
        if line in _SUB_SKILLS:
            current_sub_skill = _SUB_SKILLS[line]
            continue
        # 技能分类行：切换当前技能分类，重置子分类
        if line in _SKILL_CATEGORIES:
            current_skill = line
            current_sub_skill = None
            continue

        # 查找百分比公式
        fm = _PCT_RE.search(line)
        if not fm:
            # 没有百分比的行，可能是下一行的伤害名称，记下来
            if not any(kw in line for kw in ["lv.", "Lv.", "LV.", "等级", "技能介绍", "技能详情"]):
                prev_line = line
            continue

        formula = fm.group(0)

        # 从公式之后的文本判断数值基础类型
        after = line[fm.end():]
        basis = "攻击力"
        if "防御" in after:
            basis = "防御力"
        elif "生命" in after:
            basis = "生命值"

        # 解析公式
        hits, _ = _parse_dmg_formula(formula)
        if not hits:
            continue

        # 提取伤害名称（百分比之前的部分，即当前行的左侧文字内容）
        damage_name = line[:fm.start()].strip()
        # 清理首尾符号：括号/数字/运算符（OCR 分割残留如 "627+", "(5.50%*2+"）
        damage_name = re.sub(r'^[\s\d＋+\-*Xx/()（）]+', '', damage_name)
        damage_name = re.sub(r'[\s\d＋+\-*Xx/()（）]+$', '', damage_name)
        damage_name = re.sub(r'[\s,，。、：:]+$', '', damage_name)
        # 如果当前行没有有效名称，回溯上一行
        if not damage_name and prev_line:
            damage_name = re.sub(r'^[\s\d＋+\-*Xx/()（）]+', '', prev_line.strip())
            damage_name = re.sub(r'[\s,，。、：:]+$', '', damage_name)
            prev_line = ""
        # 回溯后仍无名称 → 放弃
        if not damage_name:
            continue

        # —— 伤害名称质量验证：过滤明显的噪声 ——
        # 名称太短（≤1 个中文字）且不是回溯来的 → 可能是噪声
        _name_chars = re.findall(r'[\u4e00-\u9fff]', damage_name)
        if len(_name_chars) < 2:  # 至少 2 个中文字才算有效伤害名称
            continue
        # 名称含文件扩展名或代码特征 → 噪声
        if re.search(r'\.(py|md|png|json|txt|ico|svg|exe|dll)\b', damage_name, re.IGNORECASE):
            continue
        if re.search(r'[A-Za-z]{10,}', damage_name):  # 长英文单词 → 不是游戏内容
            continue

        # —— 根据技能分类和子分类解析最终技能类型 ——
        resolved_skill = None
        if current_skill == "常态攻击":
            # 优先用子分类（重击/普攻），其次看伤害名称是否含"重击"，默认普攻
            if current_sub_skill:
                resolved_skill = current_sub_skill
            elif "重击" in damage_name:
                resolved_skill = "重击"
            else:
                resolved_skill = "普攻"
        elif current_skill == "共鸣回路":
            resolved_skill = None  # 默认为 "(无)"，用户自行选择
        elif current_skill == "变奏技能":
            resolved_skill = "变奏技能"
        else:
            resolved_skill = current_skill  # 共鸣技能 / 共鸣解放 直接使用

        # 构建标签前缀: 技能分类_伤害名称
        label_prefix_parts = []
        if current_skill:
            label_prefix_parts.append(current_skill)
        label_prefix_parts.append(damage_name)
        label_prefix = "_".join(label_prefix_parts)

        # 一个 formula 部件（+ 分隔的每一项）生成一条结果
        # *N 次数合并在标签中显示（如 _34.3%*5），base_mult 存单次倍率
        for hit in hits:
            # 构造倍率文字
            mult_str = format(hit["mult"], ".10g") + "%"
            if hit["count"] > 1:
                mult_str += f"*{hit['count']}"

            label = f"{label_prefix}_{mult_str}"
            results.append({
                "label": label,
                "skill": resolved_skill,
                "category": current_skill if current_skill in _SKILL_CATEGORIES else "",
                "basis": basis,
                "base_mult": hit["mult"],
                "mult_increase": 0.0,
                "mult_boosts": [0.0, 0.0, 0.0],
                "element": None,
                "effect": None,
            })

    # —— 后过滤：排除非伤害倍率（治疗/回复/能量/耐力/冷却等） ——
    _NON_DMG_KW = ["治疗", "回复", "耐力", "冷却", "消耗", "能量", "协奏"]
    _filtered = []
    for r in results:
        label = r["label"]
        # 从 label 中提取伤害名称（格式: 技能分类_伤害名称_倍率）
        parts = label.split("_")
        # 伤害名称是第二部分（跳过技能分类）
        dmg_name = parts[1] if len(parts) > 1 else ""
        if any(kw in dmg_name for kw in _NON_DMG_KW):
            continue
        _filtered.append(r)

    # —— 去重：同一技能+倍率+基准出现多次时，保留伤害名称最长（OCR 最完整）的 ——
    _dedup = {}
    for r in _filtered:
        # 从 label 提取伤害名称（格式: 技能分类_伤害名称_倍率）
        _parts = r["label"].split("_")
        _dname = _parts[1] if len(_parts) > 1 else ""
        key = (_dname, round(r["base_mult"], 4), r["basis"])
        if key not in _dedup:
            _dedup[key] = r
        else:
            # 比较伤害名称长度，保留更长的
            def _dmg_name(item):
                parts = item["label"].split("_")
                return parts[1] if len(parts) > 1 else ""
            old_name = _dmg_name(_dedup[key])
            new_name = _dmg_name(r)
            if len(new_name) > len(old_name):
                _dedup[key] = r
    _filtered = list(_dedup.values())

    # 有效数量检测：至少要有 1 条有效结果
    if len(_filtered) < 1:
        _logger.warning("倍率解析结果不足：0 条，判定为无效")
        _debug_lines.append("--- 识别倍率 ---")
        _debug_lines.append("  (无有效倍率)")
        return [], "\n".join(_debug_lines)

    # 组装调试文本：逐行解析 + 识别倍率
    _debug_lines.append("--- 识别倍率 ---")
    for it in _filtered:
        skill = it.get("skill") or "(无)"
        elem = it.get("element") or "(无)"
        _debug_lines.append(
            f"  {it['label']}  |  倍率:{it.get('base_mult',0):.10g}%  |  "
            f"基准:{it.get('basis','攻击力')}  |  技能:{skill}  |  元素:{elem}"
        )
    return _filtered, "\n".join(_debug_lines)


class OCRWorker(QThread):
    """后台线程执行 OCR，避免阻塞 UI。
    parser: 可选的自定义解析函数，接收 raw OCR results，返回解析后的数据。
            不传则默认使用 _parse_ocr_results（声骸识别）。
            传入 _parse_dmg_mult_ocr_results 则用于伤害倍率识别。
    """
    finished = pyqtSignal(object)     # 解析后的结果列表
    error = pyqtSignal(str)           # 错误消息
    progress = pyqtSignal(int, int)   # (已完成数, 总数)

    def __init__(self, sources, parser=None):
        """sources: list[tuple[image_source, is_qimage]]"""
        super().__init__()
        self.sources = sources
        self._parser = parser
        self._abort = False

    def abort(self):
        """中断 OCR 识别：设置标志位，线程安全退出。
        注意：不使用 terminate()——在 Windows 上会因 TerminateThread
        导致 Python 解释器状态损坏，引起闪退。当前正在处理的图片会跑完，
        但 run() 循环在下一轮检查到 _abort 后立即退出。"""
        self._abort = True

    def _process_one(self, ocr, source, is_qimage):
        """处理单张图片，返回 raw OCR results。
        声骸识别：全屏截图裁剪右上 1/4（声骸卡片位置）。
        倍率识别：全屏截图裁剪左侧 1/3（技能面板位置）。
        裁剪后无有效结果则回退原图。
        """
        is_echo_ocr = (self._parser is None)  # 默认 parser = 声骸识别
        crop_fn = _crop_to_echo_region if is_echo_ocr else _crop_to_mult_region
        tmp_path = None
        if is_qimage:
            tmp_path = _qimage_to_temp_file(source)
            original = tmp_path
            cropped = crop_fn(tmp_path)
        else:
            original = source
            cropped = crop_fn(source)
        was_cropped = (cropped != original)

        def _do_ocr_and_fix(img_path, ref_cost_img):
            """对 img_path 做 OCR + COST 针对性修复，返回 results。"""
            padded = _add_image_padding(img_path)
            try:
                results = ocr.predict(padded)
                _cost_re = re.compile(r'COST\s*(\d)|(\d)\s*cost', re.IGNORECASE)
                cost_found = any(
                    _cost_re.search(t)
                    for r in (results or [])
                    for t in r.get("rec_texts", [])
                )
                if not cost_found and results:
                    cost_box = None
                    for r in results:
                        for i, t in enumerate(r.get("rec_texts", [])):
                            if re.search(r'COST|费用?|費', t, re.IGNORECASE):
                                polys = r.get("dt_polys", [])
                                if i < len(polys) and len(polys[i]) >= 4:
                                    b = polys[i]
                                    cost_box = (min(p[0] for p in b), min(p[1] for p in b),
                                                max(p[0] for p in b), max(p[1] for p in b))
                                break
                        if cost_box:
                            break
                    if cost_box:
                        cost_digit = _extract_cost_via_crop(padded, cost_box)
                        if cost_digit is not None:
                            target = results[0] if results else {}
                            target.setdefault("rec_texts", [])
                            target.setdefault("rec_scores", [])
                            target.setdefault("dt_polys", [])
                            target["rec_texts"].insert(0, str(cost_digit))
                            target["rec_scores"].insert(0, 0.99)
                            x0, y0, x1, y1 = cost_box
                            target["dt_polys"].insert(0, [[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
                return results
            finally:
                try:
                    os.remove(padded)
                except OSError:
                    pass

        results = _do_ocr_and_fix(cropped, cropped)

        # —— 裁剪回退检测：裁剪后无有效内容 → 用原图重试 ——
        if was_cropped:
            all_text = []
            for r in (results or []):
                all_text.extend(r.get("rec_texts", []))
            meaningful = [t for t in all_text
                         if len(t.strip()) > 2 and not re.match(r'^\+?\d+$', t.strip())]
            if is_echo_ocr:
                has_key = any(re.search(r'COST|费用?|費|\b[134]\b', t, re.IGNORECASE)
                             for t in all_text)
            else:
                has_key = any(re.search(r'\d+\.?\d*\s*%', t) for t in all_text)
            if not has_key or len(meaningful) < 3:
                _logger.info("裁剪结果无效 (type=%s, has_key=%s, meaningful=%d)，回退原图",
                            "echo" if is_echo_ocr else "mult", has_key, len(meaningful))
                results = _do_ocr_and_fix(original, cropped)

        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return results

    def run(self):
        try:
            ocr, err = _get_ocr()
            if ocr is None:
                msg = f"OCR 引擎初始化失败：\n{err}" if err else "OCR 引擎未安装。\n请在终端执行: pip install rapidocr-onnxruntime"
                self.error.emit(msg)
                return

            parse = self._parser if self._parser else _parse_ocr_results
            total = len(self.sources)
            results_list = []
            for i, (source, is_qimage) in enumerate(self.sources):
                if self._abort:
                    break
                try:
                    raw = self._process_one(ocr, source, is_qimage)
                    data = parse(raw)
                    results_list.append(data)
                except Exception as e:
                    _logger.warning("OCRWorker 单张图片解析失败: %s", e)
                    results_list.append(None)
                self.progress.emit(i + 1, total)

            self.finished.emit(results_list)
        except Exception as exc:
            _logger.exception("OCRWorker 线程异常: %s", exc)
            self.error.emit(str(exc))

