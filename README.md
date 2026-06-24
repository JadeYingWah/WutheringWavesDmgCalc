# 🌊 鸣潮伤害计算器 — Wuthering Waves Damage Calculator

[![Release](https://img.shields.io/github/v/release/JadeYingWah/WutheringWavesDmgCalc)](https://github.com/JadeYingWah/WutheringWavesDmgCalc/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)

一个基于 PyQt6 的《鸣潮》桌面伤害计算器。一个人用 42 天从零独立开发，完全免费开源。

---

## 📥 下载

👉 **[最新版下载](https://github.com/JadeYingWah/WutheringWavesDmgCalc/releases)**

1. 下载 `WutheringWavesDmgCalc_v1.0.zip`
2. 解压到任意文件夹
3. 双击 `WWDmgCalc.lnk` 或运行 `WWDmgCalc/WWDmgCalc.exe`

> 不需要 Python、不需要配环境，解压即用。

---

## ✨ 核心功能

### 🧮 9 大乘区伤害计算
基础 / 加成 / 加深 / 暴击 / 倍率 / 防御 / 抗性 / 独立乘区 / 全伤害，修改任意数值实时重算。

### 📷 OCR 截图识别
声骸面板截图 → 自动识别主词条、副词条、套装名。技能倍率截图 → 自动填入。基于 PP-OCRv5 + ONNX Runtime。

### 📋 预设系统
角色预设、武器预设、声骸套装预设、角色增益预设。支持一键加载、官方同步、本地保存。

### 🔄 官方预设同步
一键从 GitHub 拉取最新预设，国内镜像自动切换，无需 VPN。

### 🎖️ 贡献者系统
预设支持 `author` 字段，欢迎页「🎖️ 贡献者名单」按钮展示所有贡献者。

### 🎨 双主题
暗色 / 亮色一键切换。

---

## 📦 投稿预设

想让你的预设被更多人使用？

1. 用「预设构建器」制作预设，**填写作者名**
2. 打开 `tools/上传官方预设/PresetUploader.exe`（源码位于 `tools/preset_uploader/main.py`）
3. 填写你的 GitHub 用户名 → 选择预设文件 → 提交投稿
4. 自动创建 Pull Request，审核合并后你的名字会出现在贡献者名单中 🎖️

> 💡 你需要一个 GitHub Personal Access Token（repo 权限），在 [GitHub Settings](https://github.com/settings/tokens) 中生成。

---

## 🛠 附带工具

| 工具 | 说明 |
|------|------|
| **Git 代理管理** | 自动检测代理端口，一键配置 git 走 VPN |
| **上传官方预设** | 投稿预设到官方仓库，自动创建 PR 等待审核 |

---

## 📦 发布结构

```
WutheringWavesDmgCalc/
├── WWDmgCalc.lnk
├── ErrorViewer.lnk
├── desktop.ini
├── ico/
│   └── icon.ico
├── WWDmgCalc/          ← 主程序
├── ErrorViewer/        ← 错误报告
├── tools/              ← 独立工具
├── config/             ← 配置
├── presets/
│   ├── official/       ← 官方预设
│   └── user/           ← 用户本地预设
└── save/               ← 存档
```

---

## 🔧 开发者

```bash
# 环境
pip install -r requirements.txt

# 运行
python WWDmgCalc.py

# 测试
pytest tests/ -q

# 打包
cd packaging
rm -rf build dist __pycache__
pyinstaller --clean --noconfirm WWDmgCalc.spec
pyinstaller --clean --noconfirm git_proxy_manager.spec
pyinstaller --clean --noconfirm preset_uploader.spec
cd .. && python packaging/after_build.py
```

---

## 📄 文档

- [项目总结](docs/项目总结.md) — 架构、打包规则、数据流
- [版本更新总结](docs/版本更新总结.md) — 完整版本历史
- [贡献者名单](CONTRIBUTORS.md) — 🎖️ 感谢每一位预设作者

---

## 📬 联系

- GitHub Issues: [反馈 / 建议 / Bug](https://github.com/JadeYingWah/WutheringWavesDmgCalc/issues)
- QQ群: 698544665
