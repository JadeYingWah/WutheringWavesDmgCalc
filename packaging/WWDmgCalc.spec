# -*- mode: python ; coding: utf-8 -*-
import sys, os

# 自动定位 rapidocr_onnxruntime（兼容不同 env/CI）
_rapidocr = None
for _p in sys.path:
    _try = os.path.join(_p, 'rapidocr_onnxruntime')
    if os.path.isdir(_try):
        _rapidocr = _try
        break
if not _rapidocr:
    raise FileNotFoundError('rapidocr_onnxruntime not found — pip install rapidocr-onnxruntime')

# ── 主程序 ──
a = Analysis(
    ['../WWDmgCalc.py'],
    pathex=['..'],
    binaries=[],
    datas=[
    ('../manual', 'manual'),
    ('../error_handler', 'error_handler'),
    ('../damage_calc.py', '.'),
    ('../summary_pages.py', '.'),
    ('../shared_state.py', '.'),
    ('../indep_zone.py', '.'),
    ('../enemy_res.py', '.'),
    ('../preset_manager.py', '.'),
    ('../preset_builder.py', '.'),
    ('../preset_loader.py', '.'),
    ('../theme_system.py', '.'),
    ('../ocr_engine.py', '.'),
    ('../ico/icon.ico', '.'),
    ('../models', 'models'),
    (_rapidocr, 'rapidocr_onnxruntime'),
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
        ('../ico/icon.ico', '.'),
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
