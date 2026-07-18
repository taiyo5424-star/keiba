"""JRA-VAN JV-Link export boundary.

Keep JV-Link-specific code here and export normalized CSV files for the rest
of the project. The model and EV pipeline should not import COM objects.
"""

from pathlib import Path
import platform


EXPORT_DIR = Path("data/jra_van_exports")


def check_environment() -> None:
    if platform.architecture()[0] != "32bit":
        raise RuntimeError(
            "JV-Link is a 32-bit COM component in this setup. Run this probe "
            "with 32-bit Python or use scripts/probe_jvlink.ps1 through "
            "SysWOW64 PowerShell."
        )

    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pywin32 is not installed for this Python. Use the PowerShell probe "
            "or install pywin32 into a 32-bit Python environment."
        ) from exc

    jv = win32com.client.Dispatch("JVDTLab.JVLink")
    result = jv.JVInit("UNKNOWN")
    if result != 0:
        raise RuntimeError(f"JVInit failed: {result}")


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    print("JV-Link export boundary is ready.")
    print(f"Future export directory: {EXPORT_DIR}")
    try:
        check_environment()
    except RuntimeError as exc:
        print(f"python_com_probe=skipped_or_failed: {exc}")
        print("powershell_probe=scripts/probe_jvlink.ps1")
    else:
        print("python_com_probe=ok")


if __name__ == "__main__":
    main()
