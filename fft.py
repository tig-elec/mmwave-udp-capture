import time
import matplotlib.pyplot as plt
import cupy as cp
from config import ADC_PARAMS


def get_heatmap_3dfft(adc_data):


    start = time.time()

    adc_data = cp.asarray(adc_data)

    adc_data = cp.reshape(adc_data, (-1, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['rx'], ADC_PARAMS['samples'] // 2, ADC_PARAMS['IQ'], 2))
    adc_data = cp.transpose(adc_data, (0, 1, 2, 3, 4, 6, 5))
    adc_data = cp.reshape(adc_data, (-1, ADC_PARAMS['chirps'], ADC_PARAMS['tx'], ADC_PARAMS['rx'], ADC_PARAMS['samples'], ADC_PARAMS['IQ']))
    # I first
    adc_data = (adc_data[:, :, :, :, :, 0] + 1j * adc_data[:, :, :, :, :, 1]).astype(cp.complex64)
    adc_data_frame = cp.reshape(adc_data[:, :, 0:2, :, :], (-1, ADC_PARAMS['chirps'], 2 * 4, ADC_PARAMS['samples']))


    num_angle_bins = 256

    radar_frame_gpu = adc_data_frame[0]
    # (Chirps,VA,ADC Samples)


    win_range = cp.hanning(radar_frame_gpu.shape[2]).reshape(1,1,radar_frame_gpu.shape[2])
    win_doppler = cp.hanning(radar_frame_gpu.shape[0]).reshape(radar_frame_gpu.shape[0],1,1)

    radar_frame_win = radar_frame_gpu * win_range * win_doppler

    # TODO: TDMA support — but since we only have 2 TX antennas, we can probably ignore it for now.

    # azimuth padding
    padding = ((0, 0), (0, num_angle_bins - adc_data_frame.shape[2]), (0, 0))
    adc_data = cp.pad(radar_frame_win, padding, mode='constant')

    # cupy fft
    fft_data = cp.fft.fftn(adc_data)  # 255 256(8) 256

    # fftshift
    fft_data = cp.fft.fftshift(fft_data, axes=(0, 1))  # fftshift for doppler and azimuth

    # Range - Doppler
    range_doppler = cp.log10((cp.abs(fft_data)**2).sum(1)).T
    range_doppler = (range_doppler - cp.min(range_doppler)) / (cp.max(range_doppler) - cp.min(range_doppler)) #Normalization
    range_doppler = range_doppler[::-1]  # Vertical flip
    rd_img = range_doppler
    # RD_image.append(range_doppler)


    # Range - Azimuth
    range_azimuth = cp.log10((cp.abs(fft_data)**2).sum(0)).T
    range_azimuth = (range_azimuth - cp.min(range_azimuth)) / (cp.max(range_azimuth) - cp.min(range_azimuth)) #Normalization
    range_azimuth = range_azimuth[::-1]  # Vertical flip
    ra_img = range_azimuth
    # RA_image.append(range_azimuth)


    # Doppler -Azimuth
    doppler_azimuth = cp.log10((cp.abs(fft_data)**2).sum(2)).T
    doppler_azimuth = (doppler_azimuth - cp.min(doppler_azimuth)) / (
                cp.max(doppler_azimuth) - cp.min(doppler_azimuth))  #Normalization
    # doppler_azimuth = doppler_azimuth[::-1] # Vertical flip
    da_img = doppler_azimuth
    # DA_image.append(doppler_azimuth)



    rd_img = cp.asnumpy(rd_img)
    ra_img = cp.asnumpy(ra_img)
    da_img = cp.asnumpy(da_img)

    end = time.time()

    # print("Time taken (s):", end - start)


    return rd_img, ra_img, da_img

