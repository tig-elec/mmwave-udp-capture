import numpy as np
from config import ADC_PARAMS, RADAR_TYPE, CAPTURE_SOURCE, TDM_PHASE_COMPENSATION, TX1_PHASE_OFFSET

try:
    # scipy.fft 保持 complex64 单精度;numpy.fft 会先转成 complex128 再算,慢一倍
    from scipy import fft as _fft
except ImportError:
    _fft = np.fft

# azimuth FFT 的点数(虚拟天线补零到这么多),也就是 RA 图的方位 bin 数
# Azimuth FFT size (the virtual antennas are zero-padded to this), i.e. the number of azimuth bins of the RA map
NUM_ANGLE_BINS = 256


def _range_doppler_fft(adc_data):
    """解包 → 选水平天线 → 加窗 → range + doppler FFT。返回 (Chirps, VA, Samples) complex64,doppler 已 fftshift。"""

    adc_data = np.asarray(adc_data)

    # ============ 解包:与 fft_cupy.py 相同,按 config.CAPTURE_SOURCE 选择(两套格式不可混用!) ============
    if CAPTURE_SOURCE == 'launcher':
        # 一键启动器(mmwave2243_bringup,pyRadar 4-lane)采的数据,complex1x / 2x 排布相同
        # 排布(pyRadar 作者 testDecode_AWR2243.ipynb):每个采样点 → 4 个 RX 的 I → 4 个 RX 的 Q
        # (帧, chirps, tx, samples, IQ, rx) → (帧, chirps, tx, rx, samples, IQ),I first
        adc_data = np.reshape(adc_data, (-1, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['samples'], ADC_PARAMS['IQ'], ADC_PARAMS['rx']))
        adc_data = np.transpose(adc_data, (0, 1, 2, 5, 3, 4))
        adc_data = (adc_data[:, :, :, :, :, 0] + 1j * adc_data[:, :, :, :, :, 1]).astype(np.complex64)  # I first
    else:  # 'studio' —— mmWave Studio(2-lane)采的数据
        adc_data = np.reshape(adc_data, (-1, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['rx'], ADC_PARAMS['samples'] // 2, ADC_PARAMS['IQ'], 2))
        adc_data = np.transpose(adc_data, (0, 1, 2, 3, 4, 6, 5))
        adc_data = np.reshape(adc_data, (-1, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['rx'], ADC_PARAMS['samples'], ADC_PARAMS['IQ']))
        # I first
        adc_data = (adc_data[:, :, :, :, :, 0] + 1j * adc_data[:, :, :, :, :, 1]).astype(np.complex64)

        # adc_data shape: (F, C, T, R, S) For 1843
        # For 1443 and 2243 (RADAR_TYPE == 1):
        # RX samples are interleaved inside the fast-time stream:
        # stream = [s0_rx0, s0_rx1, s0_rx2, s0_rx3, s1_rx0, ...]
        # 1843 (RADAR_TYPE == 0) is not interleaved, so skip this re-ordering.
        if RADAR_TYPE == 1:
            F, C, T, R, S = adc_data.shape
            adc_data = np.reshape(adc_data, (F, C, T, R * S))   # flatten (R,S) -> stream
            adc_data = np.reshape(adc_data, (F, C, T, S, R))    # split stream as (samples, rx)
            adc_data = np.transpose(adc_data, (0, 1, 2, 4, 3))  # -> (F, C, T, R, S)
    # -----------------------------------------------------

    # 根据发射天线数量选出方位(水平)天线：
    #   tx=1 -> [0]     (1 根 TX × 4 RX = 4 VA)
    #   tx=2 -> [0, 1]  (2 根 TX × 4 RX = 8 VA)
    #   tx=3 -> [0, 2]  (取 TX1、TX3 两根水平天线，跳过俯仰 TX2 -> 8 VA)
    if ADC_PARAMS['tx'] == 1:
        tx_sel = [0]
    elif ADC_PARAMS['tx'] == 3:
        tx_sel = [0, 2]
    else:  # tx == 2
        tx_sel = [0, 1]
    adc_data_frame = np.reshape(adc_data[:, :, tx_sel, :, :],
                                (-1, ADC_PARAMS['chirps'], len(tx_sel) * ADC_PARAMS['rx'], ADC_PARAMS['samples']))

    radar_frame = adc_data_frame[0]
    # (Chirps,VA,ADC Samples)

    win_range = np.hanning(radar_frame.shape[2]).reshape(1, 1, radar_frame.shape[2])
    win_doppler = np.hanning(radar_frame.shape[0]).reshape(radar_frame.shape[0], 1, 1)

    radar_frame *= win_range  # shape [1,1,R]，按 range 方向乘
    radar_frame *= win_doppler  # shape [D,1,1]，按 doppler 方向乘

    # range + doppler FFT 只在真实的 VA 上做(8 路),不先把 azimuth 补零到 256 路:
    # 补零的那些行全是 0,沿 range / doppler 做 FFT 还是 0,先算后算结果一样。
    fft_data = _fft.fftn(radar_frame, axes=(0, 2))

    if TDM_PHASE_COMPENSATION and len(tx_sel) == 2:
        # TDM-MIMO 相位补偿(config.TDM_PHASE_COMPENSATION,默认关),与 fft_cupy.py 相同:
        # 给第二个 TX 的通道乘 exp(-j*(phi0 + 2π·delay·k/N)),k 为有符号 doppler bin,
        # delay = 第二个 TX 的 chirp 比第一个晚了几分之几个 doppler 采样周期(2 TX 轮发时是 1/2)
        num_chirps = fft_data.shape[0]
        k = np.fft.fftfreq(num_chirps) * num_chirps
        tdm_comp = np.exp(-1j * (TX1_PHASE_OFFSET + 2 * np.pi * (tx_sel[1] / ADC_PARAMS['tx']) * k / num_chirps))
        fft_data[:, ADC_PARAMS['rx']:, :] *= tdm_comp.astype(np.complex64).reshape(-1, 1, 1)

    fft_data = np.fft.fftshift(fft_data, axes=0)  # fftshift for doppler
    return fft_data.astype(np.complex64, copy=False)


def get_cube_3dfft(adc_data):
    """
    完整的复数 cube,shape (Chirps, Azimuth, Samples),doppler / azimuth 已 fftshift,
    与 fft_cupy.py 里 fftshift 之后的 fft_data 是同一个东西。

    做法:range + doppler FFT 只在真实的 VA 上做,azimuth FFT 放在最后,在这一步补零到 256。
    cube 很大(255 chirp × 256 样点时约 134MB),生成较慢,所以实时出图不走这里(见 get_heatmap_3dfft)。
    """
    fft_data = _range_doppler_fft(adc_data)
    cube = _fft.fft(fft_data, n=NUM_ANGLE_BINS, axis=1)       # azimuth FFT,补零到 NUM_ANGLE_BINS
    return np.fft.fftshift(cube, axes=1)                      # fftshift for azimuth


def _azimuth_power(cov, num_angle_bins):
    """
    cov: (..., VA, VA) 天线协方差 cov[n, m] = Σ x[n]·conj(x[m])
    返回 (..., num_angle_bins): 补零 azimuth FFT 的功率 |FFT_az|² 沿被求和的那个轴的和(未 fftshift)

    Σ |FFT_az(补零 x)[k]|² = Σ_d r[d]·exp(-j2πkd/N),r[d] 是天线轴上的自相关(lag d),
    也就是 cov 的第 d 条对角线之和。只有 2·VA-1 个 lag 非零,所以一次 N 点 FFT 就够。
    """
    num_va = cov.shape[-1]
    acf = np.zeros(cov.shape[:-2] + (num_angle_bins,), dtype=np.complex128)
    for d in range(num_va):
        r = np.trace(cov, offset=-d, axis1=-2, axis2=-1)
        acf[..., d % num_angle_bins] += r
        if d:
            acf[..., -d % num_angle_bins] += np.conj(r)
    return np.fft.fft(acf, axis=-1).real


def get_heatmap_3dfft(adc_data, return_cube=False):
    # return_cube=True 时多返回一个完整的复数 cube (Chirps, Azimuth, Samples),见 config.GENERATE_CUBE

    if return_cube:
        # 把 cube 建出来,三张图由 cube 求和得到(和 fft_cupy.py 的流程一样,但比下面的算法慢得多)
        cube = get_cube_3dfft(adc_data)
        power = cube.real ** 2 + cube.imag ** 2
        return _to_images(power.sum(1), power.sum(0), power.sum(2)) + (cube,)

    num_angle_bins = NUM_ANGLE_BINS

    fft_data = _range_doppler_fft(adc_data).astype(np.complex128)   # (Chirps, VA, Samples),数据量小,用双精度累加

    # ============ 三张图 = |cube|² 沿某一个轴求和,这里直接算这三个和,不把 cube 建出来 ============
    # cube 是 fft_data 沿 VA 轴补零到 256 再做 FFT(见 get_cube_3dfft),所以:
    #   RD 沿 azimuth 求和 → Parseval:Σ_k |cube[k]|² = N·Σ_va |fft_data[va]|²
    #   RA / DA 沿 doppler / range 求和 → 先把该轴求和成天线协方差,再做一次 N 点 FFT(见 _azimuth_power)
    # 数值上和"建出 cube 再求和"相同(运行 python fft_cpu.py 可以自检),但快得多,也不用每帧搬动上百 MB 内存。
    rd_power = num_angle_bins * (fft_data.real ** 2 + fft_data.imag ** 2).sum(1)      # (Chirps, Samples)

    by_range = np.ascontiguousarray(fft_data.transpose(2, 0, 1))                      # (Samples, Chirps, VA)
    cov_ra = by_range.transpose(0, 2, 1) @ by_range.conj()                            # (Samples, VA, VA) 对 doppler 求和
    cov_da = fft_data @ fft_data.conj().transpose(0, 2, 1)                            # (Chirps, VA, VA) 对 range 求和

    ra_power = np.fft.fftshift(_azimuth_power(cov_ra, num_angle_bins), axes=-1).T     # (Azimuth, Samples)
    da_power = np.fft.fftshift(_azimuth_power(cov_da, num_angle_bins), axes=-1)       # (Chirps, Azimuth)

    return _to_images(rd_power, ra_power, da_power)


def _to_images(rd_power, ra_power, da_power):
    """rd (Chirps, Samples) / ra (Azimuth, Samples) / da (Chirps, Azimuth) 功率 → 与 fft_cupy.py 相同的归一化图"""

    # 丢包帧是全 0,log10(0) = -inf,和 GPU 版一样得到 NaN 图;这里只是不让 numpy 每帧打印告警
    with np.errstate(divide='ignore', invalid='ignore'):

        # Range - Doppler
        range_doppler = np.log10(rd_power).T
        range_doppler = (range_doppler - np.min(range_doppler)) / (np.max(range_doppler) - np.min(range_doppler)) #Normalization
        range_doppler = range_doppler[::-1]  # Vertical flip
        rd_img = range_doppler

        # Range - Azimuth
        range_azimuth = np.log10(ra_power).T
        range_azimuth = (range_azimuth - np.min(range_azimuth)) / (np.max(range_azimuth) - np.min(range_azimuth)) #Normalization
        range_azimuth = range_azimuth[::-1]  # Vertical flip
        ra_img = range_azimuth

        # Doppler -Azimuth
        doppler_azimuth = np.log10(da_power).T
        doppler_azimuth = (doppler_azimuth - np.min(doppler_azimuth)) / (
                    np.max(doppler_azimuth) - np.min(doppler_azimuth))  #Normalization
        da_img = doppler_azimuth

    # 与 GPU 版输出的 dtype 保持一致(RA / RD 的 .npy 是 float32)
    rd_img = np.ascontiguousarray(rd_img, dtype=np.float32)
    ra_img = np.ascontiguousarray(ra_img, dtype=np.float32)
    da_img = np.ascontiguousarray(da_img, dtype=np.float32)

    return rd_img, ra_img, da_img


if __name__ == '__main__':
    # 自检:不建 cube 算出的三张图 是否等于 把 cube 建出来再求和(return_cube=True)的三张图
    # Self-check: do the three maps computed without the cube equal the maps summed from the cube (return_cube=True)?
    frame = np.random.default_rng(0).integers(
        -2000, 2000, dtype=np.int16,
        size=ADC_PARAMS['chirps'] * ADC_PARAMS['tx'] * ADC_PARAMS['rx'] * ADC_PARAMS['samples'] * ADC_PARAMS['IQ'])
    *from_cube, cube = get_heatmap_3dfft(frame, return_cube=True)
    print('cube', cube.shape, cube.dtype, '(Chirps, Azimuth, Samples)')
    for name, a, b in zip(('RD', 'RA', 'DA'), from_cube, get_heatmap_3dfft(frame)):
        print(name, a.shape, 'max |summed from cube - computed without cube| = %.1e' % np.abs(a - b).max())
