from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1680, 1050)
        MainWindow.setMinimumSize(QtCore.QSize(1000, 700))
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")

        # --- Header Title ---
        self.header = QtWidgets.QLabel(parent=self.centralwidget)
        font = QtGui.QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.header.setFont(font)
        self.header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.header.setText("Real-Time Fabric Width Monitoring")
        self.header.setMaximumHeight(50)
        self.header.setStyleSheet("""
                    background-color: black;
                    color: white;
                    border: none
                    
                """)
        self.verticalLayout.addWidget(self.header)

        # --- Display Container ---
        self.display_container = QtWidgets.QWidget(parent=self.centralwidget)
        self.display_container.setStyleSheet("background-color: black;")
        self.display_container.setObjectName("display_container")

        self.overlay_layout = QtWidgets.QVBoxLayout(self.display_container)
        self.overlay_layout.setContentsMargins(0, 0, 0, 0)
        self.overlay_layout.setSpacing(0)

        # === LCD Width Display ===
        lcd_line = QtWidgets.QHBoxLayout()
        lcd_line.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # ↓↓↓ Add these two lines ↓↓↓
        lcd_line.setSpacing(0)  # reduces space *between* widgets
        lcd_line.setContentsMargins(0, 0, 0, 0)  # removes outer margins

        self.lcd_width = QtWidgets.QLabel(parent=self.display_container)
        self.lcd_width.setText("0.0")
        self.lcd_width.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.lcd_width.setStyleSheet("""
            background-color: black;
            color: red;
            border: none;
            font-family: 'DS-Digital', 'Courier New', monospace;
            font-size: 620px;
            font-weight: bold;
        """)
        self.lcd_width.setMinimumHeight(700)

        self.label_unit = QtWidgets.QLabel("cm", parent=self.display_container)
        self.label_unit.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.label_unit.setStyleSheet("""
            color: red;
            font: bold 50px Arial;
        """)

        lcd_line.addWidget(self.lcd_width)
        lcd_line.addWidget(self.label_unit)
        self.overlay_layout.addLayout(lcd_line)

        self.control_panel = QtWidgets.QGroupBox(parent=self.display_container)
        self.control_panel.setMaximumHeight(200)
        font = QtGui.QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.control_panel.setFont(font)
        self.control_panel.setTitle("Control Panel")
        self.control_panel.setStyleSheet(
            "background-color: rgba(20, 20, 20, 180); color: white; border-radius: 10px;"
        )

        self.control_layout = QtWidgets.QVBoxLayout(self.control_panel)
        self.control_layout.setContentsMargins(20, 20, 20, 30)
        self.control_layout.setSpacing(15)  # 🔹 slightly more vertical spacing

        # 🔹 Increase panel width and adjust position
        self.control_panel.setFixedSize(650, 180)  # was 520x150

        # 🔹 Keep it positioned nicely in bottom-left
        self.control_panel.move(30, self.display_container.height() - 150)
        self.display_container.resizeEvent = lambda event: self.control_panel.move(
            30, self.display_container.height() - 150
        )

        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(15)  # 🔹 Add horizontal spacing between widgets

        btn_font = QtGui.QFont()
        btn_font.setPointSize(12)
        btn_font.setBold(True)

        def make_btn(text):
            btn = QtWidgets.QPushButton(text)
            btn.setMinimumSize(110, 45)
            btn.setFont(btn_font)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            return btn

        self.btn_start = make_btn("▶ Start")
        self.btn_stop = make_btn("⏹ Stop")
        self.btn_settings = make_btn("Settings")

        button_row.addWidget(self.btn_start)
        button_row.addWidget(self.btn_stop)
        button_row.addWidget(self.btn_settings)

        self.entry_lot_no = QtWidgets.QLineEdit()
        self.entry_lot_no.setMinimumSize(100, 45)
        self.entry_lot_no.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.entry_lot_no.setStyleSheet("""
            background-color: black;
            color: white;
            border: 1px solid gray;
            border-radius: 5px;
            font-size: 18px;
        """)
        button_row.addWidget(self.entry_lot_no)

        self.btn_update_lot = QtWidgets.QPushButton()
        self.btn_update_lot.setMinimumSize(45, 45)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("rotate.png"), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
        self.btn_update_lot.setIcon(icon)
        button_row.addWidget(self.btn_update_lot)

        # === ✅ Reference Width Entry ===
        self.entry_actual_width = QtWidgets.QLineEdit()
        self.entry_actual_width.setMinimumSize(130, 50)
        self.entry_actual_width.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.entry_actual_width.setPlaceholderText("Actual Width (cm)")
        self.entry_actual_width.setStyleSheet("""
            background-color: black;
            color: yellow;
            border: 1px solid gray;
            border-radius: 5px;
            font-size: 18px;
        """)
        button_row.addWidget(self.entry_actual_width)

        self.btn_set_ref = QtWidgets.QPushButton("Set Ref")
        self.btn_set_ref.setMinimumSize(90, 50)
        self.btn_set_ref.setFont(btn_font)
        self.btn_set_ref.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: #1e8449;
            }
        """)
        button_row.addWidget(self.btn_set_ref)

        # 🔹 Add row and status label
        self.control_layout.addLayout(button_row)

        self.label_camera_status = QtWidgets.QLabel("Status: Idle")
        self.label_camera_status.setStyleSheet("color: white; font-size: 11pt;")
        self.label_camera_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.control_layout.addWidget(self.label_camera_status)

        #self.control_layout.addLayout(button_row)

        #self.label_camera_status = QtWidgets.QLabel("Status: Idle")
        #self.label_camera_status.setStyleSheet("color: white; font-size: 11pt;")
        #self.label_camera_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        #self.control_layout.addWidget(self.label_camera_status)

        self.overlay_layout.addWidget(self.control_panel)
        self.verticalLayout.addWidget(self.display_container)

        MainWindow.setCentralWidget(self.centralwidget)
       # MainWindow.setStatusBar(QtWidgets.QStatusBar(parent=MainWindow))
        MainWindow.showMaximized()

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Fabric Width Measurement System"))


# === Video Window (Separate Camera Feed Window) ===
class VideoWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Camera Feed")
        self.setGeometry(100, 100, 1200, 720)
        self.label_video = QtWidgets.QLabel(self)
        self.label_video.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label_video)
        self.setLayout(layout)
        self.label_video.setScaledContents(True)
