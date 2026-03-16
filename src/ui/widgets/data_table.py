"""
Reusable styled data table widget for CryptoRadar
"""
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QBrush, QColor

from ui.styles.theme import Theme


class DataTable(QTableWidget):
    """Pre-styled table widget with dark theme and sorting support."""
    
    def __init__(self, headers: list = None):
        """
        Initialize data table.
        
        Args:
            headers: List of column header strings
        """
        # Initialize with placeholder rows/columns
        super().__init__(0, len(headers) if headers else 0)
        
        self.headers = headers or []
        self.primary_color = QColor(Theme.BG_CARD)
        self.alternate_color = QColor(Theme.BG_SECONDARY)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup table styling and behavior."""
        # Set headers
        if self.headers:
            self.setHorizontalHeaderLabels(self.headers)
        
        # Hide vertical header (row numbers)
        self.verticalHeader().setVisible(False)
        
        # Configure horizontal header
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setFixedHeight(40)
        
        # Set row height
        self.verticalHeader().setDefaultSectionSize(40)
        
        # Configure selection behavior
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setAlternatingRowColors(True)
        
        # Hide grid lines
        self.setShowGrid(False)
        
        # Apply styling
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                gridline-color: transparent;
            }}
            
            QTableWidget::item {{
                padding: 0px 6px;
                border: none;
            }}
            
            QTableWidget::item:selected {{
                background-color: {Theme.BG_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
            
            QHeaderView::section {{
                background-color: {Theme.BG_SECONDARY};
                color: {Theme.ACCENT_GREEN};
                padding: 6px;
                border: 1px solid {Theme.BORDER};
                font-weight: 600;
                font-size: 10pt;
            }}
            
            QHeaderView::section:hover {{
                background-color: {Theme.BG_HOVER};
            }}
            
            QScrollBar:horizontal {{
                background-color: {Theme.BG_PRIMARY};
                height: 8px;
                border: none;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {Theme.BG_CARD};
                border-radius: 4px;
                min-width: 20px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: {Theme.BORDER};
            }}
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                border: none;
                background: none;
            }}
            
            QScrollBar:vertical {{
                background-color: {Theme.BG_PRIMARY};
                width: 8px;
                border: none;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {Theme.BG_CARD};
                border-radius: 4px;
                min-height: 20px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {Theme.BORDER};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
            }}
        """)
        
        # Enable sorting
        self.setSortingEnabled(True)
    
    def set_data(self, rows: list):
        """
        Clear table and fill with new data.
        
        Args:
            rows: List of rows, each row is a list of cell values
        """
        if not rows:
            self.setRowCount(0)
            return
        
        import logging

        
        # Determine column count from first row or headers
        num_cols = len(rows[0]) if rows else len(self.headers)
        
        # IMPORTANT: Disable sorting during data updates to avoid issues with row insertion
        was_sorting_enabled = self.isSortingEnabled()
        self.setSortingEnabled(False)
        
        try:
            # Clear data first (but preserve structure)
            self.clearContents()
            
            # Ensure correct column count
            if self.columnCount() != num_cols:
                self.setColumnCount(num_cols)
                
                # Re-set headers after column count change
                if self.headers and len(self.headers) == num_cols:
                    self.setHorizontalHeaderLabels(self.headers)
            
            # Now set the row count
            self.setRowCount(len(rows))

            # Add data to cells
            rows_added = 0
            for row_idx, row_data in enumerate(rows):
                if len(row_data) != num_cols:
                    # Pad with empty values if needed
                    row_data = list(row_data) + [""] * (num_cols - len(row_data))
                
                for col_idx, cell_value in enumerate(row_data):
                    if row_idx >= self.rowCount() or col_idx >= self.columnCount():
                        continue
                    
                    item = QTableWidgetItem(str(cell_value))
                    
                    # Determine if cell contains a number for right alignment
                    try:
                        float(str(cell_value).replace("$", "").replace("%", "").replace(",", ""))
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    except ValueError:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    
                    # Set font
                    item_font = QFont(Theme.FONT_FAMILY, 10)
                    item.setFont(item_font)
                    
                    # Set alternating row colors
                    if row_idx % 2 == 0:
                        item.setBackground(self.primary_color)
                    else:
                        item.setBackground(self.alternate_color)
                    
                    # Make item non-editable
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    
                    self.setItem(row_idx, col_idx, item)
                
                rows_added += 1
            
        
        finally:
            # Re-enable sorting if it was enabled before
            if was_sorting_enabled:
                self.setSortingEnabled(True)
    
    def highlight_row(self, row_index: int, color: str = None):
        """
        Highlight a specific row with custom color.
        
        Args:
            row_index: Row index to highlight
            color: Color code (uses ACCENT_GREEN if None)
        """
        if not color:
            color = Theme.ACCENT_GREEN
        
        brush = QBrush(QColor(color))
        
        for col_idx in range(self.columnCount()):
            item = self.item(row_index, col_idx)
            if item:
                item.setBackground(brush)
                # Adjust text color for visibility
                if color == Theme.ACCENT_GREEN:
                    item.setForeground(QBrush(QColor(Theme.BG_PRIMARY)))
    
    def get_selected_row(self) -> int:
        """
        Get the index of the currently selected row.
        
        Returns:
            Row index or -1 if no row is selected
        """
        selected_rows = self.selectedIndexes()
        if selected_rows:
            return selected_rows[0].row()
        return -1
