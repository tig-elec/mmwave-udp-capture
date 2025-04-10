import time
import numpy as np
import os
import keyboard
from datetime import datetime
from steaming import adcCapThread
from fft import get_heatmap_3dfft
from plot import plotThread
from config import periodicity

# Set a large number if you want the capture to run indefinitely.
frame_number = 999999


if __name__=='__main__':

    adc_single = adcCapThread(1,"adc")
    plot = plotThread(2,"visualization")

    adc_single.start()
    plot.start()

    t = time.time()
    folder = str(t).split(".")[0]

    # create folders
    os.makedirs(folder + "/RA")
    os.makedirs(folder + "/RD")
    os.makedirs(folder + "/DA")

    # os.makedirs(folder + "/RA/png")
    # os.makedirs(folder + "/RD/png")
    # os.makedirs(folder + "/DA/png")

    bin_file = open(folder + "/raw.bin", "wb")

    timestamp = open(folder + "/timestamp.txt", "w")
    timestamp_log = open(folder + "/timestamp_log.txt", "w")


    safe_count = 0
    frame_count = 0

    while True:

        readItem, timestamp_end, itemNum, lostPacketFlag = adc_single.getFrame()

        # The lostPacketFlag will always be False because packet loss is already handled automatically during streaming by skipping to the next available frame.
        # Therefore, to detect packet loss here, we compare the timestamps of two consecutive frames.
        # If the time difference exceeds the expected sampling interval, we consider it a lost frame.


        # if radar has data
        if itemNum >0:

            # Skip the first 10 frames at the beginning to allow the system to stabilize.
            safe_count += 1
            if safe_count > 10:

                s = datetime.now().timestamp()

                frame_count += 1

                current_bin_time = timestamp_end
                bin_time_diff = (current_bin_time - previous_bin_time) *1000
                # print("main time is " + str(current_bin_time))

                print("Current Frame is: " + str(frame_count) + " Timestamp is: " + str(current_bin_time))

                if bin_time_diff > periodicity + periodicity/2 and bin_time_diff < 2*periodicity:
                    timestamp_str = str(frame_count) + " " + str(current_bin_time)
                    timestamp_log_str = timestamp_str + " " + "Caution, current frame gap > frame rate : " + str(bin_time_diff)
                    # print("Caution: 当前帧距离上一帧时间有点长")
                elif bin_time_diff >= 2*periodicity:
                    timestamp_str = str(frame_count) + " " + str(current_bin_time)
                    timestamp_log_str = timestamp_str + " " + "Warning, current frame gap >> frame rate : " + str(bin_time_diff)
                    # print("Warning: 当前帧距离上一帧时间过长,发生了丢帧")
                else:
                    timestamp_str = str(frame_count) + " " + str(current_bin_time)
                    timestamp_log_str = timestamp_str

                # write frame_count and timestamp
                timestamp.write(timestamp_str + '\n')
                timestamp.flush()
                timestamp_log.write(timestamp_log_str + '\n')
                timestamp_log.flush()

                previous_bin_time = current_bin_time


                # write this frame into bin
                bin_file.write(readItem.tobytes())

                # fft for this frame
                rd, ra, da = get_heatmap_3dfft(readItem)

                np.save(folder + "/RA/" + str(frame_count) + ".npy", ra)
                np.save(folder + "/RD/" + str(frame_count) + ".npy", rd)
                np.save(folder + "/DA/" + str(frame_count) + ".npy", da)

                # too slow, no saving png, add a flush ?
                # plt.imshow(ra)
                # plt.savefig(folder + "/RA/png/" + str(frame_count) + ".png")
                # plt.imshow(rd)
                # plt.savefig(folder + "/RD/png/" + str(frame_count) + ".png")
                # plt.imshow(da)
                # plt.savefig(folder + "/DA/png/" + str(frame_count) + ".png")


                # heatmap visualization
                padding_gap = 25
                h_padding = np.zeros([ra.shape[0], padding_gap])
                h_heatmap = np.hstack((ra, h_padding, rd, h_padding, da))
                plot.plot(h_heatmap.T)

                # Check realtime performance
                # However, since there's a buffer in the streaming module, even if the main loop lags a bit and misses a few frames,
                # it can still catch up, so it might not be a big issue.

                e = datetime.now().timestamp()
                process_time = (e-s)*1000
                if process_time > periodicity/2 and process_time < periodicity - 10:
                    print("Caution: Real-Time Performance May be Affected " + str(process_time))
                elif process_time >= periodicity -10:
                    print("Warning: Real-Time Performance is Affected !!!! " + str(process_time))


            # # When the system is stable, update the timestamp of the previous frame.
            previous_bin_time = timestamp_end


        elif itemNum ==-1:
            print(readItem)

        elif itemNum ==-2:
            time.sleep(0.005)


        # Pressing both 'q' and 'e' simultaneously allows early termination.
        # bugs here for linux, just comment them
        if keyboard.is_pressed('q') and keyboard.is_pressed('e'):
            adc_single.whileSign = False
            bin_file.close()
            timestamp.close()
            timestamp_log.close()
            print("Exit")
            break

        if frame_count >= frame_number:
           adc_single.whileSign = False
           bin_file.close()
           timestamp.close()
           timestamp_log.close()
           print("Finished")

           break


    print('Done')
    print('\a')