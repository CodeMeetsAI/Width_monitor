from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        #MainWindow.resize(1680, 1050)
        MainWindow.resize(1280, 1050)
        MainWindow.setMinimumSize(QtCore.QSize(1000, 700))
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # Main vertical layout
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")

        # --- Header Container (green bar) ---
        self.header = QtWidgets.QFrame(parent=self.centralwidget)
        self.header.setStyleSheet("""
            background-color: #A7D8A0;
            border: none;
        """)
        self.header.setMaximumHeight(80)

        header_layout = QtWidgets.QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 5, 20, 5)
        header_layout.setSpacing(0)

        # --- LEFT Title ---
        self.left_title = QtWidgets.QLabel("INDUSTRONICS ENGINEERING (www.industronics.uk)")
        left_font = QtGui.QFont()
        left_font.setPointSize(16)
        left_font.setBold(True)
        self.left_title.setFont(left_font)
        self.left_title.setStyleSheet("color: black; border: none;")
        self.left_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft)

        # --- RIGHT Title ---
        self.right_title = QtWidgets.QLabel("Width Monitoring System")
        right_font = QtGui.QFont()
        right_font.setPointSize(20)
        right_font.setBold(True)
        right_font.setItalic(True)
        self.right_title.setFont(right_font)
        self.right_title.setStyleSheet("color: black; border: none;")
        self.right_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight)

        # Add to header layout
        header_layout.addWidget(self.left_title, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        header_layout.addStretch(1)
        header_layout.addWidget(self.right_title, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        # Add header to main layout
        self.verticalLayout.addWidget(self.header)

        # --- Display Container (gray background) ---
        self.display_container = QtWidgets.QWidget(parent=self.centralwidget)
        self.display_container.setStyleSheet("background-color: #868a8f;")
        self.display_container.setObjectName("display_container")

        display_layout = QtWidgets.QVBoxLayout(self.display_container)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(0)

        # === 8-BOX DASHBOARD SECTION (4x2 GRID) ===
        dashboard_container = QtWidgets.QWidget(parent=self.display_container)
        dashboard_layout = QtWidgets.QGridLayout(dashboard_container)
        dashboard_layout.setContentsMargins(20, 20, 20, 20)
        dashboard_layout.setHorizontalSpacing(20)
        dashboard_layout.setVerticalSpacing(20)

        class DashboardBox(QtWidgets.QFrame):
            def __init__(self, title, value):
                super().__init__()

                self.setStyleSheet("""
                    background-color: #000;
                    border: 2px solid #3A3A3A;
                    border-radius: 15px;
                """)
                self.setMinimumHeight(150)

                layout = QtWidgets.QVBoxLayout(self)
                layout.setContentsMargins(12, 10, 12, 10)
                layout.setSpacing(5)

                # Title
                self.title = QtWidgets.QLabel(title)
                self.title.setStyleSheet("color: white; border: none;")
                font = QtGui.QFont("Arial", 20)
                font.setBold(True)
                self.title.setFont(font)
                self.title.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
                self.title.setFixedHeight(25)

                # Value (large text)
                self.value = QtWidgets.QLabel(value)
                self.value.setStyleSheet("color: #00FF00; border: none;")
                self.value.setFont(QtGui.QFont("Arial", 50, QtGui.QFont.Weight.Bold))
                self.value.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

                layout.addWidget(self.title)
                layout.addStretch(1)
                layout.addWidget(self.value)
                layout.addStretch(1)

        # Create 8 boxes
        self.box_required_width = DashboardBox("Required Width (cm)", "0.00")
        self.box_required_shrink = DashboardBox("Required Shrink (%)", "0.00")
        self.box_deviation_limit = DashboardBox("Deviation Limit (%)", "0.00")
        self.box_ref_width = DashboardBox("Ref Width (cm)", "0.00")

        self.box_actual_width = DashboardBox("Actual Width (cm)", "0.00")
        self.box_actual_shrink = DashboardBox("Actual Shrink (%)", "0.00")
        self.box_deviation = DashboardBox("Deviation (%)", "0.00")
        self.box_lot_no_display = DashboardBox("LOT NO", "-")

        # Add to grid 4x2
        dashboard_layout.addWidget(self.box_required_width, 0, 0)
        dashboard_layout.addWidget(self.box_required_shrink, 0, 1)
        dashboard_layout.addWidget(self.box_deviation_limit, 0, 2)
        dashboard_layout.addWidget(self.box_ref_width, 0, 3)

        dashboard_layout.addWidget(self.box_actual_width, 1, 0)
        dashboard_layout.addWidget(self.box_actual_shrink, 1, 1)
        dashboard_layout.addWidget(self.box_deviation, 1, 2)
        dashboard_layout.addWidget(self.box_lot_no_display, 1, 3)

        # Add dashboard to display layout
        display_layout.addWidget(dashboard_container)

        # --- Separator line ---
        self.separator_line = QtWidgets.QFrame(parent=self.display_container)
        self.separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.separator_line.setStyleSheet("color: #444; background-color: #444;")
        self.separator_line.setFixedHeight(2)
        display_layout.addWidget(self.separator_line)

        # --- Control Panel (Black background with left and right sections) ---
        self.control_panel = QtWidgets.QFrame(parent=self.display_container)
        self.control_panel.setMaximumHeight(220)
        self.control_panel.setStyleSheet("background-color: #000000; border: none;")

        control_main_layout = QtWidgets.QHBoxLayout(self.control_panel)
        control_main_layout.setContentsMargins(30, 20, 30, 20)
        control_main_layout.setSpacing(60)

        # ======================== LEFT SIDE: INPUT FIELDS (2x2 Grid) ==========================
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QGridLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setHorizontalSpacing(15)
        left_layout.setVerticalSpacing(12)

        label_style = "color: white; font-size: 12pt; font-weight: bold;"
        entry_style = """
            background-color: #1a4d5e;
            color: cyan;
            border: 2px solid #2980b9;
            border-radius: 5px;
            font-size: 14pt;
            padding: 6px;
            font-weight: bold;
        """

        # Row 0: Ref Width, Required Width
        left_layout.addWidget(QtWidgets.QLabel("Ref Width (cm):", styleSheet=label_style), 0, 0,
                              alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.entry_ref_width = QtWidgets.QLineEdit()
        self.entry_ref_width.setMinimumHeight(45)
        self.entry_ref_width.setMinimumWidth(160)
        self.entry_ref_width.setStyleSheet(entry_style)
        left_layout.addWidget(self.entry_ref_width, 0, 1)

        left_layout.addWidget(QtWidgets.QLabel("Required Width (cm):", styleSheet=label_style), 0, 2,
                              alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.entry_required_width = QtWidgets.QLineEdit()
        self.entry_required_width.setMinimumHeight(45)
        self.entry_required_width.setMinimumWidth(160)
        self.entry_required_width.setStyleSheet(entry_style)
        left_layout.addWidget(self.entry_required_width, 0, 3)

        # Row 1: Lot No, Deviation Limit
        left_layout.addWidget(QtWidgets.QLabel("Lot No:", styleSheet=label_style), 1, 0,
                              alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.entry_lot_no = QtWidgets.QLineEdit()
        self.entry_lot_no.setMinimumHeight(45)
        self.entry_lot_no.setMinimumWidth(160)
        self.entry_lot_no.setStyleSheet(entry_style)
        left_layout.addWidget(self.entry_lot_no, 1, 1)

        #left_layout.addWidget(QtWidgets.QLabel("Deviation limit (%):", styleSheet=label_style), 1, 2,
         #                     alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        #self.entry_deviation_limit = QtWidgets.QLineEdit()
        #self.entry_deviation_limit.setMinimumHeight(45)
        #self.entry_deviation_limit.setMinimumWidth(160)
        #self.entry_deviation_limit.setStyleSheet(entry_style)
        #left_layout.addWidget(self.entry_deviation_limit, 1, 3)

        control_main_layout.addWidget(left_container, stretch=1)

        # ======================== RIGHT SIDE: CONTROL PANEL ==========================
        right_container = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # Title
        control_title = QtWidgets.QLabel("Control Panel")
        control_title.setStyleSheet("color: white; font-size: 20pt; font-weight: bold;")
        control_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(control_title)

        # Buttons (horizontal layout)
        btn_font = QtGui.QFont()
        btn_font.setPointSize(14)
        btn_font.setBold(True)

        def make_btn(text, width=50, height=50):
            btn = QtWidgets.QPushButton(text)
            btn.setMinimumSize(width, height)
            btn.setFont(btn_font)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    font-weight: bold;
                    border-radius: 8px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            return btn

        self.btn_start = make_btn("Start")
        self.btn_settings = make_btn("Settings")
        self.btn_stop = make_btn("Stop")

        # Horizontal button layout
        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(15)
        button_row.addWidget(self.btn_start)
        button_row.addWidget(self.btn_settings)
        button_row.addWidget(self.btn_stop)

        right_layout.addLayout(button_row)

        # Status label
        self.label_camera_status = QtWidgets.QLabel("Status: Idle")
        self.label_camera_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.label_camera_status.setStyleSheet("color: white; font-size: 14pt; font-weight: bold; padding-top: 10px;")
        right_layout.addWidget(self.label_camera_status)

        control_main_layout.addWidget(right_container, stretch=1)

        # Add control panel to display layout
        display_layout.addWidget(self.control_panel)

        # Add display_container to main vertical layout
        self.verticalLayout.addWidget(self.display_container, 1)

        # Set central widget
        MainWindow.setCentralWidget(self.centralwidget)

        # Hidden buttons (keep for backward compatibility)
        self.btn_set_ref = QtWidgets.QPushButton()
        self.btn_set_ref.hide()
        self.btn_update_lot = QtWidgets.QPushButton()
        self.btn_update_lot.hide()

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
        self.setStyleSheet("background-color: black;")

        self.label_video = QtWidgets.QLabel(self)
        self.label_video.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.label_video.setStyleSheet("background-color: black;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label_video)
        self.setLayout(layout)
        self.label_video.setScaledContents(True)