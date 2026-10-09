#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
start_awr2243.py —— AWR2243 一键启动器(脱离 mmWave Studio)
start_awr2243.py -- AWR2243 launcher (no mmWave Studio needed)

只做「启动雷达 + ARM DCA1000」这一段,复现 mmWave Studio 干的事。
**不接收、不解析、不存数据** —— 数据交给你自己的 capture.py / streaming.py。
It only starts the radar and arms the DCA1000, i.e. what mmWave Studio does.
It does NOT receive, parse or store data; that is the job of capture.py / streaming.py.

链路分工 / Two links:
  控制链(FTDI USB->SPI, 经 fpga_udp/mmWaveLink):上电 + 发配置 + sensorStart(patch 固件见 flash_patch.py)
  数据链(DCA1000 网口 UDP):config_fpga / config_record / stream_start(ARM 采集卡)
  control (FTDI USB->SPI via fpga_udp/mmWaveLink): power on + send config + sensorStart
                                                   (for the patch firmware see flash_patch.py)
  data    (DCA1000 Ethernet, UDP):                 config_fpga / config_record / stream_start (arm the card)

连续模式(setFrameCfg(0)):雷达一直发波,和 Studio 一样。
=> 本脚本发完 stream_start 就【关掉自己的 DCA socket】释放 4096/4098,
   再 sensorStart;然后你随时开 streaming.py 绑 4098 接正在跑的流(一帧不差地续上)。
Continuous mode (setFrameCfg(0)): the radar keeps transmitting, as with Studio.
=> After stream_start this script closes its own DCA sockets and releases ports 4096/4098,
   then calls sensorStart. streaming.py can bind 4098 at any time and pick up the running stream.

停止:Ctrl-C -> 经 SPI 停雷达(sensorStop)+ 关电(poweroff)。
Stop: Ctrl-C -> stops the radar over SPI (sensorStop) and powers it off (poweroff).

★ 前提(缺一不可) / Prerequisites (all required):
  1. AWR2243 + DCA1000 供电,FTDI(USB)与 DCA1000 网口都接主机
     AWR2243 + DCA1000 powered; FTDI (USB) and the DCA1000 Ethernet port connected to the host
  2. 主机网卡静态 IP 192.168.33.30/24(DCA1000 默认 192.168.33.180)
     Host NIC with static IP 192.168.33.30/24 (the DCA1000 defaults to 192.168.33.180)
  3. [Linux] FTDI 需 root 且内核模块让开:  sudo rmmod ftdi_sio usbserial;用 sudo 跑本脚本
     [Windows] 不需要管理员;装好 FTDI D2XX 驱动(ftd2xx.dll)即可,但 mmWave Studio 必须先关掉(它占着 FTDI)
     [Linux] FTDI needs root and the kernel modules unloaded: sudo rmmod ftdi_sio usbserial; run with sudo
     [Windows] no administrator rights; the FTDI D2XX driver (ftd2xx.dll) must be installed and
               mmWave Studio must be closed (it holds the FTDI device)
  4. fpga_udp 已装好:Linux 跑 build_ubuntu.sh,Windows 跑 build_windows.bat
     fpga_udp installed: run build_ubuntu.sh on Linux, build_windows.bat on Windows
  详见 README.md。 / See README.md for details.
"""

import os
import sys
import time
import signal

# 让相对路径(configFiles/…)不依赖当前工作目录
# Make the relative paths (configFiles/...) independent of the current working directory
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

try:
    import fpga_udp as radar                    # 控制层 / control: AWR2243_* (FTDI SPI + mmWaveLink)
    from mmwave.dataloader import DCA1000       # 数据卡控制 / capture card control: UDP commands
except Exception as e:
    print("[FATAL] Import failed: fpga_udp / mmwave is not installed. "
          "Run build_ubuntu.sh (Linux) or build_windows.bat (Windows) first.")
    print("        Original error:", repr(e))
    sys.exit(1)

# ============ 可修改的设置 / Settings you may change ============
# 雷达参数文件。注意 AWR2243_init 不下固件(绑定 downloadFw=false),patch 用 flash_patch.py 烧一次
# Radar parameter file. Note that AWR2243_init does not download firmware (it is bound to
# downloadFw=false); flash the patch once with flash_patch.py
RADAR_CFG = "configFiles/AWR2243_mmwaveconfig.txt"
# DCA1000 采集卡配置(lvdsMode / packetDelay)
# DCA1000 capture card configuration (lvdsMode / packetDelay)
DCA_CFG   = "configFiles/cf.json"
# 0 = 连续发波(像 Studio);>0 = 打一发定量帧后自停
# 0 = transmit continuously (like Studio); >0 = send this many frames, then stop
NUM_FRAMES = 0


def main():
    print("=" * 60)
    print("  AWR2243 launcher (continuous mode, no mmWave Studio)")
    print("=" * 60)
    for f in (RADAR_CFG, DCA_CFG):
        if not os.path.exists(f):
            print(f"[FATAL] Config file not found: {f}")
            sys.exit(1)

    dca = None
    radar_started = False
    try:
        # --- 1. 复位雷达 + DCA1000 / Reset radar + DCA1000 ---
        print("[1/6] Resetting radar + DCA1000 ...")
        dca = DCA1000()                 # 注意:这会绑 4096 + 4098,稍后 stream_start 后立刻释放
                                        # Note: this binds 4096 + 4098; released right after stream_start
        dca.reset_radar()
        dca.reset_fpga()
        time.sleep(1)

        # --- 2. 经 SPI 初始化雷达:上电 + 发全部配置(不下固件,patch 见 flash_patch.py)---
        # --- 2. Initialise the radar over SPI: power on + send the whole configuration
        #        (no firmware download; for the patch see flash_patch.py) ---
        print(f"[2/6] AWR2243_init: power on + send config ({RADAR_CFG}) ... "
              f"[Linux needs root for SPI; if the log shows RF Patch Version 0.0.0.0, run flash_patch.py first]")
        ret = radar.AWR2243_init(RADAR_CFG)
        print("      AWR2243_init returned", ret)
        if ret != 0:
            print("\n[FATAL] AWR2243_init failed (returned %s): the radar control link (FTDI SPI) is not working. Aborting." % ret)
            print("  The radar was not started; this is not a data-side (DCA1000) problem. Check in this order:")
            print("   0) Are the SOP jumpers set to functional mode 001 (middle jumper of P2 removed)? This causes 99% of the -8 errors.")
            if sys.platform.startswith("win"):
                print("   1) Is mmWave Studio still open? It holds the FTDI device and must be closed first.")
                print("   2) Do the four FTDI channels (AR-DevPack-EVM-012 A~D) show up in Device Manager? The D2XX driver is required.")
            else:
                print("   1) Was the script started with sudo -E? FTDI/SPI needs root.")
                print("   2) Unload the kernel modules: sudo rmmod ftdi_sio usbserial, then run again.")
                print("   3) Does lsusb show the FTDI device (VID 0403, or TI 0451)? If not, check USB / power / wiring.")
            return

        # --- 3. 设帧数:0 = 连续 / Number of frames: 0 = continuous ---
        print(f"[3/6] AWR2243_setFrameCfg({NUM_FRAMES})  (0 = continuous)")
        fret = radar.AWR2243_setFrameCfg(NUM_FRAMES)
        print("      setFrameCfg returned", fret)

        # --- 4. 检查 DCA1000 连通 + LVDS 参数 / Check the DCA1000 link + LVDS parameters ---
        try:
            lvds = dca.AWR2243_read_config(RADAR_CFG)
            dca.refresh_parameter()
            print("[4/6] LVDS parameter:", lvds[0], "must be <=", lvds[1])
            print("      System alive:", dca.sys_alive_check())
            print("      FPGA version:", dca.read_fpga_version())
        except Exception as e:
            print("[4/6][WARN] DCA1000 self-check raised an exception (not fatal):", repr(e))

        # --- 5. 经 UDP 配置并 ARM 采集卡 / Configure and arm the capture card over UDP ---
        print("[5/6] Configuring DCA1000 + stream_start (arming the capture card) ...")
        print("      config_fpga  :", dca.config_fpga(DCA_CFG))
        print("      config_record:", dca.config_record(DCA_CFG))
        print("      stream_start :", dca.stream_start())

        # ★ 释放 4096/4098,让你的 streaming.py 能绑上。FPGA 已被 ARM,自己持续吐数据。
        # Release 4096/4098 so that streaming.py can bind them. The FPGA is armed and keeps sending data.
        dca.close()
        dca = None
        print("      Ports 4096/4098 released (the DCA1000 keeps waiting for radar data)")

        # --- 6. 经 SPI 启动雷达发波 / Start transmitting over SPI ---
        print("[6/6] AWR2243_sensorStart: starting continuous transmission ...")
        sret = radar.AWR2243_sensorStart()
        print("      sensorStart returned", sret)
        if sret != 0:
            print("\n[FATAL] sensorStart failed (returned %s, -8 = response timeout): the radar is not transmitting. Aborting." % sret)
            print("  Usually init / configuration did not really succeed. Make sure [2/6] AWR2243_init returns 0 first.")
            print("  The DCA1000 is armed but receives no data (the radar is not transmitting).")
            return
        radar_started = True

        print("\n" + "=" * 60)
        print("  [OK] Radar is transmitting continuously; the DCA1000 is sending data to 192.168.33.30:4098")
        print("  >>> Now run your capture script (capture.py / capture_plot.py) in another terminal")
        print("  >>> It binds port 4098 and picks up the running stream (continuous mode, start order does not matter)")
        print("  Press Ctrl-C to stop the radar and power it off.")
        print("=" * 60 + "\n")

        # 保持进程存活(fpga_udp 持有 FTDI/雷达会话);雷达在后台自持发波
        # Keep the process alive (fpga_udp holds the FTDI / radar session); the radar transmits on its own
        signal.pause() if hasattr(signal, "pause") else _idle_loop()

    except KeyboardInterrupt:
        print("\n[EXIT] Ctrl-C received, stopping ...")
    except Exception as e:
        import traceback
        print("[ERROR] Exception during start-up:")
        traceback.print_exc()
    finally:
        # 停雷达走 SPI,不需要 DCA socket / Stopping the radar goes over SPI, no DCA socket needed
        if radar_started:
            try:
                print("[EXIT] AWR2243_sensorStop ...")
                radar.AWR2243_sensorStop()
            except Exception as e:
                print("       sensorStop raised:", repr(e))
        try:
            print("[EXIT] AWR2243_poweroff ...")
            radar.AWR2243_poweroff()
        except Exception as e:
            print("       poweroff raised:", repr(e))
        if dca is not None:
            try:
                dca.close()
            except Exception:
                pass
        print("[EXIT] Done. (Stop your capture script with Ctrl-C yourself)")


def _idle_loop():
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
