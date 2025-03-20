import sys
import json
import os
import serial
import serial.tools.list_ports
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QRadioButton, QButtonGroup, \
    QTextEdit, QLineEdit, QFileDialog, QGridLayout, QMessageBox
from PySide6.QtCore import QTimer, QDateTime
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QSoundEffect  # 使用 QSoundEffect播放音效
from datetime import datetime

class SerialPortHelper(QWidget):
    def __init__(self):
        super().__init__()
        self.serial_port = serial.Serial()
        self.initUI()
        self.apply_stylesheet()  # 调用样式表方法
        self.sound_effect = QSoundEffect()  # 初始化音效对象
        self.load_command_history() # 加载指令历史记录

    def initUI(self):
        layout = QVBoxLayout()

        # 定时器用于监控设备连接状态
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.check_connection_status)
        # 定时器用于定期读取串口数据
        self.status_timer.timeout.connect(self.read_serial_data)
        self.status_timer.start(100)  # 每秒检测一次设备状态

        # 串口选择
        self.port_label = QLabel("串口:")
        self.port_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_layout.addWidget(self.port_combo)

        self.update_ports()

        # 波特率选择
        self.baudrate_label = QLabel("波特率:")
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "14400", "19200", "38400", "57600", "115200","1000000"])
        self.baudrate_combo.setEditable(True)
        self.baudrate_combo.setCurrentIndex(6) # 默认波特率为 1000000

        # 校验位选择
        self.parity_label = QLabel("校验位:")
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd"])

        # 停止位选择
        self.stopbits_label = QLabel("停止位:")
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(["1", "1.5", "2"])

        # 连接按钮及状态
        self.connect_button = QPushButton("连接")
        self.connect_button.setStyleSheet("background-color: red")  # 初始状态为未连接，红色
        self.connect_button.clicked.connect(self.toggle_connection)

        # 接收区
        self.receive_label = QLabel("接收 (UTF-8):")
        self.receive_layout = QHBoxLayout()
        self.receive_clear_button = QPushButton("清空接收区")
        self.receive_clear_button.clicked.connect(lambda: self.receive_text.clear())
        self.receive_layout.addWidget(self.receive_label)
        self.receive_layout.addWidget(self.receive_clear_button)
        self.receive_text = QTextEdit()
        # self.receive_text.setReadOnly(True) # 设置为只读

        # 协议选择区
        self.protocol_label = QLabel("协议选择:")
        self.protocol_layout = QHBoxLayout()
        self.protocol1 = QRadioButton("TIRO_8bit")
        self.protocol2 = QRadioButton("TIRO_16bit")
        self.protocol2.setChecked(True)
        self.protocol_layout.addWidget(self.protocol1)
        self.protocol_layout.addWidget(self.protocol2)

        self.protocol_flag = 1  # 协议选择标志位, 0: 8bit, 1: 16bit
        self.protocol1.clicked.connect(lambda: self.protocol_select(0))
        self.protocol2.clicked.connect(lambda: self.protocol_select(1))



        # 发送区
        self.send_label = QLabel("语音播放(输入十进制):")
        self.send_layout = QHBoxLayout()

        self.send_text = QLineEdit()  # 用户输入发送内容
        self.send_text.setPlaceholderText("请输入要播放语音的十进制数值")
        # 发送按钮
        self.send_button = QPushButton("发送")
        self.send_add_button = QPushButton("+1")
        self.send_minus_button = QPushButton("-1")
        self.send_button.clicked.connect(self.send_hex_data)
        self.send_add_button.clicked.connect(self.send_hex_add)
        self.send_minus_button.clicked.connect(self.send_hex_minus)

        self.send_layout.addWidget(self.send_text)
        self.send_layout.addWidget(self.send_add_button)
        self.send_layout.addWidget(self.send_minus_button)
        self.send_layout.addWidget(self.send_button)

        # 音量发送区
        self.volume_label = QLabel("音量调节(0-15):")
        self.volume_layout = QHBoxLayout()
        self.volume_text = QLineEdit()
        self.volume_text.setPlaceholderText("请输入音量值(0-15)代表发送FFE0-FFEF")
        self.volume_add_button = QPushButton("+1")
        self.volume_add_button.clicked.connect(self.send_volume_add)
        self.volume_minus_button = QPushButton("-1")
        self.volume_minus_button.clicked.connect(self.send_volume_minus)
        self.volume_button = QPushButton("发送")
        self.volume_button.clicked.connect(self.send_volume_data)
        self.volume_layout.addWidget(self.volume_text)
        self.volume_layout.addWidget(self.volume_add_button)
        self.volume_layout.addWidget(self.volume_minus_button)
        self.volume_layout.addWidget(self.volume_button)

        # hex指令发送区
        self.hex_label = QLabel("发送hex指令:")
        self.hex_layout = QHBoxLayout()
        self.hex_text = QLineEdit()
        self.hex_text.setPlaceholderText("请输入要发送的hex指令")
        self.hex_button = QPushButton("发送")
        self.hex_button.clicked.connect(self.send_hex_value)
        self.hex_layout.addWidget(self.hex_text)
        self.hex_layout.addWidget(self.hex_button)

        # 连码播放区域
        self.play_save_layout = QHBoxLayout()
        self.play_label = QLabel("连码播放(需从头开始，中间不可留空，后面可以留空):")
        self.play_save_button = QPushButton("保存")
        self.play_save_button.clicked.connect(self.play_command_save)
        self.play_save_select_combo = QComboBox()
        self.play_save_select_combo.addItem("选择连码")
        self.play_save_select_combo.currentIndexChanged.connect(self.play_command_update)
        self.play_save_layout.addWidget(self.play_label)
        self.play_save_layout.addWidget(self.play_save_button)
        self.play_save_layout.addWidget(self.play_save_select_combo)

        ## 网格布局
        self.play_layout = QGridLayout() # 创建一个网格布局
        self.play_text1 = QLineEdit()  # 用户输入发送内容
        self.play_text2 = QLineEdit()  # 用户输入发送内容
        self.play_text3 = QLineEdit()  # 用户输入发送内容
        self.play_text4 = QLineEdit()
        self.play_text5 = QLineEdit()
        self.play_text6 = QLineEdit()
        self.play_text7 = QLineEdit()
        self.play_text8 = QLineEdit()
        self.play_text9 = QLineEdit()
        self.play_text10 = QLineEdit()
        self.play_text11 = QLineEdit()
        self.play_text12 = QLineEdit()
        self.play_text13 = QLineEdit()
        self.play_text14 = QLineEdit()
        self.play_text15 = QLineEdit()
        self.play_text16 = QLineEdit()
        self.play_text17 = QLineEdit()
        self.play_text18 = QLineEdit()
        self.play_text19 = QLineEdit()
        self.play_text20 = QLineEdit()
        self.play_text21 = QLineEdit()
        self.play_text22 = QLineEdit()
        self.play_text23 = QLineEdit()
        self.play_text24 = QLineEdit()
        self.play_text25 = QLineEdit()
        self.play_text26 = QLineEdit()
        self.play_text27 = QLineEdit()
        self.play_text28 = QLineEdit()
        self.play_text29 = QLineEdit()
        self.play_text30 = QLineEdit()
        self.play_text31 = QLineEdit()
        self.play_text32 = QLineEdit()
        self.play_text33 = QLineEdit()
        self.play_text34 = QLineEdit()
        self.play_text35 = QLineEdit()
        self.play_text36 = QLineEdit()
        self.play_text37 = QLineEdit()
        self.play_text38 = QLineEdit()
        self.play_text39 = QLineEdit()
        self.play_text40 = QLineEdit()
        self.play_layout.addWidget(self.play_text1, 0, 0)
        self.play_layout.addWidget(self.play_text2, 0, 1)
        self.play_layout.addWidget(self.play_text3, 0, 2)
        self.play_layout.addWidget(self.play_text4, 0, 3)
        self.play_layout.addWidget(self.play_text5, 0, 4)
        self.play_layout.addWidget(self.play_text6, 0, 5)
        self.play_layout.addWidget(self.play_text7, 0, 6)
        self.play_layout.addWidget(self.play_text8, 0, 7)
        self.play_layout.addWidget(self.play_text9, 0, 8)
        self.play_layout.addWidget(self.play_text10, 0, 9)
        self.play_layout.addWidget(self.play_text11, 1, 0)
        self.play_layout.addWidget(self.play_text12, 1, 1)
        self.play_layout.addWidget(self.play_text13, 1, 2)
        self.play_layout.addWidget(self.play_text14, 1, 3)
        self.play_layout.addWidget(self.play_text15, 1, 4)
        self.play_layout.addWidget(self.play_text16, 1, 5)
        self.play_layout.addWidget(self.play_text17, 1, 6)
        self.play_layout.addWidget(self.play_text18, 1, 7)
        self.play_layout.addWidget(self.play_text19, 1, 8)
        self.play_layout.addWidget(self.play_text20, 1, 9)
        self.play_layout.addWidget(self.play_text21, 2, 0)
        self.play_layout.addWidget(self.play_text22, 2, 1)
        self.play_layout.addWidget(self.play_text23, 2, 2)
        self.play_layout.addWidget(self.play_text24, 2, 3)
        self.play_layout.addWidget(self.play_text25, 2, 4)
        self.play_layout.addWidget(self.play_text26, 2, 5)
        self.play_layout.addWidget(self.play_text27, 2, 6)
        self.play_layout.addWidget(self.play_text28, 2, 7)
        self.play_layout.addWidget(self.play_text29, 2, 8)
        self.play_layout.addWidget(self.play_text30, 2, 9)
        self.play_layout.addWidget(self.play_text31, 3, 0)
        self.play_layout.addWidget(self.play_text32, 3, 1)
        self.play_layout.addWidget(self.play_text33, 3, 2)
        self.play_layout.addWidget(self.play_text34, 3, 3)
        self.play_layout.addWidget(self.play_text35, 3, 4)
        self.play_layout.addWidget(self.play_text36, 3, 5)
        self.play_layout.addWidget(self.play_text37, 3, 6)
        self.play_layout.addWidget(self.play_text38, 3, 7)
        self.play_layout.addWidget(self.play_text39, 3, 8)
        self.play_layout.addWidget(self.play_text40, 3, 9)

        self.play_label_layout = QHBoxLayout()
        self.play_clear_button = QPushButton("清空")
        self.play_send_button = QPushButton("发送")
        self.play_clear_button.clicked.connect(self.play_clear)
        self.play_send_button.clicked.connect(self.play_send)
        self.play_label_layout.addWidget(self.play_clear_button)
        self.play_label_layout.addWidget(self.play_send_button)


        layout.addWidget(self.protocol_label) # 协议选择标签
        layout.addLayout(self.protocol_layout) # 协议选择按钮

        layout.addWidget(self.port_label)
        layout.addLayout(self.port_layout)

        layout.addWidget(self.baudrate_label)
        layout.addWidget(self.baudrate_combo)

        layout.addWidget(self.parity_label)
        layout.addWidget(self.parity_combo)

        layout.addWidget(self.stopbits_label) # 停止位标签
        layout.addWidget(self.stopbits_combo) # 停止位选择

        layout.addWidget(self.connect_button)  # 连接按钮

        layout.addLayout(self.receive_layout) # 接收标签
        layout.addWidget(self.receive_text) # 接收文本框

        layout.addWidget(self.send_label)
        layout.addLayout(self.send_layout)
        layout.addWidget(self.volume_label)
        layout.addLayout(self.volume_layout)
        layout.addWidget(self.hex_label)
        layout.addLayout(self.hex_layout)
        layout.addLayout(self.play_save_layout)
        layout.addLayout(self.play_layout)
        layout.addLayout(self.play_label_layout)

        self.setLayout(layout)
        self.setWindowTitle("语音调试工具助手 1.0.0")
        self.resize(400, 400)

    def load_command_history(self):
        if os.path.exists("command_history.json"):
            with open("command_history.json", "r", encoding="utf-8") as f:
                self.command_history = json.load(f)
            # print(self.command_history)
            # 将历史记录显示在列表中
            for record in self.command_history:
                self.play_save_select_combo.addItem(record["name"])
        else:
            # 如果文件不存在则初始化一个空列表, 用于存储指令历史记录
            self.command_history = []

    def save_command(self, name, command):
        """
        Save the command with a name and timestamp.
        """
        record = {
            "name": name,
            "command": command,
            "timestamp": QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        }
        self.command_history.append(record) # 将记录添加到历史记录列表

        # Write command history to JSON file
        with open("command_history.json", "w", encoding="utf-8") as f:
            json.dump(self.command_history, f, ensure_ascii=False, indent=4)

        # 在列表和选择器中显示保存的命令
        self.play_save_select_combo.addItem(name)

    def play_command_save(self):
        """保存连码"""
        name = self.play_save_select_combo.currentText()
        if name == "选择连码":
            # 获取当前command_history列表有几个元素
            number = len(self.command_history)
            name = f"保存指令{number+1}"
            play_str = ""
            for i in range(1, 41):
                if getattr(self, f"play_text{i}").text() == "":
                    break
                play_str += getattr(self, f"play_text{i}").text() + " "
            self.save_command(name, play_str)
        else:
            play_str = ""
            for i in range(1, 41):
                if getattr(self, f"play_text{i}").text() == "":
                    break
                play_str += getattr(self, f"play_text{i}").text() + " "
            for record in self.command_history:
                if record["name"] == name:
                    record["command"] = play_str
                    break
            with open("command_history.json", "w", encoding="utf-8") as f:
                json.dump(self.command_history, f, ensure_ascii=False, indent=4)

    def play_command_update(self):
        """切换标签时更新连码"""
        name = self.play_save_select_combo.currentText()
        if name == "选择连码":
            self.play_clear()
        else:
            for record in self.command_history:
                if record["name"] == name:
                    play_str = record["command"].split() # 以空格分割
                    for i in range(1, 41):
                        if i <= len(play_str):
                            getattr(self, f"play_text{i}").setText(play_str[i-1])
                        else:
                            getattr(self, f"play_text{i}").clear()


    def refresh_ports(self):
        """刷新串口设备列表"""
        self.ports = serial.tools.list_ports.comports()
        return [port.device for port in serial.tools.list_ports.comports()]

    def check_connection_status(self):
        """检查设备连接状态"""
        if self.serial_port.is_open:
            try:
                # 刷新串口设备列表，检查当前设备是否存在
                available_ports = self.refresh_ports()
                if self.serial_port.port not in available_ports:
                    # print("串口设备已断开")
                    self.serial_port.close()
                    self.connect_button.setText("连接串口")
                    self.connect_button.setStyleSheet("background-color: red")
            except (serial.SerialException, OSError):
                print("检测设备状态时发生错误")

                self.serial_port.close()
                self.connect_button.setText("连接串口")
                self.connect_button.setStyleSheet("background-color: red")
        else:
            self.update_ports()


    def confirmation_dialog(self):
        """
        弹出确认对话框，询问用户是否继续操作。
        Args:
            None
        Returns:
            bool: 用户点击确认按钮返回True，否则返回False。
        Raises:
            None
        """
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("确认操作")
        msg_box.setText("你确定要继续吗？")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        response = msg_box.exec()
        return response == QMessageBox.Yes

    def update_ports(self):
        """
        更新串口列表，刷新串口下拉框。
        Args:
            None
        Returns:
            None
        Raises:
            None
        """
        ports = serial.tools.list_ports.comports()
        # 对比当前串口列表和新获取的串口列表，如果不一致则更新串口列表
        if len(ports) != self.port_combo.count():
            self.port_combo.clear()
            for port in ports:
                self.port_combo.addItem(port.device)

    def toggle_connection(self):
        """
        连接或断开串口。
        :arg
            None
        :returns
            None
        :raises
            None
        """
        if self.serial_port.is_open:
            self.serial_port.close()
            self.connect_button.setText("连接")
            self.connect_button.setStyleSheet("background-color: red")
        else:
            self.serial_port.port = self.port_combo.currentText()
            self.serial_port.baudrate = int(self.baudrate_combo.currentText())
            self.serial_port.parity = serial.PARITY_NONE if self.parity_combo.currentText() == "None" else serial.PARITY_EVEN if self.parity_combo.currentText() == "Even" else serial.PARITY_ODD
            self.serial_port.stopbits = serial.STOPBITS_ONE if self.stopbits_combo.currentText() == "1" else serial.STOPBITS_ONE_POINT_FIVE if self.stopbits_combo.currentText() == "1.5" else serial.STOPBITS_TWO

            try:
                self.serial_port.open()
                self.connect_button.setText("断开")
                self.connect_button.setStyleSheet("background-color: green")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"连接失败: {str(e)}")

    def send_hex_add(self):
        """
        将发送文本框中的数字加1并更新文本框。
        :arg
            none
        :returns
            none
        :raises
            none
        """
        if self.serial_port.is_open:
            hex_str = self.send_text.text()
            try:
                hex_int = int(hex_str)
                hex_int += 1
                hex_str = f"{hex_int}"
                self.send_text.setText(hex_str)
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的数字")
        else:
            QMessageBox.warning(self, "错误", "请先连接串口")

    def send_hex_minus(self):
        """
        将发送文本框中的数字减1并更新文本框。
        :arg
            none
        :returns
            none
        :raises
            none
        """
        if self.serial_port.is_open:
            hex_str = self.send_text.text()
            try:
                hex_int = int(hex_str)
                hex_int -= 1
                hex_str = f"{hex_int}"
                self.send_text.setText(hex_str)
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的数字")
        else:
            QMessageBox.warning(self, "错误", "请先连接串口")

    def send_hex_data(self):
        """
        将发送文本框中的数字转换为2位或4位hex发送。
        :arg
            none
        :returns
            none
        :raises
            none
        """
        if self.serial_port.is_open:
            hex_str = self.send_text.text()
            try:
                # 发送前将输入的字符串转换为数字类型，然后转换为长度为4的hex文件，不够的前面补零
                hex_int = int(hex_str)
                if self.protocol_flag == 0:
                    hex_value = format(hex_int, '02x')
                else:
                    hex_value = format(hex_int, '04x')
                hex_str = f"{hex_value}"
                hex_data = bytes.fromhex(hex_str)
                self.serial_port.write(hex_data)
                # 格式化当前时间
                now = datetime.now()
                formatted_time = now.strftime("%H:%M:%S")
                self.receive_text.append(f"{formatted_time} 已发送:{hex_str}")
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的数字")
        else:
            QMessageBox.warning(self, "错误", "请先连接串口")

    def receive_data(self):
        """
        从串口接收数据并显示在接收文本框中。
        :arg
            none
        :returns
            none
        :raises
            none
        """
        if self.serial_port.is_open:
            try:
                data = self.serial_port.read(self.serial_port.in_waiting or 1).decode('utf-8')
                self.receive_text.append(data)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"接收失败: {str(e)}")

    def play_clear(self):
        """
        清空连码输入框
        :arg
            none
        :returns
            none
        :raises
            none
        """
        for i in range(1, 41):
            getattr(self, f"play_text{i}").clear()

    def play_send(self):
        """
        发送连码,从第一个开始到第一个空的输入框接收，每个输入框转为hex发送，每个前面都加上F3或FFF3
        :arg
            none
        :returns
            none
        :raises
            none
        """
        # 发送连码,从第一个开始到第一个空的输入框接收，每个输入框转为hex发送，每个前面都加上FFF3
        if self.serial_port.is_open:
            hex_str = ""
            for i in range(1, 41):
                if getattr(self, f"play_text{i}").text() == "":
                    break
                play_str = getattr(self, f"play_text{i}").text()
                try:
                    if self.protocol_flag == 0:
                        play_value = format(int(play_str), '02x') # 转为2位hex
                    else:
                        play_value = format(int(play_str), '04x') # 转为4位hex
                except:
                    QMessageBox.warning(self, "错误", "请输入有效的数字")
                    return
                if self.protocol_flag == 0:
                    hex_str += f"F3{play_value}" # 8bit协议，前面加F3
                else:
                    hex_str += f"FFF3{play_value}" # 16bit协议，前面加FFF3
            try:
                hex_data = bytes.fromhex(hex_str)
                self.serial_port.write(hex_data)
                # 格式化当前时间
                now = datetime.now()
                formatted_time = now.strftime("%H:%M:%S")
                self.receive_text.append(f"{formatted_time} 已发送:{hex_str}")
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的数字")
        else:
            QMessageBox.warning(self, "错误", "请先连接串口")

    def send_volume_data(self):
        """
        发送音量值
        :arg
            none
        :returns
            none
        :raises
            none
        """
        if self.serial_port.is_open:
            volume_str = self.volume_text.text()
            try:
                volume_int = int(volume_str)
                if volume_int < 0 or volume_int > 15:
                    QMessageBox.warning(self, "错误", "音量值必须在0-15之间")
                    return
                # 发送音量值，根据协议选择发送不同的hex
                if self.protocol_flag == 0:
                    hex_str = f"E{volume_int:x}"
                else:
                    hex_str = f"FFE{volume_int:x}"
                hex_data = bytes.fromhex(hex_str)
                self.serial_port.write(hex_data)
                # 格式化当前时间
                now = datetime.now()
                formatted_time = now.strftime("%H:%M:%S")
                self.receive_text.append(f"{formatted_time} 已发送:{hex_str}")
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的数字")
        else:
            QMessageBox.warning(self, "错误", "请先连接串口")

    def send_volume_add(self):
        """
        音量值加1
        :arg
            none
        :returns
            none
        :raises
            none
        """
        if self.serial_port.is_open:
            volume_str = self.volume_text.text()
            try:
                volume_int = int(volume_str)
                volume_int += 1
                if volume_int > 15:
                    volume_int = 15
                volume_str = f"{volume_int}"
                self.volume_text.setText(volume_str)
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的数字")
        else:
            QMessageBox.warning(self, "错误", "请先连接串口")

    def send_volume_minus(self):
        """
        音量值减1
        :arg
            none
        :returns
            none
        :raises
            none
        """
        if self.serial_port.is_open:
            volume_str = self.volume_text.text()
            try:
                volume_int = int(volume_str)
                volume_int -= 1
                if volume_int < 0:
                    volume_int = 0
                volume_str = f"{volume_int}"
                self.volume_text.setText(volume_str)
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的数字")
        else:
            QMessageBox.warning(self, "错误", "请先连接串口")

    def send_hex_value(self):
        """
        发送hex指令,转换成hex直接发送
        :arg
            none
        :returns
            none
        :raises
            none
        """
        if self.serial_port.is_open:
            hex_str = self.hex_text.text()
            try:
                hex_data = bytes.fromhex(hex_str)
                self.serial_port.write(hex_data)
                # 格式化当前时间
                now = datetime.now()
                formatted_time = now.strftime("%H:%M:%S")
                self.receive_text.append(f"{formatted_time} 已接收:{hex_str}")
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的指令")
        else:
            QMessageBox.warning(self, "错误", "请先连接串口")

    def protocol_select(self, flag):
        """
        选择协议，根据协议选择发送的hex长度
        :arg
            none
        :returns
            none
        :raises
            none
        """
        self.protocol_flag = flag
        if flag == 0:
            self.volume_text.setPlaceholderText("请输入音量值(0-15)代表发送E0-EF")
        else:
            self.volume_text.setPlaceholderText("请输入音量值(0-15)代表发送FFE0-FFEF")
        self.receive_text.append(f"已选择协议: TIRO_{8*(flag+1)}bit")

    def read_serial_data(self):
        """读取串口数据并实时显示"""
        if self.serial_port and self.serial_port.is_open:
            try:
                # 检查串口是否有数据
                if self.serial_port.in_waiting:
                    # 读取数据
                    data = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    # 格式化当前时间
                    now = datetime.now()
                    formatted_time = now.strftime("%H:%M:%S")
                    # 显示在接收区
                    self.receive_text.append(f"{formatted_time} 已接收:{data}")
            except Exception as e:
                print(f"读取串口数据失败: {e}")

    # 在 SerialPort.py 文件中
    def apply_stylesheet(self):
        stylesheet = """
        QWidget {
            background-color: #f0f8ff;
            color: #333;
            font-family: Arial, sans-serif;
            font-size: 14px;
        }
        QLabel {
            color: #2e8b57;
            font-weight: bold;
        }
        QPushButton {
            background-color: #87cefa;
            border: 1px solid #4682b4;
            border-radius: 5px;
            padding: 5px;
        }
        QPushButton:hover {
            background-color: #b0e0e6;
        }
        QLineEdit, QComboBox, QTextEdit {
            border: 1px solid #4682b4;
            border-radius: 5px;
            padding: 5px;
        }
        QRadioButton {
            color: #2e8b57;
        }
        QMessageBox {
            background-color: #f0f8ff;
        }
        """
        self.setStyleSheet(stylesheet)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 设置程序图标
    app.setWindowIcon(QIcon('/favicon.ico'))
    window = SerialPortHelper()
    window.show()
    sys.exit(app.exec())
