# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['E:/Python/WutheringWavesDmgCalc/tools/preset_uploader/main.py'],
    pathex=['E:/Python/WutheringWavesDmgCalc/tools/preset_uploader'],
    binaries=[],
    datas=[],
    hiddenimports=['PyQt6.QtWidgets', 'PyQt6.QtCore'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['paddleocr', 'paddle', 'torch', 'torchvision', 'scipy', 'pandas', 'modelscope',
              'onnxruntime', 'cv2', 'PIL', 'numpy', 'shapely', 'pyclipper', 'yaml'],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='PresetUploader',
    icon='E:/Python/WutheringWavesDmgCalc/ico/icon.ico',
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
    disable_windowed_traceback=False, argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[], name='PresetUploader')
