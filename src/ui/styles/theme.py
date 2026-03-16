"""
CryptoRadar Dark Theme System
"""


class Theme:
    """Dark theme color palette and stylesheet manager."""
    
    # Background Colors
    BG_PRIMARY = "#0f0f14"      # Main background
    BG_SECONDARY = "#16161e"    # Sidebar, panels
    BG_CARD = "#1c1c28"         # Cards, inputs
    BG_HOVER = "#252536"        # Hover states
    
    # Text Colors
    TEXT_PRIMARY = "#e0e0e0"    # Main text
    TEXT_SECONDARY = "#8888a0"  # Muted text
    
    # Accent Colors
    ACCENT_GREEN = "#00d4aa"    # Positive, active
    ACCENT_RED = "#ff4757"      # Negative, errors
    ACCENT_YELLOW = "#ffa502"   # Warnings
    ACCENT_BLUE = "#3742fa"     # Info, links
    
    # UI Element Colors
    BORDER = "#2a2a3d"          # Borders, dividers
    
    # Font
    FONT_FAMILY = "Segoe UI, Arial"
    FONT_SIZE = 10
    
    @classmethod
    def get_stylesheet(cls) -> str:
        """
        Generate complete Qt stylesheet for the dark theme.
        
        Returns:
            str: Complete QSS stylesheet string
        """
        return f"""
            /* Main Windows and Widgets */
            QMainWindow {{
                background-color: {cls.BG_PRIMARY};
                color: {cls.TEXT_PRIMARY};
            }}
            
            QWidget {{
                background-color: {cls.BG_PRIMARY};
                color: {cls.TEXT_PRIMARY};
            }}
            
            QDialog {{
                background-color: {cls.BG_PRIMARY};
                color: {cls.TEXT_PRIMARY};
            }}
            
            /* Text and Labels */
            QLabel {{
                color: {cls.TEXT_PRIMARY};
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE}pt;
            }}
            
            QLabel:disabled {{
                color: {cls.TEXT_SECONDARY};
            }}
            
            /* Push Buttons */
            QPushButton {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE}pt;
                font-weight: 500;
            }}
            
            QPushButton:hover {{
                background-color: {cls.BG_HOVER};
                border: 1px solid {cls.ACCENT_GREEN};
            }}
            
            QPushButton:pressed {{
                background-color: {cls.ACCENT_GREEN};
                color: {cls.BG_PRIMARY};
                border: 1px solid {cls.ACCENT_GREEN};
            }}
            
            QPushButton:disabled {{
                color: {cls.TEXT_SECONDARY};
                border: 1px solid {cls.BORDER};
            }}
            
            /* Line Edits and Text Inputs */
            QLineEdit {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 4px;
                padding: 6px;
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE}pt;
            }}
            
            QLineEdit:focus {{
                border: 1px solid {cls.ACCENT_GREEN};
                background-color: {cls.BG_CARD};
            }}
            
            QLineEdit:disabled {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_SECONDARY};
                border: 1px solid {cls.BORDER};
            }}
            
            /* Spin Boxes */
            QSpinBox, QDoubleSpinBox {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 4px;
                padding: 4px;
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE}pt;
            }}
            
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 1px solid {cls.ACCENT_GREEN};
            }}
            
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background-color: {cls.BG_SECONDARY};
                border: none;
            }}
            
            /* Combo Boxes */
            QComboBox {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE}pt;
            }}
            
            QComboBox:focus {{
                border: 1px solid {cls.ACCENT_GREEN};
            }}
            
            QComboBox::drop-down {{
                background-color: {cls.BG_SECONDARY};
                border: none;
                width: 20px;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                selection-background-color: {cls.ACCENT_GREEN};
                selection-color: {cls.BG_PRIMARY};
                border: 1px solid {cls.BORDER};
            }}
            
            /* Table Widget */
            QTableWidget {{
                background-color: {cls.BG_PRIMARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                gridline-color: transparent;
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE}pt;
            }}
            
            QTableWidget::item {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                padding: 4px;
                border: none;
            }}
            
            QTableWidget::item:alternate {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_PRIMARY};
            }}
            
            QTableWidget::item:selected {{
                background-color: {cls.ACCENT_GREEN};
                color: {cls.BG_PRIMARY};
            }}
            
            QTableWidget::item:hover {{
                background-color: {cls.BG_HOVER};
            }}
            
            /* Table Header */
            QHeaderView::section {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_PRIMARY};
                padding: 6px;
                border: 1px solid {cls.BORDER};
                font-weight: 600;
            }}
            
            QHeaderView::section:hover {{
                background-color: {cls.BG_HOVER};
            }}
            
            /* Scroll Bars */
            QScrollBar:vertical {{
                background-color: {cls.BG_PRIMARY};
                width: 8px;
                border: none;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {cls.BG_CARD};
                border-radius: 4px;
                min-height: 20px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.BORDER};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
            }}
            
            QScrollBar:horizontal {{
                background-color: {cls.BG_PRIMARY};
                height: 8px;
                border: none;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {cls.BG_CARD};
                border-radius: 4px;
                min-width: 20px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: {cls.BORDER};
            }}
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                border: none;
                background: none;
            }}
            
            /* Tool Tips */
            QToolTip {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 4px;
                padding: 4px;
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE - 1}pt;
            }}
            
            /* Menu Bar and Menus */
            QMenuBar {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: none;
            }}
            
            QMenuBar::item:selected {{
                background-color: {cls.BG_HOVER};
            }}
            
            QMenu {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
            }}
            
            QMenu::item:selected {{
                background-color: {cls.ACCENT_GREEN};
                color: {cls.BG_PRIMARY};
            }}
            
            /* Check Box and Radio Button */
            QCheckBox, QRadioButton {{
                color: {cls.TEXT_PRIMARY};
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE}pt;
                spacing: 4px;
            }}
            
            QCheckBox::indicator, QRadioButton::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {cls.BORDER};
                border-radius: 2px;
                background-color: {cls.BG_CARD};
            }}
            
            QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
                border: 1px solid {cls.ACCENT_GREEN};
            }}
            
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
                background-color: {cls.ACCENT_GREEN};
                border: 1px solid {cls.ACCENT_GREEN};
            }}
            
            /* Tabs */
            QTabWidget::pane {{
                border: 1px solid {cls.BORDER};
            }}
            
            QTabBar::tab {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_SECONDARY};
                border: 1px solid {cls.BORDER};
                padding: 6px 12px;
                border-radius: 4px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {cls.ACCENT_GREEN};
                color: {cls.BG_PRIMARY};
                border: 1px solid {cls.ACCENT_GREEN};
            }}
            
            /* Progress Bar */
            QProgressBar {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 4px;
                height: 20px;
            }}
            
            QProgressBar::chunk {{
                background-color: {cls.ACCENT_GREEN};
                border-radius: 3px;
            }}
            
            /* Sliders */
            QSlider::groove:horizontal {{
                background-color: {cls.BG_CARD};
                border: 1px solid {cls.BORDER};
                height: 6px;
                border-radius: 3px;
            }}
            
            QSlider::handle:horizontal {{
                background-color: {cls.ACCENT_GREEN};
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            
            QSlider::handle:horizontal:hover {{
                background-color: {cls.ACCENT_GREEN};
            }}
        """
