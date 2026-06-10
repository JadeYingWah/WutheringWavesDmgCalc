# 预设系统：乘区化改造 + 倍率支持

## 目标

1. 预设数据写入要映射到数据流各乘区（上游基础值 → 中游效果/独立乘区 → 倍率乘区）
2. 角色预设的结果列表要跟主程序 ResultListPage 一致，显示所有乘区
3. 倍率乘区（base_mult / mult_increase / mult_boosts）加入角色预设
4. 抗性/防御用默认值（1.0），预设只写原始数据

## 涉及文件

| 文件 | 改动程度 | 说明 |
|------|---------|------|
| `preset_builder.py` | **大** | 加倍率输入、结果列表改为乘区预览 |
| `preset_manager.py` | 中 | JSON 结构更新、apply_preset 写入倍率 |
| `preset_loader.py` | 小 | 预览显示倍率信息 |

不改 `WWDmgCalc.py`（约束：不拆主文件）。

---

## Phase 1: preset_manager.py — 倍率数据支持

### 1.1 更新 JSON 结构注释（顶部注释块）

character 部分增加 `multiplier` 字段：

```
"character": { "name", "element", "effect", "base_hp", "base_atk", "base_def",
               "multiplier": { "base_mult", "mult_increase", "mult_boosts": [...] },
               "resonance_chain": [ { "effects": [...], "indep_zones": [...] }, ... ] },
```

### 1.2 apply_preset() — 写入倍率到 ResultPage

在 `apply_preset()` 中应用角色基础属性之后，加：

```python
multiplier = char_data.get("multiplier", {})
if multiplier:
    rp = main_screen.page_result
    rp.base_mult.setValue(multiplier.get("base_mult", 100.0))
    rp.mult_increase.setValue(multiplier.get("mult_increase", 0.0))
    for i, v in enumerate(multiplier.get("mult_boosts", [0, 0, 0])):
        if i < len(rp.mult_boosts):
            rp.mult_boosts[i].setValue(v)
```

### 1.3 validate_preset() — 软校验

```python
if "multiplier" in c:
    mult = c["multiplier"]
    if not isinstance(mult, dict):
        return False, "character.multiplier 必须是对象"
```

向后兼容：旧预设无 multiplier 字段，读取时用 `.get("multiplier", {})` + 默认值。

---

## Phase 2: preset_builder.py — 基本页加倍率输入

### 2.1 _CharacterPresetWindow._build_basic_tab()

在"基础数值"GroupBox 之后，添加"倍率设置"GroupBox：

```
基础倍率(%):  [100.0]    ← self.mult_base (QDoubleSpinBox, 0~99999, 4位小数)
倍率增加(%):  [0.0]      ← self.mult_increase
倍率提升1(%): [0.0]      ← self.mult_boosts[0]
倍率提升2(%): [0.0]      ← self.mult_boosts[1]
倍率提升3(%): [0.0]      ← self.mult_boosts[2]
```

### 2.2 to_dict() 更新

```python
"multiplier": {
    "base_mult": self.mult_base.value(),
    "mult_increase": self.mult_increase.value(),
    "mult_boosts": [s.value() for s in self.mult_boosts],
}
```

### 2.3 load_data() 更新

```python
mult = data.get("multiplier", {})
self.mult_base.setValue(mult.get("base_mult", 100.0))
self.mult_increase.setValue(mult.get("mult_increase", 0.0))
for i, v in enumerate(mult.get("mult_boosts", [0, 0, 0])):
    if i < len(self.mult_boosts):
        self.mult_boosts[i].setValue(v)
```

---

## Phase 3: preset_builder.py — 结果列表改为乘区预览

这是最大的改动。当前结果列表是共鸣链效果的扁平卡片展示，改为乘区化预览。

### 3.1 新增 _compute_preset_zones() 方法

在 `_CharacterPresetWindow` 中添加，执行独立的乘区计算：

1. 收集 `self._chain_data` 所有 7 链的 effects
2. 用 `damage_calc.py` 的关键词常量分类：
   - 攻击力百分比/固定 → base zone
   - 伤害加成/伤害提升 → bonus zone（排除暴伤关键词）
   - 加深 → deepen zone
   - 暴击率 → crit rate（基础 5%）
   - 暴击伤害/暴伤 → crit dmg（基础 150%）
3. 收集所有 indep_zones → independent zone
4. 读取倍率输入 → multiplier zone
5. 防御=1.0，抗性=1.0（默认值）
6. 计算：`base_dmg = base_zone * bonus * deepen * def * res * indep * mult / 100`
7. 返回所有乘区值 + 分类后的 items 列表

需要从 `damage_calc.py` 导入常量（无 GUI 依赖，可直接 import）：
```python
from damage_calc import BONUS_SUFFIX, DEEPEN_SUFFIX, CRIT_RATE_KEYWORDS, CRIT_DMG_KEYWORDS
```

### 3.2 新增 _refresh_result_preview() 方法

替代当前的 `_refresh_result_list()`：

1. 调用 `_compute_preset_zones()` 获取数据
2. 延迟导入 `_render_process_html`：
   ```python
   def _get_render_fn():
       from WWDmgCalc import _render_process_html
       return _render_process_html
   ```
3. 调用 `_render_process_html()` 生成 HTML（navigate_fn=None, summary_pages=None → 链接不可点击但格式一致）
4. 用 QTextEdit（read-only, RichText）显示 HTML
5. 下方保留效果卡片作为明细参考

### 3.3 重建 _build_result_tab()

新布局：

```
┌─────────────────────────────────────────┐
│ 倍率设置（与基本页同步）                   │
│ 基础倍率: [100]  倍率增加: [0]            │
│ 倍率提升1/2/3: [0] [0] [0]              │
│ 计算基点: [攻击力 ▼]                      │
├─────────────────────────────────────────┤
│ 乘区预览（QTextEdit, HTML 渲染）          │
│ ┌─────────────────────────────────────┐ │
│ │ 基础数值: ...                        │ │
│ │ 加成乘区: ...                        │ │
│ │ 加深乘区: ...                        │ │
│ │ 暴击率: ...                          │ │
│ │ 暴击乘区: ...                        │ │
│ │ 防御乘区: 1.0000 (默认)              │ │
│ │ 抗性乘区: 1.0000 (默认)              │ │
│ │ 独立乘区: ...                        │ │
│ │ 倍率乘区: ...                        │ │
│ │ 最终伤害: ...                        │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ 效果明细（原 _PresetResultCard 卡片）     │
│ [card1] [card2] [card3]                 │
│ [card4] [card5] ...                     │
└─────────────────────────────────────────┘
```

### 3.4 倍率输入同步

结果页和基本页的倍率输入共享同一份数据。方案：

- `self._multiplier_data = {"base_mult": 100.0, "mult_increase": 0.0, "mult_boosts": [0, 0, 0]}`
- 结果页的 spinbox 的 `valueChanged` 信号 → 更新 `_multiplier_data` → 触发 `_refresh_result_preview()`
- 基本页的 spinbox 同理
- `to_dict()` 和 `load_data()` 读写 `_multiplier_data`

或者更简单：结果页不放独立的 spinbox，直接读基本页的 `self.mult_base` / `self.mult_increase` / `self.mult_boosts` 的值。在结果页放一个"刷新预览"按钮，或在切换到结果页标签时自动刷新（`tabs.currentChanged` 信号）。

**选择方案 B**（更简单）：结果页不重复倍率输入，只在切换到结果页标签时自动计算预览。结果页顶部只显示"计算基点"选择器 + 一个刷新按钮。

---

## Phase 4: preset_loader.py — 预览显示倍率

### 4.1 _fmt_char() 更新

在基础数值行之后、共鸣链详情之前，添加倍率摘要：

```python
mult = c.get("multiplier", {})
if mult:
    bm = mult.get("base_mult", 100)
    mi = mult.get("mult_increase", 0)
    mb = mult.get("mult_boosts", [0, 0, 0])
    lines.append(f"倍率: 基础{bm}% + 增加{mi}%  提升:{'/'.join(f'{b}%' for b in mb)}")
    lines.append("")
```

---

## 实施顺序

1. **Phase 1** — preset_manager.py（最小改动，无 UI 影响）
2. **Phase 2** — preset_builder.py 基本页加倍率
3. **Phase 3** — preset_builder.py 结果页改为乘区预览（最大改动）
4. **Phase 4** — preset_loader.py 预览更新

## 验证

- 运行 `pytest tests/` 确保 186 个测试通过
- 手动测试：创建角色预设 → 设置倍率 → 切换到结果页 → 确认乘区预览正确
- 手动测试：保存预设 → 重新加载 → 确认倍率数据保留
- 手动测试：使用预设 → 确认倍率写入 ResultPage
- 手动测试：旧预设（无 multiplier 字段）仍能正常加载和应用
