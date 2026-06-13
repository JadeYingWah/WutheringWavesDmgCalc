# -*- coding: utf-8 -*-
"""打包后处理脚本：将 PyInstaller 扁平输出重组为用户友好的结构。

目标结构：
  dist/WutheringWavesDmgCalc/          ← 主文件夹
  ├── WWDmgCalc/                       ← 主程序
  │   ├── WWDmgCalc.exe
  │   └── _internal/
  ├── ErrorViewer/                     ← 错误报告程序
  │   ├── ErrorViewer.exe
  │   └── _internal/
  ├── WWDmgCalc.exe                    ← 快捷方式（.lnk）
  ├── ErrorViewer.exe                  ← 快捷方式（.lnk）
  ├── config/
  │   └── auto_all_config.json
  ├── presets/
  │   ├── official/                    ← 含官方预设 JSON 文件（复制）
  │   └── user/                        ← 仅空子目录，不含任何文件
  │       ├── character/
  │       ├── character_buff/
  │       ├── echo_set/
  │       └── weapon/
  └── save/                            ← 仅空目录，不含任何存档文件
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, 'dist')
OUT = os.path.join(DIST, 'WutheringWavesDmgCalc')


def create_shortcut(target, link_path, description=''):
    """用 PowerShell 创建 .lnk 快捷方式。"""
    link_lnk = link_path.replace('.exe', '.exe.lnk') if not link_path.endswith('.lnk') else link_path
    if not link_lnk.endswith('.lnk'):
        link_lnk += '.lnk'
    ps = f'''
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("{link_lnk}")
$s.TargetPath = "{target}"
$s.Description = "{description}"
$s.WorkingDirectory = "{os.path.dirname(target)}"
$s.Save()
'''
    subprocess.run(['powershell', '-Command', ps], check=True, capture_output=True)
    print(f'    Shortcut: {os.path.basename(link_lnk)} -> {target}')


def main():
    # 1. 创建目标文件夹
    folders = [
        os.path.join(OUT, 'WWDmgCalc'),
        os.path.join(OUT, 'ErrorViewer'),
        os.path.join(OUT, 'presets', 'official'),
        os.path.join(OUT, 'presets', 'user', 'character'),
        os.path.join(OUT, 'presets', 'user', 'character_buff'),
        os.path.join(OUT, 'presets', 'user', 'echo_set'),
        os.path.join(OUT, 'presets', 'user', 'weapon'),
        os.path.join(OUT, 'config'),
        os.path.join(OUT, 'save'),
    ]
    for f in folders:
        os.makedirs(f, exist_ok=True)
    print('[OK] Folders created')

    # 2. 移动 WWDmgCalc 到子目录
    src_ww = os.path.join(DIST, 'WWDmgCalc')
    dst_ww = os.path.join(OUT, 'WWDmgCalc')
    if os.path.exists(src_ww):
        for item in os.listdir(src_ww):
            s = os.path.join(src_ww, item)
            d = os.path.join(dst_ww, item)
            if os.path.isdir(s):
                if not os.path.exists(d):
                    shutil.move(s, d)
            else:
                shutil.move(s, d)
        shutil.rmtree(src_ww, ignore_errors=True)
        print('[OK] WWDmgCalc moved')

    # 3. 移动 ErrorViewer 到子目录
    src_ev = os.path.join(DIST, 'ErrorViewer')
    dst_ev = os.path.join(OUT, 'ErrorViewer')
    if os.path.exists(src_ev):
        for item in os.listdir(src_ev):
            s = os.path.join(src_ev, item)
            d = os.path.join(dst_ev, item)
            if os.path.isdir(s):
                if not os.path.exists(d):
                    shutil.move(s, d)
            else:
                shutil.move(s, d)
        shutil.rmtree(src_ev, ignore_errors=True)
        print('[OK] ErrorViewer moved')

    # 4. 复制 config
    src_cfg = os.path.join(ROOT, 'config', 'auto_all_config.json')
    dst_cfg = os.path.join(OUT, 'config', 'auto_all_config.json')
    if os.path.exists(src_cfg):
        shutil.copy2(src_cfg, dst_cfg)
        print('[OK] config copied')


    # 5. 复制官方预设文件——只复制 official/，user/ 仅保留空目录
    src_presets = os.path.join(ROOT, 'presets')
    dst_presets = os.path.join(OUT, 'presets')
    if os.path.exists(src_presets):
        src_official = os.path.join(src_presets, 'official')
        dst_official = os.path.join(dst_presets, 'official')
        if os.path.exists(src_official):
            shutil.copytree(src_official, dst_official, dirs_exist_ok=True)
            print('  presets/official copied')
        # user/ 子目录已在步骤1建好（空目录），不复制任何文件

    # 6. 存档目录——仅保留空目录，不复制任何存档文件
    # save/ 已在步骤1建好，不复制文件
    print('    save/ (空目录，不复制文件)')

    # 7. 复制 CONTRIBUTORS.md
    src_contrib = os.path.join(ROOT, 'CONTRIBUTORS.md')
    dst_contrib = os.path.join(OUT, 'CONTRIBUTORS.md')
    if os.path.exists(src_contrib):
        shutil.copy2(src_contrib, dst_contrib)
        print('  CONTRIBUTORS.md copied')

    # 8. 移入工具目录（Git 代理 + 上传预设）
    TOOLS_DIR = os.path.join(OUT, 'tools')
    TOOLS_SRC = os.path.join(DIST, '..', 'packaging', 'dist_tools')
    for src_name, exe_name, folder_label in [
        ('GitProxyManager', 'GitProxyManager', 'Git代理管理'),
        ('PresetUploader', 'PresetUploader', '上传官方预设'),
    ]:
        src_path = os.path.join(TOOLS_SRC, src_name)
        dst_path = os.path.join(TOOLS_DIR, folder_label)
        if os.path.exists(src_path):
            if os.path.exists(dst_path):
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            print(f'  tools/{folder_label}/ moved')

    # 8. 创建快捷方式（主程序 + 错误查看器 + 工具）
    create_shortcut(
        os.path.join(OUT, 'WWDmgCalc', 'WWDmgCalc.exe'),
        os.path.join(OUT, 'WWDmgCalc.lnk'),
        '鸣潮伤害计算器'
    )
    create_shortcut(
        os.path.join(OUT, 'ErrorViewer', 'ErrorViewer.exe'),
        os.path.join(OUT, 'ErrorViewer.lnk'),
        '错误查看器'
    )

    # 工具快捷方式
    for folder_label, exe_name in [
        ('Git代理管理', 'GitProxyManager'),
        ('上传官方预设', 'PresetUploader'),
    ]:
        exe_path = os.path.join(OUT, 'tools', folder_label, exe_name + '.exe')
        link_path = os.path.join(OUT, 'tools', folder_label + '.lnk')
        if os.path.exists(exe_path):
            create_shortcut(exe_path, link_path, folder_label)

    print()
    print(f'Build complete: {OUT}')


if __name__ == '__main__':
    main()
