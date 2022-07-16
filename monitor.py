#!/bin/python3

import os
import sys
import struct
from time import sleep

import socket
import psutil
import pyamdgpuinfo

UDP_IP = "192.168.0.128"
UDP_PORT = 35432
REFRESH_SPEED = 2 # seconds

FS_PATH  = '/sys/kernel/ryzen_smu_drv/'
SMN_PATH = FS_PATH + 'smn'
VER_PATH = FS_PATH + 'version'
PM_PATH  = FS_PATH + 'pm_table'
PMT_PATH = FS_PATH + 'pm_table_version'
CN_PATH  = FS_PATH + 'codename'

PM_TABLE_FP = False


def is_root():
    return os.getenv("SUDO_USER") is not None or os.geteuid() == 0

def driver_loaded():
    return os.path.isfile(VER_PATH)

def pm_table_supported():
    return os.path.isfile(PM_PATH)

def read_pm_table():
    global PM_TABLE_FP

    if PM_TABLE_FP == False:
        PM_TABLE_FP = open(PM_PATH, "rb")

    PM_TABLE_FP.seek(0, os.SEEK_SET)
    content = PM_TABLE_FP.read()

    return content

def read_float(buffer, offset):
    return struct.unpack("@f", buffer[offset:(offset + 4)])[0]

def parse_pm_table():
    pm       = read_pm_table()

    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP

    first_gpu = pyamdgpuinfo.get_gpu(0)
    NetRecv = psutil.net_io_counters(pernic = True, nowrap = True)["enp37s0"].bytes_recv
    while True:
        CpuP = psutil.cpu_percent()
        MemT = psutil.virtual_memory().used / 1024 / 1024 / 1024
        Fan = psutil.sensors_fans()["nct6795"][1].current

        NetRecvCurr = psutil.net_io_counters(pernic = True, nowrap = True)["enp37s0"].bytes_recv
        NetRecv_kybtes_per_second = (NetRecvCurr - NetRecv) / REFRESH_SPEED
        NetRecv = NetRecvCurr

        SoCP = read_float(pm, 0xFC)
        CorP = read_float(pm, 0x10C)
        GpuT = read_float(pm, 151 * 4)
        GpuL = read_float(pm, 156 * 4)

        vram_usage = first_gpu.query_vram_usage() / 1024 / 1024
        gtt_usage = first_gpu.query_gtt_usage() / 1024 / 1024

        print("\033c", end='')
        print("Core + Soc:  {:4.1f} W".format(CorP + SoCP))
        print("Gpu:  {:4.0f}% {:4.0f} ˚C".format(GpuL, GpuT))

        f = [
                Fan, # fan speed
                CpuP, # cpu load
                GpuT, # cpu temp
                CorP, # core power
                SoCP, # soc power
                MemT, # mem used
                0, # gpu FPS
                vram_usage, # gpu vram ded
                gtt_usage, # gpu vram shared
                GpuL, # gpu load
                0, # nvme load
                NetRecv_kybtes_per_second # nic dl speed
            ]
        MESSAGE = struct.pack('<'+'f'*len(f), *f)
        sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))
        sleep(REFRESH_SPEED)

        pm = read_pm_table()

def main():
    if is_root() == False:
        print("Script must be run with root privileges.")
        return

    if driver_loaded() == False:
        print("The driver doesn't seem to be loaded.")
        return

    if pm_table_supported():
        parse_pm_table()
    else:
        print("PM Table: Unsupported")

main()
