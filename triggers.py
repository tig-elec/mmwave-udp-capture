"""
Trigger source threads for hardware-trigger timestamp synchronization.

Provides two listener threads that push external trigger timestamps into a
queue, plus a factory that builds the right one based on config.py:
  - SerialMonitorThread: reads 'ON' lines from a serial port (e.g. STM32)
  - RosTriggerListener : subscribes to a ROS2 trigger topic

Both expose the same interface used by the capture main loop:
  - get_trigger_time() -> Optional[float]   # non-blocking pop from queue
  - stop()                                  # signal the thread to finish
"""

import time
import threading
import serial
import queue
from datetime import datetime
from typing import Optional, Any

from config import USE_HARDWARE_TRIGGER, TRIGGER_SOURCE, COM_PORT, ROS_TOPIC

# 有条件导入ROS相关模块
try:
    import rclpy
    from trigger.msg import Trigger
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False


class SerialMonitorThread(threading.Thread):
    """
    Thread for monitoring hardware trigger signals from a serial port.

    This thread continuously reads from a serial port, looking for
    trigger signals ('ON'/'OFF'), and stores timestamps in a queue
    when triggers are detected. It supports automatic reconnection
    if the serial connection is lost.
    """

    def __init__(self, port: str, baudrate: int = 115200, reconnect_interval: int = 5) -> None:
        """
        Initialize the serial monitor thread.

        Args:
            port: Serial port name (e.g., 'COM3')
            baudrate: Serial communication speed
            reconnect_interval: Seconds to wait between reconnection attempts
        """
        super().__init__()
        self.trigger_queue = queue.Queue()
        self.whileSign = True
        self.port = port
        self.baudrate = baudrate
        self.reconnect_interval = reconnect_interval
        self.ser = None
        self.is_serial_available = False

        # Try initial connection without blocking thread startup
        self._try_connect()

    def _try_connect(self) -> bool:
        """
        Try to connect to the serial port.

        Returns:
            Boolean indicating if connection was successful
        """
        if self.ser is not None and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=10)
            self.is_serial_available = True
            print(f"[Serial] Successfully connected to {self.port}")
            return True
        except serial.SerialException as e:
            self.is_serial_available = False
            print(f"[Serial] Could not open serial port {self.port}: {e}")
            print("[Serial] Running without hardware trigger. Will attempt reconnection.")
            self.ser = None
            return False

    def run(self) -> None:
        """
        Main thread execution method.

        Continuously monitors the serial port for trigger signals,
        with automatic reconnection attempts if connection is lost.
        """
        print(f"[Serial] Monitor thread started. Port: {self.port}")

        while self.whileSign:
            # Check serial connection
            if not self.is_serial_available:
                # Try to reconnect
                if self._try_connect():
                    print(f"[Serial] Connection restored to {self.port}")
                else:
                    # Connection failed, wait before retry
                    time.sleep(self.reconnect_interval)
                    continue

            # Serial available, read data
            try:
                data = self.ser.readline().decode('ascii', errors='ignore').strip()
                if data == "ON":
                    ts = datetime.now().timestamp()
                    self.trigger_queue.put(ts)
                    print("[Serial] Trigger timestamp captured:", ts)
            except serial.SerialException as e:
                print(f"[Serial] Connection lost: {e}")
                self.is_serial_available = False
                # Don't exit loop, next iteration will try to reconnect
            except Exception as e:
                print(f"[Serial] Unexpected error: {e}")
                # Other exceptions, pause briefly to avoid CPU overload
                time.sleep(0.1)

        # Thread ending, clean up resources
        print("[Serial] Monitor thread finishing...")
        self._cleanup()

    def get_trigger_time(self) -> Optional[float]:
        """
        Get a trigger timestamp from the queue without blocking.

        Returns:
            Timestamp (float) when trigger occurred, or None if queue is empty
        """
        try:
            return self.trigger_queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        """
        Signal the thread to stop and clean up resources.
        """
        self.whileSign = False
        self._cleanup()

    def _cleanup(self) -> None:
        """
        Clean up serial port resources.
        """
        if self.ser is not None and self.ser.is_open:
            try:
                self.ser.close()
                print("[Serial] Port closed")
            except Exception as e:
                print(f"[Serial] Error closing port: {e}")


class RosTriggerListener(threading.Thread):
    """
    ROS Thread for listening to trigger messages and storing timestamps.

    This thread listens to trigger messages on a ROS topic and stores
    the timestamps in a queue when messages are received. It can run
    concurrently with other threads and supports graceful shutdown.
    """

    def __init__(self, topic: str) -> None:
        """
        Initialize the ROS trigger listener thread.

        Args:
            topic: The ROS topic to subscribe to for trigger messages
        """
        super().__init__()
        self.trigger_queue = queue.Queue()
        self.whileSign = True
        self.topic = topic

    def run(self) -> None:
        """
        Main thread execution method.

        Listens to ROS trigger messages and stores timestamps in the queue.
        """
        print(f"[ROS] Trigger listener thread started. Topic: {self.topic}")

        # ROS 2 specific initialization
        rclpy.init()
        node = rclpy.create_node('trigger_listener')
        subscription = node.create_subscription(
            Trigger,
            self.topic,
            self.trigger_callback,
            10)

        # Spin the node to process callbacks
        rclpy.spin(node)

        # Cleanup on exit
        node.destroy_node()
        rclpy.shutdown()

    def trigger_callback(self, msg: Any) -> None:
        """
        Callback method for processing received trigger messages.

        Args:
            msg: The received trigger message (ROS Trigger type)
        """
        ts = msg.timestamp
        self.trigger_queue.put(ts)
        print("[ROS] Trigger timestamp captured:", ts)

    def get_trigger_time(self) -> Optional[float]:
        """
        Get a trigger timestamp from the queue without blocking.

        Returns:
            Timestamp (float) when trigger occurred, or None if queue is empty
        """
        try:
            return self.trigger_queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        """
        Signal the thread to stop.
        """
        self.whileSign = False
        print("[ROS] Trigger listener thread stopping...")


def create_trigger_thread() -> Optional[threading.Thread]:
    """
    Build a trigger listener thread according to config.py.

    Returns:
        - None if USE_HARDWARE_TRIGGER is False (capture will rely on the
          frame bin timestamp only).
        - A RosTriggerListener if TRIGGER_SOURCE == 'ros'.
        - A SerialMonitorThread otherwise.

    The returned thread is NOT started; the caller is responsible for start().
    """
    if not USE_HARDWARE_TRIGGER:
        print("[Main] Hardware trigger disabled. Using frame bin timestamp only.")
        return None

    if TRIGGER_SOURCE.lower() == "ros":
        if not ROS_AVAILABLE:
            raise ImportError("ROS dependencies not available. Cannot use 'ros' trigger source.")
        print(f"[Main] Hardware trigger enabled. Using ROS source. Topic: {ROS_TOPIC}")
        return RosTriggerListener(ROS_TOPIC)

    print(f"[Main] Hardware trigger enabled. Using serial source. Port: {COM_PORT}")
    return SerialMonitorThread(COM_PORT)
