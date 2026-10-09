
# ============ 触发时间戳配置 / Trigger timestamp ============
# 是否使用硬件触发时间戳做多传感器同步。
#   False: 不启动任何触发线程，直接用收到数据时打的 bin 时间戳
#   True : 启用硬触发，再由 TRIGGER_SOURCE 选择来源
# Whether to use hardware-trigger timestamps for multi-sensor synchronisation.
#   False: no trigger thread; use the timestamp taken when the frame data is received
#   True : enable the hardware trigger; the source is chosen by TRIGGER_SOURCE
USE_HARDWARE_TRIGGER = False
# 硬触发来源，仅在 USE_HARDWARE_TRIGGER = True 时生效: 'serial' 或 'ros'
# Trigger source, only used when USE_HARDWARE_TRIGGER = True: 'serial' or 'ros'
TRIGGER_SOURCE = 'serial'
# 串口触发用的端口，仅在 TRIGGER_SOURCE = 'serial' 时生效
# Serial port for the trigger, only used when TRIGGER_SOURCE = 'serial'
COM_PORT = 'COM3'
# ROS 触发用的 topic，仅在 TRIGGER_SOURCE = 'ros' 时生效
# ROS topic for the trigger, only used when TRIGGER_SOURCE = 'ros'
ROS_TOPIC = 'serial_trigger'


# ============ FFT 计算后端 / FFT backend (capture_plot.py) ============
#   'cupy' : GPU,用 fft_cupy.py(需要 CUDA + CuPy)
#   'cpu'  : CPU,用 fft_cpu.py(只需要 numpy,装了 scipy 更快);出的图与 GPU 版一致
#   'cupy' : GPU, uses fft_cupy.py (needs CUDA + CuPy)
#   'cpu'  : CPU, uses fft_cpu.py (needs only numpy; faster with scipy); same maps as the GPU version
FFT_BACKEND = 'cpu'


# ============ 是否生成 cube / Save the full cube (capture_plot.py) ============
#   False : 实时模式(默认),只出 RA / RD 图,不保存 cube
#   True  : 每帧多生成一个完整的复数 cube,shape (Chirps, Azimuth 256, Samples),complex64,
#           存到 <输出目录>/cube/<帧号>.npy;RA / RD 图改为由 cube 求和得到(结果一样)
#           每个 cube = Chirps × 256 × Samples × 8 字节(255 × 256 时约 134MB),生成和写盘都很慢,不保证实时:
#           处理不过来的帧会被帧队列丢掉,raw.bin 也会跟着缺帧。只在确实需要 cube 时打开。
#   False : real-time mode (default); only the RA / RD maps, no cube is saved
#   True  : additionally build the full complex cube of every frame, shape (Chirps, Azimuth 256, Samples),
#           complex64, saved to <output folder>/cube/<frame>.npy; the RA / RD maps are then summed from
#           the cube (same result).
#           One cube = Chirps x 256 x Samples x 8 bytes (about 134 MB for 255 x 256). Building and writing
#           it is slow and NOT real-time: frames that cannot be processed in time are dropped by the frame
#           queue and are then missing from raw.bin as well. Enable only when the cube is really needed.
GENERATE_CUBE = False


# ============ 耗时输出 / Timing output (capture_plot.py) ============
#   True : 每帧打印一行 [Time],单位 ms:
#            fft        FFT + 出图(GENERATE_CUBE = True 时含生成 cube)
#            cube save  把 cube 写盘(仅 GENERATE_CUBE = True 时有)
#            total      这一帧从取到数据到全部处理完的时间(含保存 raw / frame / RA / RD 和送去显示)
#            queue      帧队列里还积压着几帧;一直涨到满 = 处理跟不上,会丢帧
#          total 要小于帧周期(10 Hz 是 100 ms)才算跟得上。
#   False: 不打印
#   True : print one [Time] line per frame, in ms:
#            fft        FFT + maps (includes building the cube when GENERATE_CUBE = True)
#            cube save  writing the cube to disk (only when GENERATE_CUBE = True)
#            total      from receiving the frame to finishing everything (saving raw / frame / RA / RD, plotting)
#            queue      frames waiting in the frame queue; growing until full = too slow, frames get dropped
#          total has to stay below the frame period (100 ms at 10 Hz) to keep up.
#   False: no timing output
PRINT_TIMING = True


# ============ TDM-MIMO 相位补偿 / TDM-MIMO phase compensation (fft_cupy.py / fft_cpu.py) ============
# 两个 TX 轮流发,第二个 TX 的 chirp 比第一个晚半个 doppler 采样周期,运动目标在这段时间里多转了相位,
# 不补的话虚拟阵列前 4 个和后 4 个通道之间有相位台阶,运动目标的方位角会偏。
#   False : 不补偿(默认)
#   True  : doppler FFT 之后、azimuth FFT 之前,给第二个 TX 的 4 个通道乘 exp(-j*(TX1_PHASE_OFFSET + π·k/N)),
#           k 是有符号 doppler bin。只影响 RA / DA 图和 cube,RD 图不变。tx=1(单发)时不起作用。
# With two TX antennas transmitting in turn, the chirp of the second TX comes half a Doppler sampling
# period after the first. A moving target adds phase during that time, which puts a phase step between
# the first 4 and the last 4 virtual channels and shifts the azimuth of moving targets.
#   False : no compensation (default)
#   True  : after the Doppler FFT and before the azimuth FFT, multiply the 4 channels of the second TX by
#           exp(-j*(TX1_PHASE_OFFSET + pi*k/N)), k being the signed Doppler bin. Affects only the RA / DA
#           maps and the cube; the RD map is unchanged. No effect when tx=1 (single TX).
TDM_PHASE_COMPENSATION = False
# 第二个 TX 相对第一个 TX 的固定相位差(rad),板级标定量,换板子 / 换配置要重新测。
# 只在 TDM_PHASE_COMPENSATION = True 时生效;0 = 不做固定相位标定,只做上面的 doppler 相位补偿。
# Fixed phase offset (rad) of the second TX relative to the first. It is a per-board calibration value
# and must be measured again for another board or configuration.
# Only used when TDM_PHASE_COMPENSATION = True; 0 = no fixed-phase calibration, Doppler compensation only.
TX1_PHASE_OFFSET = 0.0


# ============ 采集来源 / Capture source (selects the unpacking in fft_cupy.py / fft_cpu.py) ============
# 两套字节流格式完全不同,必须和数据的实际采集方式配套,混用 = 镜像/噪声!
#   'launcher' : 用本目录 mmwave2243_bringup 一键启动器采的数据。
#                启动器只支持 AWR2243,数据排布只有一种(4-lane,每个采样点先 4 个 RX 的 I、再 4 个 RX 的 Q;
#                complex1x / 2x 相同),所以不用选型号:
#                下面的 RADAR_TYPE 在这个模式下不会被读取,填 0 还是 1 结果都一样。
#   'studio'   : 用 mmWave Studio 采的数据(2-lane)。
#                1843 和 1443 / 2243 的 RX 排列不同,必须用下面的 RADAR_TYPE 指明型号。
# The two byte layouts are completely different and must match how the data was actually captured;
# a mismatch decodes into mirror images or noise!
#   'launcher' : data captured with the launcher in mmwave2243_bringup.
#                The launcher supports only the AWR2243 and has a single layout (4-lane; for every sample
#                the I of 4 RX, then the Q of 4 RX; identical for complex1x / 2x), so no model has to be
#                chosen: RADAR_TYPE below is not read in this mode, 0 and 1 give the same result.
#   'studio'   : data captured with mmWave Studio (2-lane).
#                1843 and 1443 / 2243 order the RX differently, so RADAR_TYPE below must name the model.
CAPTURE_SOURCE = 'launcher'


# ============ 雷达型号 / Radar model (only used when CAPTURE_SOURCE = 'studio') ============
# CAPTURE_SOURCE = 'launcher' 时本项被忽略,不用管。
# CAPTURE_SOURCE = 'studio' 时决定是否对 RX 交织的 fast-time 流做重排,填错数据会错乱:
#   0 = 1843        (RX 不交织，无需重排)
#   1 = 1443 / 2243 (RX 在 fast-time 流里交织，需要重排)
# Ignored when CAPTURE_SOURCE = 'launcher'.
# When CAPTURE_SOURCE = 'studio' it decides whether the RX-interleaved fast-time stream is reordered;
# a wrong value scrambles the data:
#   0 = 1843        (RX not interleaved, no reordering)
#   1 = 1443 / 2243 (RX interleaved in the fast-time stream, reordering needed)
RADAR_TYPE = 1


# ============ ADC 参数 / ADC parameters ============
# 必须与雷达实际配置一致(用启动器时即 mmwave2243_bringup/configFiles/AWR2243_mmwaveconfig.txt):
#   chirps = 每帧的 loop 数,samples = 每个 chirp 的 ADC 采样点数,tx = 轮流发射的 TX 数
# tx 决定 fft_cupy.py / fft_cpu.py 里方位(水平)天线的选取（只做水平方位热力图，不要 elevation）：
#   tx=1 -> [0]     (1 根 TX × 4 RX = 4 VA)
#   tx=2 -> [0, 1]  (2 根 TX × 4 RX = 8 VA)  <- 默认，只开两根水平天线
#   tx=3 -> [0, 2]  (取 TX1、TX3 两根水平天线，跳过俯仰 TX2 -> 8 VA)
# Must match the actual radar configuration (with the launcher that is
# mmwave2243_bringup/configFiles/AWR2243_mmwaveconfig.txt):
#   chirps = loops per frame, samples = ADC samples per chirp, tx = number of TX transmitting in turn
# tx selects the azimuth (horizontal) antennas in fft_cupy.py / fft_cpu.py (azimuth-only maps, no elevation):
#   tx=1 -> [0]     (1 TX x 4 RX = 4 VA)
#   tx=2 -> [0, 1]  (2 TX x 4 RX = 8 VA)  <- default, the two horizontal TX only
#   tx=3 -> [0, 2]  (TX1 and TX3, the two horizontal ones, skipping the elevation TX2 -> 8 VA)
ADC_PARAMS = {'chirps': 255,
              'rx': 4,
              'tx': 2,
              'samples': 256,
              'IQ': 2,
              'bytes': 2}
