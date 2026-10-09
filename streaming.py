"""
Millimeter-Wave Radar Data Streaming Module.

This module handles the reception and processing of UDP data packets
from a millimeter-wave radar system. It provides functionality for
frame synchronization, packet loss detection, and data buffering.
"""

import socket
import struct
import threading
import numpy as np
from datetime import datetime
import queue
from typing import Tuple, Optional, Union, Any

from config import ADC_PARAMS

# STATIC CONSTANTS
MAX_PACKET_SIZE = 4096
BYTES_IN_PACKET = 1456

# DYNAMIC CONSTANTS - Calculated based on radar configuration
BYTES_IN_FRAME = (ADC_PARAMS['chirps'] * ADC_PARAMS['rx'] * ADC_PARAMS['tx'] *
                  ADC_PARAMS['IQ'] * ADC_PARAMS['samples'] * ADC_PARAMS['bytes'])
BYTES_IN_FRAME_CLIPPED = (BYTES_IN_FRAME // BYTES_IN_PACKET) * BYTES_IN_PACKET
PACKETS_IN_FRAME = BYTES_IN_FRAME / BYTES_IN_PACKET
PACKETS_IN_FRAME_CLIPPED = BYTES_IN_FRAME // BYTES_IN_PACKET
INT16_IN_PACKET = BYTES_IN_PACKET // 2
INT16_IN_FRAME = BYTES_IN_FRAME // 2


class adcCapThread(threading.Thread):
    """
    Thread for capturing and processing ADC data from a radar system.
    
    This thread receives UDP packets from the radar, assembles them into
    complete frames, and provides an interface for other components to
    retrieve the processed frames.
    """
    
    def __init__(self, threadID: int, name: str, data_port: int = 4098, 
                config_port: int = 4096, bufferSize: int = 10) -> None:
        """
        Initialize the ADC capture thread.
        
        Args:
            threadID: ID of the thread, used to differentiate multiple radar instances
            name: Thread name for identification
            data_port: UDP port for receiving data packets
            config_port: UDP port for configuration
            bufferSize: Maximum number of frames to buffer
        """
        threading.Thread.__init__(self)
        self.whileSign = True
        self.threadID = threadID
        self.name = name
        self.recentCapNum = 0
        
        # Use thread-safe queue as buffer
        self.frame_queue = queue.Queue(maxsize=bufferSize)

        # Single Radar configuration
        if self.threadID == 1:
            static_ip = '192.168.33.30'  # IP that streaming.py listens on
            adc_ip = '192.168.33.180'    # IP of the ADC/radar

        # Create configuration and data destinations
        self.cfg_dest = (adc_ip, config_port)
        self.cfg_recv = (static_ip, config_port)
        self.data_recv = (static_ip, data_port)

        # Create sockets
        self.config_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

        # Configure data socket with large buffer
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 ** 27)
        self.data_socket.bind(self.data_recv)

        # Configure and bind config socket
        self.config_socket.bind(self.cfg_recv)

        # Log the actual buffer size
        actual_size = self.data_socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        print(f"[INFO] UDP recv buffer = {actual_size} bytes ({actual_size / 1024 / 1024:.1f} MB)")

        # Create zero frame for error conditions
        self.zero_frame = np.zeros(INT16_IN_FRAME, dtype=np.int16)

    def run(self) -> None:
        """
        Main thread execution method.
        
        Starts the frame receiver to continuously process incoming data.
        """
        print(f"[{self.name}] Starting data capture thread...")
        self._frame_receiver()

    def _frame_receiver(self) -> None:
        """
        Process incoming radar data packets and assemble complete frames.
        
        This method implements a state machine with two states:
        - SYNCING: Looking for the start of a new frame
        - ASSEMBLING: Building a frame from consecutive packets
        
        It handles packet loss detection and frame boundary identification.
        """
        print(f"[{self.name}] Starting frame receiver...")
        print(f"BYTES_IN_FRAME = {BYTES_IN_FRAME}")
        
        # State machine initialization
        state = "SYNCING"
        recent_frame = None
        recent_frame_collect_count = 0
        last_packet_num = -1
        frame_start_time = 0

        self.data_socket.settimeout(50000)

        while self.whileSign:
            # 1. Get data packet
            packet_num, byte_count, packet_data = self._read_data_packet()
            if packet_num is None:
                print("[Warning] Received empty or invalid packet. Ignoring...")
                continue

            # 2. Check if this packet crosses frame boundary
            is_boundary, after_packet_count = self._is_frame_boundary_packet(byte_count)

            # 3. Process packet based on current state
            if state == "SYNCING":
                if is_boundary:
                    # Found a boundary packet
                    valid_data, expected_len = self._extract_new_frame_data(packet_data, after_packet_count)
                    
                    if valid_data.shape[0] == expected_len:
                        # Valid data, switch to ASSEMBLING state
                        state = "ASSEMBLING"
                        print("[State] Found new frame. -> ASSEMBLING")
                        
                        recent_frame = np.zeros(INT16_IN_FRAME, dtype=np.int16)
                        frame_start_time = datetime.now().timestamp()
                        
                        # Copy new frame start data
                        recent_frame[0:expected_len] = valid_data
                        self.recentCapNum = (byte_count + BYTES_IN_PACKET) // BYTES_IN_FRAME
                        recent_frame_collect_count = after_packet_count
                        last_packet_num = packet_num
                    else:
                        print("Waiting for radar data startup (initial frame invalid)...")
                        continue
                else:
                    # Not a boundary packet, continue waiting
                    last_packet_num = packet_num
                    continue

            elif state == "ASSEMBLING":
                # Check packet continuity
                if packet_num != last_packet_num + 1:
                    # Packet loss detected! Discard frame, switch back to SYNCING
                    print(f"[State] Packet Lost! last={last_packet_num}, current={packet_num}. -> SYNCING")
                    self._store_frame(self.zero_frame, frame_start_time, True)
                    state = "SYNCING"
                    continue

                # Check if this packet will complete the current frame
                if self._will_complete_frame(recent_frame_collect_count):
                    success, valid_len, completion_data = self._extract_frame_completion_data(
                        packet_data, recent_frame_collect_count)
                    
                    if success:
                        # Complete the current frame
                        recent_frame[recent_frame_collect_count // 2:] = completion_data
                        self._store_frame(recent_frame, frame_start_time, False)
                        
                        # Check if this packet also contains start of new frame
                        if is_boundary:
                            valid_data, expected_len = self._extract_new_frame_data(packet_data, after_packet_count)
                            
                            if valid_data.shape[0] == expected_len:
                                # Start new frame
                                recent_frame = np.zeros(INT16_IN_FRAME, dtype=np.int16)
                                frame_start_time = datetime.now().timestamp()
                                recent_frame[0:expected_len] = valid_data
                                self.recentCapNum = (byte_count + BYTES_IN_PACKET) // BYTES_IN_FRAME
                                recent_frame_collect_count = after_packet_count
                                last_packet_num = packet_num
                            else:
                                print("New frame start data insufficient, switching to SYNCING")
                                state = "SYNCING"
                        else:
                            state = "SYNCING"
                    else:
                        print(f"[Error] Packet data length {packet_data.shape[0]} is less than expected {valid_len}.")
                        self._store_frame(self.zero_frame, frame_start_time, True)
                        state = "SYNCING"
                else:
                    # Process intermediate packet
                    start_index = recent_frame_collect_count // 2
                    data_len_to_copy = len(packet_data)
                    end_index = start_index + data_len_to_copy
                    
                    if end_index <= INT16_IN_FRAME:
                        recent_frame[start_index:end_index] = packet_data
                        recent_frame_collect_count += data_len_to_copy * 2
                        last_packet_num = packet_num
                    else:
                        # Data exceeds buffer, discard and resync
                        print(f"[Error] Frame data overflow. Discarding frame. -> SYNCING")
                        self._store_frame(self.zero_frame, frame_start_time, True)
                        state = "SYNCING"

            # Check if current frame is full
            if recent_frame_collect_count >= BYTES_IN_FRAME:
                # Frame is full, submit it
                print(f"[State] Frame {self.recentCapNum} complete. Storing... -> SYNCING")
                self._store_frame(recent_frame, frame_start_time, False)
                
                # After submission, switch back to SYNCING
                state = "SYNCING"

    def getFrame(self, block: bool = True, timeout: Optional[float] = None) -> Tuple[Optional[np.ndarray], 
                                                                                   Optional[float], 
                                                                                   Optional[int], 
                                                                                   Optional[bool]]:
        """
        Get a processed frame from the queue.
        
        Args:
            block: Whether to block waiting for a frame (True) or return immediately (False)
            timeout: Maximum time to wait if blocking, in seconds
            
        Returns:
            Tuple containing:
            - frame_data: Numpy array containing frame data, or None if no frame available
            - timestamp: Timestamp when the frame was captured, or None
            - frame_id: Frame sequence number, or None
            - lost_packet_flag: Boolean indicating if packet loss was detected, or None
            
        Raises:
            queue.Empty: If timeout occurs while waiting for frame
        """
        try:
            # Block until data available or timeout
            frame_tuple = self.frame_queue.get(block=block, timeout=timeout)
            self.frame_queue.task_done()  # Mark task as done
            return frame_tuple
        except queue.Empty:
            # Queue empty in non-blocking mode, or timeout in blocking mode
            return None, None, None, None

    def _store_frame(self, recentframe: np.ndarray, frame_time: float, is_lost: bool) -> None:
        """
        Store a processed frame in the queue.
        
        Args:
            recentframe: The frame data to store
            frame_time: Timestamp when the frame was captured
            is_lost: Flag indicating if packet loss was detected
        """
        frame_id = self.recentCapNum
        self.recentCapNum += 1  # Prepare for next frame
        item_to_store = (recentframe.copy(), frame_time, frame_id, is_lost)

        try:
            # Use non-blocking put_nowait to detect full queue immediately
            self.frame_queue.put_nowait(item_to_store)
        except queue.Full:
            # Buffer full, consumer too slow
            # Discard oldest frame to make room for new one
            print("[Warning] Frame queue is full. Discarding the oldest frame.")
            try:
                self.frame_queue.get_nowait()  # Discard old frame
                self.frame_queue.task_done()
            except queue.Empty:
                pass  # Just consumed, now empty
            try:
                self.frame_queue.put_nowait(item_to_store)  # Try again with new frame
            except queue.Full:
                print("[Error] Failed to enqueue new frame even after making space.")

    def _read_data_packet(self) -> Tuple[Optional[int], Optional[int], Optional[np.ndarray]]:
        """
        Read a single data packet from the UDP socket.
        
        Returns:
            Tuple containing:
            - packet_num: Packet sequence number
            - byte_count: Cumulative byte count
            - packet_data: Numpy array of uint16 data
            
            If the packet is invalid, returns (None, None, None)
        """
        data, addr = self.data_socket.recvfrom(MAX_PACKET_SIZE)
        if len(data) <= 10:
            return None, None, None
        packet_num = struct.unpack('<1l', data[:4])[0]
        byte_count = struct.unpack('>Q', b'\x00\x00' + data[4:10][::-1])[0]
        packet_data = np.frombuffer(data[10:], dtype=np.int16)
        return packet_num, byte_count, packet_data

    def _is_frame_boundary_packet(self, byte_count: int) -> Tuple[bool, int]:
        """
        Determine if the current packet crosses a frame boundary.
        
        A boundary packet contains the end of the current frame and 
        the beginning of the next frame.
        
        Args:
            byte_count: Cumulative byte count from packet header
            
        Returns:
            Tuple containing:
            - is_boundary: Boolean indicating if this is a boundary packet
            - after_packet_count: Byte position after processing this packet
        """
        after_packet_count = (byte_count + BYTES_IN_PACKET) % BYTES_IN_FRAME
        return after_packet_count < BYTES_IN_PACKET, after_packet_count

    def _extract_new_frame_data(self, packet_data: np.ndarray, after_packet_count: int) -> Tuple[np.ndarray, int]:
        """
        Extract the portion of data belonging to the new frame from a boundary packet.
        
        Args:
            packet_data: The packet data array
            after_packet_count: Byte position after processing this packet
            
        Returns:
            Tuple containing:
            - valid_data: Array slice containing only the new frame data
            - expected_len: Expected length of the new frame data
        """
        valid_data = packet_data[(BYTES_IN_PACKET - after_packet_count) // 2:]
        expected_len = after_packet_count // 2
        return valid_data, expected_len

    def _will_complete_frame(self, recent_frame_collect_count: int) -> bool:
        """
        Determine if the current packet will complete the frame being assembled.
        
        Args:
            recent_frame_collect_count: Current byte count in the frame being assembled
            
        Returns:
            Boolean indicating if this packet will complete the frame
        """
        return recent_frame_collect_count + BYTES_IN_PACKET >= BYTES_IN_FRAME

    def _extract_frame_completion_data(self, packet_data: np.ndarray, recent_frame_collect_count: int) -> Tuple[bool, int, Optional[np.ndarray]]:
        """
        Extract the data needed to complete the current frame.
        
        Args:
            packet_data: The packet data array
            recent_frame_collect_count: Current byte count in the frame being assembled
            
        Returns:
            Tuple containing:
            - success: Boolean indicating if extraction was successful
            - valid_len: Length of data needed to complete the frame
            - completion_data: Array slice with the data to complete the frame, or None if extraction failed
        """
        valid_len = (BYTES_IN_FRAME - recent_frame_collect_count) // 2
        if packet_data.shape[0] >= valid_len:
            return True, valid_len, packet_data[:valid_len]
        return False, valid_len, None
