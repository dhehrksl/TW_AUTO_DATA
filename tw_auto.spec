# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 현재 디렉토리 (프로젝트 루트)
project_root = os.getcwd()
src_path = os.path.join(project_root, 'src')

a = Analysis(
    ['src/main.py'],  # src 폴더 안의 main.py 지정
    pathex=[src_path], # src 폴더를 모듈 검색 경로에 추가
    binaries=[],
    datas=[('assets', 'assets')], # assets 폴더를 exe 내부에 포함
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='tw_auto',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/my_icon.ico', # 아이콘 경로 수정
)
