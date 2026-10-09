#!/usr/bin/python3

import os
import threading
import numpy as np
# 环境里同时装了 PyQt5 和 PySide6 时,pyqtgraph 默认会选 PySide6,而下面用的是 PyQt5,
# 两套 Qt 混用会报 "QWidget: Must construct a QApplication before a QWidget"。强制统一到 PyQt5。
os.environ.setdefault('PYQTGRAPH_QT_LIB', 'PyQt5')
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
assert pg.Qt.QT_LIB == 'PyQt5', f"pyqtgraph picked {pg.Qt.QT_LIB}, expected PyQt5"

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
