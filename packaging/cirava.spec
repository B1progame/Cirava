# PyInstaller entry point for Cirava's Python + pywebview desktop shell.
from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "backend" / "main.py")],
    pathex=[str(root / "backend")],
    datas=[(str(root / "dist"), "dist"), (str(root / "packaging" / "cirava.ico"), ".")],
    hiddenimports=["webview.platforms.edgechromium", "win32api", "win32con", "win32event", "winerror", "win32gui"],
    name="Cirava",
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="Cirava", console=False, icon=str(root / "packaging" / "cirava.ico"))
