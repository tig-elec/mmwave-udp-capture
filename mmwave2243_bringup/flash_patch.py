#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flash_patch.py —— 给 AWR2243BOOST 烧一次 patch 固件(幂等:任何板子直接跑,已烧过会自动跳过)
flash_patch.py -- flash the patch firmware to an AWR2243BOOST once
                  (idempotent: safe to run on any board, an already flashed board is skipped)

背景:fpga_udp.AWR2243_init 绑定的是 MMWL_App_init(..., downloadFw=false),永远不下固件,
配置里 EnableFwDownload=1 不起作用。没 patch 的板子跑的是 ROM 出厂固件,启动日志会出现
  RF Patch Version [0.0.0.0] + "No patch detected"
mmWave Studio 每次启动都下 BSS/MSS patch 到 RAM;这里用 fpga_udp.AWR2243_firmwareDownload()
把内置的 ES1.1 metaImage 烧进板子串行 flash,功能模式(SOP 001)上电自动加载,一块板子只需一次。

Background: fpga_udp.AWR2243_init is bound to MMWL_App_init(..., downloadFw=false) and never
downloads firmware; EnableFwDownload=1 in the config has no effect. A board without the patch
runs the ROM factory firmware and the start-up log shows
  RF Patch Version [0.0.0.0] + "No patch detected"
mmWave Studio downloads the BSS/MSS patch to RAM on every start. This script instead uses
fpga_udp.AWR2243_firmwareDownload() to write the bundled ES1.1 metaImage to the board's serial
flash; it is then loaded automatically at power-up in functional mode (SOP 001). Once per board.

流程 / Steps:
  [1] 读版本(走一次 AWR2243_init 再 poweroff,只用 SPI,不需要 DCA1000)
      - init 失败  → 打印排查提示后退出
      - 已有 patch → 直接退出(--force 可强制重烧)
      - 不是 ES1.1 → 拒绝(内置镜像只适配 ES1.1,MSS 2.2.1.7)
  [2] 烧录 AWR2243_firmwareDownload()
  [3] 再读一次版本,确认 patch 不再是 0.0.0.0
  [1] Read the versions (one AWR2243_init followed by poweroff; SPI only, no DCA1000 needed)
      - init fails        -> print troubleshooting hints and exit
      - patch present     -> exit (--force flashes again)
      - not an ES1.1 part -> refuse (the bundled image only fits ES1.1, MSS 2.2.1.7)
  [2] Flash with AWR2243_firmwareDownload()
  [3] Read the versions again and confirm the patch is no longer 0.0.0.0

前提:板子上电、FTDI USB 接好、SOP 跳线 = 功能模式 001、mmWave Studio 已关、启动器没在跑。
Prerequisites: board powered, FTDI USB connected, SOP jumpers = functional mode 001,
mmWave Studio closed, the launcher not running.

用法 / Usage:  python flash_patch.py [--force]
"""

import os
import re
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = "configFiles/AWR2243_mmwaveconfig.txt"
PY = sys.executable
# TI 例程注释:ES1.0 MSS FW = 2.2.0.3,ES1.1 = 2.2.1.7
# From the TI example: MSS firmware of ES1.0 = 2.2.0.3, of ES1.1 = 2.2.1.7
ES11_MSS = (2, 2, 1, 7)


def _run(code: str) -> str:
    """
    在子进程里跑一段 python,把 C 层 printf 的输出一起完整拿回来(进程退出时 C stdout 才会刷)。
    Run a piece of Python in a subprocess and return all output including the C-level printf
    output (the C stdout is only flushed when the process exits).
    """
    env = {**os.environ, "PYTHONUTF8": "1"}
    p = subprocess.run([PY, "-u", "-c", code], cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    return p.stdout + p.stderr


def _ver(text: str, label: str):
    m = re.search(re.escape(label) + r"\s*\[\s*(\d+)\.\s*(\d+)\.\s*(\d+)\.\s*(\d+)\]", text)
    return tuple(int(x) for x in m.groups()) if m else None


def read_versions():
    """init + poweroff,解析 RF/MSS 版本与 patch 版本。 / init + poweroff, parse the RF/MSS and patch versions."""
    out = _run(
        "import fpga_udp\n"
        f"r = fpga_udp.AWR2243_init({CFG!r})\n"
        "print('INIT_RET', r)\n"
        "fpga_udp.AWR2243_poweroff()\n"
    )
    m = re.search(r"INIT_RET (-?\d+)", out)
    ret = int(m.group(1)) if m else None
    return ret, {
        "rf": _ver(out, "RF Version"),
        "mss": _ver(out, "MSS version"),
        "rf_patch": _ver(out, "RF Patch Version"),
        "mss_patch": _ver(out, "MSS Patch version"),
    }, out


def fmt(v):
    return "?" if v is None else ".".join(map(str, v))


def has_patch(v):
    return v["rf_patch"] is not None and v["mss_patch"] is not None \
        and v["rf_patch"][0] != 0 and v["mss_patch"][0] != 0


def main() -> int:
    force = "--force" in sys.argv
    os.chdir(HERE)
    if not os.path.exists(CFG):
        print(f"[FATAL] {CFG} not found")
        return 1
    try:
        import fpga_udp  # noqa: F401  只是确认当前解释器里装了 / only checks that it is installed
    except Exception as e:
        print("[FATAL] fpga_udp is not installed in the current Python:", repr(e))
        print("        Run build_ubuntu.sh (Linux) or build_windows.bat (Windows) first")
        return 1

    print("=" * 60)
    print("  AWR2243 patch firmware flashing")
    print("=" * 60)

    # ---- [1] 读版本 / Read the versions ----
    print("[1/3] Reading the board versions (AWR2243_init -> poweroff) ...")
    ret, v, out = read_versions()
    if ret != 0:
        print(f"[FATAL] AWR2243_init returned {ret}: no connection to the radar, nothing was flashed. Check:")
        print("   0) Are the SOP jumpers set to functional mode 001 (middle jumper of P2 removed)? -8 is almost always this")
        print("   1) Is mmWave Studio open? Is start_awr2243.py or a capture script still running? They hold the FTDI device")
        print("   2) Are all four channels AR-DevPack-EVM-012 A~D present in Device Manager?")
        print("---- raw output ----")
        print(out[-3000:])
        return 2
    print(f"      RF {fmt(v['rf'])}  MSS {fmt(v['mss'])}  |  RF patch {fmt(v['rf_patch'])}  MSS patch {fmt(v['mss_patch'])}")

    if has_patch(v) and not force:
        print("[OK] The board already has the patch, nothing to do. (use --force to flash again)")
        return 0
    if v["mss"] != ES11_MSS:
        print(f"[FATAL] MSS firmware {fmt(v['mss'])} is not ES1.1 (expected {fmt(ES11_MSS)}). "
              f"The bundled metaImage only fits ES1.1, refusing to flash.")
        print("        An ES1.0 board needs a different image in fpga_udp/src/mmwaveDFP_2G/firmware and a rebuild of fpga_udp.")
        return 3

    # ---- [2] 烧录 / Flash ----
    print("[2/3] Flashing the metaImage to the board's serial flash (about 3 s) ...")
    out = _run(
        "import fpga_udp\n"
        "r = fpga_udp.AWR2243_firmwareDownload()\n"
        "print('FLASH_RET', r)\n"
    )
    m = re.search(r"FLASH_RET (-?\d+)", out)
    fret = int(m.group(1)) if m else None
    ok = fret == 0 and "Firmware update successful" in out
    for line in out.splitlines():
        if any(k in line for k in ("Download in Progress", "Firmware update", "ES1.", "failed", "error")):
            print("     ", line.strip())
    if not ok:
        print(f"[FATAL] Flashing failed (returned {fret}). ---- raw output ----")
        print(out[-3000:])
        return 4

    # ---- [3] 核实 / Verify ----
    print("[3/3] Power-cycling and reading the versions again ...")
    ret, v, out = read_versions()
    print(f"      RF patch {fmt(v['rf_patch'])}  MSS patch {fmt(v['mss_patch'])}  (init returned {ret})")
    if ret == 0 and has_patch(v):
        print("[OK] Flashing succeeded, the patch is active. From now on just run start_awr2243.py; "
              "this board does not need flashing again.")
        return 0
    print("[WARN] Still no patch after flashing. Raw output:")
    print(out[-3000:])
    return 5


if __name__ == "__main__":
    sys.exit(main())
