#!/usr/bin/env bash
# ============================================================================
# build_ubuntu.sh —— 在全新 Ubuntu/Jetson 上一键装好 AWR2243 启动器
# build_ubuntu.sh -- one-step setup of the AWR2243 launcher on a fresh Ubuntu / Jetson
#
#   一条命令搞定:装系统依赖 + 装 libftd2xx + 编译安装 fpga_udp(给 root)+ 自检
#   跑完照末尾提示配网卡、【设 SOP 跳线】、启动即可。
#   One command: system packages + libftd2xx + build and install fpga_udp (for root) + self-check.
#   Afterwards follow the final message: configure the NIC, set the SOP jumpers, start the radar.
#
#   用法 / Usage:  cd mmwave2243_bringup && bash build_ubuntu.sh
#          (脚本内需要 root 的地方会自己 sudo;跑之前会问你要一次 sudo 密码)
#          (the script calls sudo itself where root is needed and asks for the password once)
# ============================================================================
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

ARCH="$(uname -m)"                 # x86_64 或 / or aarch64
echo "============================================================"
echo "  AWR2243 one-step setup  (architecture: $ARCH)"
echo "============================================================"

FTDI_DIR="$HERE/fpga_udp/src/FTDI_D2XX/Linux/$ARCH"
[ -d "$FTDI_DIR" ] || { echo "[FATAL] No FTDI library directory for $ARCH: $FTDI_DIR"; exit 1; }
# 取版本最高的 libftd2xx.so.*(若你放了 1.4.27 就优先用它)
# Use the highest version of libftd2xx.so.* (a 1.4.27 you put there takes priority)
SO_FILE="$(ls "$FTDI_DIR"/libftd2xx.so.* 2>/dev/null | sort -V | tail -n1)"
[ -n "$SO_FILE" ] || { echo "[FATAL] No libftd2xx.so.* found in $FTDI_DIR"; exit 1; }
echo "Using the bundled FTDI library: $(basename "$SO_FILE")"

# ---- 1. 系统依赖 / System packages ----
echo ""; echo "==== [1/5] System packages (build-essential / python3-dev) ===="
sudo apt-get update -y
sudo apt-get install -y build-essential python3-dev python3-pip

# ---- 2. Python 构建依赖(给 root,因为启动器用 sudo 跑)----
# ---- 2. Python build dependencies (for root, because the launcher runs with sudo) ----
echo ""; echo "==== [2/5] Python dependencies (pybind11 / numpy, installed for root) ===="
sudo python3 -m pip install --upgrade pip
sudo python3 -m pip install pybind11 numpy

# ---- 3. 安装 libftd2xx(运行期 /usr/local/lib + 链接期工程内软链)----
# ---- 3. Install libftd2xx (runtime: /usr/local/lib; link time: symlink inside the project) ----
echo ""; echo "==== [3/5] Installing libftd2xx ===="
BASENAME="$(basename "$SO_FILE")"                       # 例 / e.g. libftd2xx.so.1.4.27
sudo cp -f "$SO_FILE" /usr/local/lib/
sudo chmod 0755 "/usr/local/lib/$BASENAME"
sudo ln -sf "/usr/local/lib/$BASENAME" /usr/local/lib/libftd2xx.so
sudo ln -sf "/usr/local/lib/$BASENAME" /usr/local/lib/libftd2xx.so.1
sudo ldconfig
ln -sf "$BASENAME" "$FTDI_DIR/libftd2xx.so"             # 链接期 -lftd2xx 需要 / needed by -lftd2xx at link time
echo "     runtime library: $(ls -l /usr/local/lib/libftd2xx.so | awk '{print $NF}')"

# ---- 4. 编译安装 fpga_udp(给 root)/ Build and install fpga_udp (for root) ----
echo ""; echo "==== [4/5] Building and installing fpga_udp (takes about 1-2 minutes) ===="
sudo python3 -m pip install --force-reinstall --no-deps --no-cache-dir ./fpga_udp

# ---- 5. 自检 / Self-check ----
echo ""; echo "==== [5/5] Self-check ===="
sudo python3 - <<'PY'
import fpga_udp
from mmwave.dataloader import DCA1000
assert hasattr(fpga_udp, "AWR2243_init"), "fpga_udp has no AWR2243_init"
print("  fpga_udp.add(1,2) =", fpga_udp.add(1, 2), " (3 means the extension works)")
print("  AWR2243_init available:", hasattr(fpga_udp, "AWR2243_init"))
print("  DCA1000 import: OK")
PY

cat <<'EOF'

============================================================
  [OK] Installation complete. After connecting the hardware:

  ** Step 0 (most important: hardware jumpers) **
     Set the SOP jumpers on the AWR2243BOOST to functional mode, SOP4 = binary 001:
        P3(SOP2)=open   P2(SOP1)=open (remove the middle jumper)   P4(SOP0)=closed
     Otherwise the radar does not answer on SPI and init returns -8.
     (The Dev mode 011 used by mmWave Studio does not work with this code; it must be 001)

  1) Configure the NIC connected to the DCA1000 (find its name with: ip a):
        sudo ip addr add 192.168.33.30/24 dev <interface>
        ip neigh show | grep 192.168.33.180   # a MAC address means the DCA1000 link is OK (it does not answer ping)

  2) Start the radar (continuous transmission):
        sudo rmmod ftdi_sio usbserial 2>/dev/null
        sudo python3 start_awr2243.py

  3) In another terminal run your capture script (capture.py / capture_plot.py) to receive the data

  See README.md for details
============================================================
EOF
