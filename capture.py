"""
Millimeter-Wave Radar Data Capture Module with Hardware Trigger Support.

This module provides functionality to capture radar data frames and
match them with hardware trigger events received via a serial port or ROS.
It supports saving raw binary data, timestamps, and individual frames.

Trigger listener threads live in triggers.py; behavior is driven by config.py.
"""

import time
import numpy as np
import os
from typing import List

from streaming import adcCapThread
from triggers import create_trigger_thread


def main() -> None:
    """
    Main program logic for radar data capture with optional trigger matching.

    Behavior is driven by config.py:
      - USE_HARDWARE_TRIGGER: whether to match frames against a hardware trigger
      - TRIGGER_SOURCE: 'serial' or 'ros' (only used when the above is True)
    """
    frame_number = np.inf       # Number of frames to capture
    adc_single = None
    trigger_thread = None
    bin_file = None
    timestamp_file = None

    try:
        # --- 1. Initialization ---
        # 根据 config 决定是否启用硬件触发时间戳（禁用时返回 None）
        trigger_thread = create_trigger_thread()

        adc_single = adcCapThread(1, "adc")
        if trigger_thread is not None:
            trigger_thread.start()
        adc_single.start()

        # Create output directory structure
        folder = str(int(time.time()))
        os.makedirs(os.path.join(folder, "frame"))
        print(f"Data will be saved in folder: {folder}")

        # Open output files
        bin_file = open(os.path.join(folder, "raw.bin"), "wb")
        timestamp_file = open(os.path.join(folder, "timestamp.txt"), "w")
        timestamp_file.write("Frame_count,Frame_id,TriggerTimestamp,FrameTimestamp,Delta(ms),BrokenFlag\n")

        frame_count = 0
        pending_triggers: List[float] = []  # List to store pending trigger timestamps
        MATCH_THRESHOLD_SECONDS = 0.1       # Threshold for matching triggers with frames

        # --- 2. Main Loop ---
        while True:
            # Wait for a frame to be available (with timeout)
            frame_data, timestamp, frame_id, lostPacketFlag = adc_single.getFrame(block=True, timeout=10)

            if frame_data is None or timestamp is None or frame_id is None or lostPacketFlag is None:
                print("[Main] No valid frame received.")
                continue

            # Check for packet loss
            if lostPacketFlag:
                print(f"[Warning] A frame was dropped by streaming thread due to packet loss.")

            current_bin_time = timestamp
            frame_count += 1

            # Default values when hardware trigger is disabled
            trigger_str = "None"
            delta_str = "N/A"

            if trigger_thread is not None:
                # Step 1: Get all new trigger signals from queue
                while True:
                    new_trigger = trigger_thread.get_trigger_time()
                    if new_trigger is None:
                        break
                    pending_triggers.append(new_trigger)

                # Step 2: Find the closest trigger match for current frame
                best_match_trigger = None
                if pending_triggers:
                    deltas = [abs(current_bin_time - ts) for ts in pending_triggers]
                    min_delta = min(deltas)

                    # Step 3: Check if match is within threshold
                    if min_delta < MATCH_THRESHOLD_SECONDS:
                        best_match_index = deltas.index(min_delta)
                        # Step 4: Match successful, remove from list
                        best_match_trigger = pending_triggers.pop(best_match_index)

                # Log match result
                if best_match_trigger is not None:
                    delta = (current_bin_time - best_match_trigger) * 1000
                    delta_str = f"{delta:.6f}"
                    trigger_str = f"{best_match_trigger:.6f}"
                    print(f"[Frame] {frame_count} | Trigger MATCHED | trigger_ts: {trigger_str} | "
                          f"frame_ts: {current_bin_time:.6f} | Delta: {delta_str} ms")
                else:
                    print(f"[Frame] {frame_count} | Trigger NOT MATCHED | trigger_ts: {trigger_str} | "
                          f"frame_ts: {current_bin_time:.6f} | Delta: {delta_str} ms")

                # Step 5: Prune stale triggers from list
                triggers_to_keep = [ts for ts in pending_triggers if (current_bin_time - ts) < MATCH_THRESHOLD_SECONDS]
                if len(pending_triggers) != len(triggers_to_keep):
                    print(f"[Info] Pruned {len(pending_triggers) - len(triggers_to_keep)} stale trigger(s).")
                pending_triggers = triggers_to_keep
            else:
                print(f"[Frame] {frame_count} | HW trigger disabled | frame_ts: {current_bin_time:.6f}")

            # Save files
            timestamp_str = f"{frame_count},{frame_id},{trigger_str},{current_bin_time:.6f},{delta_str},{int(lostPacketFlag)}"
            timestamp_file.write(timestamp_str + '\n')
            timestamp_file.flush()

            bin_file.write(frame_data.tobytes())
            np.save(os.path.join(folder, "frame", f"{frame_count}.npy"), frame_data)

            # Check if target frame count reached
            if frame_count >= frame_number:
                print("Target frame number reached. Finishing...")
                break

    except KeyboardInterrupt:
        print("\nKeyboard Interrupt detected. Exiting gracefully...")
    except Exception as e:
        print(f"\nAn unexpected error occurred in main loop: {e}")
    finally:
        # --- 3. Cleanup ---
        print("Shutting down threads and closing files...")
        if adc_single:
            adc_single.whileSign = False
            # Send empty packet to unlock recvfrom
            try:
                adc_single.data_socket.sendto(b'\x00' * 1, adc_single.data_recv)
            except Exception as e:
                print(f"[Warning] Could not send unlock packet: {e}")
            print("Waiting for ADC thread to finish...")

        if trigger_thread is not None:
            print("Stopping trigger thread...")
            trigger_thread.stop()

        if bin_file:
            print("Closing binary file...")
            bin_file.close()

        if timestamp_file:
            print("Closing timestamp file...")
            timestamp_file.close()

        print("Cleanup complete. Program finished.")


if __name__ == '__main__':
    main()
