# PyInstaller spec for fleet-agent.exe: one file, the web UI inside, Windows version info.
#
#   cd web && npm ci && npm run build && cd ..
#   uv run --with pyinstaller pyinstaller packaging/fleet-agent.spec
#
# Output: dist/fleet-agent.exe. The release workflow builds it on GitHub's Windows runners
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
from fleet_agent import __version__  # noqa: E402

WEB = ROOT / "web" / "dist"
if not (WEB / "index.html").exists():
    raise SystemExit("Build the web UI first: cd web && npm ci && npm run build")

nums = tuple(int(p) for p in __version__.split(".")[:3]) + (0,)
PRODUCT = "SC Fleet Telemetry"
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=nums, prodvers=nums),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "SC Fleet Telemetry contributors"),
                        StringStruct("FileDescription", "SC Fleet Telemetry agent"),
                        StringStruct("FileVersion", __version__),
                        StringStruct("InternalName", "fleet-agent"),
                        StringStruct("LegalCopyright", "MIT License"),
                        StringStruct("OriginalFilename", "fleet-agent.exe"),
                        StringStruct("ProductName", PRODUCT),
                        StringStruct("ProductVersion", __version__),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "agent"), str(ROOT / "shared")],
    datas=[(str(WEB), "web")],
    hiddenimports=["keyring.backends.Windows", "win32ctypes.core"],
    excludes=["tkinter", "fleet_hub"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="fleet-agent",
    console=True,  # the agent's status lines; closing the window stops it
    upx=False,  # packed executables look suspicious to antivirus and to signing checks
    version=version_info,
)
