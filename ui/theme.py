"""Global dark theme stylesheet."""

STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #1E1E1E;
    color: #CCCCCC;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QLabel {
    color: #CCCCCC;
}

QLabel#title {
    font-size: 20px;
    font-weight: bold;
    color: #00BFA5;
}

QLabel#subtitle {
    font-size: 13px;
    color: #888888;
}

QPushButton {
    background-color: #00BFA5;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: bold;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #00D4B8;
}

QPushButton:pressed {
    background-color: #009688;
}

QPushButton#danger {
    background-color: #F44336;
}

QPushButton#danger:hover {
    background-color: #EF5350;
}

QPushButton#secondary {
    background-color: #333333;
    color: #CCCCCC;
    border: 1px solid #3E3E3E;
}

QPushButton#secondary:hover {
    background-color: #444444;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #2D2D2D;
    color: #CCCCCC;
    border: 1px solid #3E3E3E;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #00BFA5;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #00BFA5;
}

QComboBox {
    background-color: #2D2D2D;
    color: #CCCCCC;
    border: 1px solid #3E3E3E;
    border-radius: 6px;
    padding: 6px 10px;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #2D2D2D;
    color: #CCCCCC;
    selection-background-color: #00BFA5;
}

QTableWidget {
    background-color: #252526;
    color: #CCCCCC;
    border: 1px solid #3E3E3E;
    gridline-color: #3E3E3E;
    selection-background-color: #00BFA5;
}

QTableWidget::item {
    padding: 6px;
}

QTableWidget QHeaderView::section {
    background-color: #1E1E1E;
    color: #00BFA5;
    border: none;
    border-bottom: 1px solid #3E3E3E;
    padding: 6px;
    font-weight: bold;
}

QScrollBar:vertical {
    background: #1E1E1E;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #444444;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #00BFA5;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QGroupBox {
    border: 1px solid #3E3E3E;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    color: #00BFA5;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}

QSpinBox {
    background-color: #2D2D2D;
    color: #CCCCCC;
    border: 1px solid #3E3E3E;
    border-radius: 6px;
    padding: 5px;
}

QCheckBox {
    color: #CCCCCC;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #3E3E3E;
    background: #2D2D2D;
}

QCheckBox::indicator:checked {
    background: #00BFA5;
    border: 1px solid #00BFA5;
}

QTabWidget::pane {
    border: 1px solid #3E3E3E;
    background: #252526;
    border-radius: 6px;
}

QTabBar::tab {
    background: #1E1E1E;
    color: #888888;
    padding: 8px 18px;
    border: 1px solid #3E3E3E;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background: #252526;
    color: #00BFA5;
}

QMessageBox {
    background-color: #252526;
}

QMessageBox QPushButton {
    min-width: 80px;
}

QProgressBar {
    background-color: #2D2D2D;
    border: 1px solid #3E3E3E;
    border-radius: 4px;
    text-align: center;
    color: #CCCCCC;
}

QProgressBar::chunk {
    background-color: #00BFA5;
    border-radius: 4px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #3E3E3E;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #00BFA5;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSplitter::handle {
    background: #3E3E3E;
    width: 1px;
}

QStatusBar {
    background: #1E1E1E;
    color: #888888;
    border-top: 1px solid #3E3E3E;
}
"""
