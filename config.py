
# ============ 触发时间戳配置 ============
# 是否使用硬件触发时间戳做多传感器同步。
#   False: 不启动任何触发线程，直接用收到数据时打的 bin 时间戳
#   True : 启用硬触发，再由 TRIGGER_SOURCE 选择来源
USE_HARDWARE_TRIGGER = False
# 硬触发来源，仅在 USE_HARDWARE_TRIGGER = True 时生效: 'serial' 或 'ros'
TRIGGER_SOURCE = 'serial'
# 串口触发用的端口，仅在 TRIGGER_SOURCE = 'serial' 时生效
COM_PORT = 'COM3'
# ROS 触发用的 topic，仅在 TRIGGER_SOURCE = 'ros' 时生效
ROS_TOPIC = 'serial_trigger'


# ============ 雷达型号 ============
# 决定 fft.py 里是否需要对 RX 交织的 fast-time 流做重排。
#   0 = 1843        (RX 不交织，无需重排)
#   1 = 1443 / 2243 (RX 在 fast-time 流里交织，需要重排)
RADAR_TYPE = 0


# ============ ADC 参数 ============
# ADC_PARAMS = {'chirps': 255,
#               'rx': 4,
#               'tx': 2,
#               'samples': 256,
#               'IQ': 2,
#               'bytes': 2}


# tx 决定 fft.py 里方位(水平)天线的选取（只做水平方位热力图，不要 elevation）：
#   tx=1 -> [0]     (1 根 TX × 4 RX = 4 VA)
#   tx=2 -> [0, 1]  (2 根 TX × 4 RX = 8 VA)  <- 默认，只开两根水平天线
#   tx=3 -> [0, 2]  (取 TX1、TX3 两根水平天线，跳过俯仰 TX2 -> 8 VA)
ADC_PARAMS = {'chirps': 255,
              'rx': 4,
              'tx': 2,
              'samples': 192,
              'IQ': 2,
              'bytes': 2}
