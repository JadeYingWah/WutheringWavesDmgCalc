# 🌊 鸣潮伤害计算器 - Wuthering Waves Damage Calculator

[![Release](https://img.shields.io/github/v/release/JadeYingWah/WutheringWavesDmgCalc)](https://github.com/JadeYingWah/WutheringWavesDmgCalc/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

一个基于 PyQt6 的《鸣潮》（Wuthering Waves）伤害计算器桌面应用。支持 **OCR 截图识别**、**预设系统**、**官方预设一键同步**、**暗色/亮色双主题**。

---

## 📥 下载

前往 [Releases](https://github.com/JadeYingWah/WutheringWavesDmgCalc/releases) 下载最新版本：

1. 下载 `WutheringWavesDmgCalc_v1.0.zip`
2. 解压到任意目录
3. 运行 `WutheringWavesDmgCalc/WWDmgCalc.exe`

> 💡 不需要安装 Python 或任何依赖，解压即用。

---

## ✨ 功能

### 🧮 伤害计算
- 完整 9 大乘区伤害公式：基础 / 加成 / 加深 / 暴击 / 倍率 / 防御 / 抗性 / 独立乘区 / 全伤害
- 角色基础属性、武器、声骸、共鸣链全支持
- 实时计算，修改任意数值自动重算

### 📷 OCR 截图识别
- 声骸面板截图 → 自动识别主词条、副词条、套装名
- 技能倍率截图 → 自动填入倍率数值
- 基于 PP-OCRv5 + ONNX Runtime

### 📋 预设系统
- **角色预设**：基础属性 + 倍率 + 共鸣链效果 + 结果列表
- **武器预设**：基础攻击 + 精炼效果
- **声骸套装预设**：套装阶段效果 + 首位声骸增益
- **角色增益预设**：常驻 + 触发效果 + 关键词关联

### 🔄 官方预设同步
- 一键从 GitHub 拉取最新官方预设
- 多源自动切换（直连 → 镜像 → CDN），国内无需 VPN

### 🎨 双主题
- 暗色 / 亮色主题一键切换

---

## 🛠 附带工具

解压后在 `tools/` 文件夹下有两个独立工具：

| 工具 | 功能 |
|------|------|
| **Git 代理管理** | 自动检测代理端口，一键配置 git 走 VPN |
| **上传官方预设** | GUI 界面上传本地预设到 GitHub（需 Token） |

---

## 📦 最终发布结构

```
WutheringWavesDmgCalc/
├── WWDmgCalc.lnk              ← 快捷方式
├── ErrorViewer.lnk            ← 快捷方式
├── WWDmgCalc/                 ← 主程序
├── ErrorViewer/               ← 错误报告程序
├── tools/                     ← 辅助工具
│   ├── Git代理管理.lnk
│   ├── 上传官方预设.lnk
│   ├── Git代理管理/
│   └── 上传官方预设/
├── config/                    ← 配置文件
├── presets/                   ← 预设文件
│   ├── official/              ← 官方预设（同步源）
│   └── user/                  ← 用户预设
└── save/                      ← 存档目录
```

---

## 🔧 开发者说明

### 环境要求
- Python 3.13
- 虚拟环境 `.venv/`

### 本地运行
```bash
pip install -r requirements.txt
python WWDmgCalc.py
```

### 打包
```bash
cd packaging
pip install pyinstaller
python -m PyInstaller WWDmgCalc.spec --clean
cd tools_specs
python -m PyInstaller git_proxy_manager.spec --distpath ../dist_tools --workpath ../build_tools --clean
python -m PyInstaller preset_uploader.spec --distpath ../dist_tools --workpath ../build_tools --clean
cd ..
python after_build.py
```

---

## 📄 文档

- [项目总结](docs/项目总结.md) — 架构说明、打包规则、数据流
- [版本更新总结](docs/版本更新总结.md) — 版本历史、测试覆盖

> 📌 旧版完整技术文档存档在 `docs/PROJECT_SUMMARY.md.bak`，遇到疑难问题可对照参考。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！如果你制作了新的预设，欢迎通过 PR 贡献到 `presets/official/` 目录。

---

## 📜 许可证

[MIT License](LICENSE)

---

## 📬 联系

- GitHub Issues: [https://github.com/JadeYingWah/WutheringWavesDmgCalc/issues](https://github.com/JadeYingWah/WutheringWavesDmgCalc/issues)
- QQ群: 698544665
 
