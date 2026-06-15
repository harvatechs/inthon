# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['inthon_bin.py'],
    pathex=[],
    binaries=[],
    datas=[('../inthon/parser/grammar.lark', 'inthon/parser')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'transformers', 'numpy', 'pandas', 'matplotlib', 'scipy', 'sklearn', 'pyarrow', 'polars', 'datasets', 'huggingface_hub', 'sympy', 'jedi', 'PyPDF2', 'pdfminer', 'yt_dlp', 'IPython', 'notebook', 'jupyter', 'openai', 'seaborn', 'scikit-learn', 'comm', 'ipykernel', 'ipywidgets', 'widgetsnbextension', 'nbconvert', 'nbformat', 'notebook_shim'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='inthon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['E:\\AITHON\\documents\\icon.ico'],
)
