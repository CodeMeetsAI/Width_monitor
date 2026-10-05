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
        self.verticalLayout.addWidget(self.header)

        # --- Display Container ---
        self.display_container = QtWidgets.QWidget(parent=self.centralwidget)
        self.display_container.setStyleSheet("background-color: black;")
        self.display_container.setObjectName("display_container")

        self.overlay_layout = QtWidgets.QVBoxLayout(self.display_container)
        self.overlay_layout.setContentsMargins(0, 0, 0, 0)
        self.overlay_layout.setSpacing(0)

        # === LCD Width Display ===
        self.lcd_width = QtWidgets.QLabel(parent=self.display_container)
        self.lcd_width.setText("0.00")
        self.lcd_width.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lcd_width.setStyleSheet("""
            background-color: black;
            color: red;
            border: none;
            font-family: 'DS-Digital', 'Courier New', monospace;
            font-size: 400px;        /* Adjust this to make it even bigger */
            font-weight: bold;
        """)
        self.lcd_width.setMinimumHeight(700)
        self.overlay_layout.addWidget(
            self.lcd_width,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        # === Control Panel (bottom) ===
        self.control_panel = QtWidgets.QGroupBox(parent=self.display_container)
        self.control_panel.setMaximumHeight(120)
        font = QtGui.QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.control_panel.setFont(font)
        self.control_panel.setTitle("Control Panel")
        self.control_panel.setStyleSheet(
            "background-color: rgba(20, 20, 20, 180); color: white; border-radius: 10px;"
        )

        self.control_layout = QtWidgets.QVBoxLayout(self.control_panel)
        self.control_layout.setContentsMargins(10, 10, 10, 10)
        self.control_layout.setSpacing(5)

        # Move control panel to bottom-left corner, fixed position
        self.control_panel.setFixedSize(520, 150)

        # Use absolute positioning so it stays overlayed in bottom-left
        self.control_panel.move(20, self.display_container.height() - 120)

        # Make sure it stays positioned even when window resizes
        self.display_container.resizeEvent = lambda event: self.control_panel.move(20, self.display_container.height() - 120)


        button_row = QtWidgets.QHBoxLayout()
        btn_font = QtGui.QFont()
        btn_font.setPointSize(12)
        btn_font.setBold(True)

        def make_btn(text):
            btn = QtWidgets.QPushButton(text)
            btn.setMinimumSize(100, 40)
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
        self.entry_lot_no.setMinimumSize(80, 40)
        self.entry_lot_no.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        button_row.addWidget(self.entry_lot_no)

        self.btn_update_lot = QtWidgets.QPushButton()
        self.btn_update_lot.setMinimumSize(40, 40)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("rotate.png"), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
        self.btn_update_lot.setIcon(icon)
        button_row.addWidget(self.btn_update_lot)

        self.control_layout.addLayout(button_row)

        self.label_camera_status = QtWidgets.QLabel("Status: Idle")
        self.label_camera_status.setStyleSheet("color: lightgray; font-size: 11pt;")
        self.label_camera_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.control_layout.addWidget(self.label_camera_status)

        self.overlay_layout.addWidget(self.control_panel)
        self.verticalLayout.addWidget(self.display_container)

        MainWindow.setCentralWidget(self.centralwidget)
        MainWindow.setStatusBar(QtWidgets.QStatusBar(parent=MainWindow))
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
        self.setGeometry(100, 100, 1000, 700)
        self.label_video = QtWidgets.QLabel(self)
        self.label_video.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label_video)
        self.setLayout(layout)
