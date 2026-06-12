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
  │   ├── official/
  │   └── user/
  └── save/
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
    print(f'  快捷方式: {os.path.basename(link_lnk)} -> {target}')


def main():
    # 1. 创建目标文件夹
    folders = [
        os.path.join(OUT, 'WWDmgCalc'),
        os.path.join(OUT, 'ErrorViewer'),
        os.path.join(OUT, 'presets', 'official'),
        os.path.join(OUT, 'presets', 'user'),
        os.path.join(OUT, 'config'),
        os.path.join(OUT, 'save'),
    ]
    for f in folders:
        os.makedirs(f, exist_ok=True)
    print('[OK]文件夹结构已创建')

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
        print('[OK]WWDmgCalc 已移入子目录')

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
        print('[OK]ErrorViewer 已移入子目录')

    # 4. 复制 config
    src_cfg = os.path.join(ROOT, 'config', 'auto_all_config.json')
    dst_cfg = os.path.join(OUT, 'config', 'auto_all_config.json')
    if os.path.exists(src_cfg):
        shutil.copy2(src_cfg, dst_cfg)
        print('[OK]config/auto_all_config.json 已复制')


    # 5. 复制官方预设文件到主文件夹 presets/official/
    src_presets = os.path.join(ROOT, 'presets')
    dst_presets = os.path.join(OUT, 'presets')
    if os.path.exists(src_presets):
        for cat in ['official', 'user']:
            src_cat = os.path.join(src_presets, cat)
            dst_cat = os.path.join(dst_presets, cat)
            if os.path.exists(src_cat):
                shutil.copytree(src_cat, dst_cat, dirs_exist_ok=True)
                print(f'  presets/{cat} 已复制')

    # 6. 复制存档文件
    src_save = os.path.join(ROOT, 'save')
    dst_save = os.path.join(OUT, 'save')
    if os.path.exists(src_save):
        shutil.copytree(src_save, dst_save, dirs_exist_ok=True)
        print(f'  save/ 已复制')

    # 7. 创建快捷方式
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

    print()
    print(f'打包完成: {OUT}')
    print('结构:')
    for root, dirs, files in os.walk(OUT):
        level = root.replace(OUT, '').count(os.sep)
        indent = '  ' * level
        print(f'{indent}{os.path.basename(root)}/')
        if level < 3:
            subindent = '  ' * (level + 1)
            for f in sorted(files):
                print(f'{subindent}{f}')


if __name__ == '__main__':
    main()
