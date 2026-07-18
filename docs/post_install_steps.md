# TARGET / JV-Link post-install steps

Status observed on 2026-06-14:

- JV-Link installed under `C:\Program Files (x86)\JRA-VAN\Data Lab`.
- TARGET frontier JV launched as `TFJV`.
- TARGET is expanding historical data on first startup.
- Data Lab. utilization key was entered by the user.
- 32-bit PowerShell COM probe returned `JVInit=0`.
- JV-Link `RACE` export succeeded with this-week data.
- Raw export created `data/jra_van_exports/raw_race_records.csv`.

## While TARGET is expanding data

Do not cancel unless it stops for a very long time with no disk/CPU activity.

This first run can take a long time because TARGET prepares historical race data.

## After expansion completes

1. Confirm TARGET opens normally.
2. Confirm Racing Viewer integration later from TARGET settings.
3. Extend JV-Link extraction to odds snapshots.
4. Add full fixed-width parsers for RA/SE records.

## Local checks

```powershell
& "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" src/jvlink_export_stub.py
& "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "scripts\probe_jvlink.ps1"
& "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "scripts\export_jvdata_raw.ps1"
& "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" src\normalize_jv_race.py
```

Next coding target after the key is configured:

- replace `src/jvlink_export_stub.py` with a COM probe that calls JV-Link initialization
- export normalized races/starts/odds snapshots into `data/jra_van_exports/`
