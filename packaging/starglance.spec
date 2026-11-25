# PyInstaller spec for starglance.exe: one file, the web UI inside, a windowed app (tray
# icon and its own window: starglance/app.py), Windows version info and icon.
#
#   cd web && npm ci && npm run build && cd ..
#   uv run --extra app --with pyinstaller pyinstaller packaging/starglance.spec
#
# Output: dist/starglance.exe. The release workflow builds it on GitHub's Windows runners
# and sends it to SignPath for signing (docs/CODE_SIGNING.md).
import sys
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).parent
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "shared")]
from starglance import __version__  # noqa: E402

WEB = ROOT / "web" / "dist"
if not (WEB / "index.html").exists():
    raise SystemExit("Build the web UI first: cd web && npm ci && npm run build")

nums = tuple(int(p) for p in __version__.split(".")[:3]) + (0,)
PRODUCT = "Starglance"
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=nums, prodvers=nums),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "Starglance contributors"),
                        StringStruct("FileDescription", "Starglance agent"),
                        StringStruct("FileVersion", __version__),
                        StringStruct("InternalName", "starglance"),
                        StringStruct("LegalCopyright", "MIT License"),
                        StringStruct("OriginalFilename", "starglance.exe"),
                        StringStruct("ProductName", PRODUCT),
                        StringStruct("ProductVersion", __version__),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

# The icon: the logo, drawn by the app's own code at the sizes Windows uses.
from starglance.app import draw_icon  # noqa: E402

ICON = Path(workpath) / "starglance.ico"
ICON.parent.mkdir(parents=True, exist_ok=True)
draw_icon(256).save(ICON, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "agent"), str(ROOT / "shared")],
    datas=[(str(WEB), "web"), (str(ICON), ".")],
    hiddenimports=[
        "keyring.backends.Windows",
        "win32ctypes.core",
        "pystray._win32",
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "truststore",
        "zstandard",
    ],
    excludes=["tkinter", "starglance_hub"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="starglance",
    console=False,  # a windowed app: tray icon and window; output in logs/starglance.log
    icon=str(ICON),
    upx=False,  # packed executables look suspicious to antivirus and to signing checks
    version=version_info,
)
