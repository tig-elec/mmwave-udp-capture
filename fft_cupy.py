import time
import matplotlib.pyplot as plt
import cupy as cp
import numpy as np
from config import ADC_PARAMS, RADAR_TYPE, CAPTURE_SOURCE, TDM_PHASE_COMPENSATION, TX1_PHASE_OFFSET




def deint4(x, order):
    return cp.concatenate([x[..., k::4] for k in order], axis=-1)




def get_heatmap_3dfft(adc_data, return_cube=False):
    # return_cube=True 时多返回一个完整的复数 cube (Chirps, Azimuth, Samples),见 config.GENERATE_CUBE

    adc_data = cp.asarray(adc_data)

    # ============ 解包:按 config.CAPTURE_SOURCE 选择(两套格式不可混用!) ============
    if CAPTURE_SOURCE == 'launcher':
        # 一键启动器(mmwave2243_bringup,pyRadar 4-lane)采的数据,complex1x / 2x 排布相同
        # 排布(pyRadar 作者 testDecode_AWR2243.ipynb):每个采样点 → 4 个 RX 的 I → 4 个 RX 的 Q
        # (帧, chirps, tx, samples, IQ, rx) → (帧, chirps, tx, rx, samples, IQ),I first
        # RX 已在正确位置,无需 RADAR_TYPE 重排
        adc_data = cp.reshape(adc_data, (-1, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['samples'], ADC_PARAMS['IQ'], ADC_PARAMS['rx']))
        adc_data = cp.transpose(adc_data, (0, 1, 2, 5, 3, 4))
        adc_data = (adc_data[:, :, :, :, :, 0] + 1j * adc_data[:, :, :, :, :, 1]).astype(cp.complex64)  # I first
    else:  # 'studio' —— mmWave Studio(2-lane)采的数据
        adc_data = cp.reshape(adc_data, (-1, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['rx'], ADC_PARAMS['samples'] // 2, ADC_PARAMS['IQ'], 2))
        adc_data = cp.transpose(adc_data, (0, 1, 2, 3, 4, 6, 5))
        adc_data = cp.reshape(adc_data, (-1, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['rx'], ADC_PARAMS['samples'], ADC_PARAMS['IQ']))
        # I first
        adc_data = (adc_data[:, :, :, :, :, 0] + 1j * adc_data[:, :, :, :, :, 1]).astype(cp.complex64)

        # adc_data shape: (F, C, T, R, S) For 1843
        # For 1443 and 2243 (RADAR_TYPE == 1):
        # RX samples are interleaved inside the fast-time stream:
        # stream = [s0_rx0, s0_rx1, s0_rx2, s0_rx3, s1_rx0, ...]
        # 1843 (RADAR_TYPE == 0) is not interleaved, so skip this re-ordering.
        if RADAR_TYPE == 1:
            F, C, T, R, S = adc_data.shape
            adc_data = cp.reshape(adc_data, (F, C, T, R * S))   # flatten (R,S) -> stream
            adc_data = cp.reshape(adc_data, (F, C, T, S, R))    # split stream as (samples, rx)
            adc_data = cp.transpose(adc_data, (0, 1, 2, 4, 3))  # -> (F, C, T, R, S)
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
    adc_data_frame = cp.reshape(adc_data[:, :, tx_sel, :, :],
                                (-1, ADC_PARAMS['chirps'], len(tx_sel) * ADC_PARAMS['rx'], ADC_PARAMS['samples']))

    # azimuth FFT 的点数(虚拟天线补零到这么多),也就是 RA 图的方位 bin 数
    # Azimuth FFT size (the virtual antennas are zero-padded to this), i.e. the number of azimuth bins of the RA map
    num_angle_bins = 256

    radar_frame_gpu = adc_data_frame[0]
    # (Chirps,VA,ADC Samples)


    win_range = cp.hanning(radar_frame_gpu.shape[2]).reshape(1,1,radar_frame_gpu.shape[2])
    win_doppler = cp.hanning(radar_frame_gpu.shape[0]).reshape(radar_frame_gpu.shape[0],1,1)

    radar_frame_gpu *= win_range  # shape [1,1,R]，按 range 方向乘
    radar_frame_gpu *= win_doppler  # shape [D,1,1]，按 doppler 方向乘


    radar_frame_win = radar_frame_gpu

    # azimuth padding
    padding = ((0, 0), (0, num_angle_bins - adc_data_frame.shape[2]), (0, 0))

    if TDM_PHASE_COMPENSATION and len(tx_sel) == 2:
        # TDM-MIMO 相位补偿(config.TDM_PHASE_COMPENSATION,默认关):先做 doppler FFT,
        # 给第二个 TX 的通道乘 exp(-j*(phi0 + 2π·delay·k/N)),再补零做 azimuth + range FFT
        #   phi0 : 两个 TX 间的固定相位差(config.TX1_PHASE_OFFSET)
        #   delay: 第二个 TX 的 chirp 比第一个晚了几分之几个 doppler 采样周期(2 TX 轮发时是 1/2,即 π·k/N)
        #   k    : 有符号 doppler bin
        fft_data = cp.fft.fft(radar_frame_win, axis=0)
        num_chirps = fft_data.shape[0]
        k = np.fft.fftfreq(num_chirps) * num_chirps
        tdm_comp = np.exp(-1j * (TX1_PHASE_OFFSET + 2 * np.pi * (tx_sel[1] / ADC_PARAMS['tx']) * k / num_chirps))
        fft_data[:, ADC_PARAMS['rx']:, :] *= cp.asarray(tdm_comp.astype(np.complex64)).reshape(-1, 1, 1)
        adc_data = cp.pad(fft_data, padding, mode='constant')
        fft_data = cp.fft.fftn(adc_data, axes=(1, 2))
    else:
        adc_data = cp.pad(radar_frame_win, padding, mode='constant')

        # 3D FFT → (Chirps, Azimuth, Samples)
        fft_data = cp.fft.fftn(adc_data)

    # fftshift
    fft_data = cp.fft.fftshift(fft_data, axes=(0, 1))  # fftshift for doppler and azimuth

    # Range - Doppler
    range_doppler = cp.log10((cp.abs(fft_data)**2).sum(1)).T
    range_doppler = (range_doppler - cp.min(range_doppler)) / (cp.max(range_doppler) - cp.min(range_doppler)) #Normalization
    range_doppler = range_doppler[::-1]  # Vertical flip
    rd_img = range_doppler


    # Range - Azimuth
    range_azimuth = cp.log10((cp.abs(fft_data)**2).sum(0)).T
    range_azimuth = (range_azimuth - cp.min(range_azimuth)) / (cp.max(range_azimuth) - cp.min(range_azimuth)) #Normalization
    range_azimuth = range_azimuth[::-1]  # Vertical flip
    ra_img = range_azimuth


    # Doppler -Azimuth
    doppler_azimuth = cp.log10((cp.abs(fft_data)**2).sum(2)).T
    doppler_azimuth = (doppler_azimuth - cp.min(doppler_azimuth)) / (
                cp.max(doppler_azimuth) - cp.min(doppler_azimuth))  #Normalization
    da_img = doppler_azimuth



    rd_img = cp.asnumpy(rd_img)
    ra_img = cp.asnumpy(ra_img)
    da_img = cp.asnumpy(da_img)

    if return_cube:
        return rd_img, ra_img, da_img, cp.asnumpy(fft_data)

    return rd_img, ra_img, da_img
