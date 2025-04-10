#!/usr/bin/python3

import threading
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore

import time

class plotThread(threading.Thread):

    def __init__(self, threadID, name):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.init_completed = threading.Event()  # Event to signal initialization completion

    def update_image(self, data):
        self.view.setImage(data)

    class ImageUpdater(QtCore.QObject):
        new_image = QtCore.pyqtSignal(np.ndarray)

    def run(self):
        self.app = QtWidgets.QApplication([])

        self.view = pg.ImageView()
        self.view.setColorMap(pg.colormap.get('viridis'))

        self.view.ui.histogram.hide()
        self.view.ui.roiBtn.hide()
        self.view.ui.menuBtn.hide()

        self.view.setWindowTitle('mmWave Radar Heatmap')

        self.view.show()

        self.image_updater = self.ImageUpdater()
        self.image_updater.new_image.connect(self.update_image)

        self.init_completed.set()  # Signal that initialization is complete
        self.app.exec_()

    def plot(self, data):
        self.init_completed.wait()  # Wait for the initialization to complete
        self.image_updater.new_image.emit(data)

# if __name__ == '__main__':
#     a = plotThread(2, "plot")
#     a.start()
#     for i in range (1000):
#         image = np.random.rand(256, 256)
#         a.plot(image)
#         time.sleep(0.01)
