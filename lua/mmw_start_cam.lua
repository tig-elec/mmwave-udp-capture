
COM_PORT = 10

-- Reset Button

ar1.FullReset()
RSTD.Sleep(2000)

ar1.SOPControl(2)
RSTD.Sleep(1000)


-- Connect

ar1.Connect(COM_PORT,921600,1000)
RSTD.Sleep(2000)

ar1.Calling_IsConnected()

ar1.frequencyBandSelection("77G")
RSTD.Sleep(1000)

ar1.SelectChipVersion("XWR1843")
RSTD.Sleep(1000)

-- Load BSS
ar1.DownloadBSSFw("C:\\ti\\mmwave_studio_02_01_01_00\\rf_eval_firmware\\radarss\\xwr18xx_radarss.bin")
RSTD.Sleep(2000)

ar1.GetBSSFwVersion()

ar1.GetBSSPatchFwVersion()

-- Load MSS
ar1.DownloadMSSFw("C:\\ti\\mmwave_studio_02_01_01_00\\rf_eval_firmware\\masterss\\xwr18xx_masterss.bin")
RSTD.Sleep(2000)

ar1.GetMSSFwVersion()


-- SPI Connect
ar1.PowerOn(0, 1000, 0, 0)
RSTD.Sleep(1000)

-- RF Power On
ar1.SelectChipVersion("XWR1843")

ar1.RfEnable()

ar1.GetMSSFwVersion()

ar1.GetBSSFwVersion()

ar1.GetBSSPatchFwVersion()

RSTD.Sleep(1000)




-- tx0 tx2 rx0-3

ar1.ChanNAdcConfig(1, 0, 1, 1, 1, 1, 1, 2, 1, 0)
RSTD.Sleep(1000)

ar1.LPModConfig(0, 0)
RSTD.Sleep(1000)


-- RF init 
ar1.RfInit()
RSTD.Sleep(1000)


-- Data config

ar1.DataPathConfig(513, 1216644097, 0)
RSTD.Sleep(1000)

ar1.LvdsClkConfig(1, 1)
RSTD.Sleep(1000)

ar1.LVDSLaneConfig(0, 1, 1, 0, 0, 1, 0, 0)
RSTD.Sleep(1000)


-- Sensor config
ar1.ProfileConfig(0, 77, 20, 6, 60, 0, 0, 0, 0, 0, 0, 60, 0, 256, 6000, 0, 0, 30)

RSTD.Sleep(1000)


ar1.ChirpConfig(0, 0, 0, 0, 0, 0, 0, 1, 0, 0)
RSTD.Sleep(1000)

ar1.ChirpConfig(1, 1, 0, 0, 0, 0, 0, 0, 0, 1)
RSTD.Sleep(1000)

ar1.DisableTestSource(0)

ar1.FrameConfig(0, 1, 0, 255, 100, 0, 0, 1)
RSTD.Sleep(1000)


-- setup dca1000


ar1.GetCaptureCardDllVersion()

ar1.SelectCaptureDevice("DCA1000")
RSTD.Sleep(1000)

ar1.CaptureCardConfig_EthInit("192.168.33.30", "192.168.33.180", "12:34:56:78:90:12", 4096, 4098)
RSTD.Sleep(1000)

ar1.CaptureCardConfig_Mode(1, 2, 1, 2, 3, 30)
RSTD.Sleep(1000)

ar1.CaptureCardConfig_PacketDelay(50)
RSTD.Sleep(1000)

ar1.GetCaptureCardFPGAVersion()






ar1.CaptureCardConfig_StartRecord("C:\\Users\\tiger\\Desktop\\bin_data_dca1000\\adc_data.bin", 1)

RSTD.Sleep(1000)


print("start the frame")

ar1.StartFrame()
