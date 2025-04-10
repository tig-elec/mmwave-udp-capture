import socket
import struct
import threading
import numpy as np
from datetime import datetime

from config import ADC_PARAMS



# STATIC
MAX_PACKET_SIZE = 4096
BYTES_IN_PACKET = 1456

# DYNAMIC
BYTES_IN_FRAME = (ADC_PARAMS['chirps'] * ADC_PARAMS['rx'] * ADC_PARAMS['tx'] *
                  ADC_PARAMS['IQ'] * ADC_PARAMS['samples'] * ADC_PARAMS['bytes'])

BYTES_IN_FRAME_CLIPPED = (BYTES_IN_FRAME // BYTES_IN_PACKET) * BYTES_IN_PACKET
PACKETS_IN_FRAME = BYTES_IN_FRAME / BYTES_IN_PACKET
PACKETS_IN_FRAME_CLIPPED = BYTES_IN_FRAME // BYTES_IN_PACKET
UINT16_IN_PACKET = BYTES_IN_PACKET // 2
UINT16_IN_FRAME = BYTES_IN_FRAME // 2


class adcCapThread (threading.Thread):
    def __init__(self, threadID, name, data_port=4098, config_port=4096, bufferSize = 3000):
        threading.Thread.__init__(self)
        self.whileSign = True
        self.threadID = threadID
        self.name = name
        self.recentCapNum = 0
        self.latestReadNum = 0
        self.nextReadBufferPosition = 0
        self.nextCapBufferPosition = 0
        self.bufferOverWritten = True
        self.bufferSize = bufferSize #超长时间采集的时候 buffersize可以调的大一点

        # Single Radar
        if (self.threadID == 1):
            static_ip = '192.168.33.30'
            adc_ip = '192.168.33.180'


        # Create configuration and data destinations
        self.cfg_dest = (adc_ip, config_port)
        self.cfg_recv = (static_ip, config_port)
        self.data_recv = (static_ip, data_port)

        # Create sockets
        self.config_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

        # Bind data socket to fpga
        self.data_socket.bind(self.data_recv)
        self.data_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,2**27)

        # Bind config socket to fpga
        self.config_socket.bind(self.cfg_recv)

        self.bufferArray = np.zeros((self.bufferSize,BYTES_IN_FRAME//2), dtype = np.int16)
        self.itemNumArray = np.zeros(self.bufferSize, dtype = np.int32)
        self.lostPackeFlagtArray = np.zeros(self.bufferSize,  dtype = bool)
        self.bufferArray_timestamp = np.zeros((self.bufferSize), dtype = float)



    def run(self):
        self._frame_receiver()
    
    def _frame_receiver(self):
        # first capture -- find the beginning of a Frame
        self.data_socket.settimeout(10)
        lost_packets = False

        recentframe = np.zeros(UINT16_IN_FRAME, dtype=np.int16)

        # 此循环要找到第一帧，要等之前一个frame里很多个chip传完，然后才会找到第一帧，于是break
        while self.whileSign:
            # 不断接收udp数据
            packet_num, byte_count, packet_data = self._read_data_packet()

            after_packet_count = (byte_count+BYTES_IN_PACKET)% BYTES_IN_FRAME

            # print(after_packet_count)
            # print(BYTES_IN_PACKET) #1456

            # 现在找到了新的一帧, 应该只找到第一帧的开始
            # the recent Frame begin at the middle of this packet
            if after_packet_count < BYTES_IN_PACKET :

                # print("新的一帧时间: " + str(datetime.now().timestamp()))  # 只有start是对的！！
                framestart_time = datetime.now().timestamp()

                recentframe[0:after_packet_count//2] = packet_data[(BYTES_IN_PACKET-after_packet_count)//2:]

                self.recentCapNum = (byte_count+BYTES_IN_PACKET)//BYTES_IN_FRAME
                recentframe_collect_count = after_packet_count
                last_packet_num = packet_num
                break

            last_packet_num = packet_num

        # 主循环
        while self.whileSign:
            # 不断接收udp
            packet_num, byte_count, packet_data = self._read_data_packet()

            # 如果发生了丢包,这一帧就废了,也就是丢帧了
            # TODO 这里有问题，丢了以后就不能再要这一帧了
            # 现在貌似解决了，但需要测试
            # fix up the lost packets
            if last_packet_num < packet_num-1:                
                lost_packets = True
                print('\a')
                print("Packet Lost! Please discard this data.")
                # print("but now continue")
                # exit(0)

                # 重新找到新的一帧
                # 此循环要找到第一帧，要等之前一个frame里很多个chip传完，然后才会找到第一帧，于是break
                while True:
                    # 不断接收udp数据
                    packet_num, byte_count, packet_data = self._read_data_packet()
                    after_packet_count = (byte_count + BYTES_IN_PACKET) % BYTES_IN_FRAME

                    # 现在找到了新的一帧
                    # the recent Frame begin at the middle of this packet
                    if after_packet_count < BYTES_IN_PACKET:
                        # print("新的一帧时间: " + str(datetime.now().timestamp()))  # 只有start是对的！！
                        recentframe[0:after_packet_count // 2] = packet_data[(BYTES_IN_PACKET - after_packet_count) // 2:]
                        self.recentCapNum = (byte_count + BYTES_IN_PACKET) // BYTES_IN_FRAME
                        recentframe_collect_count = after_packet_count
                        print("Re-acquired a new frame")
                        break



            # begin to process the recent packet
            # 接收很多packet之后，才能组成一个完整的frame
            # 这一帧所有的packet已经全部接收完成 # if the frame finished when this packet collected
            if recentframe_collect_count + BYTES_IN_PACKET >= BYTES_IN_FRAME:

                frameend_time = datetime.now().timestamp()
                recentframe[recentframe_collect_count//2:]=packet_data[:(BYTES_IN_FRAME-recentframe_collect_count)//2]

                # print("loop time is " + str(frameend_time))

                #把这一帧保存好
                self._store_frame(recentframe, frameend_time)



                # 然后新的一帧开始接收, 接着处理新的packet，没有接收完成的时候会转到下面的else
                # 注意，这里的framestart_time 也许并不是真实雷达新的一帧启动的时间,
                # 在上面一帧的数据传完以后,转到这里,但是此时雷达还没到下一帧的触发时间,因此可能被self._read_data_packet()给卡住,因此现在
                # 直接记录每一帧收集结束之后的 frameend_time
                # framestart_time = datetime.now().timestamp()

                self.lostPackeFlagtArray[self.nextCapBufferPosition] = False
                self.recentCapNum = (byte_count + BYTES_IN_PACKET)//BYTES_IN_FRAME

                recentframe = np.zeros(UINT16_IN_FRAME, dtype=np.int16)

                after_packet_count = (recentframe_collect_count + BYTES_IN_PACKET)%BYTES_IN_FRAME
                recentframe[0:after_packet_count//2] = packet_data[(BYTES_IN_PACKET-after_packet_count)//2:]
                recentframe_collect_count = after_packet_count
                lost_packets = False

            else:
                # 之前找到新的一帧break之后，就会到这里继续
                # 不断接收这一帧的每一个packet_data
                after_packet_count = (recentframe_collect_count + BYTES_IN_PACKET)%BYTES_IN_FRAME
                recentframe[recentframe_collect_count//2:after_packet_count//2]=packet_data
                recentframe_collect_count = after_packet_count

            last_packet_num = packet_num
    
    def getFrame(self):
        if self.latestReadNum != 0:
            if self.bufferOverWritten == True:
                return "bufferOverWritten","timestamp N/A", -1,False
        else: 
            self.bufferOverWritten = False


        # 这里作用跟指针一样，每次getframe被调用之后，都检查缓冲区，优先返回最早的部分，即使主函数慢了点，也会慢慢跟上最新的数据
        # 还要仔细看看
        nextReadPosition = (self.nextReadBufferPosition+1)%self.bufferSize


        # 新的frame还没有接收完全部的packet，就被主函数频繁触发
        if self.nextReadBufferPosition == self.nextCapBufferPosition:
            return "wait new frame", "timestamp N/A", -2, False

        # frame 封装完成，返回 frame 和 启动时间戳
        else:
            readframe = self.bufferArray[self.nextReadBufferPosition]

            timestamp = self.bufferArray_timestamp[self.nextReadBufferPosition]

            self.latestReadNum = self.itemNumArray[self.nextReadBufferPosition]

            lostPacketFlag = self.lostPackeFlagtArray[self.nextReadBufferPosition]

            self.nextReadBufferPosition = nextReadPosition

        return readframe, timestamp, self.latestReadNum, lostPacketFlag
    
    def _store_frame(self,recentframe, frame_time):

        self.bufferArray[self.nextCapBufferPosition] = recentframe
        self.bufferArray_timestamp[self.nextCapBufferPosition] = frame_time

        self.itemNumArray[self.nextCapBufferPosition] = self.recentCapNum
        if((self.nextReadBufferPosition-1+self.bufferSize)%self.bufferSize == self.nextCapBufferPosition):
            self.bufferOverWritten = True

        self.nextCapBufferPosition += 1

        # 这里是覆盖掉之前的
        self.nextCapBufferPosition %= self.bufferSize

        # print(self.nextCapBufferPosition )

    def _read_data_packet(self):
        """
        Returns:
            int: Current packet number, byte count of data that has already been read, raw ADC data in current packet
        """

        # 会在这里卡住等待数据接收, 等到接收完之后才会执行下一步
        data, addr = self.data_socket.recvfrom(MAX_PACKET_SIZE)

        packet_num = struct.unpack('<1l', data[:4])[0]

        byte_count = struct.unpack('>Q', b'\x00\x00' + data[4:10][::-1])[0]

        packet_data = np.frombuffer(data[10:], dtype=np.uint16)

        return packet_num, byte_count, packet_data

