from ft_function import FT260_STATUS, FT260_I2C_FLAG, FT260_I2C_STATUS
import ft
import time
import struct

import tkinter as tk
import tkinter.ttk as ttk
import tkinter.scrolledtext as tkst
from tkinter import font

FT260_Vid = 0x0403
FT260_Pid = 0x6030


class _ConfigFrame(tk.Frame):
    @property
    def clock(self):
        return self.entry_clock.get()

    @clock.setter
    def clock(self, new_value):
        self.entry_clock.delete(0, tk.END)
        self.entry_clock.insert(0, new_value)

    @property
    def slave_address(self):
        return self.entry_address.get()

    @slave_address.setter
    def slave_address(self, new_value):
        self.entry_address.delete(0, tk.END)
        self.entry_address.insert(0, new_value)

    def open(self):
        ft.open_ftlib()
        if self.i2c_handle is not None:
            raise Exception("Device already opened. Action to open it twice should be disabled")

        if not ft.find_device_in_paths(FT260_Vid, FT260_Pid):
            self.msg_error("No FT260 device found. Check USB connection")
            return True

        self.i2c_handle = ft.openFtAsI2c(FT260_Vid, FT260_Pid, int(self.clock))

        if self.i2c_handle is None:
            self.msg_error("Error opening I2C")
            return True

        self.button_open.config(state="disabled")
        self.entry_clock.config(state="disabled")
        self.button_close.config(state="normal")
        self.msg_info("FT260 opened correctly")
        return False

    def close(self):
        if self.i2c_handle is not None:
            ft.close_device(self.i2c_handle)
            self.i2c_handle = None
            self.button_open.config(state="normal")
            self.entry_clock.config(state="normal")
            self.button_close.config(state="disabled")
            self.msg_info("FT260 closed correctly")
        else:
            raise Exception("Device is not opened. Action to close it twice should be disabled.")

    def add_status_msg(self, lvl, msg):
        self.entry_scroll_message.configure(state="normal")
        t = time.strftime("%Y-%m-%d %H:%M:%S")
        self.entry_scroll_message.insert(tk.INSERT, "\n" + t + " " + lvl + ": " + msg)
        self.entry_scroll_message.configure(state="disabled")
        self.entry_scroll_message.see("end")

    def msg_info(self, msg):
        self.add_status_msg("INFO", msg)

    def msg_warning(self, msg):
        self.add_status_msg("WARNING", msg)

    def msg_error(self, msg):
        self.add_status_msg("ERROR", msg)

    def __del__(self):
        if self.i2c_handle is not None:
            ft.close_device(self.i2c_handle)

    def __init__(self, parent):
        self.parent = parent
        self.i2c_handle = None
        super().__init__(self.parent)
        self.config(pady=5)
        self.grid_columnconfigure(4, weight=1)
        label_clock = tk.Label(self, text="Clock rate [kbps]:")
        label_address = tk.Label(self, text="I2C slave device address [hex]:")
        self.entry_clock = tk.Entry(self, width=6)
        self.entry_address = tk.Entry(self, width=6)
        self.button_open = tk.Button(self, text="Open device", command=self.open)
        self.button_close = tk.Button(self, text="Close device", command=self.close, state="disabled")
        self.entry_scroll_message = tkst.ScrolledText(
            self, height="3", width="20", wrap=tk.WORD, font=font.nametofont("TkDefaultFont"))
        label_msb_warning = tk.Label(self, text="Multiple bytes are send and read as MSByte first, LSByte last.")

        label_clock.grid(row=0, column=0, padx=(3, 0))
        self.entry_clock.grid(row=0, column=1)
        label_address.grid(row=1, column=0, padx=(3, 0))
        self.entry_address.grid(row=1, column=1)
        self.button_open.grid(row=0, column=2, padx=(3, 0))
        self.button_close.grid(row=0, column=3)
        self.entry_scroll_message.grid(row=0, column=4, rowspan=3, sticky="nsew", padx=5)
        label_msb_warning.grid(row=2, column=0, padx=(3, 0), columnspan=4)


class _DeviceScannerFrame(tk.Frame):

    def scan_button(self):
        if self.conf.i2c_handle is None:
            return
        self.entry_addresses.delete(0, tk.END)
        for address in range(1, 127):
            (ft_status, data_real_read_len, readData, status) = ft.ftI2cRead(self.conf.i2c_handle,
                                                                             address,
                                                                             FT260_I2C_FLAG.FT260_I2C_START_AND_STOP,
                                                                             1)
            if not (status & FT260_I2C_STATUS.FT260_SLAVE_NACK):
                self.entry_addresses.insert(tk.END, hex(address) + " ")

    def __init__(self, parent, config):
        self.parent = parent
        self.conf = config
        super().__init__(self.parent)
        self.config(pady=5)
        self.grid_columnconfigure(2, weight=1)

        button_scan = tk.Button(self, text="Scan I2C bus", command=self.scan_button)
        label_scan_result = tk.Label(self, text="Found addresses:")
        self.entry_addresses = tk.Entry(self, width=30)

        button_scan.grid(row=0, column=0)
        label_scan_result.grid(row=0, column=1, padx=(3, 0))
        self.entry_addresses.grid(row=0, column=2, sticky="ew")


class _RegFrame(tk.Frame):

    def read_button(self):
        if self.conf.i2c_handle is None:
            return
        pack_str = ['>', 'B' if self.register_address_size == 1 else 'H']
        unpack_str = ['>', 'B']
        if self.register_size == 2:
            unpack_str[1] = 'H'
        elif self.register_size == 4:
            unpack_str[1] = 'I'
        # Interpret register address as hexadecimal value
        reg_addr = int(self.register_address, 16)
        # Interpret device address as hexadecimal value
        dev_addr = int(self.conf.slave_address, 16)
        ft.ftI2cWrite(self.conf.i2c_handle,
                      dev_addr,
                      FT260_I2C_FLAG.FT260_I2C_START,
                      struct.pack("".join(pack_str), reg_addr))
        # Register address is send. Can now retrieve register data
        (ft_status, data_real_read_len, readData, status) = ft.ftI2cRead(self.conf.i2c_handle,
                                                                         dev_addr,
                                                                         FT260_I2C_FLAG.FT260_I2C_START_AND_STOP,
                                                                         self.register_size)
        if data_real_read_len != len(readData):
            print("Read {} bytes from ft260 lib, but {} bytes are in buffer".format(data_real_read_len, len(readData)))

        if not ft_status == FT260_STATUS.FT260_OK.value:
            print("Read error : %s" % ft_status)

        if not len(readData) == 0:
            self.register_value = "%#x" % struct.unpack("".join(unpack_str), readData)

    def write_button(self):
        if self.conf.i2c_handle is None:
            return
        pack_str = ['>', 'B', 'B']
        if self.register_address_size == 2:
            pack_str[1] = 'H'
        if self.register_size == 2:
            pack_str[2] = 'H'
        elif self.register_size == 4:
            pack_str[2] = 'I'
        # Interpret register address as hexadecimal value
        reg_addr = int(self.register_address, 16)
        # Interpret device address as hexadecimal value
        dev_addr = int(self.conf.slave_address, 16)
        # Interpret value to write as hexadecimal value
        try:
            reg_value = int(self.register_value, 16)
        # Single hex value may not be valid for any reason. Just drop execution then.
        except ValueError:
            return
        ft.ftI2cWrite(self.conf.i2c_handle, dev_addr, FT260_I2C_FLAG.FT260_I2C_START_AND_STOP,
                      struct.pack("".join(pack_str), reg_addr, reg_value))

    @property
    def register_address(self):
        return self.entry_address.get()

    @register_address.setter
    def register_address(self, new_value):
        self.entry_address.delete(0, tk.END)
        self.entry_address.insert(0, new_value)

    @property
    def register_value(self):
        return self.entry_value.get()

    @register_value.setter
    def register_value(self, new_value):
        self.entry_value.delete(0, tk.END)
        self.entry_value.insert(0, new_value)

    @property
    def register_address_size(self):
        size = self.combo_reg_bits.get()
        if size == "8 bits":
            return 1
        elif size == "16 bits":
            return 2
        else:
            raise Exception("Unknown option {} in register_address_size combobox.".format(bytes))

    @property
    def register_size(self):
        size = self.combo_value_bits.get()
        if size == "8 bits":
            return 1
        elif size == "16 bits":
            return 2
        elif size == "32 bits":
            return 4
        else:
            raise Exception("Unknown option {} in register_size combobox.".format(bytes))

    def __init__(self, parent, config):
        self.parent = parent
        self.conf = config
        super().__init__(self.parent)
        self.config(pady=5)
        label_reg_bits = tk.Label(self, text="Register address size:")
        self.combo_reg_bits = ttk.Combobox(self, values=["8 bits", "16 bits"], width=6)
        self.combo_reg_bits.current(0)
        label_address = tk.Label(self, text="Register address:")
        self.entry_address = tk.Entry(self, width=6)
        label_value_bits = tk.Label(self, text="Register value size:")
        self.combo_value_bits = ttk.Combobox(self, values=["8 bits", "16 bits", "32 bits"], width=6)
        self.combo_value_bits.current(0)
        label_value = tk.Label(self, text="Register value:")
        self.entry_value = tk.Entry(self, width=10)
        button_write = tk.Button(self, text="Write", command=self.write_button)
        button_read = tk.Button(self, text="Read", command=self.read_button)

        label_reg_bits.grid(row=0, column=0, padx=(3, 0))
        self.combo_reg_bits.grid(row=0, column=1)
        label_address.grid(row=0, column=2, padx=(3, 0))
        self.entry_address.grid(row=0, column=3)
        label_value_bits.grid(row=0, column=4, padx=(3, 0))
        self.combo_value_bits.grid(row=0, column=5)
        label_value.grid(row=0, column=6, padx=(3, 0))
        self.entry_value.grid(row=0, column=7)
        button_write.grid(row=0, column=8)
        button_read.grid(row=0, column=9)


class _DataFrame(tk.Frame):

    @property
    def data_size(self):
        return self.entry_data_size.get()

    @data_size.setter
    def data_size(self, new_value):
        self.entry_data_size.delete(0, tk.END)
        self.entry_data_size.insert(0, new_value)

    @property
    def data(self):
        return self.entry_data.get()

    @data.setter
    def data(self, new_value):
        self.entry_data.delete(0, tk.END)
        self.entry_data.insert(0, new_value)

    @property
    def data_word(self):
        size = self.combo_word_size.get()
        if size == "8 bits":
            return 1
        elif size == "16 bits":
            return 2
        elif size == "32 bits":
            return 4
        else:
            raise Exception("Unknown option {} in data_word combobox.".format(bytes))

    def write_button(self):
        if self.conf.i2c_handle is None:
            return
        data_to_write = self.data.split(' ')
        words = []
        pack_str = '>'
        for hex_word in data_to_write:
            if hex_word != "":
                words.append(int(hex_word, 16))
                pack_str += self.word_symbol[self.data_word]

        (ft_status, data_real_write_len, writeData, status) = ft.ftI2cWrite(self.conf.i2c_handle,
                                                                            int(self.conf.slave_address, 16),
                                                                            FT260_I2C_FLAG.FT260_I2C_START_AND_STOP,
                                                                            struct.pack("".join(pack_str), *words)
                                                                            )

        unpack_str = ">" + self.word_symbol[self.data_word] * int(len(writeData) / self.data_word)
        update_str = ""
        for index, value in enumerate(struct.unpack(unpack_str, writeData)):
            if index >= data_real_write_len:
                break
            update_str = update_str + hex(value) + " "

        self.data = update_str

    def read_button(self):
        if self.conf.i2c_handle is None:
            return
        (ft_status, data_real_read_len, readData, status) = ft.ftI2cRead(self.conf.i2c_handle,
                                                                         int(self.conf.slave_address, 16),
                                                                         FT260_I2C_FLAG.FT260_I2C_START_AND_STOP,
                                                                         int(self.data_size) * self.data_word)

        # Error checking
        if data_real_read_len != len(readData):
            print("Read {} bytes from ft260 lib, but {} bytes are in buffer".format(data_real_read_len,
                                                                                    len(readData)))
        if not ft_status == FT260_STATUS.FT260_OK.value:
            print("Read error : %s" % ft_status)

        unpack_str = ">" + self.word_symbol[self.data_word] * int(len(readData) / self.data_word)
        update_str = ""
        for i in struct.unpack(unpack_str, readData):
            update_str = update_str + hex(i) + " "
        self.data = update_str

    def __init__(self, parent, config):
        self.parent = parent
        self.conf = config
        super().__init__(self.parent)
        self.config(pady=5)
        self.grid_columnconfigure(5, weight=1)

        label_data_size = tk.Label(self, text="Data length:")
        self.entry_data_size = tk.Entry(self, width=6)
        label_word_size = tk.Label(self, text="Data word size:")
        self.combo_word_size = ttk.Combobox(self, values=["8 bits", "16 bits", "32 bits"], width=6)
        self.combo_word_size.current(0)
        label_data = tk.Label(self, text="Data [hex]:")
        self.entry_data = tk.Entry(self, width=30)
        button_write = tk.Button(self, text="Write", command=self.write_button)
        button_read = tk.Button(self, text="Read", command=self.read_button)

        label_data_size.grid(row=0, column=0, padx=(3, 0))
        self.entry_data_size.grid(row=0, column=1)
        label_word_size.grid(row=0, column=2, padx=(3, 0))
        self.combo_word_size.grid(row=0, column=3)
        label_data.grid(row=0, column=4, padx=(3, 0))
        self.entry_data.grid(row=0, column=5, sticky="we")
        button_write.grid(row=0, column=6)
        button_read.grid(row=0, column=7)

        self.word_symbol = {1: "B", 2: "H", 4: "I"}


class _PSDistCtrlFrame(tk.Frame):

    def read_reg(self, dev_addr, reg_addr):
        if self.conf.i2c_handle is None:
            return
        ft.ftI2cWrite(self.conf.i2c_handle,
                      dev_addr,
                      FT260_I2C_FLAG.FT260_I2C_START,
                      int.to_bytes(reg_addr, 1, 'big'))
        # Register address is send. Can now retrieve register data
        (ft_status, data_real_read_len, readData, status) = ft.ftI2cRead(self.conf.i2c_handle,
                                                                         dev_addr,
                                                                         FT260_I2C_FLAG.FT260_I2C_START_AND_STOP,
                                                                         1)
        error = False
        if data_real_read_len != len(readData):
            self.msg_error(
                "Read {} bytes from ft260 lib, but {} bytes are in buffer".format(
                    data_real_read_len, len(readData)))
            error = True
        if not ft_status == FT260_STATUS.FT260_OK.value:
            self.msg_error("FTLib status: {}, FT260 status: 0x{:X}".format(ft_status, status))
            error = True

        if not len(readData) == 0:
            reg_val = int.from_bytes(readData, 'big')
        else:
            reg_val = None
        return reg_val, error

    def write_reg(self, dev_addr, reg_addr, reg_val):
        if self.conf.i2c_handle is None:
            return
        (ft_status, data_real_write_len, writeData, status) = ft.ftI2cWrite(
            self.conf.i2c_handle, dev_addr, FT260_I2C_FLAG.FT260_I2C_START_AND_STOP,
            bytes(bytearray((reg_addr, reg_val))))
        error = True
        if data_real_write_len != len(writeData):
            self.msg_error(
                "Wrote {} bytes from ft260 lib, but {} bytes are in buffer. ft_status {}, status 0x{:X}".format(
                    data_real_write_len, len(writeData), ft_status, status))
        elif not ft_status == FT260_STATUS.FT260_OK.value:
            self.msg_error("Write error : %s" % ft_status)
        else:
            error = False
        return error

    def write_verify_reg(self, dev_addr, reg_addr, reg_val):
        error = self.write_reg(dev_addr, reg_addr, reg_val)
        if error:
            self.msg_error("Error writing register 0x{:X} on device 0x{:X}".format(reg_addr, dev_addr))
            return True
        (reg_val_read, error) = self.read_reg(dev_addr, reg_addr)
        if error:
            self.msg_error("Error reading register 0x{:X} on device 0x{:X}".format(reg_addr, dev_addr))
            return True
        else:
            if reg_val_read != reg_val:
                self.msg_error("Error verifying register 0x{:X} on device 0x{:X}. Wrote 0x{:X}. got 0x{:X}".format(
                    reg_addr, dev_addr, reg_val, reg_val_read))
                return True
        return False

    def init(self):
        # init_map = ((0x20, 0x2, 0xff), (0x20, 0x6, 0xc0),
        #             (0x20, 0x3, 0xff), (0x20, 0x7, 0xc0),
        #             (0x21, 0x2, 0xff), (0x21, 0x6, 0xc0))
        init_map = ((0x20, 0x6, 0xc0), (0x20, 0x7, 0xc0), (0x21, 0x6, 0xc0))
        for i in range(len(init_map)):
            dev = init_map[i][0]
            reg = init_map[i][1]
            val = init_map[i][2]
            error = self. write_verify_reg(dev, reg, val)
            if error:
                self.msg_error("Error during init")
                self.init_status.configure(background="red", text="Failed")
                return True
        self.msg_info("Initialization successful")
        self.init_status.configure(background="green", text="Success")
        # self.ru_all_on_off(False)
        self.read_status()
        return False

    def update_status(self, ps, ru, val, error):
        if error:
            color = "red"
            text = "Error"
        elif (val >> ru) & 1:
            color = "green"
            text = "On"
        else:
            color = "yellow"
            text = "Off"
        self.status_ru[ps][ru+1].configure(background=color, text=text)

    def ru_on_off(self, on, ps, ru):
        if ru == 0:
            ru_str = "ALL RUs"
        else:
            ru_str = "RU{}".format(ru)
        self.msg_info("Setting PS{} switch of {} to {}".format(ps, ru_str, "ON" if on else "OFF"))
        map_dev_ps = (0x20, 0x20, 0x21)
        map_reg_ps = (0x02, 0x03, 0x02)
        dev = map_dev_ps[ps]
        reg = map_reg_ps[ps]
        (val, error) = self.read_reg(dev, reg)
        if error:
            self.msg_error("Error while reading output register. PS{}".format(ps))
            return error
        if ru == 0:
            list_ru = range(self.ru_n)
        else:
            list_ru = range(ru-1, ru)
        for i in list_ru:
            if on:
                val &= ~(0x1 << i)
            else:
                val |= 0x1 << i
        error = self.write_verify_reg(dev, reg, val)
        warning = False
        if error:
            self.msg_error("Error during RU on/off command. PS{} {} - ON = {}".format(ps, ru_str, on))
        if ps == 2:
            (latch_val, error) = self.read_reg(dev, 0x1)
            if error:
                self.msg_error("Error reading latched value")
                return error
            if (latch_val & 0x3F) != (~val & 0x3F):
                self.msg_warning("ALDO input power supply is on, cannot change switch settings")
                self.msg_warning("First switch off the input power supply, then change switch settings")
                warning = True
                error = self.write_verify_reg(dev, reg, val & 0xC0 | (~latch_val & 0x3F))
                if error:
                    self.msg_error("Error writing back latched value")
        else:
            latch_val = ~val
        for i in list_ru:
            self.update_status(ps, i, latch_val, error)
        if not warning:
            self.msg_info("PS{} switch of {} correctly set to {}".format(ps, ru_str, "ON" if on else "OFF"))
        return error

    def ru_all_on_off(self, on):
        for ps in range(3):
            self.ru_on_off(on, ps, 0)

    def btn(self, on, ps, ru):
        if on:
            btn_text = "ON"
            col = 0
        else:
            btn_text = "OFF"
            col = 1
        btn = tk.Button(self, text=btn_text, command=lambda: self.ru_on_off(on, ps, ru))
        btn.grid(row=5+ru, column=1+col+self.main_col*ps, sticky="nsew")

    def read_status(self):
        map_dev_ps = (0x20, 0x20, 0x21)
        map_reg_ps = (0x02, 0x03, 0x01)
        for ps in range(len(map_dev_ps)):
            dev = map_dev_ps[ps]
            reg = map_reg_ps[ps]
            (val, error) = self.read_reg(dev, reg)
            if ps != 2:
                val = ~val
            print(ps, val)
            if error:
                self.msg_error("Error while reading register. PS{}".format(ps))
                return error
            for ru in range(6):
                self.update_status(ps, ru, val, error)
        self.msg_info("Status read successful")
        return False

    def add_status_msg(self, lvl, msg):
        self.status_msg_text.configure(state="normal")
        t = time.strftime("%Y-%m-%d %H:%M:%S")
        self.status_msg_text.insert(tk.INSERT, "\n" + t + " " + lvl + ": " + msg, lvl)
        self.status_msg_text.configure(state="disabled")
        self.status_msg_text.see("end")

    def msg_info(self, msg):
        self.add_status_msg("INFO", msg)

    def msg_warning(self, msg):
        self.add_status_msg("WARNING", msg)

    def msg_error(self, msg):
        self.add_status_msg("ERROR", msg)

    def __init__(self, parent, config):
        self.parent = parent
        self.conf = config
        super().__init__(self.parent)
        self.config(pady=5)
        col_width = (1, 1, 1, 1)
        self.main_col = len(col_width)
        for i in range(3):
            for j in range(len(col_width)):
                self.grid_columnconfigure(4*i+j, weight=col_width[j])

        self.button_init = tk.Button(self, text="Init board", command=self.init)
        label_init_status = tk.Label(self, text="Init status")
        self.init_status = tk.Label(self, text="Not init", background="red")

        self.button_read = tk.Button(self, text="Read status", command=self.read_status)

        self.status_msg_text = tkst.ScrolledText(
            self, height="5", width="20", wrap=tk.WORD, font=font.nametofont("TkDefaultFont"))

        label_b_pol = tk.Label(self, text="bPOL12V PS control (PS0)")
        label_tec = tk.Label(self, text="TEC PS control (PS1)")
        label_aldo = tk.Label(self, text="ALDO PS control (PS2)")

        self.label_ru = []
        self.status_ru = []
        row_str = ["ALL RU"]
        self.ru_n = 6
        for i in range(self.ru_n):
            row_str.append("RU{:1d}".format(i+1))
        for j in range(3):
            self.label_ru.append([])
            self.status_ru.append([])
            for i in range(self.ru_n+1):
                self.label_ru[j].append(tk.Label(self, text=row_str[i]))
                self.label_ru[j][-1].grid(row=5+i, column=0+j*self.main_col, sticky="nsew")
                self.btn(True, j, i)
                self.btn(False, j, i)
                if i == 0:
                    str_status = "Status"
                    bg = parent.cget("background")
                else:
                    str_status = "Unknown"
                    bg = 'orange'
                self.status_ru[j].append(tk.Label(self, text=str_status, background=bg))
                self.status_ru[j][-1].grid(row=5+i, column=3+self.main_col*j, sticky="nsew")

        self.button_init.grid(row=0, column=0, columnspan=self.main_col, sticky="nsew")
        label_init_status.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.init_status.grid(row=1, column=2, columnspan=2, sticky="nsew")

        self.button_read.grid(row=2, column=0, columnspan=self.main_col, sticky="nsew")

        label_all = tk.Label(self, text="ALL PS&RU")
        label_all.grid(row=3, column=0, sticky="nsew")
        button_all_on = tk.Button(self, text="ON", command=lambda: self.ru_all_on_off(True))
        button_all_on.grid(row=3, column=1, sticky="nsew")
        button_all_off = tk.Button(self, text="OFF", command=lambda: self.ru_all_on_off(False))
        button_all_off.grid(row=3, column=2, sticky="nsew")

        label_b_pol.grid(row=4, column=0, columnspan=self.main_col, padx=(3, 0), sticky="nsew")
        label_tec.grid(row=4, column=self.main_col, columnspan=self.main_col, padx=(3, 0), sticky="nsew")
        label_aldo.grid(row=4, column=2*self.main_col, columnspan=self.main_col, padx=(3, 0), sticky="nsew")

        self.status_msg_text.grid(
            row=0, column=self.main_col, columnspan=2*self.main_col, rowspan=4, sticky="nsew", padx=5)

        self.status_msg_text.tag_config("INFO", foreground="black")
        self.status_msg_text.tag_config("WARNING", foreground="purple")
        self.status_msg_text.tag_config("ERROR", foreground="red")


class _CommLog(tk.Frame):
    """
    Communication log for USB-I2C messages
    """

    def __init__(self, parent, config):
        """
        Constructor
        """
        self.parent = parent
        self.conf = config
        super().__init__(self.parent)

        # Inside frame grid config
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Set the treeview
        self.tree = ttk.Treeview(self, columns=('Timestamp', 'Direction', 'Address', 'Message', 'Mode', 'Status'))
        self.tree.heading('#0', text='#')
        self.tree.heading('#1', text='Timestamp')
        self.tree.heading('#2', text='Direction')
        self.tree.heading('#3', text='Address')
        self.tree.heading('#4', text='Message')
        self.tree.heading('#5', text='Mode')
        self.tree.heading('#6', text='Status')
        self.tree.column('#0', minwidth=46, width=46, stretch=tk.NO)
        self.tree.column('#1', minwidth=130, width=130, stretch=tk.NO)
        self.tree.column('#2', minwidth=70, width=70, stretch=tk.NO)
        self.tree.column('#3', minwidth=70, width=70, stretch=tk.NO)
        self.tree.column('#4', minwidth=130, width=130, stretch=tk.YES)
        self.tree.column('#5', minwidth=90, width=90, stretch=tk.NO)
        self.tree.column('#6', minwidth=50, width=50, stretch=tk.NO)

        # Scrollbar
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.vsb.set)

        # Layout
        self.tree.grid(row=0, column=0, sticky='nsew')
        self.vsb.grid(row=0, column=1, sticky='ns')

        # Initialize the counter
        self.message_number = 0

    def add_new_log_entry(self, item_list):
        """
        Callback to add data to log window.
        :param item_list: list with several items in the order of the tree columns
        :return: None
        """
        v = list()
        v.append(time.strftime("%Y-%m-%d %H:%M:%S"))
        v.extend(item_list)
        item = self.tree.insert('', 'end', text=str(self.message_number), values=v)
        self.message_number += 1
        self.tree.see(item)


def main():

    parent = tk.Tk()
    parent.title("CMS BTL Power Supply Distribution Control")
    config = _ConfigFrame(parent)
    config.clock = "400"
    config.slave_address = "0x7f"
    config.pack(fill="x", expand=False)
    separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
    separator.pack(fill="x")
    scanner = _DeviceScannerFrame(parent, config)
    scanner.pack(fill="x")
    separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
    separator.pack(fill="x")
    reg = _RegFrame(parent, config)
    reg.pack(fill="x")
    reg.register_address = "0x00"
    separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
    separator.pack(fill="x")
    ctrl = _PSDistCtrlFrame(parent, config)
    ctrl.pack(fill="x")
    comm_log = _CommLog(parent, config)
    comm_log.pack(fill="both", expand=True)
    ft._callback = comm_log.add_new_log_entry
    error = config.open()
    if not error:
        ctrl.init()
    parent.mainloop()


if __name__ == "__main__":
    main()
