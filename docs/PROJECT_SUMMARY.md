# WutheringWavesDmgCalc 项目总结

> 生成: 2026-05-30 | 更新: 2026-06-10 | 版本: v0.11

---

## 一、项目概览

**WutheringWavesDmgCalc** 是《鸣潮》(Wuthering Waves) 的伤害计算器桌面应用。基于 PyQt6，主模块 + 7 个拆分模块（主编 [WWDmgCalc.py](../WWDmgCalc.py) ~10638 行），支持暗色/亮色双主题、OCR 识别、存档管理、基础数值手动覆盖、错误日志系统、数据流调试器（实时计算 + 冲突对比）、使用手册。项目使用 **Git** 做版本管理，可随时回退到历史状态。

### ⚠️ 当前开发状态（v0.11）

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
├── WWDmgCalc.py                          # 主程序（~10185 行，已拆分 7 个模块）
├── damage_calc.py                        # ★ 独立计算引擎（纯函数/零 GUI，主程序和测试共用）
├── theme_system.py                       # ★ 主题配色系统（~587行，从主编拆分）
├── enemy_res.py                          # ★ 抗性数值页（~510行，从主编拆分）
├── char_base_page.py                     # ★ 角色武器页（~140行，从主编拆分）
├── indep_zone.py                         # ★ 独立乘区页（~310行，从主编拆分）
├── summary_pages.py                      # ★ 数值总结页（~675行，从主编拆分，含副名称双向同步）
├── ocr_engine.py                         # ★ OCR 图文识别引擎（~1100行，从主编拆分）
│
├── tests/                                # 🧪 自动化测试
│   ├── __init__.py
│   ├── run_tests_gui.py                  #     测试运行器（GUI 窗口）
│   ├── test_damage_formula.py            #     伤害公式测试（71 个用例）
│   ├── test_save_format.py              #     存档格式测试（14 个用例）
│   ├── test_sync_chain.py               #     共鸣链同步测试（9 个用例）
│   └── test_data_flow.py               #     数据流端到端测试（91 个用例）
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
| pytest | 自动化测试（186 个用例，2.9s 完成） |
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
│  [错误日志]   │  → ErrorReportDialog（有未读错误时显示计数）
│  [数据流]     │  → DataFlowViewerDialog（数据流调试器，实时计算+冲突对比+文本报告）
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

### 链路 1：角色基础值 → 最终伤害

```
用户在 CharBasePage（角色与武器页）填写：
  角色等级 [80]  角色基础生命 [12000]  角色基础攻击 [400]  角色基础防御 [600]
  武器基础攻击 [500]  武器附加属性 [攻击力 12.4%]
        │
        │ CharBasePage.collect_data() → dict
        │   {char_level:80, base_hp:12000, base_atk:400, base_def:600,
        │    weapon_base_atk:500, weapon_bonus:("攻击力", 12.4)}
        │
        │ _collect_all_items() 展开为 6 元组：
        │   ("角色基础攻击", 400,   "角色武器", "char_base", "", "")
        │   ("武器基础攻击", 500,   "角色武器", "char_base", "", "")
        │   ("武器附加攻击力", 12.4, "角色武器", "char_base", "", "")
        ▼
  SummaryBasePage.recalc()  ← 基础乘区筛选
        │  匹配规则：名字含"基础"/"攻击"/"生命"/"防御" + 固定值
        │  命中：角色基础攻击(400), 武器基础攻击(500), 武器附加攻击力(12.4%)
        │
        │  填入基础乘区总结表格（7 列：名称/副名称/序列号/数值/取值/来源/操作）
        │  用户可在总结页编辑副名称、隐藏、锁定、删除
        │
        │  合计计算：
        │  base_zone = (400 + 500) × (1 + 12.4/100) = 1011.6
        ▼
  ResultPage（计算结果页）
        │  接收 base_zone = 1011.6
        │  用户选择：基础值类型=攻击、元素=冷凝、技能类型=普攻
        │  用户填写：基础倍率=100%、倍率增加=0、倍率增幅=0
        │
        │  乘区汇总：
        │  最终伤害 = 1011.6 × bonus × deepen × crit × def × res × indep × mult / 100
        ▼
  结果显示 → 用户点击"计入结果" → ResultListPage 卡片
```

### 链路 2：综合填写（常驻/触发）→ 最终伤害

```
用户在 CombinedEntryPage（综合填写 - 常驻）添加词条：
  搜索"伤害加成" → 数值 [30] → 来源 [声骸] → 点击添加
        │
        │  表格新增一行：
        │  ┌────────┬────────┬──────┬──────┬──────┬──────┬────────┐
        │  │伤害加成│ (空)   │ 常驻1│ 30   │ 百分比│声骸  │隐藏│锁│删│
        │  └────────┴────────┴──────┴──────┴──────┴──────┴────────┘
        │
        │  用户可编辑副名称（输入框直接输入 或 点击「…」展开编辑窗）
        │  用户可点击"隐藏"（从总结页消失但保留数据）
        │  用户可点击"锁定"（总结页显示锁图标，不可被共鸣链覆盖）
        │
        │ CombinedEntryPage.collect_data() →
        │   [("伤害加成", 30, false, "声骸", "常驻1", "")]
        │
        │ _collect_all_items() 转换为 6 元组：
        │   ("伤害加成", 30, "声骸", "combined_perm", "常驻1", "")
        ▼
  SummaryBonusPage.recalc()  ← 加成乘区筛选
        │  匹配规则：名字含"伤害加成"/"伤害提升"
        │  命中：伤害加成(30%)
        │
        │  bonus_zone = 1 + 30/100 = 1.30
        ▼
  ResultPage → 代入公式 → 最终伤害

---

综合触发页同理，区别仅在于来源标签为"触发"：
  CombinedEntryPage(触发).collect_data() → [("暴击率", 10, false, "声骸", "触发1", "")]
  → SummaryCritPage 筛选命中 → crit_rate = 5 + 10 = 15
```

### 链路 3：声骸 → 最终伤害

```
用户在 EchoCounterPage 点击"添加声骸" → 创建 EchoPage（声骸1）
  选择 COST = 4
  主词条：[攻击力] 数值 [33]
  固定词条：自动填充 [基础攻击 150]
  副词条行1：[暴击率] 数值 [10.5]
  副词条行2：[暴击伤害] 数值 [21.0]
  副词条行3：[伤害加成] 数值 [8.6]
        │
        │ EchoPage.collect_data() → dict {
        │   main_stat:  ("攻击力", 33),
        │   fixed_stat: ("基础攻击", 150),
        │   sub_stats:  [("暴击率", 10.5, true), ("暴击伤害", 21.0, true), ("伤害加成", 8.6, true)]
        │ }
        │
        │ _collect_all_items() 展开为 4 条 6 元组：
        │   ("[声骸]主词条-攻击力",   33,   "声骸1费", "echo_1", "", "")
        │   ("[声骸]固定词条-基础攻击", 150, "声骸1费", "echo_1", "", "")
        │   ("[声骸]副词条-暴击率",   10.5, "声骸1费", "echo_1", "", "")
        │   ("[声骸]副词条-暴击伤害",  21.0, "声骸1费", "echo_1", "", "")
        │   ("[声骸]副词条-伤害加成",   8.6, "声骸1费", "echo_1", "", "")
        ▼
  4 个 SummaryPage 各自筛选：
        │  SummaryBasePage  ← 命中：主词条-攻击力(33%), 固定词条-基础攻击(150)
        │  SummaryBonusPage ← 命中：副词条-伤害加成(8.6%)
        │  SummaryCritPage  ← 命中：副词条-暴击率(10.5%), 副词条-暴击伤害(21.0%)
        │  SummaryDeepenPage ← 无命中
        ▼
  ResultPage → 代入各乘区 → 最终伤害
```

### 链路 4：共鸣链增益 → 综合填写 + 关键词关联 → 最终伤害（最复杂链路）

```
用户在 ResonanceBuffPage（共鸣链增益页）看到 6 个共鸣链卡片
  点击共鸣链1的"展开编辑" → ResonanceChainEditDialog（非模式弹窗）
        │
        │  弹窗内有 3 个表格：
        │  ┌─────────────────────────────────────────────────┐
        │  │ 常驻增益表格        触发增益表格       特定增益表格 │
        │  │ ┌─────┬────┬───┐  ┌─────┬────┬───┐  ┌─────┬───┐│
        │  │ │伤害加成│30%│删│  │暴击率│10%│删│  │冷凝伤│15%│删│
        │  │ └─────┴────┴───┘  └─────┴────┴───┘  └─────┴───┘│
        │  └─────────────────────────────────────────────────┘
        │
        │  用户在"特定增益表格"添加一行：
        │  名称 [冷凝伤害加成] → 数值 [15] → 来源 [共鸣]
        │
        │  实时同步触发（每次编辑 300ms 防抖后执行）：
        │
        └── _collect_and_sync() → _sync_chain_to_pages(item)
                │
                │  item["effects"] = [
                │    {name:"伤害加成", value:30, type:"常驻", source:"共鸣", sub_name:""},
                │    {name:"暴击率", value:10, type:"触发", source:"共鸣", sub_name:""},
                │    {name:"冷凝伤害加成", value:15, type:"特定", source:"共鸣", sub_name:""},
                │  ]
                │
                ├──→ 同步到 CombinedEntryPage（综合填写页）
                │       │
                │       │  常驻效果 → page_combined_perm（综合常驻页）
                │       │    表格新增一行：┌────────────┬────┬──────┬────┬──────┬────┬──────┐
                │       │                  │伤害加成    │(空)│共鸣链1│30  │百分比│共鸣│隐藏│锁│删│
                │       │                  └────────────┴────┴──────┴────┴──────┴────┴──────┘
                │       │
                │       │  触发效果 → page_combined_trigger（综合触发页）
                │       │    表格新增一行：┌──────┬────┬──────┬────┬──────┬────┬──────┐
                │       │                  │暴击率│(空)│共鸣链1│10  │百分比│共鸣│隐藏│锁│删│
                │       │                  └──────┴────┴──────┴────┴──────┴────┴──────┘
                │       │
                │       │  特定效果 → 同样添加到对应综合填写页（根据常驻/触发分类）
                │       │
                │       └── 来源标签 = "共鸣链1"，序列号 = "共鸣链1"（用于后续删除/替换）
                │
                └──→ 同步到 KeywordAssociationPage（关键词关联页）
                        │
                        │  所有效果 → keyword_assoc 表格新增行：
                        │  ┌────────────┬────┬──────────┬────┬──────┬────┬────────┬────┐
                        │  │伤害加成    │(空)│共鸣链1-常1│30  │百分比│共鸣│(编辑)  │ 删除│
                        │  │暴击率      │(空)│共鸣链1-触1│10  │百分比│共鸣│(编辑)  │ 删除│
                        │  │冷凝伤害加成│(空)│共鸣链1-特1│15  │百分比│共鸣│(编辑)  │ 删除│
                        │  └────────────┴────┴──────────┴────┴──────┴────┴────────┴────┘
                        │
                        │  序列号格式："共鸣链{N}-{类型首字}{序号}"
                        │  用户可在此页点击"关键词关联"按钮编辑关联的关键词
                        │
                        └── 触发 _on_change_cb → 进入下游重算链路
```

**共鸣链同步后的下游重算路径：**

```
_sync_chain_to_pages() 完成后触发 _on_change_cb()
        │
        │  此时 _collect_all_items() 会收集到共鸣链新增的词条：
        │   ("伤害加成", 30, "共鸣", "combined_perm", "共鸣链1", "")
        │   ("暴击率", 10, "共鸣", "combined_trigger", "共鸣链1", "")
        │
        ▼
  4 个 SummaryPage.recalc() 重新筛选：
        │  SummaryBonusPage ← 命中：伤害加成(30%) → bonus_zone 更新
        │  SummaryCritPage  ← 命中：暴击率(10%) → crit_rate 更新
        │
        ▼
  ResultPage → 代入更新后的乘区 → 最终伤害更新
        │
        ▼
  ResultListPage → 刷新未锁定卡片的伤害数值
```

**共鸣链启用/关闭：**

```
用户点击共鸣链卡片的"启用/关闭"开关
        │
        ├── 关闭 → _sync_chain_to_pages(item) 清除该链所有效果
        │   │  综合填写页删除来源为"共鸣链1"的所有行
        │   │  关键词关联页删除序列号含"共鸣链1"的所有行
        │   └── 触发 _on_change_cb → 下游重算（共鸣链效果消失）
        │
        └── 启用 → _sync_chain_to_pages(item) 重新添加所有效果
            │  综合填写页 + 关键词关联页新增对应行
            └── 触发 _on_change_cb → 下游重算（共鸣链效果恢复）
```

### 链路 5：手动添加关键词关联 → 最终伤害

```
用户在 KeywordAssociationPage（关键词关联页）手动添加词条：
  搜索"伤害加深" → 数值 [20] → 来源 [共鸣] → 点击添加
        │
        │  表格新增一行：
        │  ┌────────┬────┬──────┬────┬──────┬────┬────────┬────┐
        │  │伤害加深│(空)│ 关联1│20  │百分比│共鸣│(编辑)  │ 删除│
        │  └────────┴────┴──────┴────┴──────┴────┴────────┴────┘
        │
        │  序列号 "关联1"（_counter 递增，区别于共鸣链同步的"共鸣链X关联N"）
        │
        │  用户可点击"关键词关联"按钮 → 弹窗编辑关键词列表
        │  （关键词用于结果列表的搜索和筛选）
        │
        │ KeywordAssociationPage.get_items() →
        │   [{name:"伤害加深", value:20, eff_type:"加深", source:"共鸣",
        │     sub_name:"", keywords:[], seq:"关联1"}]
        │
        │  注：关键词关联页的数据不经过 _collect_all_items()
        │     而是由 SummaryPage.recalc() 中的 _fill_source_table() 单独收集
        ▼
  SummaryDeepenPage.recalc()  ← 加深乘区筛选
        │  匹配规则：名字含"加深"
        │  命中：伤害加深(20%)
        │
        │  deepen_zone = 1 + 20/100 = 1.20
        ▼
  ResultPage → 代入公式 → 最终伤害
```

### 链路 6：敌人防御减伤 → 最终伤害

```
用户在 EnemyDefensePage（防御减伤页）填写：
  角色等级 [80]（通常自动从 CharBasePage 同步）
  敌人等级 [90]
        │
        │  系统自动汇总综合填写页中所有"无视防御"词条：
        │  例：CombinedEntryPage 中有一行 "无视防御" 数值 18%
        │
        │  EnemyDefensePage.recalc() 计算：
        │  敌方基础防御 = 792 + 8 × 90 = 1512
        │  敌方最终防御 = 1512 × (1 − 0.18) = 1240
        │  def_zone = (800 + 8×80) / (1240 + 800 + 8×80) = 1440 / 2680 = 0.537
        ▼
  ResultPage → 接收 def_zone = 0.537 → 代入公式

---

注意：防御乘区的数据来源是"无视防御"词条
  → 该词条来自 CombinedEntryPage（综合填写页）
  → 可能由用户手动添加，也可能由共鸣链同步添加
  → EnemyDefensePage 只负责汇总和计算，不存储词条本身
```

### 链路 7：敌人抗性 → 最终伤害

```
用户在 EnemyResistancePage（抗性数值页）操作：
  方式一：点击预设按钮（世界/深塔/全息）→ 自动填充 6 元素抗性值
  方式二：手动填写每个元素的基础抗性/抗性提升/抗性减少
        │
        │  例：冷凝元素
        │  基础抗性 [10%]  抗性提升 [30%]  抗性减少 [0%]
        │
        │  系统自动汇总综合填写页中所有"抗性减免"词条（如有）
        │
        │  EnemyResistancePage._recalc() 计算：
        │  最终抗性 = 10% × (1 + 30%) − 0% = 13%
        │  抗性乘区 = 1 − 13/100 = 0.87
        ▼
  ResultPage → 接收 res_zone = 0.87
        │  根据用户选择的元素（如"冷凝"）取对应的抗性乘区
        │  代入公式 → 最终伤害

---

注：6 个元素各自独立计算，ResultPage 根据筛选条件中的"元素"选择取哪个值
  用户选"冷凝" → 取冷凝抗性乘区
  用户选"热熔" → 取热熔抗性乘区
```

### 链路 8：独立乘区 → 最终伤害

```
用户在 IndepZonePage（独立乘区页）填写：
  组1：组名 [共鸣技能独立]
    ┌──────────────┬──────┐
    │共鸣技能伤害提升│ 25%  │
    └──────────────┴──────┘
  组2：组名 [声骸独立]
    ┌──────────────┬──────┐
    │声骸技能伤害提升│ 15%  │
    └──────────────┴──────┘
        │
        │  计算规则：组内加法、组间乘法
        │  组1合计 = 25%
        │  组2合计 = 15%
        │
        │  indep_zone = (1 + 25/100) × (1 + 15/100) = 1.25 × 1.15 = 1.4375
        ▼
  ResultPage → 接收 indep_zone = 1.4375 → 代入公式
```

### 链路 9：ResultPage → 最终伤害计算 → 结果列表

```
ResultPage（计算结果页）汇总所有乘区：
        │
        │  用户设置筛选条件：
        │  ┌──────────┬────────┬──────────┬────────┬──────────┐
        │  │基础值类型 │  元素  │ 技能类型 │  效应  │  关键词   │
        │  │  攻击    │  冷凝  │   普攻   │  无    │ [普攻]   │
        │  └──────────┴────────┴──────────┴────────┴──────────┘
        │
        │  用户设置倍率：
        │  基础倍率 [100%]  倍率增加 [0]  倍率增幅 [0]
        │
        │  关键词关联注入（与 ResultListPage 卡片相同逻辑）：
        │  用户添加的关键词与 KeywordAssociationPage 条目做交集匹配
        │  匹配的效果注入 filtered_items 参与乘区计算
        │  点击"计入结果"时关键词随 _last_computed 传递到卡片
        │
        │  公式计算：
        │  mult_zone = (100 + 0) × (1 + 0/100) = 100
        │
        │  最终伤害 = base_zone × bonus_zone × deepen_zone × crit_zone
        │             × def_zone × res_zone × indep_zone × mult_zone / 100
        │
        │  输出显示（仅计算过程，计算结果 QGroupBox 已移除）：
        │  ┌────────────────────────────────────────────┐
        │  │  [基础数值] (612 + 337) × (1 + 12.4%) = ... │
        │  │  [加成乘区] 1 + 30% + 20% = 1.50           │
        │  │  [暴击率] (5% + 69.4%) = 74.4%             │
        │  │  [暴击乘区] (150% + 100%) / 100 = 2.50     │
        │  │  ...                                        │
        │  │  暴击后伤害 = 12,345                        │
        │  └────────────────────────────────────────────┘
        │
        │  用户点击"计入结果"：
        ▼
  ResultListPage（结果列表页）
        │
        │  生成一张结果卡片：
        │  ┌────────────────────────────────────────────────────┐
        │  │  标题（可编辑）        关键词：[xxx]                 │
        │  │  基准：攻击力          元素：冷凝  技能：普攻        │
        │  │  暴击伤害：12,345      非暴击伤害：5,678             │
        │  │  基础×1011.6  加成×1.3  加深×1.2  暴击×2.0 ...     │
        │  │  [锁定] [更新] [展开] [删除]                         │
        │  └────────────────────────────────────────────────────┘
        │
        │  用户可操作：
        │  - 搜索：按标题和关键词过滤
        │  - 关键词：每张卡片可添加（最多30字符）
        │  - 锁定：锁定后自动更新不覆盖
        │  - 展开：非模态详情弹窗，可同时操作主界面
        │  - 批量：多选后批量锁定/解锁/删除
        │  - 自动更新：开启后上游变更自动刷新未锁定卡片
```

### 链路 10：上游任意变更 → 全局回调链

```
当任意上游页面的数据发生变更时（添加/编辑/删除/共鸣链同步）：
        │
        │  触发该页面的 _on_change_cb()
        │
        ├──→ 1. EnemyDefensePage.recalc()
        │       汇总综合填写页中所有"无视防御"词条 → 重新计算 def_zone
        │
        ├──→ 2. EnemyResistancePage._recalc()
        │       汇总综合填写页中所有"抗性减免"词条 → 重新计算 res_zone
        │
        ├──→ 3. 四个 SummaryPage.recalc()
        │       重新调用 _collect_all_items() 收集所有上游数据
        │       按乘区筛选 → 填表 → 合计 → 更新各乘区数值
        │       同时处理关键词关联页的数据
        │
        ├──→ 4. ResultPage.auto_compute()
        │       受"自动更新"开关控制（按钮文本：开启/关闭自动更新）
        │       代入所有更新后的乘区 → 计算最终伤害 → 生成过程 HTML
        │
        └──→ 5. ResultListPage.recalc()
                受"自动更新"开关控制（按钮文本：开启/关闭自动更新）
                刷新所有未锁定卡片的伤害数值 + 重新生成计算过程 HTML
                同步已打开的详情弹窗
```

### 链路 11：总结页反向编辑 → 上游同步

```
用户在 SummaryPage（数值总结页）编辑副名称或数值：
        │
        │  副名称编辑：
        │  _on_summary_sub_name_changed(new_sub)
        │    匹配条件：name + source + seq_label 三元组
        │    找到 CombinedEntryPage 对应行 → rd['sub_name_edit'].setText(new_sub)
        │    → 触发该页 _on_item_value_changed → 全局重算
        │
        │  数值编辑：
        │  _on_summary_value_changed(new_val)
        │    同理，回写 CombinedEntryPage 对应行的 value_spin
        │    → 触发该页 _on_item_value_changed → 全局重算
        │
        │  注：只能回写 CombinedEntryPage 的行（综合填写页）
        │     CharBasePage、EchoPage、KeywordAssociationPage 不可从总结页编辑
        │     共鸣链同步的行可通过综合填写页间接修改
```

### 链路 12：存档保存/加载

```
保存：collect_full_state()
    │
    ├── CharBasePage → {char_level, base_hp, base_atk, base_def, weapon_base, ...}
    ├── CombinedEntryPage × 2 → {rows: [{name, value, source, sub_name, locked, seq}, ...], counter}
    ├── EchoCounterPage → {echoes, echo_id_counter}
    ├── EchoPage × N → {cost, main_stat, fixed_stat, sub_stats}
    ├── EnemyDefensePage → {char_level, enemy_level, trigger_states}
    ├── EnemyResistancePage → {spins, boost_checks, trigger_states, preset}
    ├── ResonanceBuffPage → {items: [{id, name, enabled, effects}, ...]}
    ├── KeywordAssociationPage → {items: [{name, value, eff_type, source, sub_name, keywords, seq}, ...], counter, chain_counter}
    ├── ResultListPage → {items, auto_update}
    ├── ResultPage → {filter states, auto_compute, mult settings}
    └── 其他 → theme, base_override, hidden/locked sets

加载：apply_state()
    │
    ├── 1. 恢复主题
    ├── 2. 恢复 CharBasePage
    ├── 3. 恢复 CombinedEntryPage × 2（_restore_table_page）
    │       → counter = saved_counter
    │       → 逐行 _add_row_with_source(name, value, seq, source)
    │       → 恢复 sub_name、locked 状态
    ├── 4. 恢复 EchoCounterPage + EchoPages
    ├── 5. 恢复 EnemyDefensePage + EnemyResistancePage
    ├── 6. 恢复 ResultPage 筛选状态
    ├── 7. 恢复 IndepZonePage
    ├── 8. 恢复 SummaryPages（通过 recalc 重新计算）
    ├── 9. 恢复 ResonanceBuffPage（更新已有卡片，不同步）
    ├── 10. 恢复 KeywordAssociationPage
    │       → 有 seq 的：add_effect_with_seq(seq) ← 不递增计数器
    │       → 无 seq + 共鸣链来源：add_effect(chain_prefix) ← 递增 _chain_counter
    │       → 无 seq + 其他来源：add_effect() ← 递增 _counter
    ├── 11. 恢复 ResultListPage
    ├── 12. 恢复基础数值覆盖
    └── 13. 导航到安全落地页
```

### 链路 13：数据流调试器（DataFlowViewerDialog）

```
侧边栏点击"数据流"按钮 → 打开非模态 DataFlowViewerDialog

窗口结构（5 列树形视图 + 文本报告区）：
┌──────────────────────────────────────────────────────────────────────────┐
│ [刷新] [复制报告] [关闭]                                                 │
├──────────────────────────────────────────────────────────────────────────┤
│ ▼ 上游：数据来源（64 条）                                                │
│   ▼ 角色武器（5 条）                                                     │
│     #001 角色基础攻击力 = 612.0    [基础]    来源:角色武器    ✅ 一致     │
│     #002 武器基础攻击力 = 337.0    [基础]    来源:角色武器    ✅ 一致     │
│   ▼ 声骸4费（7 条）                                                     │
│     #016 [声骸]主词条-暴击率 = 22.0 [暴击率] 来源:声骸4费    ✅ 一致     │
│   ▼ 共鸣（6 条）                                                        │
│     #051 暴击率加成 = 15.0         [暴击率]  来源:共鸣        ✅ 一致     │
│ ▼ 中间层：关键词关联（8 条）                                             │
│   ▼ 共鸣链同步（6 条）                                                   │
│     伤害提升 = 35.0                [加成]    来源:共鸣链效果   ← #052    │
│ ▼ 中游：乘区汇总                                                        │
│   ▼ 基础乘区（17 条, 合计=1452.8）                                      │
│   ▼ 加成乘区（19 条, 合计=867.3）                                       │
│   ▼ 暴击率（8 条, 合计=99.4）                                           │
│   ▼ 暴击伤害（7 条, 合计=357.6）                                        │
│   ▼ 独立乘区（乘积=1.0000, 0 组）                                       │
│ ▼ 下游：计算结果（真实 vs 独立对比）                                     │
│   基础乘区: 2124.2620           (基础612+武器337 百分比+123.8%)  ✅ 一致  │
│   加成乘区: 3.7500              (Σ加成=+275.0%)                 ✅ 一致  │
│   暴击率:   74.4000%            (5% + Σ=69.4%)                  ✅ 一致  │
│   暴击伤害: 3.0760              ((150+Σ)/100=3.0760)            ✅ 一致  │
│   ✅ 全部一致                                                            │
├──────────────────────────────────────────────────────────────────────────┤
│ === 数据流调试器报告 ===                                                 │
│ 【上游：数据来源】                                                       │
│   #001 角色基础攻击力 = 612.0  [基础]  来源:角色武器                      │
│   ...（完整文本，可复制）                                                │
│ 【下游：计算结果（真实 vs 独立对比）】                                    │
│   基础乘区: 2124.2620  ✅                                                │
│   结论: ✅ 全部一致                                                      │
└──────────────────────────────────────────────────────────────────────────┘

核心原理：
  1. 上游数据 → 直接读取各页面的 collect_data() / _items，每条分配唯一 ID（#001 格式）
     - HSV 黄金角旋转生成颜色，每条 ID 用彩色描边文字显示
     - 分类用 classify_item_category() 路由到乘区
  2. 中间层 → 读取 KeywordAssociationPage.get_items()，显示共鸣链同步和手动添加的关联
  3. 中游 → 按乘区分组汇总（基础/加成/加深/暴击率/暴击伤害/防御/抗性/独立乘区）
  4. 下游 → 真实计算（调用 ResultPage.compute()）vs 独立计算（_collect_all_items + 筛选 + 关键词注入）
     - 真实值从 _last_computed["zones"] 读取
     - 独立值从收集的 items 用相同逻辑计算
     - 逐乘区对比，差值 < 0.001 视为一致
     - 不一致时红色 ⚠️ 标记并显示差值
  5. 文本报告 → 底部 QTextEdit 显示完整报告，"复制报告"一键复制到剪贴板

窗口特性：
  - 非模态（可同时操作主界面）
  - 列宽按比例自适应窗口宽度（_COL_RATIOS 比例分配）
  - 水平滚动条始终显示，Shift+滚轮可水平滚动
  - 点击三角形/双击文字可展开收起节点
```

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
| `CombinedEntryPage` | 1248 | 综合填写页（来源：武器谐振/合鸣效果/技能效果/角色效果/其他效果/共鸣链效果/关联效果/首位声骸效果） |
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
| `ResultPage` | 6688 | 伤害计算（筛选/倍率/关键词关联/计算过程 HTML，已移除计算结果 QGroupBox） |
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
| `ResonanceChainEditDialog` | 4232 | 共鸣链编辑（3 页：共鸣链介绍 / 通用增益 / 特定增益，实时同步） |
| `DataFlowViewerDialog` | ~4470 | 数据流调试器（5 列：项目/数值/分类/序列号/副名称状态，实时计算+冲突对比+文本报告） |
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
- 全局开关：同时控制结果页 + 结果列表的"自动更新"按钮（文本统一为"开启/关闭自动更新"，半透明背景样式）
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

项目引入了基于 **pytest** 的自动化测试体系，包含 **186 个测试用例**，全部 **2.9 秒内完成**。测试覆盖伤害公式的每个乘区、筛选匹配逻辑、存档格式验证、边界条件、共鸣链同步链路和数据流端到端验证。

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
4. **pytest 自动执行** — `python -m pytest tests\` 自动发现并运行所有测试，2.9 秒内完成 186 个用例。

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
| `TestSyncBasics` | test_sync_chain.py | 4 | 共鸣链→综合填写/关键词关联基础同步 |
| `TestSubNameSync` | test_sync_chain.py | 2 | 副名称在同步过程中不丢失 |
| `TestIncrementalSync` | test_sync_chain.py | 2 | 增删效果后重新同步 |
| `TestSequenceFormat` | test_sync_chain.py | 1 | 关键词关联页序列号格式 |
| `TestClassifyItemCategory` | test_data_flow.py | 46 | 词条名称→乘区分类路由（基础/加成/加深/暴击/防御/抗性） |
| `TestCharBaseFlow` | test_data_flow.py | 5 | 角色基础值→_collect_all_items→基础乘区 |
| `TestCombinedEntryFlow` | test_data_flow.py | 9 | 综合填写→_collect_all_items→各乘区（序列号/副名称/来源） |
| `TestEchoFlow` | test_data_flow.py | 8 | 声骸→_collect_all_items→各乘区（主/固/副词条） |
| `TestMixedSourcesFlow` | test_data_flow.py | 2 | 多来源混合→完整数据流端到端 |
| `TestSourceToZoneCoverage` | test_data_flow.py | 21 | 常见词条名称全覆盖路由验证 |
| **合计** | | **186** | |

### 测试运行器（[tests/run_tests_gui.py](../tests/run_tests_gui.py)）

独立的 PyQt6 GUI 窗口，提供一键测试体验：

- **13 个分类按钮**：全部/伤害公式/存档格式/同步链路/各乘区/筛选/边界/常量
- **自定义参数输入**：直接输入 pytest 原生参数（如 `-k defense --lf`），回车运行
- **实时彩色输出**：通过绿色/通过红色/失败黄色/汇总
- **后台线程**：QThread 执行 pytest，UI 不卡顿
- **命令行快捷**：`python tests/run_tests_gui.py 4` 打开即跑防御乘区
- **使用手册按钮**：内置帮助文档，说明原理和用法
- **启动自动跑**：打开窗口自动执行全部测试

### 使用场景

| 场景 | 操作 | 耗时 |
|------|------|------|
| 修改伤害公式后验证 | 点"全部测试" | 2.9s |
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
- **v0.8**：数据流调试器（DataFlowViewerDialog）— 5 列树形视图 + 文本报告 + 冲突对比
- **v0.8**：数据流调试器下游改为真实计算（调用 ResultPage.compute）+ 独立计算对比，逐乘区 ✅/⚠️ 标记
- **v0.8**：数据流调试器同步筛选条件（元素/技能/效应/关键词），独立计算使用 _collect_all_items 去重数据
- **v0.8**：数据流调试器 Shift+滚轮水平滚动、列宽按比例自适应、"复制报告"一键复制
- **v0.9**：共鸣链介绍页（ResonanceChainEditDialog 新增第一个 Tab）
- **v0.9**：共鸣链卡片布局重构（标题→常驻计数→触发计数→特定计数→介绍框→按钮）
- **v0.9**：暴击乘区拆分为暴击率 + 暴击伤害（classify_item_category + DataFlowViewerDialog）
- **v0.10**：ResultPage 新增关键词关联（标签式输入，逐个添加/删除，与 KeywordAssociationPage 交集匹配）
- **v0.10**：计算结果页移除"计算结果"QGroupBox（纯展示，无程序读取），仅保留计算过程
- **v0.10**：计算过程 HTML 提取为模块级 `_render_process_html` 函数，ResultPage 和卡片弹窗共用
- **v0.10**：卡片计算过程实时更新（_patch_process_html 重新生成，格式与 ResultPage 一致）
- **v0.11**：自动按钮文本统一为"开启/关闭自动更新"，半透明背景样式，固定宽度
- **v0.11**：主工具栏全局自动按钮同步控制结果页 + 结果列表的自动更新状态
- **v0.11**：综合填写新增"首位声骸效果"来源选项

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

卡片式布局，默认 6 张卡片（共鸣链 1~6），两列均分宽度：

- **第一行**：共鸣链名称（可重命名，格式 `前缀的第X个共鸣链`）
- **第二行**：通用增益数量（常驻 + 触发效果条数）
- **第三行**：特定增益数量（特定效果条数）
- **第四~七行**：介绍文本框（只读，可选中复制，带滚动条，最大 120px）
- **第八行**：按钮行 — 启用/关闭（橙/灰）+ 展开编辑（绿）
- **启用联动**：关闭卡片 → 自动从综合填写页和关键词关联页移除所有效果；启用 → 自动恢复

### 共鸣链编辑弹窗（ResonanceChainEditDialog）

3 页分页式编辑：

| 页 | 内容 | 说明 |
|----|------|------|
| 共鸣链介绍 | 可编辑文本区域 | 实时保存到 item["intro"]，卡片表面同步显示 |
| 通用增益 | 常驻 + 触发效果表格 | SearchCombo 输入，支持添加/删除行 |
| 特定增益 | 特定增益效果表格 | 每行可设置特定增益效果 |

- **实时同步**：编辑弹窗内任何变更（名称/数值/副名称/增删行）300ms 防抖后自动同步到综合填写页和关键词关联页
- **启用联动**：卡片启用时效果计入计算，关闭时自动从所有页面移除
- **默认状态**：卡片默认关闭，按钮显示「启用」（暖橙），需主动开启
- **存档兼容**：intro 字段随存档保存/加载，旧存档自动兼容（intro 为空）

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
