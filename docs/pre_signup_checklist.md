# JRA-VAN Data Lab. signup status

Last updated: 2026-06-14 JST

Status:

- Paid registration completed by user.
- Plan includes Racing Viewer.
- Full member ID is not stored in this repository.

Official links:

- Data Lab. product page: https://jra-van.jp/dlb/
- Purchase lineup: https://jra-van.jp/buy/
- Payment methods: https://jra-van.jp/buy/pay.html
- Data Lab. member page / key confirmation: https://app.jra-van.jp/member/WAAlDlb0011.do
- Data Lab. only purchase: https://app.jra-van.jp/member/WAAlDlb0101.do
- Data Lab. + Racing Viewer purchase: https://app.jra-van.jp/member/WAAlSet0101.do?button_name=LabRVSet
- Racing Viewer option only: https://app.jra-van.jp/member/WAAlJrv0009.do

## Selected plan

Selected:

- JRA-VAN Data Lab. with JRA Racing Viewer
- Monthly price shown before signup: 2,640 JPY including tax

Base comparison:

- Data Lab. only: 2,090 JPY/month including tax
- Data Lab. + Racing Viewer: 2,640 JPY/month including tax
- Difference: 550 JPY/month

## Why Racing Viewer is useful here

The Racing Viewer option is useful if video review becomes part of the EV process.

Video-driven checks:

- hidden trip trouble
- finishing action
- pace stress
- whether a horse quit or was blocked
- track bias and lane advantage
- paddock/body movement before the race
- training video impressions

These can become qualitative notes or later structured features.

## Next steps after signup

1. Install TARGET frontier JV and JV-Link from the official Data Lab. flow.
2. Confirm the Data Lab. utilization key is set.
3. Run `src/jvlink_export_stub.py` to verify the local project boundary.
4. Replace the stub with COM extraction code.
5. Export normalized CSVs into `data/jra_van_exports/`.

## Local status check

As of 2026-06-14, local checks did not find an existing JRA-VAN/JV-Link/TARGET install under common Program Files or registry locations.

Next likely action:

- Download the official `JVPlusTF.exe` installer from JRA-VAN.
- Run the installer interactively.
- Let the installer set up TARGET frontier JV and JV-Link.

## If only Data Lab. payment choices appear

The URL is probably the Data Lab.-only purchase page.

Use this page for the intended bundle:

https://app.jra-van.jp/member/WAAlSet0101.do?button_name=LabRVSet

If the bundle path fails, the fallback is:

1. Subscribe to Data Lab. only.
2. Add Racing Viewer separately from https://app.jra-van.jp/member/WAAlJrv0009.do.
