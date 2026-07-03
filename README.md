# 📡 mmwave-udp-capture

<a id="chinese"></a>
🌐 **简体中文** · [English](#english)

**基于 DCA1000EVM 的 TI 毫米波雷达实时采集与处理工具。**

直接从 DCA1000EVM 抓取原始 UDP 数据流，借助 **CuPy（CUDA）** 做 FFT，实时解包成 **RA（Range-Azimuth）** 与 **RD（Range-Doppler）** 热力图，可按需保存原始帧数据供后续处理。

> 用 **CuPy** 替代 **NumPy**，把 FFT 等运算搬到 GPU，单帧处理耗时可压到几毫秒，从而支持实时处理。

---

## ✨ 特性

- 直接接收 DCA1000 的 UDP 原始数据 → FFT → RA / RD 图
- 实时可视化+采集保存（`capture_plot.py`）或纯采集保存（`capture.py`）
- 逐帧记录时间戳与状态，支持**硬件触发**做多传感器时间对齐
- 天线配置自适应（`tx = 1 / 2 / 3`），Windows 与 Ubuntu 均可采集

### 已验证支持的型号

| 型号 | 说明 |
|------|------|
| **AWR1843** | 默认配置，`RADAR_TYPE = 0` |
| **AWR1443 / AWR2243** | RX 在 fast-time 流里交织，需设 `RADAR_TYPE = 1` |

> 💡 理论上任何基于 **DCA1000EVM** 的采集卡（例如 **AWR2243-2X-CAS-EVM**）都能抓到数据，但其数据格式需要进一步研究后才能正确解包。

---

## ⚙️ 依赖环境

- **CUDA Toolkit**（与你的 GPU 匹配）
- **CuPy**（版本需与 CUDA 版本对应）
- **matplotlib**（实时绘图）

---

## 🚀 使用方法

目前提供两种运行方式，**方法一（mmWave Studio）最稳，推荐使用**。

### 方法一：通过 mmWave Studio（推荐）

1. 先用 **mmWave Studio** 加载雷达配置并启动毫米波雷达。
2. 待雷达启动后，确认板子上的 **`DATA_TRAN` 指示灯正在闪烁**（表示正在发送数据）。
3. 在 Windows 任务管理器里**结束掉 `DCA1000_recording_cli` 进程**。

   > ⚠️ 如果不结束它，本脚本一旦启动开始抢数据，mmWave Studio 长时间收不到 UDP 就会自动 **stop frame**，导致雷达停止发送。

4. 运行采集脚本：
   - **`capture.py`** —— 保存每一帧的原始数据以及 RA / RD 图。
   - **`capture_plot.py`** —— 在 `capture.py` 的基础上，额外**实时显示** RA / RD 图。
5. 结束采集时，**直接关闭 terminal 即可**。数据会保存下来，每一帧的时间戳与状态也会依次记录。

> 📌 **注意：** 目前只显示 RA 和 RD 图，因此只考虑打开**水平天线**。即使打开了垂直天线，也只显示方位（azimuth）维度。

### 在 Ubuntu 上采集

如果雷达是通过 **mmWave Studio（Windows）** 启动的，那么一旦开始传输数据就**不能更换网卡**——换了网卡将收不到任何数据。因此最稳妥的做法是使用 **USB 网卡**，直接把整个网卡拔下来迁移。

1. 在 Windows 上用 mmWave Studio 启动雷达，启动后拔掉所有 USB 线（防止 stop frame）。
2. **拔掉整个（USB）网卡**，插到 Ubuntu 机器上。
3. **先运行 `config_buffer_once.sh`（一定要运行！）**，调大 UDP 接收缓冲，否则会丢包。
4. 之后照常运行 `capture.py` 或 `capture_plot.py`。

---

## ⏱️ 硬件触发（多传感器同步）

毫米波雷达支持硬件触发：用一路外部 **3.3V 信号**触发雷达，可用于——

- 与其他传感器**时间对齐**；
- 多台毫米波雷达同步触发，**避免互相干扰**。

本脚本支持在外部单片机触发的同时，输入一个**串口字符**，为每一帧打上硬件时间戳。

> ✅ **实测：** 通过「接收每个 UDP 包的时间戳」与「硬件标识时间戳」对比，两者误差在 **1ms 以内**。

> 🛠️ 关于单芯片及 *MMWCAS-RF-EVM*（级联）毫米波雷达如何修改硬件电路来实现硬件触发，**约 2 个月后**会出更详细的教程。

---

## 🔧 配置说明（`config.py`）

| 配置项 | 取值 | 含义 |
|--------|------|------|
| `USE_HARDWARE_TRIGGER` | `False`（默认） | 不启动触发线程，直接用收到数据时打的时间戳 |
| | `True` | 启用硬件触发，来源由 `TRIGGER_SOURCE` 决定 |
| `TRIGGER_SOURCE` | `'serial'` / `'ros'` | 硬触发来源（仅 `USE_HARDWARE_TRIGGER=True` 时生效） |
| `COM_PORT` | 如 `'COM3'` | 串口触发端口（`TRIGGER_SOURCE='serial'` 时） |
| `ROS_TOPIC` | 如 `'serial_trigger'` | ROS 触发 topic（`TRIGGER_SOURCE='ros'` 时） |
| `RADAR_TYPE` | `0` = 1843 | RX 不交织，无需重排 |
| | `1` = 1443 / 2243 | RX 在 fast-time 流里交织，**必须设 1**，否则数据错乱 |

**ADC 参数与天线选取（`ADC_PARAMS`）：** `tx` 决定 `fft.py` 里方位（水平）天线的选取，只做水平方位热力图，不取 elevation：

| `tx` | 选取的天线 | 虚拟天线数 |
|------|-----------|-----------|
| `1` | `[0]` | 1 TX × 4 RX = 4 VA |
| `2`（默认） | `[0, 1]` | 2 TX × 4 RX = 8 VA |
| `3` | `[0, 2]`（取 TX1、TX3 两根水平天线，跳过俯仰 TX2） | 8 VA |

---

## 📂 脚本说明

| 文件 | 作用 |
|------|------|
| `capture.py` | 采集并保存每帧数据 + RA / RD 图 |
| `capture_plot.py` | 在 `capture.py` 基础上实时显示 RA / RD |
| `streaming.py` | UDP 数据接收与组帧核心 |
| `fft.py` | CuPy FFT，解包成 RA / RD |
| `triggers.py` | 硬件触发（serial / ros）时间戳线程 |
| `config.py` | 全部可调参数 |
| `config_buffer_once.sh` | **Ubuntu 上采集前必跑**，调大 UDP 接收缓冲防丢包 |
| `udp buffer/` | 相关网络缓冲配置（`99-udp.conf` 等） |
| `plot.py` | 绘图工具函数 |

---

## 🧩 通过 Cfg 直接启动

> 🚧 等我研究出来再补充。（不依赖 mmWave Studio，直接用配置文件启动雷达的方式）

---
---

<a id="english"></a>
## 🌐 English

[简体中文](#chinese) · **English**

**Real-time acquisition and processing tool for TI mmWave radars based on the DCA1000EVM.**

It grabs the raw UDP data stream directly from the DCA1000EVM, runs the FFT with **CuPy (CUDA)**, and decodes it in real time into **RA (Range-Azimuth)** and **RD (Range-Doppler)** heatmaps. Raw frame data can optionally be saved for further processing.

> By replacing **NumPy** with **CuPy**, the FFT and other operations run on the GPU, cutting per-frame processing to a few milliseconds and enabling real-time processing.

---

### ✨ Features

- Receives raw UDP data from the DCA1000 directly → FFT → RA / RD maps
- Real-time visualization + saving (`capture_plot.py`), or capture-only (`capture.py`)
- Per-frame timestamp & status logging; **hardware trigger** for multi-sensor time alignment
- Adaptive antenna configuration (`tx = 1 / 2 / 3`); works on both Windows and Ubuntu

#### Verified radar models

| Model | Notes |
|-------|-------|
| **AWR1843** | Default, `RADAR_TYPE = 0` |
| **AWR1443 / AWR2243** | RX is interleaved in the fast-time stream; set `RADAR_TYPE = 1` |

> 💡 In principle any DCA1000EVM-based capture card (e.g. **AWR2243-2X-CAS-EVM**) can capture data, but its data format needs further study before it can be decoded correctly.

---

### ⚙️ Requirements

- **CUDA Toolkit** (matching your GPU)
- **CuPy** (version must match your CUDA version)
- **matplotlib** (real-time plotting)

---

### 🚀 Usage

Two methods are provided; **Method 1 (mmWave Studio) is the most stable and recommended.**

#### Method 1: via mmWave Studio (recommended)

1. Load the radar configuration and start the radar in **mmWave Studio**.
2. Once it is running, make sure the **`DATA_TRAN` LED** on the board is **blinking** (data is being transmitted).
3. In the Windows Task Manager, **kill the `DCA1000_recording_cli` process**.

   > ⚠️ If you don't kill it, once this script starts grabbing the data, mmWave Studio no longer receives UDP; after a while it will automatically **stop the frame**, halting the radar.

4. Run a capture script:
   - **`capture.py`** — saves each frame's raw data plus the RA / RD maps.
   - **`capture_plot.py`** — same as above, plus **real-time display** of RA / RD.
5. To stop, **just close the terminal**. The data is saved, and each frame's timestamp and status are logged in order.

> 📌 **Note:** Only RA and RD maps are shown, so only **horizontal antennas** are considered. Even if elevation antennas are enabled, only the azimuth dimension is displayed.

#### Capturing on Ubuntu

If the radar was started via **mmWave Studio (Windows)**, you **must not change the NIC** once streaming has begun — switching NICs means you receive no data at all. The safest approach is to use a **USB NIC** and physically move the whole adapter.

1. Start the radar with mmWave Studio on Windows; after it starts, unplug all USB cables (to prevent stop frame).
2. **Unplug the entire (USB) NIC** and plug it into the Ubuntu machine.
3. **Run `config_buffer_once.sh` first (do NOT skip it!)** to enlarge the UDP receive buffer, otherwise packets will be dropped.
4. Then run `capture.py` or `capture_plot.py` as usual.

---

### ⏱️ Hardware trigger (multi-sensor sync)

The radar supports hardware triggering: an external **3.3V signal** can trigger the radar to —

- **time-align** with other sensors;
- **synchronize multiple radars** to avoid mutual interference.

This script supports feeding a **serial character** at the moment of the external MCU trigger, stamping each frame with a hardware timestamp.

> ✅ **Measured:** comparing the "per-UDP-packet receive timestamp" against the "hardware trigger timestamp", the error is **within 1 ms**.

> 🛠️ A more detailed tutorial on modifying the hardware circuit to implement hardware triggering on single-chip and **MMWCAS-RF-EVM** (cascaded) radars will come in **~2 months**.

---

### 🔧 Configuration (`config.py`)

| Option | Value | Meaning |
|--------|-------|---------|
| `USE_HARDWARE_TRIGGER` | `False` (default) | No trigger thread; use the timestamp taken when data is received |
| | `True` | Enable hardware trigger; source chosen by `TRIGGER_SOURCE` |
| `TRIGGER_SOURCE` | `'serial'` / `'ros'` | Trigger source (only when `USE_HARDWARE_TRIGGER=True`) |
| `COM_PORT` | e.g. `'COM3'` | Serial port for the trigger (when `TRIGGER_SOURCE='serial'`) |
| `ROS_TOPIC` | e.g. `'serial_trigger'` | ROS topic (when `TRIGGER_SOURCE='ros'`) |
| `RADAR_TYPE` | `0` = 1843 | RX not interleaved, no reordering needed |
| | `1` = 1443 / 2243 | RX interleaved in the fast-time stream; **must set 1**, otherwise data is corrupted |

**ADC params & antenna selection (`ADC_PARAMS`):** `tx` determines which azimuth (horizontal) antennas `fft.py` selects — azimuth-only heatmaps, no elevation:

| `tx` | Selected antennas | Virtual antennas |
|------|-------------------|------------------|
| `1` | `[0]` | 1 TX × 4 RX = 4 VA |
| `2` (default) | `[0, 1]` | 2 TX × 4 RX = 8 VA |
| `3` | `[0, 2]` (TX1 & TX3, skipping elevation TX2) | 8 VA |

---

### 📂 Scripts

| File | Purpose |
|------|---------|
| `capture.py` | Capture & save per-frame data + RA / RD maps |
| `capture_plot.py` | Same as above, plus real-time RA / RD display |
| `streaming.py` | Core UDP receive & frame assembly |
| `fft.py` | CuPy FFT, decode into RA / RD |
| `triggers.py` | Hardware-trigger (serial / ros) timestamp thread |
| `config.py` | All tunable parameters |
| `config_buffer_once.sh` | **Must run before capturing on Ubuntu**; enlarges the UDP receive buffer to prevent drops |
| `udp buffer/` | Related network buffer configs (`99-udp.conf`, etc.) |
| `plot.py` | Plotting helpers |

---

### 🧩 Direct start via Cfg

> 🚧 To be added once I work it out. (Starting the radar directly from a config file, without mmWave Studio.)

---
---

## 📖 引用 / Citation

本项目为论文 [**CubeDN: Real-Time Drone Detection in 3D Space from Dual mmWave Radar Cubes**](https://ieeexplore.ieee.org/abstract/document/11127766)（ICRA 2025）而设计。如果本工具对你的研究有帮助，欢迎引用：

This project was built for the paper [**CubeDN: Real-Time Drone Detection in 3D Space from Dual mmWave Radar Cubes**](https://ieeexplore.ieee.org/abstract/document/11127766) (ICRA 2025). If this tool helps your research, please cite:

```bibtex
@INPROCEEDINGS{11127766,
  author={Fang, Yuan and Shi, Fangzhan and Wei, Xijia and Chen, Qingchao and Chetty, Kevin and Julier, Simon},
  booktitle={2025 IEEE International Conference on Robotics and Automation (ICRA)},
  title={CubeDN: Real-Time Drone Detection in 3D Space from Dual mmWave Radar Cubes},
  year={2025},
  pages={3977-3983},
  doi={10.1109/ICRA55743.2025.11127766}}
```

---

## 🙏 致谢 / Acknowledgements

感谢启发并支持了本项目的优秀开源雷达项目，包括但不限于 [mmMesh](#)、[Pyradar](#)。

特别感谢 **Shang Xu** 修复了 `int16` 与 `uint16` 的数据类型 bug。

Thanks to the excellent open-source radar projects that inspired and supported this work, including but not limited to [mmMesh](#) and [Pyradar](#).

Special thanks to **Shang Xu** for fixing the `int16` / `uint16` dtype bug.
