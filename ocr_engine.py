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
        # 降低阈值以捕获大字 COST 数字、小字 Z/X 等被检测模型过滤的内容
        self._ocr = RapidOCR(
            text_score=0.2,
            det_thresh=0.15,
            det_box_thresh=0.25,
            det_model_path=None,
            det_limit_side_len=1280,
        )

    def predict(self, image_path):
        """返回与 PaddleOCR predict() 相同格式的结果列表"""
        # 调用时也降低识别阈值，防止低置信度的大字 / 单字符被丢弃
        result, _ = self._ocr(image_path, text_score=0.2, box_thresh=0.25)
        rec_texts, rec_scores, dt_polys = [], [], []
        if result:
            for box, text, conf in result:
                rec_texts.append(text)
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
    """判断宽高是否接近常见显示器分辨率（±6% 容差）。"""
    _monitor_res = [(1920, 1080), (2560, 1440), (3840, 2160),
                    (1366, 768), (1680, 1050), (1920, 1200)]
    for mw, mh in _monitor_res:
        if abs(w - mw) <= mw * 0.06 and abs(h - mh) <= mh * 0.06:
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
    left, top = 0, 0
    right, bottom = w // 2, h
    cropped = img.crop((left, top, right, bottom))
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cropped.save(path, "PNG")
    _logger.info("全屏截图 %d×%d → 倍率识别裁剪左半区 (%d×%d)", w, h, right - left, bottom - top)
    return path


def _crop_to_echo_region(input_path):
    """全屏截图 → 裁剪右上"口"字区域（声骸卡片所在位置）。
    非全屏则返回原路径。"""
    from PIL import Image
    import tempfile
    img = Image.open(input_path)
    w, h = img.size
    if not _is_fullscreen_image(w, h):
        return input_path
    # 裁剪右上 1/4："田"字的右上"口"
    left, top = w // 2, 0
    right, bottom = w, h // 2
    cropped = img.crop((left, top, right, bottom))
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cropped.save(path, "PNG")
    _logger.info("全屏截图 %d×%d → 声骸裁剪右上区域 (%d×%d)", w, h, right - left, bottom - top)
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
                if re.search(r'COST|合鸣|声骸|简述|推荐|筛选|全部|冷却|召唤|装配|伤害加成提升|技能冷却|共鸣回响|鸣式|虚造|\+25', t, re.IGNORECASE):
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

    for idx, line in enumerate(lines):
        m = cost_pattern.search(_line_text(line))
        if m:
            c = None
            for g in m.groups():
                if g and g.isdigit():
                    c = int(g)
                    break
            if c in (1, 3, 4):
                cost = c
                cost_line_idx = idx
                break

    # 同一行没找到数字 → COST 标签和数字被 OCR 拆到相邻行
    if cost is None:
        for idx, line in enumerate(lines):
            lt = _line_text(line)
            if _cost_label_re.search(lt):
                # 按 Y 距离排序取最近的几行（COST 数字可能因字号不同被归到邻近行）
                line_y = sum(e["y"] for e in line) / len(line)
                nearby = sorted(
                    [i for i in range(len(lines)) if i != idx],
                    key=lambda i: abs(
                        (sum(e["y"] for e in lines[i]) / len(lines[i])) - line_y
                    )
                )
                for adj in nearby[:4]:
                    adj_text = _line_text(lines[adj]).strip()
                    nums = re.findall(r'\d+', adj_text)
                    for ns in nums:
                        n = int(ns)
                        if n in (1, 3, 4):
                            cost = n
                            cost_line_idx = idx
                            break
                    if cost is not None:
                        break
                    # 短行纯数字但被 OCR 误读 → 尝试还原
                    if len(adj_text) <= 4 and nums:
                        for ns in nums:
                            n = int(ns)
                            # 两位数：30→3, 40→4, 33→3, 44→4
                            if 10 <= n <= 99:
                                d = n // 10 if n % 10 == 0 else n // 11
                                if d in (1, 3, 4) and n in (d * 10, d * 11):
                                    cost = d
                                    cost_line_idx = idx
                                    break
                            # 三位数：300→3, 400→4, 150→(取首位)1
                            if 100 <= n <= 999 and n % 10 == 0:
                                d = n // 100
                                if d in (1, 3, 4):
                                    cost = d
                                    cost_line_idx = idx
                                    break
                        if cost is not None:
                            break
                if cost is not None:
                    break

    # COST 同行字符被 OCR 误读 → 字符级恢复（如 "1" 被读成 "Z"）
    if cost is None:
        for idx, line in enumerate(lines):
            lt = _line_text(line)
            if not _cost_label_re.search(lt):
                continue
            # 去掉 COST 标签，分析同行剩余文本
            remainder = _cost_label_re.sub("", lt).strip()
            # 逐个词条检查（保留原始分词顺序）
            _digit_aliases = {
                # ——— 1 ———
                "Z": 1, "z": 1, "乙": 1, "l": 1, "I": 1, "|": 1,
                "i": 1, "¡": 1, "¹": 1, "⒈": 1,
                # ——— 3 ———
                "了": 3, "ō": 3, "ヨ": 3, "Ξ": 3,
                # ——— 4 ———
                "乡": 4, "午": 4, "キ": 4,
            }
            for e in line:
                t = e["text"].strip()
                if t in _digit_aliases:
                    cost = _digit_aliases[t]
                    cost_line_idx = idx
                    break
                # 通用单字符匹配：单字母/符号被误读
                if len(t) == 1 and t not in _digit_aliases:
                    if t.isalpha() and t.upper() in ("Z", "I", "L"):
                        # Z → 1, I → 1, L → 1 (common OCR confusion for "1")
                        cost = 1
                        cost_line_idx = idx
                        break
            if cost is not None:
                break

    # —— 噪声行预过滤：如果总行数>10且已知词条命中率<30%，剔除明显是UI污染的整行 ——
    if len(lines) > 10:
        line_texts = [_line_text(ln) for ln in lines]
        _noise_kw = (
            r'声骸技能|合鸣效果|简述|推荐|筛选|全部|冷却|召唤|装配|伤害加成提升|'
            r'技能冷却|共鸣回响|鸣式|虚造|装配该|首位|对敌人|造成|伤害。|使用声骸|'
            r'技能。|\+25'
        )
        _noise_re = re.compile(_noise_kw, re.IGNORECASE)
        valid_lines = []
        _cost_line_kept = None  # 记录 COST 行在过滤后的新索引
        for i, lt in enumerate(line_texts):
            if not lt.strip():
                continue
            if _noise_re.search(lt):
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

        # 跳过纯 UI 元素
        if re.match(r'^[ZzCc弃锁棄鎖\s\.]+$', text):
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

    # —— 固定词条反推 COST（COST 数字未被识别时使用） ——
    if cost is None and fixed_stat:
        fname = fixed_stat.get("name", "")
        fval = fixed_stat.get("value", 0)
        if fname == "固定攻击" and abs(fval - 150) < 1:
            cost = 4
        elif fname == "固定攻击" and abs(fval - 100) < 1:
            cost = 3
        elif fname == "固定生命" and abs(fval - 2280) < 1:
            cost = 1

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
    """解析游戏伤害倍率界面 OCR 结果，返回 (list[dict], raw_text)"""
    rec_texts = []
    for page in (ocr_results or []):
        rec_texts.extend(page.get("rec_texts", []))
    if not rec_texts:
        return [], ""

    full_text = "\n".join(rec_texts)

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

    for line in rec_texts:
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

    # —— 去重：同一倍率+基准出现多次时，保留伤害名称最长（OCR 最完整）的 ——
    _dedup = {}
    for r in _filtered:
        key = (round(r["base_mult"], 4), r["basis"])
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
        return [], full_text

    return _filtered, full_text


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

