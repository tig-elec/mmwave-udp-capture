# 📡 mmwave-udp-capture

<a id="chinese"></a>
🌐 **简体中文** · [English](#english)

**基于 DCA1000EVM 的 TI 毫米波雷达实时采集与处理工具。**

直接从 DCA1000EVM 抓取原始 UDP 数据流，实时做 FFT，解包成 **RA（Range-Azimuth）** 与 **RD（Range-Doppler）** 热力图，并保存原始帧数据供后续处理。FFT 可以跑在 **GPU（CuPy）** 上，也可以跑在 **CPU（NumPy）** 上；AWR2243 还可以**不经过 mmWave Studio，一条命令直接启动**。

---

## ✨ 特性

- 直接接收 DCA1000 的 UDP 原始数据 → FFT → RA / RD 图
- 实时可视化 + 采集保存（`capture_plot.py`），或纯采集保存（`capture.py`）
- 逐帧记录时间戳与状态，支持**硬件触发**做多传感器时间对齐
- 天线配置自适应（`tx = 1 / 2 / 3`），Windows 与 Ubuntu 均可使用

### 🆕 v6.0 新增

- **AWR2243 一键启动器**（`mmwave2243_bringup/`）：不需要 mmWave Studio，用配置文件直接启动 AWR2243BOOST + DCA1000；附带 Windows 和 Ubuntu 的一键安装脚本，以及 patch 固件烧录脚本
- **CPU 版 FFT**：没有 GPU 也能实时出图，`config.py` 里一个开关切换，出的图与 GPU 版一致
- **可选保存完整 cube**：每帧的 Doppler × Azimuth × Range 复数 cube
- **每帧耗时输出**：直接看出处理是否跟得上帧率
- **TDM-MIMO 相位补偿**（可选，默认关）：修正两个 TX 轮发时运动目标的方位角偏移

### 已验证支持的型号

| 型号 | 启动方式 | `config.py` 里的设置 |
|------|---------|--------------------|
| **AWR2243** | 本仓库的一键启动器（无需 mmWave Studio） | `CAPTURE_SOURCE = 'launcher'` |
| **AWR1843** | mmWave Studio | `CAPTURE_SOURCE = 'studio'`，`RADAR_TYPE = 0` |
| **AWR1443 / AWR2243** | mmWave Studio | `CAPTURE_SOURCE = 'studio'`，`RADAR_TYPE = 1` |

> 💡 理论上任何基于 **DCA1000EVM** 的采集卡（例如 **AWR2243-2X-CAS-EVM**）都能抓到数据，但其数据格式需要进一步研究后才能正确解包。

---

## ⚙️ 依赖环境

| 用途 | 需要安装 |
|------|---------|
| 基本采集（`capture.py`） | Python 3（在 3.8 上测试）、NumPy |
| 实时显示（`capture_plot.py`） | 另需 PyQt5、pyqtgraph |
| GPU 版 FFT（`FFT_BACKEND = 'cupy'`） | 另需 CUDA Toolkit、CuPy（版本与 CUDA 对应）、matplotlib |
| CPU 版 FFT（`FFT_BACKEND = 'cpu'`） | 不需要额外的包；装了 SciPy 会更快 |
| 串口硬件触发 | pyserial（不用硬件触发时不需要） |
| AWR2243 启动器 | 由安装脚本编译安装，见下文 |

---

## 🚀 使用方法

有两种启动雷达的方式，采集脚本是同一套：

| | 方式一：一键启动器 | 方式二：mmWave Studio |
|---|---|---|
| 适用型号 | AWR2243BOOST | AWR1843 / AWR1443 / AWR2243 |
| 是否需要 mmWave Studio | 不需要 | 需要 |
| `CAPTURE_SOURCE` | `'launcher'` | `'studio'` |

> ⚠️ 两种方式的数据排布不同，`config.py` 里的 `CAPTURE_SOURCE` 必须和实际启动方式一致，否则解出来是镜像或噪声。

### 方式一：AWR2243 一键启动器（无需 mmWave Studio）

**第一次使用时的准备（只做一次）**

1. **设 SOP 跳线为功能模式（001）**。这是最关键的一步，不设对启动器必然报 `-8`：

   | 跳线 | 位置 |
   |---|---|
   | P3 (SOP2) | 开 |
   | P2 (SOP1) | 开（中间那根拔掉） |
   | P4 (SOP0) | 闭 |

   mmWave Studio 用的是另一种跳线设置，两种工作方式之间切换需要改跳线。

2. **安装启动器**（编译 `fpga_udp` 扩展）：

   ```bash
   # Windows：会自动安装 MSVC Build Tools（如缺），并让你选择装进哪个 Python 环境
   mmwave2243_bringup\build_windows.bat

   # Ubuntu / Jetson
   cd mmwave2243_bringup && bash build_ubuntu.sh
   ```

3. **给新板子烧一次 patch 固件**（每块板子只需一次，已经烧过会自动跳过）：

   ```bash
   python mmwave2243_bringup/flash_patch.py
   ```

4. **设置网卡**：接 DCA1000 的网口设为静态 IP `192.168.33.30`，掩码 `255.255.255.0`。

**每次采集**

```bash
# 终端 1：启动雷达（Ubuntu 上需要先 sudo rmmod ftdi_sio usbserial，并用 sudo 运行）
python mmwave2243_bringup/start_awr2243.py
#   看到 "[OK] Radar is transmitting continuously" 就是成功了

# 终端 2：收数据
python capture_plot.py        # 实时显示 RA / RD 并保存；或 python capture.py 只保存
```

- 结束时先在终端 2 按 Ctrl-C 停止采集，再在终端 1 按 Ctrl-C 停止雷达（会自动断电）。
- Windows 上运行启动器不需要管理员权限，但 **mmWave Studio 必须关掉**（它占着 FTDI）。
- 雷达参数在 `mmwave2243_bringup/configFiles/AWR2243_mmwaveconfig.txt`。当前这组参数是 77 GHz、65.998 MHz/µs、4.8 Msps、256 个采样点、2 个 TX 轮发 × 255 loops、10 Hz，对应距离分辨率约 4.3 cm、最大距离约 10.9 m。
- 改了采样点数、loop 数或 TX 数，要同步修改 `config.py` 里的 `ADC_PARAMS`。

跳线、参数含义、数据格式和排障的详细说明见 [`mmwave2243_bringup/README.md`](mmwave2243_bringup/README.md)。

### 方式二：通过 mmWave Studio

先把 `config.py` 里的 `CAPTURE_SOURCE` 设为 `'studio'`，并按雷达型号设好 `RADAR_TYPE`。

1. 用 **mmWave Studio** 加载雷达配置并启动毫米波雷达（`lua/skeleton.lua` 是一份可参考的配置脚本）。
2. 待雷达启动后，确认板子上的 **`DATA_TRAN` 指示灯正在闪烁**（表示正在发送数据）。
3. 在 Windows 任务管理器里**结束掉 `DCA1000_recording_cli` 进程**。

   > ⚠️ 如果不结束它，本脚本一旦启动开始抢数据，mmWave Studio 长时间收不到 UDP 就会自动 **stop frame**，导致雷达停止发送。

4. 运行 `capture.py` 或 `capture_plot.py`。
5. 结束采集时按 Ctrl-C，或直接关闭 terminal。

> 📌 **注意：** 目前只显示 RA 和 RD 图，因此只考虑打开**水平天线**。即使打开了垂直天线，也只显示方位（azimuth）维度。

### 在 Ubuntu 上采集

**采集前先运行 `config_buffer_once.sh`**，调大 UDP 接收缓冲，否则会丢包（重启后需要重新运行；想永久生效用 `udp buffer/` 里的配置）。这一步只在 Linux 上需要，Windows 上不用做。

如果雷达是用 **mmWave Studio（Windows）** 启动的，那么一旦开始传输数据就**不能更换网卡**——换了网卡将收不到任何数据。稳妥的做法是使用 **USB 网卡**，直接把整个网卡拔下来迁移：

1. 在 Windows 上用 mmWave Studio 启动雷达，启动后拔掉所有 USB 线（防止 stop frame）。
2. **拔掉整个（USB）网卡**，插到 Ubuntu 机器上。
3. 运行 `config_buffer_once.sh`，之后照常运行 `capture.py` 或 `capture_plot.py`。

用一键启动器时没有这个限制，直接在 Ubuntu 上启动雷达即可。

---

## 📁 输出内容

每次运行会在当前目录下新建一个以 Unix 时间戳命名的文件夹：

| 文件 | 内容 | 由谁生成 |
|------|------|---------|
| `raw.bin` | 所有帧的原始 ADC 数据（int16）连续写入 | 两个脚本都有 |
| `timestamp.txt` | 每帧一行：帧计数、帧号、触发时间戳、帧时间戳、两者之差、`BrokenFlag` | 两个脚本都有 |
| `frame/<n>.npy` | 第 n 帧的原始 ADC 数据（int16 一维数组） | 两个脚本都有 |
| `RA/<n>.npy`、`RD/<n>.npy` | 归一化到 0–1 的 RA / RD 图（float32） | 仅 `capture_plot.py` |
| `cube/<n>.npy` | 完整复数 cube，shape `(Chirps, 256, Samples)`，complex64 | 仅 `GENERATE_CUBE = True` 时 |

`BrokenFlag = 1` 表示这一帧发生了丢包，数据已用 0 填充，时间戳不可信，后处理时应过滤掉。

---

## 🔧 配置说明（`config.py`）

所有开关都在 `config.py` 里，文件内有中英双语说明。

| 配置项 | 取值 | 含义 |
|--------|------|------|
| `CAPTURE_SOURCE` | `'launcher'`（默认） | 数据来自一键启动器（AWR2243，4-lane）；此时 `RADAR_TYPE` 被忽略 |
| | `'studio'` | 数据来自 mmWave Studio（2-lane）；此时必须用 `RADAR_TYPE` 指明型号 |
| `RADAR_TYPE` | `0` = 1843 | 仅 `CAPTURE_SOURCE='studio'` 时生效：RX 不交织，无需重排 |
| | `1` = 1443 / 2243 | 仅 `CAPTURE_SOURCE='studio'` 时生效：RX 在 fast-time 流里交织，**必须设 1**，否则数据错乱 |
| `ADC_PARAMS` | 字典 | `chirps`（每帧 loop 数）、`samples`（每个 chirp 的采样点数）、`tx`（轮发的 TX 数）必须与雷达实际配置一致 |
| `FFT_BACKEND` | `'cpu'`（默认） | 用 CPU 算 FFT（`fft_cpu.py`） |
| | `'cupy'` | 用 GPU 算 FFT（`fft_cupy.py`），需要 CUDA + CuPy |
| `GENERATE_CUBE` | `False`（默认） | 实时模式，只出 RA / RD 图 |
| | `True` | 每帧额外保存完整复数 cube（每帧 100MB 以上，不保证实时，来不及处理的帧会被丢弃） |
| `PRINT_TIMING` | `True`（默认） | 每帧打印一行 `[Time]`：FFT 耗时、整帧耗时、帧队列积压数 |
| `TDM_PHASE_COMPENSATION` | `False`（默认） | 不做 TDM-MIMO 相位补偿 |
| | `True` | 对第二个 TX 的通道做 Doppler 相位补偿，修正运动目标的方位角偏移 |
| `TX1_PHASE_OFFSET` | 弧度，默认 `0.0` | 两个 TX 间的固定相位差（板级标定量），仅补偿打开时生效 |
| `USE_HARDWARE_TRIGGER` | `False`（默认） | 不启动触发线程，直接用收到数据时打的时间戳 |
| | `True` | 启用硬件触发，来源由 `TRIGGER_SOURCE` 决定 |
| `TRIGGER_SOURCE` | `'serial'` / `'ros'` | 硬触发来源（仅 `USE_HARDWARE_TRIGGER=True` 时生效） |
| `COM_PORT` | 如 `'COM3'` | 串口触发端口（`TRIGGER_SOURCE='serial'` 时） |
| `ROS_TOPIC` | 如 `'serial_trigger'` | ROS 触发 topic（`TRIGGER_SOURCE='ros'` 时） |

**天线选取：** `ADC_PARAMS` 里的 `tx` 决定取哪些方位（水平）天线，只做水平方位热力图，不取 elevation：

| `tx` | 选取的天线 | 虚拟天线数 |
|------|-----------|-----------|
| `1` | `[0]` | 1 TX × 4 RX = 4 VA |
| `2`（默认） | `[0, 1]` | 2 TX × 4 RX = 8 VA |
| `3` | `[0, 2]`（取 TX1、TX3 两根水平天线，跳过俯仰 TX2） | 8 VA |

### GPU 还是 CPU

两种后端出的图一致（归一化图的差异在 1e-5 以内），区别只在速度。255 chirp × 256 采样点时，在一台笔记本上 GPU 每帧约 10 ms 以内，CPU 约 30 ms，10 Hz 帧率下两者都跟得上；具体取决于机器。

判断是否跟得上，看 `capture_plot.py` 每帧打印的这一行：

```
[Time]  39 | fft 30.3 | total 35.7 ms | queue 0/10
```

`total` 要小于帧周期（10 Hz 是 100 ms）；`queue` 是帧队列里积压的帧数，一直涨到满就说明处理跟不上，会开始丢帧。

### 保存 cube

`GENERATE_CUBE = True` 时每帧会多存一个 `(Chirps, 256, Samples)` 的复数 cube。它很大（255 × 256 时约 134 MB 一帧），生成和写盘都慢，CPU 上基本做不到 10 Hz 实时。需要完整数据时，更稳妥的做法是采集时保持 `False`，事后对保存下来的帧调用 `fft_cpu.get_cube_3dfft(frame)`，结果相同。

### TDM-MIMO 相位补偿

两个 TX 轮流发射时，第二个 TX 的 chirp 比第一个晚半个 Doppler 采样周期，运动目标的方位角会因此偏移。把 `TDM_PHASE_COMPENSATION` 设为 `True` 可以按 Doppler bin 补偿这个相位；`TX1_PHASE_OFFSET` 是两个 TX 之间的固定相位差，需要按板子标定，不确定时保持 `0.0`。只影响 RA 图和 cube，RD 图不变。

---

## ⏱️ 硬件触发（多传感器同步）

毫米波雷达支持硬件触发：用一路外部 **3.3V 信号**触发雷达，可用于——

- 与其他传感器**时间对齐**；
- 多台毫米波雷达同步触发，**避免互相干扰**。

本脚本支持在外部单片机触发的同时，输入一个**串口字符**（或 ROS 消息），为每一帧打上硬件时间戳。把 `USE_HARDWARE_TRIGGER` 设为 `True` 并选好 `TRIGGER_SOURCE` 即可。

> ✅ **实测：** 通过「接收每个 UDP 包的时间戳」与「硬件标识时间戳」对比，两者误差在 **1ms 以内**。

> 🛠️ 关于单芯片及 *MMWCAS-RF-EVM*（级联）毫米波雷达如何修改硬件电路来实现硬件触发，后续会补充更详细的教程。

---

## 📂 文件说明

| 文件 | 作用 |
|------|------|
| `capture.py` | 采集并保存每帧原始数据 |
| `capture_plot.py` | 在 `capture.py` 基础上实时计算、显示并保存 RA / RD |
| `config.py` | 全部可调参数（中英双语说明） |
| `streaming.py` | UDP 数据接收与组帧核心 |
| `fft_cupy.py` | GPU（CuPy）版 FFT |
| `fft_cpu.py` | CPU（NumPy）版 FFT，输出与 GPU 版一致；`python fft_cpu.py` 可自检 |
| `plot.py` | 实时显示窗口 |
| `triggers.py` | 硬件触发（serial / ros）时间戳线程 |
| `config_buffer_once.sh` | **Ubuntu 上采集前必跑**，调大 UDP 接收缓冲防丢包 |
| `udp buffer/` | 让 UDP 缓冲设置永久生效的配置（`99-udp.conf` 等） |
| `lua/skeleton.lua` | mmWave Studio 用的雷达配置脚本；启动器的雷达参数与它一致 |
| `mmwave2243_bringup/` | AWR2243 一键启动器：`start_awr2243.py`、`flash_patch.py`、两个安装脚本和雷达配置文件 |

---
---

<a id="english"></a>
## 🌐 English

[简体中文](#chinese) · **English**

**Real-time acquisition and processing tool for TI mmWave radars based on the DCA1000EVM.**

It grabs the raw UDP data stream directly from the DCA1000EVM, runs the FFT in real time, decodes it into **RA (Range-Azimuth)** and **RD (Range-Doppler)** heatmaps, and saves the raw frames for further processing. The FFT runs either on the **GPU (CuPy)** or on the **CPU (NumPy)**, and an AWR2243 can be **started with a single command, without mmWave Studio**.

---

### ✨ Features

- Receives raw UDP data from the DCA1000 directly → FFT → RA / RD maps
- Real-time visualization + saving (`capture_plot.py`), or capture-only (`capture.py`)
- Per-frame timestamp & status logging; **hardware trigger** for multi-sensor time alignment
- Adaptive antenna configuration (`tx = 1 / 2 / 3`); works on both Windows and Ubuntu

#### 🆕 New in v6.0

- **AWR2243 launcher** (`mmwave2243_bringup/`): starts an AWR2243BOOST + DCA1000 directly from a config file, no mmWave Studio needed; comes with one-step setup scripts for Windows and Ubuntu and a patch-firmware flashing script
- **CPU FFT**: real-time maps without a GPU, selected by one switch in `config.py`, same maps as the GPU version
- **Optional full-cube saving**: the complex Doppler × Azimuth × Range cube of every frame
- **Per-frame timing output**: shows at a glance whether processing keeps up with the frame rate
- **TDM-MIMO phase compensation** (optional, off by default): corrects the azimuth shift of moving targets when two TX antennas transmit in turn

#### Verified radar models

| Model | Started with | Settings in `config.py` |
|-------|--------------|-------------------------|
| **AWR2243** | the launcher in this repository (no mmWave Studio) | `CAPTURE_SOURCE = 'launcher'` |
| **AWR1843** | mmWave Studio | `CAPTURE_SOURCE = 'studio'`, `RADAR_TYPE = 0` |
| **AWR1443 / AWR2243** | mmWave Studio | `CAPTURE_SOURCE = 'studio'`, `RADAR_TYPE = 1` |

> 💡 In principle any DCA1000EVM-based capture card (e.g. **AWR2243-2X-CAS-EVM**) can capture data, but its data format needs further study before it can be decoded correctly.

---

### ⚙️ Requirements

| Purpose | What to install |
|---------|-----------------|
| Basic capture (`capture.py`) | Python 3 (tested with 3.8), NumPy |
| Real-time display (`capture_plot.py`) | additionally PyQt5 and pyqtgraph |
| GPU FFT (`FFT_BACKEND = 'cupy'`) | additionally CUDA Toolkit, CuPy (matching your CUDA version), matplotlib |
| CPU FFT (`FFT_BACKEND = 'cpu'`) | nothing extra; faster if SciPy is installed |
| Serial hardware trigger | pyserial (not needed otherwise) |
| AWR2243 launcher | built and installed by the setup scripts, see below |

---

### 🚀 Usage

There are two ways to start the radar; the capture scripts are the same for both:

| | Method 1: the launcher | Method 2: mmWave Studio |
|---|---|---|
| Radar | AWR2243BOOST | AWR1843 / AWR1443 / AWR2243 |
| mmWave Studio required | no | yes |
| `CAPTURE_SOURCE` | `'launcher'` | `'studio'` |

> ⚠️ The two methods produce different byte layouts. `CAPTURE_SOURCE` in `config.py` must match how the radar was actually started, otherwise the frames decode into mirror images or noise.

#### Method 1: the AWR2243 launcher (no mmWave Studio)

**One-time preparation**

1. **Set the SOP jumpers to functional mode (001).** This is the most important step; with the wrong jumpers the launcher always fails with `-8`:

   | Jumper | Position |
   |---|---|
   | P3 (SOP2) | open |
   | P2 (SOP1) | open (remove the middle jumper) |
   | P4 (SOP0) | closed |

   mmWave Studio uses a different jumper setting, so switching between the two workflows means changing the jumpers.

2. **Install the launcher** (builds the `fpga_udp` extension):

   ```bash
   # Windows: installs MSVC Build Tools if missing and asks which Python environment to use
   mmwave2243_bringup\build_windows.bat

   # Ubuntu / Jetson
   cd mmwave2243_bringup && bash build_ubuntu.sh
   ```

3. **Flash the patch firmware once per board** (a board that already has it is skipped automatically):

   ```bash
   python mmwave2243_bringup/flash_patch.py
   ```

4. **Configure the NIC** connected to the DCA1000 with the static IP `192.168.33.30`, mask `255.255.255.0`.

**Every capture**

```bash
# Terminal 1: start the radar (on Ubuntu first run: sudo rmmod ftdi_sio usbserial, and use sudo)
python mmwave2243_bringup/start_awr2243.py
#   "[OK] Radar is transmitting continuously" means it worked

# Terminal 2: receive the data
python capture_plot.py        # show RA / RD live and save; or python capture.py to save only
```

- To finish, press Ctrl-C in terminal 2 to stop capturing, then Ctrl-C in terminal 1 to stop the radar (it is powered off automatically).
- On Windows the launcher needs no administrator rights, but **mmWave Studio must be closed** (it holds the FTDI device).
- The radar parameters are in `mmwave2243_bringup/configFiles/AWR2243_mmwaveconfig.txt`. The current set is 77 GHz, 65.998 MHz/µs, 4.8 Msps, 256 samples, 2 TX in turn × 255 loops at 10 Hz, i.e. about 4.3 cm range resolution and about 10.9 m maximum range.
- When you change the number of samples, loops or TX, update `ADC_PARAMS` in `config.py` accordingly.

Details on the jumpers, the parameters, the data format and troubleshooting are in [`mmwave2243_bringup/README.md`](mmwave2243_bringup/README.md) (in Chinese).

#### Method 2: via mmWave Studio

First set `CAPTURE_SOURCE = 'studio'` in `config.py` and set `RADAR_TYPE` for your radar.

1. Load the radar configuration and start the radar in **mmWave Studio** (`lua/skeleton.lua` is an example configuration script).
2. Once it is running, make sure the **`DATA_TRAN` LED** on the board is **blinking** (data is being transmitted).
3. In the Windows Task Manager, **kill the `DCA1000_recording_cli` process**.

   > ⚠️ If you don't kill it, once this script starts grabbing the data, mmWave Studio no longer receives UDP; after a while it will automatically **stop the frame**, halting the radar.

4. Run `capture.py` or `capture_plot.py`.
5. To stop, press Ctrl-C or just close the terminal.

> 📌 **Note:** Only RA and RD maps are shown, so only **horizontal antennas** are considered. Even if elevation antennas are enabled, only the azimuth dimension is displayed.

#### Capturing on Ubuntu

**Run `config_buffer_once.sh` before capturing** to enlarge the UDP receive buffer, otherwise packets will be dropped (it has to be run again after a reboot; use the files in `udp buffer/` to make it permanent). This step is needed on Linux only, not on Windows.

If the radar was started via **mmWave Studio (Windows)**, you **must not change the NIC** once streaming has begun — switching NICs means you receive no data at all. The safe approach is to use a **USB NIC** and physically move the whole adapter:

1. Start the radar with mmWave Studio on Windows; after it starts, unplug all USB cables (to prevent stop frame).
2. **Unplug the entire (USB) NIC** and plug it into the Ubuntu machine.
3. Run `config_buffer_once.sh`, then run `capture.py` or `capture_plot.py` as usual.

With the launcher there is no such restriction: just start the radar on Ubuntu directly.

---

### 📁 Output

Every run creates a folder named after the current Unix timestamp in the working directory:

| File | Content | Written by |
|------|---------|------------|
| `raw.bin` | raw ADC data (int16) of all frames, concatenated | both scripts |
| `timestamp.txt` | one line per frame: frame count, frame id, trigger timestamp, frame timestamp, their difference, `BrokenFlag` | both scripts |
| `frame/<n>.npy` | raw ADC data of frame n (1-D int16 array) | both scripts |
| `RA/<n>.npy`, `RD/<n>.npy` | RA / RD maps normalised to 0–1 (float32) | `capture_plot.py` only |
| `cube/<n>.npy` | full complex cube, shape `(Chirps, 256, Samples)`, complex64 | only when `GENERATE_CUBE = True` |

`BrokenFlag = 1` marks a frame that lost packets; its data is zero-filled and its timestamp is not reliable, so filter such frames out in post-processing.

---

### 🔧 Configuration (`config.py`)

All switches live in `config.py`, which is commented in both Chinese and English.

| Option | Value | Meaning |
|--------|-------|---------|
| `CAPTURE_SOURCE` | `'launcher'` (default) | Data from the launcher (AWR2243, 4-lane); `RADAR_TYPE` is ignored |
| | `'studio'` | Data from mmWave Studio (2-lane); the model must be given via `RADAR_TYPE` |
| `RADAR_TYPE` | `0` = 1843 | Only used when `CAPTURE_SOURCE='studio'`: RX not interleaved, no reordering needed |
| | `1` = 1443 / 2243 | Only used when `CAPTURE_SOURCE='studio'`: RX interleaved in the fast-time stream; **must set 1**, otherwise data is corrupted |
| `ADC_PARAMS` | dict | `chirps` (loops per frame), `samples` (ADC samples per chirp) and `tx` (number of TX transmitting in turn) must match the actual radar configuration |
| `FFT_BACKEND` | `'cpu'` (default) | Run the FFT on the CPU (`fft_cpu.py`) |
| | `'cupy'` | Run the FFT on the GPU (`fft_cupy.py`); needs CUDA + CuPy |
| `GENERATE_CUBE` | `False` (default) | Real-time mode, RA / RD maps only |
| | `True` | Also save the full complex cube of every frame (100+ MB per frame; not guaranteed real-time, frames that cannot be processed in time are dropped) |
| `PRINT_TIMING` | `True` (default) | Print one `[Time]` line per frame: FFT time, total time per frame, frames waiting in the queue |
| `TDM_PHASE_COMPENSATION` | `False` (default) | No TDM-MIMO phase compensation |
| | `True` | Apply Doppler phase compensation to the channels of the second TX, correcting the azimuth shift of moving targets |
| `TX1_PHASE_OFFSET` | radians, default `0.0` | Fixed phase offset between the two TX (a per-board calibration value); only used when the compensation is on |
| `USE_HARDWARE_TRIGGER` | `False` (default) | No trigger thread; use the timestamp taken when data is received |
| | `True` | Enable hardware trigger; source chosen by `TRIGGER_SOURCE` |
| `TRIGGER_SOURCE` | `'serial'` / `'ros'` | Trigger source (only when `USE_HARDWARE_TRIGGER=True`) |
| `COM_PORT` | e.g. `'COM3'` | Serial port for the trigger (when `TRIGGER_SOURCE='serial'`) |
| `ROS_TOPIC` | e.g. `'serial_trigger'` | ROS topic (when `TRIGGER_SOURCE='ros'`) |

**Antenna selection:** `tx` in `ADC_PARAMS` determines which azimuth (horizontal) antennas are used — azimuth-only heatmaps, no elevation:

| `tx` | Selected antennas | Virtual antennas |
|------|-------------------|------------------|
| `1` | `[0]` | 1 TX × 4 RX = 4 VA |
| `2` (default) | `[0, 1]` | 2 TX × 4 RX = 8 VA |
| `3` | `[0, 2]` (TX1 & TX3, skipping elevation TX2) | 8 VA |

#### GPU or CPU

Both backends produce the same maps (the normalised maps differ by less than 1e-5); only the speed differs. With 255 chirps × 256 samples, a laptop needs under about 10 ms per frame on the GPU and about 30 ms on the CPU, so both keep up with 10 Hz; the exact numbers depend on the machine.

To see whether processing keeps up, look at the line `capture_plot.py` prints for every frame:

```
[Time]  39 | fft 30.3 | total 35.7 ms | queue 0/10
```

`total` has to stay below the frame period (100 ms at 10 Hz). `queue` is the number of frames waiting in the frame queue; if it keeps growing until it is full, processing is too slow and frames start to be dropped.

#### Saving the cube

With `GENERATE_CUBE = True` every frame additionally stores a complex cube of shape `(Chirps, 256, Samples)`. It is large (about 134 MB per frame for 255 × 256) and slow to build and write; on a CPU it cannot keep up with 10 Hz. When complete data matters, it is safer to capture with `False` and build the cubes afterwards from the saved frames with `fft_cpu.get_cube_3dfft(frame)`, which gives the same result.

#### TDM-MIMO phase compensation

When two TX antennas transmit in turn, the chirp of the second TX comes half a Doppler sampling period after the first, which shifts the azimuth of moving targets. Setting `TDM_PHASE_COMPENSATION = True` compensates this phase per Doppler bin. `TX1_PHASE_OFFSET` is the fixed phase offset between the two TX; it has to be calibrated per board, keep it at `0.0` when unsure. Only the RA map and the cube are affected; the RD map is unchanged.

---

### ⏱️ Hardware trigger (multi-sensor sync)

The radar supports hardware triggering: an external **3.3V signal** can trigger the radar to —

- **time-align** with other sensors;
- **synchronize multiple radars** to avoid mutual interference.

This script supports feeding a **serial character** (or a ROS message) at the moment of the external MCU trigger, stamping each frame with a hardware timestamp. Set `USE_HARDWARE_TRIGGER = True` and choose the `TRIGGER_SOURCE`.

> ✅ **Measured:** comparing the "per-UDP-packet receive timestamp" against the "hardware trigger timestamp", the error is **within 1 ms**.

> 🛠️ A more detailed tutorial on modifying the hardware circuit to implement hardware triggering on single-chip and **MMWCAS-RF-EVM** (cascaded) radars will be added later.

---

### 📂 Files

| File | Purpose |
|------|---------|
| `capture.py` | Capture and save the raw data of every frame |
| `capture_plot.py` | Same as above, plus computing, displaying and saving RA / RD in real time |
| `config.py` | All tunable parameters (commented in Chinese and English) |
| `streaming.py` | Core UDP receive & frame assembly |
| `fft_cupy.py` | GPU (CuPy) FFT |
| `fft_cpu.py` | CPU (NumPy) FFT, same output as the GPU version; `python fft_cpu.py` runs a self-check |
| `plot.py` | Real-time display window |
| `triggers.py` | Hardware-trigger (serial / ros) timestamp thread |
| `config_buffer_once.sh` | **Must run before capturing on Ubuntu**; enlarges the UDP receive buffer to prevent drops |
| `udp buffer/` | Configuration to make the UDP buffer setting permanent (`99-udp.conf`, etc.) |
| `lua/skeleton.lua` | Radar configuration script for mmWave Studio; the launcher uses the same radar parameters |
| `mmwave2243_bringup/` | The AWR2243 launcher: `start_awr2243.py`, `flash_patch.py`, the two setup scripts and the radar configuration |

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
