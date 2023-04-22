# -*- coding: utf-8 -*-
import os
import re
import socket
import sys
import subprocess
import _thread
import time

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QMainWindow, QInputDialog, QMessageBox
import FrmMain
import Utils

version = "2.0.0"


def read_default_config():
    path = sys.path[0] + "/Source/SlimeVR-Tracker-ESP-main/"
    # platformio.ini
    txt = Utils.read_txt(path + "platformio.ini")

    com = re.search(r'upload_port =.*', txt).group()
    com = com[13:].strip()
    window.cbCOM.setCurrentText(com)

    wifi_name = re.search(r'-DWIFI_CREDS_SSID=.*', txt).group()
    wifi_name = wifi_name.split("\"")[1]
    window.txtSSID.setText(wifi_name)

    wifi_pwd = re.search(r'-DWIFI_CREDS_PASSWD=.*', txt).group()
    wifi_pwd = wifi_pwd.split("\"")[1]
    window.txtPWD.setText(wifi_pwd)

    # defines.h
    txt = Utils.read_txt(path + "src/defines.h")

    sensor = re.search(r'#define IMU .*', txt).group()
    sensor = sensor.split("IMU_")[1]
    window.cbModel.setCurrentText(sensor)

    rotation = re.search(r'#define IMU_ROTATION .*', txt).group()
    rotation = rotation.split("IMU_ROTATION ")[1]
    window.cbRotation.setCurrentText(rotation)

    start_index = txt.find("if BOARD == BOARD_NODEMCU")
    if start_index >= 0:
        io_str = txt[start_index:]
        sda = re.search(r'#define PIN_IMU_SDA .*', io_str).group()
        sda = sda.split(" ")[2]
        window.txtSDA.setText(sda)

        scl = re.search(r'#define PIN_IMU_SCL .*', io_str).group()
        scl = scl.split(" ")[2]
        window.txtSCL.setText(scl)

        int_1 = re.search(r'#define PIN_IMU_INT .*', io_str).group()
        int_1 = int_1.split(" ")[2]
        window.txtINT1.setText(int_1)

        int_2 = re.search(r'#define PIN_IMU_INT_2 .*', io_str).group()
        int_2 = int_2.split(" ")[2]
        window.txtINT2.setText(int_2)


def fix():
    python_path = sys.path[0] + "/.platformio/penv/Scripts/python"
    path = sys.path[0] + "/Source/SlimeVR-Tracker-ESP-main/"
    # 提取参数
    wifi_name = window.txtSSID.text()
    wifi_pwd = window.txtPWD.text()
    com = window.cbCOM.currentText()
    sensor = window.cbModel.currentText()
    rotation = window.cbRotation.currentText()
    io_sda = window.txtSDA.text()
    io_scl = window.txtSCL.text()
    io_int_1 = window.txtINT1.text()
    io_int_2 = window.txtINT2.text()

    if wifi_name == "" or len(wifi_pwd) < 8:
        QMessageBox.information(window, '提示', '请确认WIFI的名称、密码无误后再试吧！')
        return
    if len(io_sda) == 0 or len(io_scl) == 0 or len(io_int_1) == 0 or len(io_int_2) == 0:
        QMessageBox.information(window, '提示', '请填写接线定义后再试吧！', QMessageBox.Yes)
        return
    if com == "":
        QMessageBox.information(window, '提示', '未检测到设备，请检查硬件是否连接、驱动是否安装后再试！')
        return

    # 修改platformio.ini
    path_platform_io = path + "platformio.ini"
    txt = Utils.read_txt(path_platform_io)
    txt = re.sub(r'upload_port =.*', "upload_port = " + com, txt, 1)
    txt = re.sub(r'-DWIFI_CREDS_SSID=.*', "-DWIFI_CREDS_SSID=\'\"" + wifi_name + "\"\'", txt, 1)
    txt = re.sub(r'-DWIFI_CREDS_PASSWD=.*', "-DWIFI_CREDS_PASSWD=\'\"" + wifi_pwd + "\"\'", txt, 1)
    rep_list = ["upload_protocol = espota", "upload_flags =", " --auth=SlimeVR-OTA"]
    if com[:3] == "COM":
        # print("串口下载")
        for rep_str in rep_list:
            txt = re.sub(r"\x20*" + rep_str, "; " + rep_str, txt, 1)
        txt = re.sub(r";{2,}", ";", txt)
    else:
        # print("OTA下载")
        for rep_str in rep_list:
            txt = re.sub(r";*\x20*" + rep_str, rep_str, txt, 1)
    Utils.write_txt(path_platform_io, txt)

    # 修改defines.h
    path_defines = path + "src/defines.h"
    txt = Utils.read_txt(path_defines)
    txt = re.sub(r'#define IMU .*', "#define IMU IMU_" + sensor, txt, 1)
    txt = re.sub(r'#define IMU_ROTATION .*', "#define IMU_ROTATION " + rotation, txt, 1)
    io_index = txt.find("if BOARD == BOARD_NODEMCU")
    txt1 = txt[:io_index]
    txt2 = txt[io_index:]
    txt2 = re.sub(r'#define PIN_IMU_SDA .*', "#define PIN_IMU_SDA " + io_sda, txt2, 1)
    txt2 = re.sub(r'#define PIN_IMU_SCL .*', "#define PIN_IMU_SCL " + io_scl, txt2, 1)
    txt2 = re.sub(r'#define PIN_IMU_INT .*', "#define PIN_IMU_INT " + io_int_1, txt2, 1)
    txt2 = re.sub(r'#define PIN_IMU_INT_2 .*', "#define PIN_IMU_INT_2 " + io_int_2, txt2, 1)
    txt = txt1 + txt2
    Utils.write_txt(path_defines, txt)

    # 开始烧录
    cmd = "cmd /k " + python_path + " -m platformio run -t upload"
    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE, shell=False, cwd=path)


class MyFrmMain(QMainWindow, FrmMain.Ui_MainWindow):
    def __init__(self, parent=None):
        super(MyFrmMain, self).__init__(parent)
        self.setupUi(self)
        self.setWindowTitle("SlimeVR烧录工具 v" + version + " By:KAIFENG-ch")


def install_slime_drive():
    try:
        # 获取SteamVR路径
        steam_vr_path = Utils.get_steamvr_path()
        if steam_vr_path is None or not os.path.isdir(steam_vr_path):
            steam_vr_path = QInputDialog.getText(window, '提示', '请手动输入SteamVR路径：')
            if steam_vr_path[1] is False:
                return
            steam_vr_path = str(steam_vr_path[0])
            if not os.path.isdir(steam_vr_path):
                QMessageBox.information(window, '错误', '路径不存在，请检查后再试吧！')
                return
        steam_vr_path = str(steam_vr_path)

        message_box = QMessageBox()
        message_box.setWindowTitle("提示")
        message_box.setText("您想要安装哪个驱动呢？【显示修复】版本驱动如有异常请使用【原版驱动】")
        message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        message_box.button(QMessageBox.Yes).setText('显示修复')
        message_box.button(QMessageBox.No).setText('原版')
        message_box.button(QMessageBox.Cancel).setText('取消')
        message_box.exec()

        type_str = message_box.clickedButton().text()
        source_path = sys.path[0] + "/Source/SlimeVR-OpenVR-Driver/"
        if type_str == "原版":
            source_path += "original"
        elif type_str == "显示修复":
            source_path += "repair"
        else:
            return

        # 安装SlimeVR驱动
        target_path = steam_vr_path + "drivers/slimevr"
        Utils.copy_files(source_path, target_path)
        QMessageBox.information(window, '提示', 'SlimeVR驱动已安装成功，重启SteamVR后生效！')
    except Exception as e:
        QMessageBox.information(window, '错误', '安装失败，请重新尝试！')
        print(e)


def view_rotation():
    os.startfile(sys.path[0] + "/UI/rotation.png")


def start_slime_vr():
    path = sys.path[0]
    path = path.replace("\\", "/")
    path = path[:path.rfind("/")]
    try:
        subprocess.Popen("cmd /c start 3.启动SlimeVR.bat", cwd=path)
    except Exception as e:
        print(e)


def change_tips():
    if window.labTips.text()[0:4] != "Tips":
        return
    device_com = window.cbCOM.currentText()
    if len(device_com) == 0 or device_com.find("COM") >= 0:
        window.labTips.setText("Tips：烧录程序时，注意不要使用魔法喔~")
    else:
        window.labTips.setText("Tips：使用OTA无线升级时，需要重启设备并在60秒内进行烧录~")


# 自动刷新设备列表
remote_device_list = {}


def thread_find_serial():
    while True:
        new_list = Utils.get_serial_list()
        for device in remote_device_list:
            if time.time() - remote_device_list[device] < 2:  # 只显示2秒内有UDP数据的设备
                new_list.append(device)
        now_com = window.cbCOM.currentText()
        window.cbCOM.clear()
        window.cbCOM.addItems(new_list)
        window.cbCOM.setCurrentText(now_com)
        time.sleep(2)


def get_remote_device():
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(("", 6969))
        while True:
            try:
                ip = udp_socket.recvfrom(1024)[1][0]
                remote_device_list[ip] = time.time()
            except Exception as e:
                print("[UDP]接收信息时发生错误：")
                print(e)
    except Exception as e:
        window.labTips.setText("Warn：UDP端口被占用，OTA功能停止使用。如需使用无线升级，请不要多开以及关闭SlimeVR！")
        print("Warn：UDP端口被占用，OTA功能停止使用。如需使用无线升级，请不要多开以及关闭SlimeVR！")
        print(e)
    # udp_socket.close()


def bind_frm():
    window.btnInstallSlimeVR.clicked.connect(install_slime_drive)
    window.btnViewRotation.clicked.connect(view_rotation)
    window.btnFix.clicked.connect(fix)
    window.cbCOM.currentIndexChanged.connect(change_tips)
    window.btnStartSlimeVR.clicked.connect(start_slime_vr)

    # 启动无线设备查找线程
    _thread.start_new_thread(get_remote_device, ())
    # 启动扫描端口线程
    _thread.start_new_thread(thread_find_serial, ())

    change_tips()


# 提供杀自身线程的bat文件
def record_self_pid(flag: bool):
    txt = "@echo off"
    file_name = "kill.bat"
    if flag:
        txt += "\necho ========== 关闭烧录工具 =========="
        txt += "\ntaskkill /pid " + str(os.getpid())
        txt += "\necho \"@echo off\" > " + file_name
    Utils.write_txt(file_name, txt)


if __name__ == '__main__':
    record_self_pid(True)
    app = QtWidgets.QApplication(sys.argv)
    window = MyFrmMain()
    window.show()
    bind_frm()
    read_default_config()
    # 等待窗体退出
    exit_code = app.exec_()
    record_self_pid(False)
    sys.exit(exit_code)
