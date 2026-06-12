# -*- mode: python ; coding: utf-8 -*-

# ── 主程序 ──
a = Analysis(
    ['../WWDmgCalc.py'],
    pathex=['..'],
    binaries=[],
    datas=[
    ('../manual', 'manual'),
    ('../error_handler', 'error_handler'),
    ('../damage_calc.py', '.'),
    ('../ico/icon.ico', '.'),
    ('../models', 'models'),  # PP-OCRv5 自定义 ONNX 模型
],
    hiddenimports=['onnxruntime', 'cv2', 'pyclipper', 'shapely', 'yaml', 'six',
                   'error_handler.error_system'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['paddleocr', 'paddle', 'paddlex', 'torch', 'torchvision', 'scipy', 'pandas', 'skimage', 'modelscope'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WWDmgCalc',
    icon='../ico/icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WWDmgCalc',
)

# ── 外部错误报告程序（独立 .exe） ──
a2 = Analysis(
    ['../error_handler/error_viewer.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../ico/icon.ico', '.'),  # 窗口图标
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['paddleocr', 'paddle', 'paddlex', 'torch', 'torchvision', 'scipy', 'pandas', 'skimage', 'modelscope'],
    noarchive=False,
    optimize=0,
)
pyz2 = PYZ(a2.pure)

exe2 = EXE(
    pyz2,
    a2.scripts,
    exclude_binaries=True,
    name='ErrorViewer',
    icon='../ico/icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll2 = COLLECT(
    exe2,
    a2.binaries,
    a2.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ErrorViewer',
)
