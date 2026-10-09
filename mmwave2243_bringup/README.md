# mmwave2243_bringup —— 不用 mmWave Studio 启动 AWR2243

在 Ubuntu / Jetson / 树莓派 / Windows 上一条命令启动 **AWR2243BOOST + DCA1000** 连续发波、输出 raw ADC,
**不需要 mmWave Studio**。控制链走 **FTDI USB→SPI + mmWaveLink**(复用 pyRadar 的 `fpga_udp`)。

本目录只负责启动雷达;收数据用上一级目录的 `capture.py` / `capture_plot.py`。

---

## ⚠️ 最关键的一步:SOP 跳线(不设对必然返回 -8)

AWR2243BOOST 的控制模式由板上 **SOP 物理跳线**决定,**上电时读跳线,软件改不了**。
本方案走 SPI,必须把跳线设成 **功能模式(SOP4 = 二进制 001)**:

| 跳线 | 位置 | 值 |
|---|---|---|
| P3 (SOP2) | **开** | 0 |
| P2 (SOP1) | **开(中间那根拔掉)** | 0 |
| P4 (SOP0) | **闭** | 1 |

> mmWave Studio 默认用的是 Dev 模式(SOP2 = 011,走 UART),在本代码下**不通**。
> 现象:不改跳线 → `AWR2243_init` 恒返回 `-8`(设备不在 SPI 上应答)。改成 001 即可。
> 依据:AWR2243BOOST 用户指南 SPRUIT8D,Table 2-4 SOP Modes。

---

## 安装

### Ubuntu / Jetson / 树莓派

```bash
cd mmwave2243_bringup
bash build_ubuntu.sh
```
自动完成:装系统依赖 → 装 libftd2xx → 编译安装 `fpga_udp`(装给 root)→ 自检。
成功标志:末尾打印 `fpga_udp.add(1,2) = 3` 和 `DCA1000 import: OK`。这一步不用接雷达。

### Windows

```bat
build_windows.bat                         :: 不带参数:扫描本机 Python / conda 环境,让你选装进哪个
build_windows.bat C:\path\to\python.exe   :: 或直接指定
```
自动完成:装 MSVC Build Tools(缺才装,约 2 GB,会弹 UAC)→ 检查并修复 conda 环境里过旧的 VC 运行库 →
pip 装 pybind11 / numpy → 编译安装 `fpga_udp` → 与 Ubuntu 版相同的自检。

- FTDI 的 `.lib` 已在 `fpga_udp/src/FTDI_D2XX/Windows/`,`setup.py` 按平台自动选,不用另装。
- 运行启动器不需要管理员权限,但 mmWave Studio 必须关掉(它占着 FTDI)。

### 新板子一次性:烧 patch 固件

`AWR2243_init` 绑定的是 `MMWL_App_init(..., downloadFw=false)`,**不会下固件**,配置里 `EnableFwDownload=1` 不起作用。
启动日志若出现 `RF Patch Version [0.0.0.0]` 和 `No patch detected`,说明跑的是 ROM 出厂固件,
和 mmWave Studio 每次下 BSS / MSS patch 不等价。一块板子只需要处理一次:

```bash
# 雷达上电、mmWave Studio 关闭、启动器未运行:
python flash_patch.py          # 幂等:已有 patch 自动跳过;非 ES1.1 板子拒绝;烧完自动核实
```
之后每次以功能模式上电都会自动从 flash 加载 patch,启动日志应显示 `RF Patch 2.2.4.0 / MSS Patch 2.2.2.0`。
mmWave Studio 走 SOP 011 + UART 把固件下到 RAM,不受 flash 影响。

---

## 运行

### Windows

```powershell
# 0. SOP 跳线 = 功能模式 001(见上表);接 DCA1000 的网卡设静态 IP 192.168.33.30/24
# 1. 关掉 mmWave Studio
python mmwave2243_bringup\start_awr2243.py          # 看到 "[OK] Radar is transmitting continuously" = 成
# 2. 另开终端,在工程根目录
python capture_plot.py                              # 或 capture.py(只落盘)
```
判断 DCA1000 链路**别用 ping**(它不回 ICMP),看 `Get-NetNeighbor -IPAddress 192.168.33.180` 有没有 MAC。
启动日志里应有 `RF Patch Version [2.2.4.0]`;若是 `[0.0.0.0]`,先跑 `flash_patch.py`(见上)。

### Linux

```bash
# 1. 设 SOP 跳线 = 功能模式 001(见上表)
# 2. 配网卡(接 DCA1000 的网口, ip a 查名字)
sudo ip addr add 192.168.33.30/24 dev <网口名>
ip neigh show | grep 192.168.33.180     # 有 MAC = DCA1000 链路 OK(ping 不通是正常的,它不回 ICMP)

# 3. 启动雷达(连续发波)
sudo rmmod ftdi_sio usbserial 2>/dev/null
sudo python3 start_awr2243.py           # 看到 "[OK] Radar is transmitting continuously" = 成

# 4. 另开终端,在工程根目录跑采集脚本
python3 capture.py                       # 绑 4098 收正在跑的流(连续模式,先后无所谓)
```

停止:启动器 Ctrl-C(自动 sensorStop + poweroff);采集脚本自行 Ctrl-C。
`flash_patch.py` 会复位并断电雷达,**跑它之前先停启动器,跑完再重新启动**。

---

## 目录结构

```
mmwave2243_bringup/
├── start_awr2243.py     启动器(控制雷达 + ARM DCA1000,连续模式,不收数据)
├── flash_patch.py       新板子一次性烧 patch 固件(幂等)
├── build_ubuntu.sh      一键安装脚本(Linux)
├── build_windows.bat    一键安装脚本(Windows)
├── configFiles/
│   ├── AWR2243_mmwaveconfig.txt   雷达参数(通常只需要改这个文件)
│   └── cf.json                    DCA1000 配置(lvdsMode=1 4-lane / packetDelay 5 µs)
├── fpga_udp/            C++ 扩展:mmWaveLink + FTDI + patch 固件(pybind11),复用自 pyRadar
│   ├── src/FTDI_D2XX/{Linux,Windows}/         内置 libftd2xx / ftd2xx.lib
│   └── src/mmwaveDFP_2G/firmware/             TI DFP 2.2.3.2 的 BSS+MSS patch(xwr22xx_metaImage),flash_patch.py 烧的就是它
└── mmwave/              DCA1000 UDP 控制类(dataloader/adc.py),复用自 pyRadar
```

---

## 端口说明

pyRadar 的 `DCA1000` 类会同时绑 4096 和 4098 两个端口,和采集脚本的 `streaming.py` 冲突。
所以启动器发完 `stream_start`(ARM 采集卡)后**立刻 `dca.close()` 释放这两个端口**;
采集卡一旦被 ARM 就会自己往 4098 持续发数据,不需要主机一直开着 socket。
这样 `streaming.py` 就能正常绑 4098。停止雷达只走 SPI,不碰端口。

---

## 参数

- **连续 / 定量**:`start_awr2243.py` 里 `NUM_FRAMES = 0` 是连续发波(和 mmWave Studio 一样);改成正整数就是发完指定帧数后自停。
- **雷达参数**在 `configFiles/AWR2243_mmwaveconfig.txt`(文本,改数值不用重新编译)。
  格式 `key=value;`,`#` 开头是整行注释,值后面可以跟 `; # 注释`。
  解析器从文件头顺序扫描,**段的顺序不能乱**(profile 段的 `numAdcSamples` 必须在 frame 段的之前)。
- **DCA1000** 配置在 `cf.json`:`lvdsMode=1`(4-lane)、`packetDelay_us=5`。
- **三处必须配套改**:mmwaveconfig 的 profile 段 `numAdcSamples`、frame 段 `numAdcSamples`(= 前者 × 2)、
  `loopCount` 和 TX 数,要与根目录 `config.py` 的 `ADC_PARAMS`(`samples` / `chirps` / `tx`)一致。

### 当前参数(由根目录 `lua/skeleton.lua` 逐项翻译)

| 项 | 值 | 配置文件里 |
|---|---|---|
| 天线 | TX1+TX3(0-index TX0+TX2)+ RX1~4 = 8 VA | `channelTx=5` `channelRx=15`,chirp0 `txEnable=1`,chirp1 `txEnable=4` |
| f0 | 77 GHz | `startFreqConst=1435384035` |
| slope | 65.998 MHz/µs | `freqSlopeConst=1367` |
| Fs | 4.8 MSps | `digOutSampleRate=4800` |
| N_ADC | 256 | profile `numAdcSamples=256`,frame `numAdcSamples=512`,config.py `samples=256` |
| adcStart / rampEnd / idle | 6 / 60 / 20 µs | `600` / `6000` / `2000` |
| txStartTime | 0 | `txStartTime=0` |
| 帧 | 2 chirp × 255 loops @ 100 ms | `loopCount=255` `periodicity=20000000`,config.py `chirps=255` |
| 结果 | B_eff≈3.52 GHz,ΔR≈4.3 cm,Rmax≈10.9 m(complex1x,256 bin 全有效;保守按 0.9 Fs 取 9.8 m),2.09 MB/帧,≈167 Mbps | |

校验:ADC 采样 53.33 µs + adcStart 6 = 59.33 ≤ rampEnd 60 ✓;扫频 3.96 GHz 终止 80.96 GHz ≤ 81 ✓;
ADC buffer 4.1 kB ≤ 16 kB(4RX complex 上限 1024 点)✓;LVDS 4352 ≤ 80 µs × 300 = 24000 ✓。

**与 lua 唯一不同的是 lane 数**:lua 是 2-lane(1843 只有 2 条 lane),这里是 4-lane(`laneEn=15`、cf.json `lvdsMode=1`),
原因见下面"LVDS 带宽"。lane 数只影响传输,不影响雷达发的波形和 ADC 数据。

---

## 数据格式(采集端和解包端必须配套)

采集方式和根目录 `fft_cupy.py` / `fft_cpu.py` 里的解包必须配套(由 `config.py` 的 `CAPTURE_SOURCE` 选择),混用会解出镜像或噪声:

| 采集方式 | 字节流格式 | 配套解包 |
|---|---|---|
| mmWave Studio(2-lane) | Studio 2-lane 交织 | `CAPTURE_SOURCE='studio'` |
| **本启动器(4-lane)** | sample-major:每个采样点 → 4 个 RX 的 I → 4 个 RX 的 Q | `CAPTURE_SOURCE='launcher'` |

- 本目录的配置:`adcFormat=1`(complex1x)、`iqSwapSel=0`、`chInterleave=0`、`laneEn=15`(4-lane)、cf.json `lvdsMode=1`,
  Programmable Filter 关闭(`progFiltLen=0`、`progFiltFreqShift=0`)。
- `'launcher'` 解包:`reshape(-1,chirps,tx,samples,IQ,rx) → transpose(0,1,2,5,3,4) → I first`,不需要 `RADAR_TYPE` 的 RX 重排
  (来自 pyRadar 作者的 testDecode_AWR2243.ipynb)。complex1x 和 2x 的字节流排布相同,解包不用改。
- **Programmable Filter 必须关**:pyRadar 默认配置里是 `progFiltLen=14`、`progFiltFreqShift=100`。TI 头文件注明该频移
  1 LSB = 0.01 Fs 且**仅在 complex1x 下生效**,100 相当于把 IF 频谱搬移一个 Fs 到低通阻带外,只剩噪底;
  complex2x 不经过这一级所以不受影响。mmWave Studio 不配这一段。用 complex1x 时这两项必须是 0。

---

## complex 1x 与 2x

两种都是 I/Q 复数、每点 4 字节、采样率 Fs、字节流排布相同,差别只在芯片 DFE 怎么处理 IF 频带:

| | complex 1x(`adcFormat=1`) | complex 2x(`adcFormat=2`) |
|---|---|---|
| DFE | 把 IF 频带搬移半个 Fs 再滤波,0~Fs 的正拍频全落进采样带宽 | 不搬移,通带 −Fs/2 ~ +Fs/2 |
| 可用 IF 带宽 | ≈ 0.9 Fs | Fs / 2 |
| 256 个 range bin | 全部有效 | 前 128 有目标,后 128 是负频率镜像带(永远是噪声) |
| 同 Fs 最大距离 | 10.9 m(保守 9.8 m) | 5.5 m |
| mmWave Studio 默认 | 是 | 否 |

FMCW 的拍频只有正的,2x 等于白扔一半采样率;它只在需要观察负频带(干扰分析等)时有用。本配置用 1x。

---

## LVDS 带宽

DCA1000 每条 lane 上限 600 Mbps → **2-lane = 150 字节/µs,4-lane = 300 字节/µs**。
约束:`每 chirp 字节 = 采样点 × RX × 4 字节 + 52 包头(对齐到 256) ≤ 带宽 × chirp 周期(idle + rampEnd)`。

- **当前参数**(256 样点 / 4800 ksps / 周期 80 µs):需要 4352 字节/chirp;4-lane 给 24000,余量充足。
  带宽上 2-lane 也放得下(给 12000)。这里用 4-lane 不是因为带宽,而是启动器的数据通路和 `'launcher'` 解包
  是按 4-lane 验证的;改成 2-lane 字节排布会变,要换解包并重新验证。
- **高采样率时必须 4-lane**:例如 192 样点 / 22500 ksps / 周期 21 µs 需要 3328 字节/chirp,2-lane 只给 3150,放不下。
- **1843**:物理上只有 2 条 lane,持续采样率上限约 9.4 Msps(4RX 复数 16 bit)。

---

## 排障

| 现象 | 处理 |
|---|---|
| `AWR2243_init 返回 -8` | **基本都是 SOP 跳线没设成 001**(见顶部)。其次 Linux:没用 sudo / 没 rmmod ftdi_sio;Windows:mmWave Studio 开着 / 上一个启动器没停 |
| 启动日志 `RF Patch Version [0.0.0.0]` | 板子没有 patch,跑一次 `flash_patch.py` |
| 数据全是噪声,raw int16 幅度只有 ±50 | 看配置里 Programmable Filter 段是否 `progFiltLen=0; progFiltFreqShift=0`;`adcFormat=1` 时这段非零必然是噪声 |
| RA / RD 图是镜像或噪声 | `config.py` 的 `CAPTURE_SOURCE` 与采集方式不配套(启动器用 `'launcher'`,mmWave Studio 用 `'studio'`) |
| Windows `QWidget: Must construct a QApplication before a QWidget` | 环境里 PyQt5 与 PySide6 并存,pyqtgraph 选了 PySide6;根目录 `plot.py` 已强制 PyQt5,别改 import 顺序 |
| `import fpga_udp` 失败 | 重跑 `build_ubuntu.sh` / `build_windows.bat` 看编译报错,并确认用的是装了 `fpga_udp` 的那个 Python 环境 |
| Windows 上 `import fpga_udp` 直接崩溃、没有任何报错 | conda 环境自带的旧版 VC 运行库(vcruntime140 / msvcp140)与 VS2022 编译的扩展不兼容;`build_windows.bat` 的 [1.5] 步会自动换成系统版(原文件备份为 `.bak`) |
| `sudo python3` 说没有 AWR2243_init | `fpga_udp` 只装给了普通用户,没装给 root → `sudo python3 -m pip install ./fpga_udp` |
| 链接找不到 `-lftd2xx` | 确认 `fpga_udp/src/FTDI_D2XX/Linux/<arch>/libftd2xx.so` 软链存在(build 脚本会建) |
| DCA1000 `sys_alive_check` 无响应 | 网卡 IP 是否 192.168.33.30;网线;DCA1000 是否上电 |

---

## 可选:换用其他版本的 libftd2xx

`build_ubuntu.sh` 用工程内自带的 libftd2xx(取版本号最高的)。如果想用 pyRadar 推荐的 `1.4.27`,
把它拷进工程,build 脚本会自动优先用它:
```bash
cp /usr/local/lib/libftd2xx.so.1.4.27  fpga_udp/src/FTDI_D2XX/Linux/x86_64/
```
不拷也行,自带的版本配合正确的 SOP 跳线同样能用。
