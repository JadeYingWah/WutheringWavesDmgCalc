# WutheringWavesDmgCalc 项目总结

> 生成: 2026-05-30 | 更新: 2026-06-08 | 版本: v0.9

---

## 一、项目概览

**WutheringWavesDmgCalc** 是《鸣潮》(Wuthering Waves) 的伤害计算器桌面应用。基于 PyQt6，主模块 + 7 个拆分模块（主编 [WWDmgCalc.py](../WWDmgCalc.py) ~9560 行），支持暗色/亮色双主题、OCR 识别、存档管理、基础数值手动覆盖、错误日志系统、使用手册。项目使用 **Git** 做版本管理，可随时回退到历史状态。

### ⚠️ 当前开发状态（v0.9）

**以下功能正在开发中，尚未完成：**

| 模块 | 状态 | 说明 |
|------|------|------|
| 预设系统 | 🔧 开发中 | `preset_manager.py` / `preset_builder.py` / `preset_loader.py` 框架已搭建，UI 已创建，但端到端测试未完成 |
| 预设构建器 | 🔧 开发中 | 角色/武器/声骸套装预设的分页式编辑器，UI 已创建但功能未完全验证 |
| GitHub 集成 | ⏳ 待实现 | 官方预设从 GitHub 同步功能预留，repo 未上传时显示友好提示 |

### 文件结构

```
WutheringWavesDmgCalc/
│
├── .gitignore                            # Git 忽略规则（排除 build/dist/cache/日志）
├── WWDmgCalc.py                          # 主程序（~9560 行，已拆分 7 个模块）
├── damage_calc.py                        # ★ 独立计算引擎（纯函数/零 GUI，主程序和测试共用）
├── theme_system.py                       # ★ 主题配色系统（~460行，从主编拆分）
├── enemy_res.py                          # ★ 抗性数值页（~510行，从主编拆分）
├── char_base_page.py                     # ★ 角色武器页（~140行，从主编拆分）
├── indep_zone.py                         # ★ 独立乘区页（~310行，从主编拆分）
├── summary_pages.py                      # ★ 数值总结页（~620行，从主编拆分，含副名称双向同步）
├── ocr_engine.py                         # ★ OCR 图文识别引擎（~1100行，从主编拆分）
│
├── tests/                                # 🧪 自动化测试
│   ├── __init__.py
│   ├── run_tests_gui.py                  #     测试运行器（GUI 窗口）
│   ├── test_damage_formula.py            #     伤害公式测试（71 个用例）
│   └── test_save_format.py              #     存档格式测试（14 个用例）
│
├── docs/                                 # 📄 文档
│   └── PROJECT_SUMMARY.md                #     项目总结（本文件）
│
├── error_handler/                        # 🛡 错误处理
│   ├── __init__.py
│   ├── error_system.py                   # ★ 错误日志系统（从主编拆分，~450行）
│   ├── error_viewer.py                   #     外部错误报告程序（闪退后自动启动）
│   └── test_crash.py                     #     闪退测试脚本（模拟崩溃）
│
├── config/                               # ⚙ 用户偏好
│   ├── auto_all_config.json              #     "一键全自动"开关状态（启动时读取，1 行 JSON）
│   └── error_log.json                    #     错误日志（跨会话保留、结构存储、最多 500 条）
│
├── packaging/                            # 📦 打包
│   └── WWDmgCalc.spec                    #     PyInstaller 打包参数（入口/数据文件/图标）
│
├── save/                                 # 💾 用户存档
│   └── 赞妮[测试效应加深和重击加深是否相同乘区].json  # 存档示例（JSON，含全部页面状态）
│
├── defaultsave/                          # 🎁 预设存档（由用户自行放入，JSON 格式同 save/）
│
├── manual/                               # 📖 使用手册
│   ├── content.json                      #     手册内容（HTML 片段，按章节 key 索引）
│   └── images/                           #     手册内嵌图片
│       ├── 官方维基角色基础数值例图.png        #         角色基础数值对照截图
│       ├── 基础数值调整窗口使用步骤教程.png     #         覆盖功能使用说明截图
│       ├── 角色基础数值例图.png               #         游戏内角色属性面板截图
│       └── 武器基础数值例图.png               #         游戏内武器属性面板截图
│
├── ico/                                  # 🖼 应用图标
│   ├── assemble_ico.py                   #     多分辨率 .ico 组装脚本（Pillow）
│   ├── icon.ico                          #     最终图标文件（供 PyInstaller 使用）
│   ├── Wico16.ico  /  Wico16.svg         #     16×16 源文件
│   ├── Wico24.ico  /  Wico24.svg         #     24×24 源文件
│   ├── Wico32.ico                        #     32×32（由 36×36 SVG 转换后自动降为 32）
│   ├── Wico36.svg                        #     36×36 SVG 源文件
│   ├── Wico48.ico  /  Wico48.svg         #     48×48 源文件
│   ├── Wico64.ico  /  Wico64.svg         #     64×64 源文件
│   ├── Wico128.ico /  Wico128.svg        #     128×128 源文件
│   └── Wico256.ico /  Wico256.svg        #     256×256 源文件
│
└── dist/                                 # 🚀 分发包（PyInstaller 输出，可删除后重新打包）
    └── WWDmgCalc/                        #     独立运行目录
        ├── WWDmgCalc.exe                 #         可执行文件
        └── _internal/                    #         运行时依赖（.pyd / .dll 等）
```

### 技术栈

| 技术 | 用途 |
|------|------|
| PyQt6 | GUI 框架 |
| rapidocr-onnxruntime | OCR（声骸面板 + 技能倍率） |
| OpenCV (cv2) | 图像预处理 |
| difflib | 游戏文字模糊匹配 |
| JSON | 存档 / 配置 / 手册 |
| pytest | 自动化测试（86 个用例，0.2s 完成） |
| Git | 版本管理（提交历史，随时回退） |
| PyInstaller | 打包 .exe |

### 安装依赖

```bash
pip install PyQt6 rapidocr-onnxruntime opencv-python numpy Pillow pytest
```

打包另需 `pip install pyinstaller`。

---

## 二、UI 架构

### 侧边栏

```
┌─────────────┐
│  鸣潮计算器   │  标题
│  [返回]      │  回欢迎页
│  [使用手册]   │  → ManualDialog（根据当前页面定位章节）
│  [基础数值调整]│  → BaseOverrideDialog（启用时显示 ✓ + accent 色）
│ ─────────── │  分割线
│  导航树      │  5 大分类
└─────────────┘
```

### 导航树（5 分类，~14 页面）

| 分类 | 颜色 | 页面 |
|------|------|------|
| 角色与武器 | 橙 `#ff5722` | char_base — 角色基础 + 武器基础 |
| | | chain_buff — 共鸣链增益（卡片式，6 链） |
| 数值来源 | 蓝 `#1976d2` | echo_counter / echo_N — 声骸管理 |
| | | combined_perm — 综合常驻 buff |
| | | combined_trigger — 综合触发 buff |
| 综合填写 | 蓝 `#1976d2` | keyword_assoc — 关键词关联 |
| 数值总结 | 绿 `#388e3c` | summary_base / bonus / deepen / crit / indep |
| 敌人减伤 | 青 `#00838f` | enemy_defense — 防御减伤 |
| | | enemy_resistance — 抗性数值 |
| 计算结果 | 紫 `#7b1fa2` | result — 伤害计算 |
| | | result_list — 结果卡片列表 |

---

## 三、数据流

```
CharBasePage ──────────┐
CombinedEntryPage × 2 ─┤  ← 共鸣链效果自动同步到此
EchoPage × N ──────────┘
        │
        ▼ _collect_all_items() → [(name, value, src, nav_key, seq), ...]
        │
  ┌─────┼─────────────────┬──────────────────┐
  ▼     ▼                 ▼                  ▼
防御页  抗性页        4 个总结页          结果页
        │            (隐藏/锁定/删除)    (筛选+倍率→过程)
        │                 │                  │
        └─────────┬───────┘                  ▼
                  ▼                     结果列表页
              重算回调链               (卡片/锁定/自动更新)
```

### 回调链

任意来源页变更（含共鸣链同步） → `_on_change_cb` →
1. `EnemyDefensePage.recalc()` + `EnemyResistancePage._recalc()`
2. 四个 `SummaryPage.recalc()`
3. `ResultPage.auto_compute()`（受自动计算开关控制）
4. `ResultListPage.recalc()`（受自动更新开关控制）

### 伤害公式

```
敌方基础防御 = 792 + 8 × 敌人等级
敌方最终防御 = 敌方基础防御 × (1 − 无视防御合计)
def_zone   = (800 + 8 × 角色等级) / (敌方最终防御 + 800 + 8 × 角色等级)

base_zone  = (角色基础 + 武器基础) × (1 + 百分比加成/100) + 固定值
bonus_zone = 1 + Σ(伤害加成)/100
deepen_zone= 1 + Σ(伤害加深)/100
crit_zone  = (150 + Σ(暴击伤害))/100
crit_rate  = 5 + Σ(暴击率)
res_zone   = 1 − 最终抗性/100（≥0） 或 1 − 最终抗性/200（<0）
indep_zone = Π(独立乘区组因子)
mult_zone  = (基础倍率 + 倍率增加) × Π(1 + 倍率增幅/100)

最终伤害 = base × bonus × deepen × crit × def × res × indep × mult / 100
```

---

## 四、核心类（29 个，仅主编；拆分模块另有约 15 个）

### GUI 组件

| 类 | 行 | 说明 |
|----|-----|------|
| `NavTree` | 589 | 侧边栏导航树，平滑滚动动画 |
| `WelcomeScreen` | 654 | 欢迎页 |
| `SearchCombo` | 691 | 可搜索下拉框，模糊过滤 |
| `AttrListItem` | 945 | 单条属性行（名称/数值/锁定/删除） |
| `BaseTableAttrPage` | 1051 | 表格属性编辑基类 |
| `CombinedEntryPage` | 1248 | 综合填写页（含来源选择器、隐藏/锁定） |
| `EchoCounterItem` | 1451 | 声骸列表项 |
| `LoadingOverlay` | 2105 | 半透明加载遮罩 + 转圈动画 |
| `PropTable` | 3735 | 等比列宽表格 |
| `MarqueeLabel` | 5883 | 走马灯标签（溢出自动滚动、悬停暂停） |
| `FlowLayout` | 6681 | 流式布局（计算过程曾用） |

### 数据页面

| 类 | 行 | 说明 |
|----|-----|------|
| `EchoCounterPage` | 2996 | 声骸管理（增删、OCR 导入，限 5 个 / cost ≤ 12） |
| `EchoPage` | 3390 | 单声骸编辑（cost/主词条/副词条） |
| `CharBasePage` | — | 角色 + 武器基础属性 |
| `KeywordAssociationPage` | 1084 | 关键词关联管理（手动+共鸣链效果，序列号区分来源） |
| `ResonanceBuffPage` | 3990 | 共鸣链增益卡片页（6 卡，启用/关闭联动综合填写） |
| `EnemyDefensePage` | 3554 | 防御减伤（等级/无视/穿透 + 外部来源整合） |
| `EnemyResistancePage` | 3905 | 抗性（6 元素 + 3 种预设世界/塔/全息） |
| `IndepZonePage` | 5295 | 独立乘区（组内加算、组间乘算） |
| `ResultPage` | 6688 | 伤害计算（筛选/倍率/计算过程 HTML） |
| `ResultListPage` | 5962 | 结果卡片列表（锁定/批量/自动更新） |

### 汇总页面（均继承 SummaryBasePage）

| 类 | 说明 |
|----|------|
| `SummaryBasePage` (4705) | 基类：来源表格 + 隐藏/锁定 + 高亮动画 |
| `SummaryBaseZonePage` | 基础乘区（攻/生/防分列） |
| `SummaryBonusZonePage` | 加成乘区（伤害加成/提升） |
| `SummaryDeepenZonePage` | 加深乘区 |
| `SummaryCritZonePage` | 暴击乘区（暴击率 5% 底 + 暴伤 150% 底） |

### 弹窗

| 类 | 行 | 说明 |
|----|-----|------|
| `SubStatDialog` | 3350 | 副词条选择 |
| `OCRConfirmDialog` | 2169 | OCR 结果确认（多 Tab） |
| `DamageMultConfirmDialog` | 2644 | 技能倍率 OCR 确认（6 列可编辑表格） |
| `ResultDetailDialog` | 4840 | 结果详情（编辑/重算/锁定/删除） |
| `ResonanceChainEditDialog` | 4232 | 共鸣链编辑（2 页：通用增益 / 特定增益，联动综合填写+关键词关联） |
| `QuickLoadDialog` | 4621 | 存档选择 |
| `BaseOverrideDialog` | 8989 | 基础数值手动覆盖 |
| `ManualDialog` | 8994 | 使用手册（浏览 + 编辑模式，非模态） |
| `ErrorReportDialog` | 453 | 错误日志查看（非模态） |
| `ErrorDetailDialog` | 301 | 单条错误详情（自动分析 + 建议） |

### 数据/逻辑

| 类 | 行 | 说明 |
|----|-----|------|
| `_RapidOCRAdapter` | 1549 | RapidOCR 适配器 |
| `OCRWorker(QThread)` | 2037 | 后台 OCR 线程 |
| `SaveManager` | 4278 | 存档读/写/状态收集/恢复（静态方法） |
| `MainScreen` | 8605 | 主界面：侧边栏 + 页面栈 + 全部跨页回调 |
| `DmgCalculator` | 9228 | 应用窗口：主题/存档工具栏/全局自动 |

---

## 五、基础数值手动覆盖

### 背景
游戏内对每个百分比加成单独乘基础值后取整（量子化），理论计算与游戏实际值存在偏差。用户可手动输入游戏内显示值来同步。

### 流程

```
侧边栏 [基础数值调整] → BaseOverrideDialog
  ├── 显示当前自动计算值（参考）
  ├── QDoubleSpinBox 输入手动值
  └── [启用] / [取消] 切换
        │
        ▼ callback(enabled, value)
MainScreen._on_base_override_changed()
  ├── → ResultPage.set_base_override()
  │      └── compute() 中：computed_base_zone 存原始值
  │          if enabled → base_zone = override_value
  ├── → ResultListPage.set_base_override()
  │      └── _recalc_one() 中：同上
  │          _refresh_cards() 刷新卡片
  └── → _update_all() 强制重算结果列表
```

### 提示位置

| 位置 | 内容 | 条件 |
|------|------|------|
| 侧边栏按钮 | `基础数值调整 ✓` + accent 色 | 启用时 |
| 计算结果 — 基础数值行 | 值正常显示 + 下方蓝色提示 `▸ 已启用手动填写基础数值` | 启用时 |
| 计算过程 HTML | `▸ 已启用手动填写，原本计算值: xxx`（`#64b5f6`，换行） | 启用时 |
| 结果卡片 | `基础数值（手动填写）` 或 `（原本数值）`（`#64b5f6`，始终显示） | 始终 |
| 展开详情弹窗 | `▸ 已启用手动填写基础数值`（`#64b5f6`） | 启用时 |

### 存档集成
- `collect_full_state()` → `base_override_enabled` + `base_override_value`
- `apply_state()` → 恢复状态 → 传播到页面 → 若弹窗打开则 `reset_state()` → 重算
- 加载存档**不覆盖**当前主题

---

## 六、OCR 系统

### 声骸面板识别（EchoCounterPage）
- 支持多图片（≤5 张）、截图或文件导入
- 图像预处理：中值滤波 → OTSU 二值化 → 反色 → 自适应阈值 fallback
- 全屏截图自动裁剪右侧声骸卡片区域（以 COST 为锚点，X 轴 50% 图宽容差）
- 噪声行预过滤（声骸技能/合鸣效果/简述/+25 等关键词）
- COST 行保护：噪声过滤不删除 COST 定位行，过滤后重新计算索引
- 数值识别增强：小数（44.0%）匹配模式加 `.` 支持
- `+` 前缀兼容：词条名匹配前清理全角/半角加号噪音前缀
- 后解析验证：主词条名不在已知列表 → 丢弃；至少 2 条有效数据才算成功
- 模糊匹配：`difflib.get_close_matches` 对照 `_OCR_STAT_ALIASES`
- `OCRConfirmDialog` 多 Tab 确认

### 技能倍率识别（ResultPage）
- 正则解析技能名称、倍率、基准（ATK/HP/DEF），上限 10 张截图
- 全屏截图自动裁剪左半区（技能面板位置）
- 噪声过滤：不含公式的行触发跳过关键词；含百分比公式的行不受拦截
- 技能分类按行跟踪：全屏截图下多个标签同时可见时，伤害行归入最近的技能分类（而非全局扫描第一个匹配）
- OCR 分辨率提升：`det_limit_side_len` 960→1280，全屏裁切后不再缩放，笔画密集的汉字（如"掀"）不再丢失
- 伤害名称清洗：去除括号、数字、运算符等 OCR 分割残留
- 后过滤：自动排除治疗/回复/耐力/冷却/协奏等非伤害倍率
- 智能去重：同一 (倍率, 基准) 多次出现时，保留伤害名称最长的（残缺名被完整名覆盖）
- 右侧原始文本分两个区域：`逐行解析结果` + `识别倍率`
- `DamageMultConfirmDialog` 6 列表格确认
- 失败时写入错误日志 + 弹窗提示可查看错误报告

---

## 七、存档系统

### 格式

```json
{
  "version": 1, "app": "WWDmgCalc",
  "timestamp": "...", "name": "",
  "pages": {
    "char_base": {}, "combined_perm": {}, "combined_trigger": {},
    "enemy_defense": {}, "enemy_resistance": {},
    "echo_counter": {}, "echo_pages": {},
    "result": {}, "summary_indep": {}, "result_list": {}
  },
  "base_override_enabled": false,
  "base_override_value": 0.0,
  "hidden_items": [], "locked_items": [], "hidden_echo_ids": []
}
```

### 操作
- 快速保存 / 快速加载（按时间排序） / 导入 / 导出 / 预设
- `SaveManager.apply_state()` → 重建全部页面 + 跨页绑定 + 覆盖状态

---

## 八、主题系统

### 架构

主题系统位于 [theme_system.py](../theme_system.py)，提供：
- **`THEMES` 字典**：存储暗色/亮色两套主题的完整颜色配置
- **`build_stylesheet(theme)` 函数**：根据主题名称生成完整的 Qt 样式表

### 颜色配置

#### 暗色主题（默认）

| 色值 | 颜色 | 用途 |
|------|------|------|
| `bg` | `#1a1a2e` | 主窗口 / 欢迎页 / 主界面 背景 |
| `bg_secondary` | `#16213e` | 右侧内容区 (contentArea) 背景 |
| `bg_card` | `#0f3460` | 卡片 (QGroupBox, resultCard, indepGroupFrame) |
| `text` | `#e6e6e6` | 正文 (QLabel, QCheckBox, QComboBox, 导航树, QGroupBox) |
| `text_secondary` | `#a0a0b0` | 次要文字 (labelSecondary, 按钮, 表头, 提示) |
| `accent` | `#e94560` | 强调色 (标题, 结果数值, 链接, 选中态, 聚焦边框) |
| `accent_hover` | `#ff6b81` | 强调色悬停 |
| `btn_bg` | `#e94560` | 主按钮背景 (startButton, addButton, itemAddBtn, calcBtn) |
| `btn_hover` | `#ff6b81` | 主按钮悬停 |
| `btn_pressed` | `#c0392b` | 主按钮按下 |
| `sidebar_bg` | `#16213e` | 左侧导航栏背景 |
| `sidebar_hover` | `#1a3a5c` | 导航树 hover / 列表项 hover / 卡片 hover |
| `border` | `#2a2a4a` | 边框 (QGroupBox, 表格, 卡片, 输入框, 分割线) |
| `input_bg` | `#16213e` | 输入框背景 (QSpinBox, QComboBox, QListWidget) |
| `input_border` | `#2a2a4a` | 输入框边框 |
| `input_focus` | `#e94560` | 输入框聚焦边框 |
| `checkbox_bg` | `#e94560` | 复选框选中背景 |
| `alt_row` | `rgba(255,255,255,0.025)` | 表格交替行背景 |
| `nav_selected_bg` | `#1a2a44` | 导航树选中项背景 / 按钮激活态背景 |
| `scrollbar_handle` | `#a0a0b0` | 滚动条滑块 |
| `scrollbar_handle_hover` | `#e94560` | 滚动条滑块悬停 |
| `header_grad_end` | `#16213e` | 表头渐变终点色 |
| `card_title_bg` | `#1a2a44` | 预设卡片标题栏背景 |
| `add_btn` | `#27ae60` | 添加按钮（绿色） |
| `del_btn` | `#c0392b` | 删除按钮（红色） |

#### 亮色主题

| 色值 | 颜色 | 用途 |
|------|------|------|
| `bg` | `#dce3f0` | 主窗口 / 欢迎页 / 主界面 背景 |
| `bg_secondary` | `#e4eaf5` | 右侧内容区 (contentArea) 背景 |
| `bg_card` | `#edf2f9` | 卡片 (QGroupBox, resultCard, indepGroupFrame) |
| `text` | `#1b2035` | 正文 (QLabel, QCheckBox, QComboBox, 导航树, QGroupBox) |
| `text_secondary` | `#5c6a80` | 次要文字 (labelSecondary, 按钮, 表头, 提示) |
| `accent` | `#5070e8` | 强调色 (标题, 结果数值, 链接, 选中态, 聚焦边框) |
| `accent_hover` | `#4360d4` | 强调色悬停 |
| `btn_bg` | `#5070e8` | 主按钮背景 |
| `btn_hover` | `#4360d4` | 主按钮悬停 |
| `btn_pressed` | `#3852c0` | 主按钮按下 |
| `sidebar_bg` | `#d4dcec` | 左侧导航栏背景 |
| `sidebar_hover` | `#c4cee2` | 导航树 hover / 列表项 hover / 卡片 hover |
| `border` | `#bfcadb` | 边框 |
| `input_bg` | `#f0f4fa` | 输入框背景 |
| `input_border` | `#b8c4d6` | 输入框边框 |
| `input_focus` | `#5070e8` | 输入框聚焦边框 |
| `checkbox_bg` | `#5070e8` | 复选框选中背景 |
| `alt_row` | `#f2f5fb` | 表格交替行背景 |
| `nav_selected_bg` | `#cbd8ed` | 导航树选中项背景 |
| `scrollbar_handle` | `#bdc7d6` | 滚动条滑块 |
| `scrollbar_handle_hover` | `#5070e8` | 滚动条滑块悬停 |
| `header_grad_end` | `#dfe6f2` | 表头渐变终点色 |
| `card_title_bg` | `#c4d4ec` | 预设卡片标题栏背景 |
| `add_btn` | `#27ae60` | 添加按钮（绿色） |
| `del_btn` | `#c0392b` | 删除按钮（红色） |

### 样式表组件覆盖

`build_stylesheet()` 生成的样式表覆盖以下 Qt 组件：

| 组件 | 样式说明 |
|------|---------|
| `QMainWindow` | 主窗口背景 |
| `QTreeWidget#navTree` | 导航树：透明背景，选中项 accent 色左边框 |
| `QGroupBox` | 圆角 8px，标题 accent 色，bg_card 背景 |
| `QTableWidget#attrTable` | 透明背景，圆角 6px，交替行背景 |
| `QPushButton#addButton` | accent 色主按钮 |
| `QPushButton#backButton` | 透明背景，边框按钮 |
| `QPushButton#itemDeleteBtn` | 红色删除按钮 |
| `QDoubleSpinBox` / `QSpinBox` | input_bg 背景，input_border 边框 |
| `QComboBox` | input_bg 背景，下拉列表适配主题 |
| `QCheckBox` | 自定义 indicator 样式 |
| `QLabel#sectionTitle` | 22px 粗体标题 |
| `QLabel#labelSecondary` | text_secondary 次要文字 |
| `QLabel#accentLabel` | accent 强调色文字 |
| `QHeaderView::section` | 渐变背景，accent 色底边 |
| `QScrollBar` | 细滚动条，accent 色悬停 |
| `QTabWidget::pane` | bg_secondary 背景，border 边框 |
| `QTabBar::tab` | input_bg 背景，选中时 accent 色文字 |
| `QDialog` | bg_secondary 背景，统一弹窗样式 |
| `QMessageBox` / `QInputDialog` / `QFileDialog` | 统一弹窗样式 |
| `QFrame#resultCard` | bg_card 背景，hover 时 accent 边框 |
| `QFrame#presetCard` | 预设卡片样式 |
| `QPushButton#presetSaveBtn` | 预设保存按钮 |

### 主题切换机制

1. **触发**：`DmgCalculator._toggle_theme()` 切换 `current_theme` 属性
2. **应用**：调用 `_apply_theme()` → `build_stylesheet()` 生成样式表 → `setStyleSheet()`
3. **刷新**：重新生成计算过程 HTML（内联颜色需更新）、刷新结果卡片
4. **持久化**：加载存档**不覆盖**当前主题

### 导航树颜色适配

导航树各区域使用硬编码颜色，需根据主题选择不同色值：

```python
is_light = self._is_light_theme()
if is_light:
    sec_fg = QColor(210, 105, 0)    # 深橙色（亮色主题）
    child_fg = QColor(180, 90, 0)   # 暗橙色
else:
    sec_fg = QColor(255, 152, 0)    # 琥珀色（暗色主题）
    child_fg = QColor(255, 183, 77) # 淡橙色
```

### 预设窗口主题继承

预设构建器和编辑窗口通过 `_apply_theme()` 方法继承主程序主题：

```python
def _apply_theme(self):
    """继承主程序主题"""
    try:
        from theme_system import THEMES, build_stylesheet
        w = self.parent()
        while w is not None:
            if hasattr(w, 'current_theme') and w.current_theme in THEMES:
                self.setStyleSheet(build_stylesheet(w.current_theme))
                return
            w = w.parent()
        self.setStyleSheet(build_stylesheet("dark"))
    except Exception:
        pass
```

**继承链**：`DmgCalculator` → `PresetBuilderDialog` → `_CharacterPresetWindow` / `_WeaponPresetWindow`

每个窗口向上遍历父级查找 `current_theme` 属性，找到后应用对应主题样式表。若找不到则默认使用暗色主题。

---

## 九、关键机制

### 隐藏 / 锁定
- 全局集合：`HIDDEN_ITEMS`、`LOCKED_SUMMARY_ITEMS`、`HIDDEN_ECHO_IDS`
- 4 元素键：`(name, src_label, nav_key, seq_label)` — 序列号确保同名不同行独立操作
- CombinedEntryPage 中：`seq_label` = `"常驻1"` / `"触发2"` 格式；声骸中 = `"1号声骸主词"` 格式
- 隐藏条目不计入计算但数据保留，持久化到存档

### 高亮动画
- `_place_highlight_overlay()` 统一函数：两轮黄色渐入渐出（共 2s）
- 总结页来源表行：平滑滚动 + 黄色叠层
- 综合填写表行 / 声骸主词条区 / 副词条行：对应区域黄色叠层
- 序列号匹配定位，跳转延迟 200ms

### 一键全自动
- 全局开关：同时开启结果页自动计算 + 结果列表自动更新
- 状态持久化到 `config/auto_all_config.json`，启动时自动恢复
- 任意来源页变更（综合填写/角色武器/声骸）→ 防御+抗性重算 → 总结页重算 → 计算结果 auto_compute → 结果列表 recalc
- 结果列表 recalc 同步刷新非模态详情弹窗（ResultDetailDialog）
- CombinedEntryPage 的回调链在 v0.5 已修复（此前遗漏导致隐藏/锁定不触发自动更新）

---

## 十、游戏常量

### 声骸
- `ECHO_MAIN_STATS`：cost 4/3/1 主词条
- `ECHO_FIXED_MAIN`：固定副词条（4c = 150 固定攻击等）
- `ECHO_SUB_STATS`：13 种副词条

### 筛选
- `ELEMENTS`：冷凝/热熔/气动/导电/衍射/湮灭 + 无
- `SKILL_TYPES`：普攻/重击/共鸣技能/解放/变奏/声骸 + 无
- `EFFECTS`：光噪/风蚀/虚湮/聚爆/霜渐/电磁 + 无

### 乘区关键词
- `BONUS_SUFFIX`：伤害加成 / 伤害提升 → 加成乘区
- `DEEPEN_SUFFIX`：加深 → 加深乘区
- `CRIT_RATE_KEYWORDS` / `CRIT_DMG_KEYWORDS` → 暴击乘区
- `DEFENSE_ITEM_NAMES` / `RESISTANCE_ITEM_NAMES` → 防御/抗性

---

## 十一、自动化测试（v0.6 新增）

### 概述

项目引入了基于 **pytest** 的自动化测试体系，包含 **86 个测试用例**，全部 **0.2 秒内完成**。测试覆盖伤害公式的每个乘区、筛选匹配逻辑、存档格式验证和边界条件。

### 设计理念

**四层架构，damage_calc.py 是唯一真相来源**：

```
damage_calc.py  ← 唯一真相来源（纯函数，零 GUI 依赖）
    │               所有公式、常量、筛选逻辑都在这里
    │
    ├── import ── WWDmgCalc.py          主程序 GUI
    │              _matches_filter() → damage_calc.matches_filter()
    │              EnemyDefensePage.recalc() → damage_calc.calc_defense_zone()
    │              EnemyResistancePage._recalc() → damage_calc.calc_resistance_zone()
    │
    └── import ── tests/test_damage_formula.py  测试
                   from damage_calc import calc_defense_zone, ...
                   assert calc_defense_zone(90, 100, 0) == ...
```

1. **独立计算模块**（[damage_calc.py](../damage_calc.py)）— 把所有伤害公式、游戏常量、筛选逻辑从 GUI 代码中提取出来，变成纯 Python 函数。零 GUI 依赖，可独立 import。
2. **主程序引用** — `WWDmgCalc.py` 顶部 `import damage_calc`，关键方法（`_matches_filter`、`EnemyDefensePage.recalc()`、`EnemyResistancePage._recalc()`）委托给 `damage_calc` 的纯函数。
3. **测试 import 同一模块** — `tests/test_damage_formula.py` 也从 `damage_calc` import，用 `assert` 验证每个公式。**测试的是真实代码，不是副本**。
4. **pytest 自动执行** — `python -m pytest tests\` 自动发现并运行所有测试，0.2 秒内完成 86 个用例。

### 测试覆盖

| 测试类 | 文件 | 用例数 | 覆盖内容 |
|--------|------|--------|----------|
| `TestDefenseZone` | test_damage_formula.py | 10 | 敌方防御减伤（等级/无视/截断/范围） |
| `TestResistanceZone` | test_damage_formula.py | 7 | 抗性乘区（正负抗性/提升/减免/clamp） |
| `TestIndepZone` | test_damage_formula.py | 5 | 独立乘区（组内加法×组间乘法） |
| `TestBaseZone` | test_damage_formula.py | 7 | 基础乘区（攻/生/防，百分比+固定值） |
| `TestBonusZone` | test_damage_formula.py | 3 | 加成乘区（1 + Σ加成/100） |
| `TestDeepenZone` | test_damage_formula.py | 2 | 加深乘区 |
| `TestCritZone` | test_damage_formula.py | 5 | 暴击乘区+暴击率（150%底/5%底） |
| `TestMultZone` | test_damage_formula.py | 5 | 倍率乘区（增加+增幅） |
| `TestFullDamageFormula` | test_damage_formula.py | 3 | 完整伤害端到端 |
| `TestFilterMatching` | test_damage_formula.py | 10 | 元素/技能/效应筛选匹配 |
| `TestGameConstants` | test_damage_formula.py | 7 | 常量完整性 |
| `TestEdgeCases` | test_damage_formula.py | 4 | 边界条件（负数/零值/多组） |
| `TestSaveFormat` | test_save_format.py | 8 | 存档结构验证 |
| `TestSaveRoundtrip` | test_save_format.py | 3 | JSON 读写完整性（含中文） |
| `TestSaveBackwardCompatibility` | test_save_format.py | 3 | 旧版格式兼容 |
| **合计** | | **86** | |

### 测试运行器（[tests/run_tests_gui.py](../tests/run_tests_gui.py)）

独立的 PyQt6 GUI 窗口，提供一键测试体验：

- **12 个分类按钮**：全部/伤害公式/存档格式/各乘区/筛选/边界/常量
- **自定义参数输入**：直接输入 pytest 原生参数（如 `-k defense --lf`），回车运行
- **实时彩色输出**：通过绿色/通过红色/失败黄色/汇总
- **后台线程**：QThread 执行 pytest，UI 不卡顿
- **命令行快捷**：`python tests/run_tests_gui.py 4` 打开即跑防御乘区
- **使用手册按钮**：内置帮助文档，说明原理和用法
- **启动自动跑**：打开窗口自动执行全部测试

### 使用场景

| 场景 | 操作 | 耗时 |
|------|------|------|
| 修改伤害公式后验证 | 点"全部测试" | 0.2s |
| 只验证改动的乘区 | 点对应按钮 | <0.1s |
| 调试上次失败的测试 | 自定义输入 `--lf` | <0.1s |
| 搜特定关键词的测试 | 自定义输入 `-k defense` | <0.1s |
| 发现 bug 后写测试 | 先写测试（红）→ 修代码 → 跑测试（绿） | — |

---

## 十二、Git 版本管理（v0.6 新增）

### 是什么

Git 是一个**版本管理工具**。原理不是"保存文件副本"，而是**给每次改动拍快照**。每次 `commit` 记录的是整个项目那一瞬间的完整状态。所有历史版本存储在 `.git/` 隐藏文件夹中，没改的文件只存指针不占空间。

### 在哪使用

在 **VSCode 终端**里操作。按 `` Ctrl+` ``（Ctrl 加反引号）打开底部终端，光标会自动定位到项目目录，直接输命令即可：

```
PS C:\Users\yutia\Python\WutheringWavesDmgCalc> git status        ← 在这里输入
```

### 两个文件

| 文件 | 作用 |
|------|------|
| `.gitignore` | Git 忽略规则——告诉 Git 哪些文件不管理（`build/`、`dist/`、`__pycache__/`、`error_log.json`） |
| `.git/` | Git 数据库（隐藏文件夹），存着所有提交历史，**平时不用打开** |

---

### 第一步：日常存档（最常用，每次改完代码做一次）

改完代码后，在 VSCode 终端里依次输入两行：

```powershell
git add -A
git commit -m "这里写你改了什么"
```

示例——比如你修了一个 bug：

```powershell
PS C:\Users\yutia\Python\WutheringWavesDmgCalc> git add -A
PS C:\Users\yutia\Python\WutheringWavesDmgCalc> git commit -m "修复防御公式截断问题"
```

就这两步，改动就存进版本历史了。之后任何时候都能回退到这个状态。

---

### 第二步：查看状态（想知道当前什么情况）

```powershell
git status                    # 哪些文件改过、哪些还没 commit —— 红字=改了没暂存，绿字=已暂存待提交
git log --oneline             # 提交历史，一行一条。最上面是最新的，前面那串字母数字是 commit-id
git diff                      # 具体改了哪些行 —— 绿底是新增的，红底是删除的
```

---

### 第三步：出问题回退（改坏了怎么救）

| 情况 | 命令 | 说明 |
|------|------|------|
| 刚改坏了，**还没 commit** | `git checkout -- .` | 撤回所有未保存的改动，回到上次 commit 状态 |
| **已经 commit 了**才发现改错了 | `git reset --hard HEAD~1` | 回退到倒数第二个 commit，最近那个 commit 作废 |
| 要回退到**很久以前**的某个版本 | `git reset --hard <id>` | 先用 `git log --oneline` 找到那条的 id，替换 `<id>` |

---

### 实际场景速查

| 场景 | 操作 |
|------|------|
| 今天开始写代码前 | `git status` 确认没有未保存的改动 |
| AI 改了一轮，想存档 | `git add -A` → `git commit -m "AI 加了测试框架"` |
| AI 改完发现把代码改坏了 | `git checkout -- .` 回到改之前 |
| 想看看这周改了哪些东西 | `git log --oneline` 浏览提交记录 |
| 打包发版本前 | `git status` 确认干净 → `git log --oneline` 确认版本号 |

---

### 被 Git 忽略的文件

以下已被 `.gitignore` 排除，不会被纳入版本管理：

- `build/`、`dist/` — PyInstaller 产物（可随时重新打包生成）
- `__pycache__/`、`.pytest_cache/` — 缓存
- `config/error_log.json` — 运行时日志（跨会话累积，不是代码）

---

## 十三、预设系统（v0.8 — ⚠️ 未完成）

### 概述

预设系统允许用户创建、加载和管理角色/武器/声骸套装的预设配置。预设以 JSON 格式存储，分为官方预设（从 GitHub 同步）和用户预设（本地创建）。

**⚠️ 当前状态：框架和核心逻辑已实现，但未端到端测试，UI 可能有 bug。以下为设计文档。**

### 文件结构

| 文件 | 说明 |
|------|------|
| `preset_manager.py` | 预设核心逻辑：list/load/validate/apply_preset/export_temp_preset/update_official_presets/submit_as_official |
| `preset_builder.py` | PresetBuilderDialog：角色/武器/声骸套装三页编辑器 |
| `preset_loader.py` | PresetLoaderDialog：列表+详情预览+应用+更新官方预设 |
| `presets/official/character/` 等 | 官方预设目录（按类别分三个子目录，从 GitHub 同步或手动放入） |
| `presets/user/character/` 等 | 用户预设目录（按类别分三个子目录，通过 PresetBuilderDialog 保存） |

### 预设 JSON 结构

```json
{
  "version": 1, "type": "preset", "name": "预设名称",
  "character": {
    "name": "角色名", "element": "热熔", "effect": "(无)",
    "base_hp": 10000, "base_atk": 500, "base_def": 400,
    "resonance_chain": [
      {
        "effects": [{"type": "常驻", "name": "...", "value": 10.0,
                      "source": "共鸣链效果", "sub_name": "", "default_hidden": false}],
        "indep_zones": [{"group_name": "组名",
                          "values": [{"name": "...", "value": 10.0, "hidden": false}]}]
      }
    ]
  },
  "weapon": {
    "name": "武器名", "base_atk": 500,
    "bonus_type": "暴击率", "bonus_value": 24.3,
    "refinement": [
      {
        "resonance_desc": "谐振效果描述",
        "effects": [...], "indep_zones": [...]
      }
    ]
  },
  "echo_set": {
    "name": "套装名",
    "stages": [{"required_count": 1, "effects": [...]}],
    "first_echo_bonus": {"effects": [...], "indep_zones": [...]}
  }
}
```

---

## 十四、共鸣链增益系统（v0.8 — ⚠️ 未完成）

### 概述

共鸣链增益系统允许用户为角色的每个共鸣链配置增益效果，并支持：
- 启用/禁用单个共鸣链
- 通用增益（常驻/触发效果）
- 特定增益（仅对特定关键词的计算结果生效）

### 导航树位置

```
▼ 角色与武器
    角色基础
    共鸣链增益        ← 新增页面
```

### 页面结构

| 页面 | 说明 |
|------|------|
| `ResonanceBuffPage` | 共鸣链增益主页面（卡片列表） |
| `ResonanceChainEditDialog` | 共鸣链编辑弹窗（2 页分页） |

### 共鸣链卡片

每个共鸣链显示为一张卡片，包含：
- **启用/禁用按钮**：控制该共鸣链是否生效
- **名称**：共鸣链名称
- **效果数量**：显示有多少条效果和特定规则
- **展开按钮**：打开编辑弹窗
- **删除按钮**：删除该共鸣链

### 编辑弹窗（2 页分页）

#### 页面1：通用增益
- **常驻效果表格**：名称 | 数值 | 类型 | 删除
- **触发效果表格**：名称 | 数值 | 类型 | 删除
- 使用标准的 CombinedEntryPage 表格格式

#### 页面2：特定增益
- **效果选择列表**：多选要设置特定增益的效果
- **目标关键词输入**：逗号分隔的关键词（留空 = 增益全部卡片）
- **已添加规则列表**：显示已设置的特定增益规则

### 数据结构

```json
{
  "name": "共鸣链 1",
  "enabled": true,
  "effects": [
    {"name": "攻击力加成", "value": 12.0, "type": "常驻", "source": "共鸣链效果"}
  ],
  "specific_rules": [
    {"effect_idx": 0, "keywords": ["共鸣技能", "冷凝"]}
  ]
}
```

### 待完成事项

- [ ] 共鸣链增益与伤害计算的集成
- [ ] 特定增益规则在计算中的应用逻辑
- [ ] 启用/禁用状态在计算中的处理
- [ ] 保存/加载共鸣链数据到存档
- [ ] 与预设系统的集成

---

## 十五、开发注意事项

- 单文件架构，避免大规模重写
- ⚠️ **行匹配必须用序列号**：CombinedEntryPage 允许同名多行。查找/匹配/操作特定行时，只用 `name` 会命中所有同名行。必须同时匹配 `seq_label`（如 `"常驻3"`）。血的教训：防御页/抗性页勾选框、数值总结页改值/删除/高亮 共 5 处同名 bug 均源于此。
- `_row_seq(page, idx)` 工具方法（summary_pages.py）可根据页面类型生成序列标签；防御/抗性页用 `_make_item_key(name, src_label, seq_label)`。
- 4 元素键 `(name, src_label, nav_key, seq_label)` 是隐藏/锁定/高亮/过滤的统一标识
- `CombinedEntryPage` 使用 `page_key`（`"combined_perm"` / `"combined_trigger"`）
- 全局样式用 object-name 选择器，加新页面无需改 `build_stylesheet()`
- OCR 线程通过 `QThread` + `pyqtSignal`，注意信号生命周期
- 存档版本 `SAVE_FILE_VERSION = 1`，向后兼容在 `SaveManager` 中
- 计算过程 HTML 内联颜色需在主题切换后调用 `compute()` 重新生成
- `BaseOverrideDialog.reset_state()` 加载存档时同步弹窗，不触发回调
- `MarqueeLabel` 主题判断用 `self.window()` 而非 `QApplication.instance()`
- 加载存档不覆盖当前主题
- 所有弹窗启动时自动居中屏幕（`_center_window`）
- 程序闪退自动写入 `error_log.json` + 启动 `error_viewer.py` 外部报告窗口
- 全屏截图 OCR 自动裁剪到目标区域（声骸右上 1/4、倍率左 1/2），裁剪无效则回退原图
- **v0.4**：HIDDEN_ITEMS/LOCKED_SUMMARY_ITEMS 升级为 4 元素 key `(name, source, page_key, seq_label)`，同名不同行独立操作
- **v0.4**：跨页隐藏/锁定/删除实时同步、查看总结按钮+高亮跳转、搜索结果+关键词、锁定 toast 提示
- **v0.5**：使用手册重写（15 章节完整覆盖）；图片点击用系统程序查看原图；公式中 `/100` → 规范化
- **v0.5**：使用手册和错误日志窗口改为非模态（`show()` + `WA_DeleteOnClose`）
- **v0.5**：错误分析引擎升级（11 种错误类型覆盖、具体建议）
- **v0.5**：全部弹窗居中改用 `QTimer.singleShot(0, ...)`，布局完成后执行
- **v0.5**：综合填写→总结跳转改序列号匹配（`常驻1`/`触发2`），同名不冲突
- **v0.5**：打包适配 — 所有路径改用 `_APP_DIR`（`sys.frozen` 判断 `sys.executable` vs `__file__`），`save/config/defaultsave/manual` 目录正确位于 exe 同级
- **v0.5**：使用手册图片路径改为相对路径，打包后不同机器均可正常显示
- **v0.5**：CombinedEntryPage._on_change_cb 遗漏修复 —— 综合填写页变更现在正确触发自动计算/自动更新
- **v0.5**：结果详情弹窗支持实时更新 —— 自动更新时同步刷新打开的详情窗口数值
- **v0.5**：基础数值覆盖提示改为独立标签（蓝字 `▸ 已启用手动填写基础数值`），不再内联到数值中
- **v0.6**：提取 `damage_calc.py` 独立计算引擎（12 个纯函数+全部常量+筛选逻辑），零 GUI 依赖，主程序和测试共用
- **v0.6**：`WWDmgCalc.py` 关键方法委托给 `damage_calc`（`_matches_filter`、防御/抗性乘区公式）
- **v0.6**：引入 pytest 自动化测试体系（86 个用例，覆盖全部乘区+筛选+存档+边界条件）
- **v0.6**：`tests/test_damage_formula.py` 从手抄副本改为 `import damage_calc`，测试的是真实代码
- **v0.6**：新增 `run_tests_gui.py` 测试运行器（GUI 窗口，后台线程，实时彩色输出，自定义参数输入，内置使用手册）
- **v0.6**：PROJECT_SUMMARY.md 新增第十二章"自动化测试"（四层架构说明）
- **v0.6**：初始化 Git 仓库 + `.gitignore`（排除 build/dist/__pycache__/error_log.json）
- **v0.6**：文件结构规范化 — 测试文件归入 `tests/`，错误处理归入 `error_handler/`，删除多余 spec
- **v0.6**：PROJECT_SUMMARY.md 新增第十三章"Git 版本管理"（原理/常用命令/使用场景）
- **v0.6**：独立乘区新增隐藏/一键隐藏功能（隐藏数值不参与计算，变灰显示）
- **v0.6**：修复 5 个回调遗漏（防御/抗性内部修改、基础乘区隐藏删除、CharBasePage 复选框、CombinedEntryPage 新增行、详情弹窗同步刷新）
- **v0.6**：使用手册 8 个章节重写（加成/加深/暴击/独立/防御/抗性/计算结果/结果列表）
- **v0.6**：使用手册图片显示修复（_fix_image_paths 兼容 ./manual/images/ 格式路径）
- **v0.6**：使用手册编辑模式蓝字 bug 修复 + 图片点击查看原图 + 光标切换修复
- **v0.6**：声骸 OCR 全屏识别优化（COST 行保护、小数匹配、X 轴容差放宽、+ 前缀清理）
- **v0.6**：倍率 OCR 上限 5→10 张、公式行不受 skip 关键词拦截、名称清洗、非伤害后过滤、智能去重
- **v0.6**：倍率 OCR 技能分类改为按行跟踪（修复全屏截图下标签栏干扰导致分类全错的问题）
- **v0.6**：OCR 引擎 det_limit_side_len 960→1280（修复全屏裁切后汉字笔画丢失导致缺字的问题）
- **v0.6**：拆分主程序第一步——提取错误处理系统到 `error_handler/error_system.py`（~450行），主编减至 ~10836 行
- **v0.6**：修复 `_new_error_count` 跨模块 import 后更新丢失（改用 list 包装）
- **v0.6**：错误日志按钮显示未读计数（非历史总数），三个弹窗改为单例
- **v0.6**：error_viewer.py 支持 `--crash` 标志（闪退时先弹详情，手动时直接弹列表）
- **v0.6**：打包配置支持独立 ErrorViewer.exe + 闪退时自动定位启动
- **v0.7**：拆分主程序第二步——提取 OCR 引擎到 `ocr_engine.py`（~1100行），主编 ~9815 行
- **v0.7**：拆分主程序第三步——提取主题系统到 `theme_system.py`（~460行），主编 ~9363 行
- **v0.7**：倍率 OCR 上限 10→5（避免批量添加时卡顿），识别中提示上限信息
- **v0.7**：声骸全屏 OCR 优化——COST 行保护、小数匹配、X 轴容差放宽、+ 前缀清理
- **v0.7**：倍率 OCR——公式行不受 skip 关键词拦截、名称清洗（括号/数字/运算符）、非伤害后过滤、智能去重
- **v0.7**：倍率 OCR 技能分类改为按行跟踪（修复全屏截图下标签栏干扰）+ det_limit_side_len 960→1280
- **v0.7**：防御/抗性页面表格新增序列号列、双向视角跳转+平滑滚动+黄色叠层高亮
- **v0.7**：综合填写表格高度自适应行数（AdjustToContents + fix_table_height + 禁用表内滚条），QScrollArea 统一滚动
- **v0.7**：防御/抗性/基础乘区页面内部修改实时同步自动计算和自动更新（5 个回调遗漏修复）
- **v0.7**：结果列表搜索框主题跟随、卡片 hover 透明化、锁定按钮双向同步、详情弹窗展开修复
- **v0.7**：使用手册目录拖拽排序+章节样式自定义+取消更改恢复、8 个章节重写、表格主题适配
- **v0.7**：拆分主程序第四步——提取总结页到 `summary_pages.py`（~540行），主编 ~9093 行
- **v0.7**：依赖注入模式——summary_pages 通过 inject_dependencies() 接收共享变量，避免循环依赖
- **v0.7**：导航树父分类记忆——点击父节点跳回上次访问的子页面
- **v0.7**：结果卡片关键词行始终显示，计入结果默认空、OCR 导入自动生成
- **v0.7**：拆分主程序第五步——提取独立乘区页到 `indep_zone.py`（~310行），主编 ~8837 行
- **v0.7**：拆分主程序第六步——提取角色武器页到 `char_base_page.py`（~140行），主编 ~8710 行
- **v0.7**：拆分主程序第七步——提取抗性数值页到 `enemy_res.py`（~510行），主编 ~8259 行
- **v0.7**：修复综合填写输入框回车添加问题——补全触发二次 textChanged 导致词条列表被重置
- **v0.7**：综合填写与数值总结新增"副名称"列——用户自定义备注（如"守岸人延奏buff"），QLineEdit 双向实时同步
- **v0.7**：计算结果计算过程 tooltip 新增第三行"副名称：xxxx"，sub_map 改用 (名称, 来源) 元组做键避免同名覆盖
- **v0.7**：数值总结表格列宽与综合填写统一（副名称180/序列号80/数值180/取值80/来源85，操作列自适应伸缩）
- **v0.7**：副名称输入框自适应列宽（移除 setMaximumWidth 限制）
- **v0.7**：修复防御减伤/抗性数值页面勾选框同名联动 bug——_make_item_key 加入序列号确保每行独立
- **v0.7**：修复数值总结 3 个同名 bug——数值变更/删除/高亮跳转全部改用名称+序列号精确匹配
- **v0.7**：数值总结高亮叠层增加 RuntimeError 防护——表格在动画/定时器触发前被销毁时静默跳过

### 错误处理与日志（v0.3）
- **持久化存储**：`config/error_log.json` 结构化 JSON 数组，最多 500 条，跨会话保留，5 秒内相同错误去重
- **ErrorReportDialog**：摘要列表 + 查看按钮，每条可展开到 `ErrorDetailDialog`（原始信息 + 自动分析 + 评估建议）
- **ErrorDetailDialog**：三区块（标题/原始信息/分析建议），各自固定高度 + 滚动条，窗口可拖拽，居中显示
- **错误自动分析**（`_analyze_error`）：覆盖 11 种常见错误类型，每种提供针对性原因分析和操作建议
  | 类型 | 匹配关键词 | 分析要点 |
  |------|-----------|----------|
  | OCR 识别失败 | `ocr` + `识别失败/未能识别` | 图片分辨率过低 / 截图区域不含目标面板 |
  | OCR 污染 | `ocr` + `污染/垃圾/无效` | 读取成功但内容含大量 UI 噪音，建议用局部截图 |
  | OCR 解析失败 | `ocr` + `解析` | 读取成功但解析器未匹配到有效数据，可能游戏版本更新导致 |
  | OCR 未定义变量 | `ocr` + `name '/not defined` | 代码重构遗漏的导入或全局变量 |
  | OCR 其他异常 | `ocr` + 其他 | 通用 OCR 流程异常 |
  | 缺少依赖 | `importerror/modulenotfound` | 缺少 Python 依赖包，建议 `pip install -r requirements.txt` |
  | 文件不存在 | `filenotfound/不存在` | 文件或目录缺失，检查 `config/` 和 `save/` 目录 |
  | JSON 损坏 | `json` | 存档或配置文件损坏，建议删除后重新生成 |
  | 变量未定义 | `name '/not defined` | Python 变量/函数未定义，通常由代码重构遗漏导致 |
  | 手动中断 | `keyboardinterrupt` | 用户按下 Ctrl+C，非错误 |
  | 线程异常 | `线程/thread` | 后台线程异常，主程序可继续运行但该线程功能已中止 |
- **崩溃捕获**：`sys.excepthook` → 写入 `error_log.json` → 自动启动 `error_viewer.py`（弹出外部报告窗口）
- **error_viewer.py**：先展崩溃详情，关闭后展示完整日志列表（和主程序内 ErrorReportDialog 互通）
- **侧边栏**：「错误日志」按钮，有未读错误时变红 + 计数，新错误触发平滑滚动动画，查看后恢复
- **全局居中**：所有 9 个弹窗统一调用 `_center_window()` 居中屏幕
- 所有 `except Exception: pass` → `_logger.warning/debug/exception`
- 所有 `traceback.print_exc()` → `_logger.exception()`

---

## 十六、共鸣链增益系统（v0.9）

### 概述

共鸣链增益系统允许用户为角色的 6 个共鸣链分别配置增益效果。每个共鸣链以卡片形式展示，支持启用/禁用，效果自动同步到综合填写页和关键词关联页。

### 共鸣链增益页面（ResonanceBuffPage）

卡片式布局，默认 6 张卡片（共鸣链 1~6）：

- **卡片头部**：共鸣链名称（可重命名，格式 `前缀的第X个共鸣链`）
- **卡片副标题**：效果数量 + 特定规则数量
- **按钮行**：启用/关闭（橙/红）+ 展开编辑（绿）
- **启用联动**：关闭卡片 → 自动从综合填写页和关键词关联页移除所有效果；启用 → 自动恢复

### 共鸣链编辑弹窗（ResonanceChainEditDialog）

2 页分页式编辑（v0.9 移除「特定增益规则」页，关键词关联统一在关键词关联页面管理）：

| 页 | 内容 | 说明 |
|----|------|------|
| 通用增益 | 常驻 + 触发效果表格 | SearchCombo 输入，支持添加/删除行 |
| 特定增益 | 特定增益效果表格 | 每行可设置特定增益效果 |

- **保存联动**：保存时自动将效果同步到综合填写页（常驻/触发）和关键词关联页
- **启用联动**：卡片启用时效果计入计算，关闭时自动从所有页面移除
- **默认状态**：卡片默认关闭，按钮显示「启用」（暖橙），需主动开启

### 关键词关联页面（KeywordAssociationPage）

位于「综合填写」分类下，管理效果与关键词的关联：

- **8 列表格**：名称 / 副名称 / 序列号 / 数值 / 取值 / 来源 / 关键词关联 / 操作
- **来源区分**：
  | 添加方式 | 来源显示 |
  |----------|----------|
  | 手动添加 | **关联效果** |
  | 共鸣链自动 | **共鸣链效果** |
- **序列号格式**：
  | 来源 | 格式 | 示例 |
  |------|------|------|
  | 手动添加 | `关联X` | 关联1、关联2 |
  | 共鸣链 | `共鸣链X关联Y` | 共鸣链1关联1、共鸣链1关联2 |
- **关键词编辑**：点击「关键词关联」按钮弹出编辑窗，支持增删关键词，确认后更新按钮文本
- **计算联动**：修改关键词关联页 → 自动触发完整计算链（总结页 → 计算结果 → 结果列表），`_recalc_one` 按关键词交集匹配效果计入伤害

### 同步机制（`_sync_chain_to_pages`）

```
_resonanceChainEditDialog._save()
    │
    └→ parent._sync_chain_to_pages(item)
         │
         ├── KeywordAssociationPage.remove_effects_by_chain(chain_num)
         │   └── 按序列号前缀 "共鸣链X关联" 匹配并移除
         │
         ├── CombinedEntryPage.remove_effects_by_source_and_names(source, names, chain_num)
         │   └── 按来源 + 名称 + chain_num 精确匹配并移除
         │
         ├── 若启用 → 重新添加效果到综合填写 + 关键词关联页
         │    ├── _add_row_with_source(name, value, seq, source, chain_num=chain_num)
         │    └── add_effect(name, value, type, source, sub_name, keywords, chain_prefix)
         │
         └── 触发下游重算（_on_change_cb）
              ├── 综合填写回调 → 数值总结 → 计算结果 → 结果列表
              └── 关键词关联回调 → 数值总结 → 计算结果 → 结果列表
```

### 代码质量（v0.9 优化）

- **清理死代码**：删除 2 个重复类定义（`ResultDetailDialog`、`MarqueeLabel`）+ 重复 import + 粘贴残留块，共 −509 行
- **替换通配符导入**：7 处 `from X import *` → 显式导入，明确依赖关系
- **提取样式常量**：`ResonanceBuffPage._BTN_STYLE` 类常量消除重复样式字符串
- **删除「特定增益规则」tab**：~210 行，功能与关键词关联页面冲突，统一在关键词关联页面管理
- **存档系统补全**：`collect_full_state` / `apply_state` 新增 `chain_buff` 和 `keyword_assoc` 页面，向后兼容
- **过程 HTML 实时生成**：`_rebuild_process_html()` 从 zones 实时构建计算过程，倍率变更即时反映
- **黑夜主题边框加强**：`border` #2a2a4a→#3d3d5e，QGroupBox 1px→2px
- **按钮逻辑反转**：启用中显示「关闭」（蓝灰），未启用显示「启用」（暖橙），默认关闭
