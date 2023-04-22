# -*- coding: utf-8 -*-
import os
import string
import shutil
import serial
import serial.tools.list_ports


def read_txt(path: str) -> str:
    file = open(path)
    txt = file.read()
    file.close()
    return txt


def write_txt(path: str, txt: str):
    file = open(path, 'w')
    file.write(txt)
    file.close()


def get_steamvr_path():
    sub_path = "/common/SteamVR"
    parent_path = ["SteamLibrary", "Program Files/SteamLibrary", "Program Files (x86)/SteamLibrary",
                   "Steam/steamapps", "Program Files/Steam/steamapps", "Program Files (x86)/Steam/steamapps"]
    for a in string.ascii_uppercase:
        disk = a + ':/'
        if os.path.isdir(disk):
            for b in parent_path:
                path = disk + b + sub_path
                if os.path.isdir(path):
                    return path + "/"
    return None


def get_serial_list() -> list:
    new_list = []
    port_list = serial.tools.list_ports.comports()
    for com in port_list:
        name = com.name
        # 排除电脑主板自带串口
        if name == "COM1" or name == "COM2":
            continue
        new_list.append(name)
    return new_list


def copy_files(source_path, target_path):
    if not os.path.exists(target_path):
        # 如果目标路径不存在原文件夹的话就创建
        os.makedirs(target_path)

    if os.path.exists(target_path):
        # 如果目标路径存在原文件夹的话就先删除
        shutil.rmtree(target_path)

    shutil.copytree(source_path, target_path)
