# 📡 mmwave-udp-capture

**mmwave-udp-capture** is a lightweight tool designed to acquire data from mmWave radar over Ethernet and decode it into heatmaps with the help of CUDA acceleration. This enables real-time radar data processing.

The core idea is to replace **NumPy** with **CuPy**, which significantly reduces the time required for processing operations such as FFT down to just a few milliseconds.

---

## ⚙️ Requirements

- **CUDA Toolkit** (compatible with your GPU, maybe cuDNN as well)
- **CuPy** (version must match your CUDA version)

---

## 🚀 How to Use

### 🧪 Step-by-Step (with mmWave Studio)

This project assumes you're using **mmWave Studio** to configure and start the radar. The general workflow is:

1. **Load the Lua script** in mmWave Studio.
2. Ensure the radar is on and actively transmitting data.
3. (On **Windows**) Open Task Manager and **terminate** the process named something like `DCA1000EVM_CLI_Record.exe` (exact name TBD).  
   > ⚠️ This process occpuys lots of network bandwidth so you should find it easily. If it's not killed, the mmWave Studio will stop the radar after a few minutes of inactivity because the udp capture script is robbing the data that mmWave Studio is supposed to receive.
4. Run `capture_single.py`.

---

### 🐧 Running on Ubuntu

If you wish to capture radar data on Ubuntu:

1. Start the radar using **mmWave Studio on Windows**.
2. Reboot into Ubuntu (dual-boot setup), **or** unplug the **entire Ethernet adapter** (not just the cable) and plug it into your Ubuntu machine.  
   > 💡 A **USB Ethernet adapter** is highly recommended to simplify this step.

---

## 📦 Notes

- Tested only with **AWR1843** for now.
- More radar models will be supported in the future.
- You must **update the Lua script** and **adjust the config** in the scripts to match your radar settings.

---

## 📌 Project Background

This project was originally built for the [**CubeDN**](#) project.  
As a result, there may be hardcoded parameters or loosely structured parts in the codebase.

---

## 🎁 Variants

I've also created some extended versions of this project that work with:

- **Realsense Depth Cameras**
- **Arzue Kinect**
- Combined capture of:
  - mmWave radar data
  - RGB camera images
  - Skeleton tracking data

These versions allow synchronous multi-modal data collection and are ideal for sensing research or robotics applications. Will upload them soon.

---

## 🙏 Acknowledgements

Thanks to the amazing open-source radar projects that inspired or supported this work, including but not limited to:

- [mmMesh](#)
- [Pyradar](#)



