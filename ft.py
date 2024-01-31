from ft_function import *
import struct
import platform

_callback = None
_ftlib = None


def open_ftlib():
    global _ftlib
    if _ftlib is None:
        if platform.uname()[0] == "Windows":
            _ftlib = FTlib("lib/LibFT260.dll")
        else:
            _ftlib = []


def close_device(i2c_handle):
    if _ftlib is not None:
        _ftlib.ftClose(i2c_handle)


def find_device_in_paths(vid, pid):
    if _ftlib is None:
        return None
    # Preparing paths list
    dev_num = c_ulong(0)
    path_buf = c_wchar_p('/0'*128)
    s_open_device_name = u"vid_{0:04x}&pid_{1:04x}".format(vid, pid)
    print("Searching for {} in paths".format(s_open_device_name))
    ret = False
    _ftlib.ftCreateDeviceList(byref(dev_num))

    # For each path check that search string is within and list them
    valid_devices = list()
    for i in range(dev_num.value):
        _ftlib.ftGetDevicePath(path_buf, 128, i)
        if path_buf.value.find(s_open_device_name) > 0:
            ret = True
            valid_devices.append(path_buf.value)
        print("Index:%d\r\nPath:%s\r\n\r\n" % (i, path_buf.value))

    # For each valid device try to use the composite device (with &mi_00)
    s_open_device_name += "&mi_00"
    for i in range(len(valid_devices)):
        if valid_devices[i].find(s_open_device_name) > 0:
            print("Composite FT260 device found on path {}\r\n".format(valid_devices[i]))
        else:
            print("Not composite FT260 device found on path {}\r\n".format(valid_devices[i]))
    return ret


def openFtAsI2c(Vid, Pid, cfgRate):
    """
    Tries to open FY260 device by its VID and PID. Also initialize it with I2C speed defined by rate.
    Returns device handle.
    :param Vid: Vendor ID of the USB chip. For FT260 it is 0x0403
    :param Pid: Product ID of the USB chip. For FT260_it is 0x6030
    :param cfgRate: speed of connection in kbots. 100 and 400 are mostly used in I2C devices, though higher values are
    also possible.
    :return: handle for opened device. Handle must be stored for future use.
    """
    if _ftlib is None:
        return None
    handle = c_void_p()

    # mode 0 is I2C, mode 1 is UART
    # Opening first device of possibly many available is used by providing indev 0 as third parameter.
    ftStatus = _ftlib.ftOpenByVidPid(Vid, Pid, 0, byref(handle))
    if not ftStatus == FT260_STATUS.FT260_OK.value:
        print("Open device Failed, status: %s\r\n" % FT260_STATUS(ftStatus))
        return None
    else:
        print("Open device OK")

    ftStatus = _ftlib.ftI2CMaster_Init(handle, cfgRate)
    if not ftStatus == FT260_STATUS.FT260_OK.value:
        _ftlib.ftClose(handle)
        ftStatus = _ftlib.ftOpenByVidPid(Vid, Pid, 1, byref(handle))
        if not ftStatus == FT260_STATUS.FT260_OK.value:
            print("ReOpen device Failed, status: %s\r\n" % FT260_STATUS(ftStatus))
            return None
        else:
            print("ReOpen device OK")
        ftStatus = _ftlib.ftI2CMaster_Init(handle, cfgRate)
        if not ftStatus == FT260_STATUS.FT260_OK.value:
            print("I2c Init Failed, status: %s\r\n" % FT260_STATUS(ftStatus))
            return None

    print("I2c Init OK")

    return handle

def I2C_Mode_Name(flag :FT260_I2C_FLAG):
    Dict = {FT260_I2C_FLAG.FT260_I2C_NONE: 'None',
            FT260_I2C_FLAG.FT260_I2C_REPEATED_START: 'Repeated start',
            FT260_I2C_FLAG.FT260_I2C_START_AND_STOP: 'Start&stop',
            FT260_I2C_FLAG.FT260_I2C_START: 'Start',
            FT260_I2C_FLAG.FT260_I2C_STOP: 'Stop'
            }
    return Dict[flag]

def ftI2cConfig(handle, cfgRate):
    """
    Sets I2C speed (rate). Standard values are 100 and 400 kbods. Higher values are also possible.
    :param handle: Device handle from previous openFtAsI2c calls.
    :param cfgRate: Rate in kbods. Example: 100
    :return: None
    """
    if _ftlib is None:
        return None
    _ftlib.ftI2CMaster_Reset(handle)
    ftStatus = _ftlib.ftI2CMaster_Init(handle, cfgRate)
    if not ftStatus == FT260_STATUS.FT260_OK.value:
        print("I2c Init Failed, status: %s\r\n" % FT260_STATUS(ftStatus))
        return 0
    else:
        print("I2c Init OK")


def ftI2cWrite(handle, i2cDev, flag, data):
    global _callback

    if _ftlib is None:
        return None
    # Write data
    dwRealAccessData = c_ulong(0)
    status = c_uint8(0)  # To store status after operation
    buffer = create_string_buffer(data)
    buffer_void = cast(buffer, c_void_p)
    ftStatus = _ftlib.ftI2CMaster_Write(handle, i2cDev, flag, buffer_void, len(data), byref(dwRealAccessData))
    _ftlib.ftI2CMaster_GetStatus(handle, byref(status))
    if not ftStatus == FT260_STATUS.FT260_OK.value:
        print("I2c Write NG : %s\r\n" % FT260_STATUS(ftStatus))
    else:
        # Logging block. If enabled and there is data
        if _callback is not None and dwRealAccessData.value > 0:
            unpackstr = "<" + "B" * dwRealAccessData.value
            writetuple = struct.unpack(unpackstr, buffer.raw[:dwRealAccessData.value])
            msg =""
            for i in writetuple:
                msg += hex(i) + " "

            _callback(['Write', hex(i2cDev), msg, I2C_Mode_Name(flag), status.value])


    # We have to cut return buffer at this point because last byte is \0 closing the string
    return ftStatus, dwRealAccessData.value, buffer.raw[:-1], status.value


def ftI2cRead(handle, i2cDev, flag, readLen):
    """
    Read data
    :param handle:
    :param i2cDev:
    :param flag:
    :param readLen:
    :return:
    """
    global _callback

    if _ftlib is None:
        return None
    dwRealAccessData = c_ulong(0) # Create variable to store received bytes
    status = c_uint8(0) # To store status after operation
    buffer = create_string_buffer(readLen + 1) # Create string to hold received data with additional terminating byte
    buffer_void = cast(buffer, c_void_p) # Convert the same buffer to void pointer

    ftStatus = _ftlib.ftI2CMaster_Read(handle, i2cDev, flag, buffer_void, readLen, byref(dwRealAccessData))
    _ftlib.ftI2CMaster_GetStatus(handle, byref(status))

    # Logging block. If enabled, data is valid and there is data
    if _callback is not None and ftStatus == FT260_STATUS.FT260_OK.value and dwRealAccessData.value > 0:
        unpackstr = "<" + "B" * dwRealAccessData.value
        readtuple = struct.unpack(unpackstr, buffer.raw[:dwRealAccessData.value])
        msg = ""
        for i in readtuple:
            msg += hex(i) + " "

        _callback(['Read', hex(i2cDev), msg, I2C_Mode_Name(flag), status.value])

    # We have to cut return buffer at this point because last byte is \0 closing the string
    return ftStatus, dwRealAccessData.value, buffer.raw[:-1], status.value


def openFtAsUart(Vid, Pid):
    if _ftlib is None:
        return None

    ftStatus = c_int(0)
    handle = c_void_p()

    # mode 0 is I2C, mode 1 is UART
    ftStatus = _ftlib.ftOpenByVidPid(Vid, Pid, 1, byref(handle))
    if not ftStatus == FT260_STATUS.FT260_OK.value:
        print("Open device Failed, status: %s\r\n" % FT260_STATUS(ftStatus))
        return 0
    else:
        print("Open device OK")

    ftStatus = _ftlib.ftUART_Init(handle)
    if not ftStatus == FT260_STATUS.FT260_OK.value:
        print("Uart Init Failed, status: %s\r\n" % FT260_STATUS(ftStatus))
        return 0
    else:
        print("Uart Init OK")

    # config TX_ACTIVE for UART 485
    ftStatus = _ftlib.ftSelectGpioAFunction(handle, FT260_GPIOA_Pin.FT260_GPIOA_TX_ACTIVE)
    if not ftStatus == FT260_STATUS.FT260_OK.value:
        print("Uart TX_ACTIVE Failed, status: %s\r\n" % FT260_STATUS(ftStatus))
        return 0
    else:
        print("Uart TX_ACTIVE OK")

    # config UART
    _ftlib.ftUART_SetFlowControl(handle, FT260_UART_Mode.FT260_UART_XON_XOFF_MODE)
    ulBaudrate = c_ulong(9600)
    _ftlib.ftUART_SetBaudRate(handle, ulBaudrate)
    _ftlib.ftUART_SetDataCharacteristics(handle, FT260_Data_Bit.FT260_DATA_BIT_8, FT260_Stop_Bit.FT260_STOP_BITS_1, FT260_Parity.FT260_PARITY_NONE)
    _ftlib.ftUART_SetBreakOff(handle)

    uartConfig = UartConfig()
    ftStatus = _ftlib.ftUART_GetConfig(handle, byref(uartConfig))
    if not ftStatus == FT260_STATUS.FT260_OK.value:
        print("UART Get config NG : %s\r\n" % FT260_STATUS(ftStatus))
    else:
        print("config baud:%ld, ctrl:%d, data_bit:%d, stop_bit:%d, parity:%d, breaking:%d\r\n" % (
            uartConfig.baud_rate, uartConfig.flow_ctrl, uartConfig.data_bit, uartConfig.stop_bit, uartConfig.parity, uartConfig.breaking))
    return handle


def ftUartWrite(handle):
    if _ftlib is None:
        return None
    # Write data
    while True:
        str = input("> ")
        dwRealAccessData = c_ulong(0)
        bufferData = c_char_p(bytes(str,'utf-8'))
        buffer = cast(bufferData, c_void_p)
        ftStatus = _ftlib.ftUART_Write(handle, buffer, len(str), len(str), byref(dwRealAccessData))
        if not ftStatus == FT260_STATUS.FT260_OK.value:
            print("UART Write NG : %s\r\n" % FT260_STATUS(ftStatus))
        else:
            print("Write bytes : %d\r\n" % dwRealAccessData.value)



def ftUartReadLoop(handle):
    if _ftlib is None:
        return None

    while True:
        # Read data
        dwRealAccessData = c_ulong(0)
        dwAvailableData = c_ulong(0)
        buffer2Data = c_char_p(b'\0'*200)
        memset(buffer2Data, 0, 200)
        buffer2 = cast(buffer2Data, c_void_p)
        _ftlib.ftUART_GetQueueStatus(handle, byref(dwAvailableData))
        if dwAvailableData.value == 0:
            continue
        print("dwAvailableData : %d\r\n" % dwAvailableData.value)

        ftStatus = _ftlib.ftUART_Read(handle, buffer2, 50, dwAvailableData, byref(dwRealAccessData))
        if not ftStatus == FT260_STATUS.FT260_OK.value:
            print("UART Read NG : %s\r\n" % FT260_STATUS(ftStatus))
        else:
            buffer2Data = cast(buffer2, c_char_p)
            print("Read bytes : %d\r\n" % dwRealAccessData.value)
            if dwAvailableData.value > 0:
                print("buffer : %s\r\n" % buffer2Data.value.decode("utf-8"))
