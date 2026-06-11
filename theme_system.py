# -*- coding: utf-8 -*-
# 主题配色系统（从 WWDmgCalc.py 拆分）

__all__ = ["THEMES", "build_stylesheet"]

THEMES = {
    "dark": {
        "bg": "#1a1a2e",                       # 主窗口 / 欢迎页 / 主界面 背景
        "bg_secondary": "#16213e",             # 右侧内容区 (contentArea) 背景
        "bg_card": "#0f3460",                  # 卡片 (QGroupBox, resultCard, indepGroupFrame)
        "text": "#e6e6e6",                     # 正文 (QLabel, QCheckBox, QComboBox, 导航树, QGroupBox)
        "text_secondary": "#a0a0b0",           # 次要文字 (labelSecondary, 按钮, 表头, 提示)
        "accent": "#e94560",                   # 强调色 (标题, 结果数值, 链接, 选中态, 聚焦边框)
        "accent_hover": "#ff6b81",             # 强调色悬停 (暂未直接使用在样式表中)
        "btn_bg": "#e94560",                   # 主按钮背景 (startButton, addButton, itemAddBtn, calcBtn)
        "btn_hover": "#ff6b81",                # 主按钮悬停
        "btn_pressed": "#c0392b",              # 主按钮按下
        "sidebar_bg": "#16213e",               # 左侧导航栏背景
        "sidebar_hover": "#1a3a5c",            # 导航树 hover / 列表项 hover / 卡片 hover
        "border": "#3d3d5e",                   # 边框 (QGroupBox, 表格, 卡片, 输入框, 分割线)
        "input_bg": "#16213e",                 # 输入框背景 (QSpinBox, QComboBox, QListWidget)
        "input_border": "#3d3d5e",             # 输入框边框
        "input_focus": "#e94560",              # 输入框聚焦边框
        "checkbox_bg": "#e94560",              # 复选框选中背景
        "alt_row": "rgba(255,255,255,0.025)",  # 表格交替行背景
        "nav_selected_bg": "#1a2a44",          # 导航树选中项背景 / 按钮激活态背景
        "scrollbar_handle": "#a0a0b0",         # 滚动条滑块
        "scrollbar_handle_hover": "#e94560",   # 滚动条滑块悬停
        "header_grad_end": "#16213e",          # 表头渐变终点色
        "card_title_bg": "#1a2a44",            # 预设卡片标题栏背景
        "add_btn": "#27ae60",                  # 添加按钮（绿色）
        "del_btn": "#c0392b",                  # 删除按钮（红色）
    },
    "light": {
        "bg": "#dce3f0",                       # 主窗口 / 欢迎页 / 主界面 背景
        "bg_secondary": "#e4eaf5",             # 右侧内容区 (contentArea) 背景
        "bg_card": "#edf2f9",                  # 卡片 (QGroupBox, resultCard, indepGroupFrame)
        "text": "#1b2035",                     # 正文 (QLabel, QCheckBox, QComboBox, 导航树, QGroupBox)
        "text_secondary": "#5c6a80",           # 次要文字 (labelSecondary, 按钮, 表头, 提示)
        "accent": "#5070e8",                   # 强调色 (标题, 结果数值, 链接, 选中态, 聚焦边框)
        "accent_hover": "#4360d4",             # 强调色悬停 (暂未直接使用在样式表中)
        "btn_bg": "#5070e8",                   # 主按钮背景 (startButton, addButton, itemAddBtn, calcBtn)
        "btn_hover": "#4360d4",                # 主按钮悬停
        "btn_pressed": "#3852c0",              # 主按钮按下
        "sidebar_bg": "#d4dcec",               # 左侧导航栏背景
        "sidebar_hover": "#c4cee2",            # 导航树 hover / 列表项 hover / 卡片 hover
        "border": "#bfcadb",                   # 边框 (QGroupBox, 表格, 卡片, 输入框, 分割线)
        "input_bg": "#f0f4fa",                 # 输入框背景 (QSpinBox, QComboBox, QListWidget)
        "input_border": "#b8c4d6",             # 输入框边框
        "input_focus": "#5070e8",              # 输入框聚焦边框
        "checkbox_bg": "#5070e8",              # 复选框选中背景
        "alt_row": "#f2f5fb",                  # 表格交替行背景
        "nav_selected_bg": "#cbd8ed",          # 导航树选中项背景 / 按钮激活态背景
        "scrollbar_handle": "#bdc7d6",         # 滚动条滑块
        "scrollbar_handle_hover": "#5070e8",   # 滚动条滑块悬停
        "header_grad_end": "#dfe6f2",          # 表头渐变终点色
        "card_title_bg": "#c4d4ec",            # 预设卡片标题栏背景
        "add_btn": "#27ae60",                  # 添加按钮（绿色）
        "del_btn": "#c0392b",                  # 删除按钮（红色）
    },
}

def build_stylesheet(theme):
    c = THEMES[theme]
    return f"""
    * {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; }}
    QMainWindow {{ background-color: {c["bg"]}; }}
    QWidget#WelcomeScreen {{ background-color: {c["bg"]}; }}
    QLabel#welcomeTitle {{ color: {c["text"]}; font-size: 42px; font-weight: 300; }}
    QLabel#welcomeSubtitle {{ color: {c["text_secondary"]}; font-size: 16px; }}
    QPushButton#startButton {{
        background-color: {c["btn_bg"]}; color: white; border: none;
        padding: 14px 60px; font-size: 18px; font-weight: 600; border-radius: 8px;
    }}
    QPushButton#startButton:hover {{ background-color: {c["btn_hover"]}; }}
    QPushButton#startButton:pressed {{ background-color: {c["btn_pressed"]}; }}
    QPushButton#themeButton {{
        background-color: transparent; border: 1px solid {c["border"]};
        color: {c["text_secondary"]}; padding: 3px 8px; border-radius: 6px; font-size: 13px;
    }}
    QPushButton#themeButton:hover {{ border-color: {c["accent"]}; color: {c["accent"]}; }}
    QWidget#MainScreen {{ background-color: {c["bg"]}; }}
    QWidget#sidebar {{ background-color: {c["sidebar_bg"]}; border-right: 1px solid {c["border"]}; }}
    QTreeWidget#navTree {{
        background-color: transparent; border: none; outline: none;
        color: {c["text"]}; font-size: 14px;
    }}
    QTreeWidget#navTree::item {{
        padding: 4px 6px; border-radius: 6px; margin: 2px 8px;
    }}
    QTreeWidget#navTree::item:hover {{ background-color: {c["sidebar_hover"]}; }}
    QTreeWidget#navTree::item:selected {{
        color: {c["accent"]}; font-weight: 600;
        background-color: {c["nav_selected_bg"]};
        border-left: 3px solid {c["accent"]};
    }}
    QTreeWidget#navTree::branch {{ background: transparent; border: none; }}
    QTreeWidget#navTree::branch:has-children:closed {{ border: none; image: none; }}
    QTreeWidget#navTree::branch:has-children:open {{ border: none; image: none; }}
    QTreeWidget#navTree::branch:!has-children {{ border: none; image: none; width: 0; }}
    QTreeWidget#dataFlowTree {{
        background-color: {c["input_bg"]}; border: 1px solid {c["border"]};
        border-radius: 6px; color: {c["text"]}; font-size: 13px;
        outline: none;
    }}
    QTreeWidget#dataFlowTree::item {{
        padding: 3px 6px;
        border-left: 1px solid {c["border"]};
        border-right: 1px solid {c["border"]};
        border-bottom: 1px solid {c["border"]};
    }}
    QTreeWidget#dataFlowTree::item:hover {{
        background-color: {c["sidebar_hover"]};
    }}
    QTreeWidget#dataFlowTree::item:selected {{
        background-color: {c["nav_selected_bg"]}; color: {c["accent"]};
    }}
    QTreeWidget#dataFlowTree QHeaderView::section {{
        background-color: {c["bg_card"]}; color: {c["text"]};
        border-right: 1px solid {c["border"]};
        border-bottom: 2px solid {c["border"]};
        padding: 4px 8px; font-weight: 600;
        text-align: center;
    }}
    QWidget#contentArea {{ background-color: {c["bg_secondary"]}; }}
    QLabel#sectionTitle {{ color: {c["text"]}; font-size: 22px; font-weight: 600; padding: 4px 0; }}
    QGroupBox {{
        background-color: {c["bg_card"]}; border: 2px solid {c["border"]};
        border-radius: 8px; margin-top: 6px; padding-top: 8px;
        padding-left: 16px; padding-right: 16px; padding-bottom: 8px;
        color: {c["text"]}; font-size: 14px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; left: 15px; padding: 0 8px;
        color: {c["accent"]}; font-weight: 600; font-size: 15px;
    }}
    QLabel#groupBoxTitle {{
        color: {c["accent"]}; font-weight: 600; font-size: 15px;
    }}
    QFrame#dashedDivider {{
        border-left: 1px dashed {c["border"]};
        min-width: 1px; max-width: 1px;
    }}
    QDoubleSpinBox, QSpinBox {{
        padding: 2px 4px; border: 1px solid {c["input_border"]}; border-radius: 6px;
        background: {c["input_bg"]}; color: {c["text"]}; min-width: 120px; font-size: 14px;
    }}
    QDoubleSpinBox:focus, QSpinBox:focus {{ border-color: {c["input_focus"]}; }}
    QDoubleSpinBox#itemValueSpin {{
        padding: 1px 2px; padding-right: 36px; border: 1px solid {c["input_border"]};
        border-radius: 6px; background: {c["input_bg"]}; color: {c["text"]}; font-size: 13px;
    }}
    QDoubleSpinBox#itemValueSpin:focus {{ border-color: {c["input_focus"]}; border-width: 1px; }}
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
    QSpinBox::up-button, QSpinBox::down-button {{
        width: 0; height: 0; border: none; background: transparent;
    }}
    QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow,
    QSpinBox::up-arrow, QSpinBox::down-arrow {{ image: none; border: none; width: 0; height: 0; }}
    QComboBox {{
        padding: 2px 4px; border: 1px solid {c["input_border"]}; border-radius: 6px;
        background: {c["input_bg"]}; color: {c["text"]}; min-width: 120px; font-size: 14px;
    }}
    QComboBox:focus {{ border-color: {c["input_focus"]}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox::down-arrow {{ border: none; }}
    QComboBox QAbstractItemView {{
        background-color: {c["input_bg"]}; color: {c["text"]};
        border: 1px solid {c["border"]}; border-radius: 6px;
        selection-background-color: {c["sidebar_hover"]};
        selection-color: {c["accent"]}; outline: none;
    }}
    QCheckBox {{ color: {c["text"]}; spacing: 6px; font-size: 14px; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px; border-radius: 4px;
        border: 2px solid {c["input_border"]}; background: {c["input_bg"]};
    }}
    QCheckBox::indicator:checked {{ background-color: {c["checkbox_bg"]}; border-color: {c["checkbox_bg"]}; }}
    QCheckBox#smallCheckbox {{ font-size: 12px; spacing: 3px; }}
    QCheckBox#smallCheckbox::indicator {{ width: 14px; height: 14px; border-radius: 3px; }}
    QLabel {{ color: {c["text"]}; }}
    QLabel#labelSecondary {{ color: {c["text_secondary"]}; }}
    QLabel#accentLabel {{ color: {c["accent"]}; }}
    QLabel#unitLabel {{ color: {c["accent"]}; font-size: 12px; font-weight: 600; }}
    QLabel#fixedStatLabel {{ color: {c["text_secondary"]}; font-size: 13px; }}
    QLabel#fixedStatValue {{ color: {c["accent"]}; font-size: 14px; font-weight: 600; }}
    QFormLayout {{ spacing: 10px; }}
    QPushButton#backButton {{
        background-color: transparent; border: 1px solid {c["border"]};
        color: {c["text_secondary"]}; padding: 2px 8px; border-radius: 6px; font-size: 13px;
    }}
    QPushButton#backButton:hover {{ border-color: {c["accent"]}; color: {c["accent"]}; }}
    QPushButton#backButton[active="true"] {{
        border-color: {c["accent"]}; color: {c["accent"]}; background-color: {c["nav_selected_bg"]};
    }}
    QPushButton#addButton {{
        background-color: {c["btn_bg"]}; color: white; border: none;
        padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;
    }}
    QPushButton#addButton:hover {{ background-color: {c["btn_hover"]}; }}
    QPushButton#itemAddBtn {{
        background-color: {c["btn_bg"]}; color: white; border: none;
        padding: 2px 8px; border-radius: 6px; font-size: 14px; font-weight: 600;
    }}
    QPushButton#itemAddBtn:hover {{ background-color: {c["btn_hover"]}; }}
    QListWidget#attrList {{
        background-color: {c["input_bg"]}; border: 1px solid {c["border"]};
        border-radius: 6px; color: {c["text"]}; font-size: 13px; padding: 4px; min-height: 200px;
    }}
    QListWidget#attrList::item {{
        padding: 0px; border-radius: 4px; margin: 2px 0; min-height: 42px; border: none;
    }}
    QListWidget#attrList::item:hover {{ background-color: {c["sidebar_hover"]}; }}
    QListWidget#attrList::item:selected {{ background-color: transparent; border: none; }}
    QPushButton#itemLockBtn {{
        background-color: {c["input_border"]}; color: {c["text"]};
        border: none; border-radius: 4px; font-size: 12px;
        padding: 3px 6px;
    }}
    QPushButton#itemLockBtn:hover {{ background-color: {c["accent"]}; color: white; }}
    QPushButton#itemDeleteBtn {{
        background-color: #c0392b; color: white;
        border: none; border-radius: 4px; font-size: 12px;
        padding: 3px 6px;
    }}
    QPushButton#itemDeleteBtn:hover {{ background-color: #e74c3c; }}
    QPushButton#itemDeleteBtn:disabled {{ background-color: {c["input_border"]}; color: {c["text_secondary"]}; }}
    QDoubleSpinBox#itemValueSpin:disabled {{ color: {c["text_secondary"]}; }}
    QLineEdit#nameEdit {{
        border: 1px solid {c["input_border"]}; border-radius: 4px;
        background: {c["input_bg"]}; font-size: 14px; padding: 2px 4px; color: {c["text"]};
    }}
    QLineEdit#nameEdit:focus {{ border: 1px solid {c["input_focus"]}; }}
    QTextEdit {{
        border: 1px solid {c["input_border"]}; border-radius: 6px;
        background: {c["input_bg"]}; color: {c["text"]}; font-size: 14px;
        padding: 6px;
    }}
    QTextEdit:focus {{ border-color: {c["input_focus"]}; }}
    QLabel#seqLabel {{
        border: 1px solid {c["input_border"]}; border-radius: 4px; padding: 4px;
        color: {c["accent"]}; font-size: 12px; font-weight: 600;
    }}
    QPushButton#calcBtn {{
        background-color: {c["btn_bg"]}; color: white; border: none;
        padding: 6px 24px; font-size: 16px; font-weight: 600; border-radius: 8px;
    }}
    QPushButton#calcBtn:hover {{ background-color: {c["btn_hover"]}; }}
    QLabel#resultValue {{ color: {c["accent"]}; font-size: 14px; font-weight: 700; padding: 4px 0px; }}
    QFrame#indepGroupFrame {{
        background: {c["bg_card"]}; border: 1px solid {c["border"]};
        border-radius: 4px; padding: 6px 10px;
    }}
    QFrame#resultCard {{
        background-color: {c["bg_card"]}; border: 1px solid {c["border"]};
        border-radius: 6px; padding: 4px 6px;
    }}
    QFrame#resultCard:hover {{
        border-color: {c["accent"]}; background-color: rgba(128,128,144,0.04);
    }}
    QLabel#resultLabel {{ color: {c["text_secondary"]}; font-size: 14px; }}
    QLabel#resultHeader {{ color: {c["text"]}; font-size: 18px; font-weight: 700; }}
    QFrame#processZoneFrame {{
        background-color: {c["input_bg"]}; border: 1px solid {c["border"]};
        border-radius: 6px; padding: 4px 0;
    }}
    QLabel#processBracket {{ color: {c["accent"]}; font-size: 18px; font-weight: 700; }}
    QLabel#processZoneTitle {{ color: {c["accent"]}; font-size: 14px; font-weight: 600; }}
    QLabel#processZoneText {{ color: {c["text"]}; font-size: 14px; }}
    QPushButton#processLink {{
        color: {c["accent"]}; font-size: 14px; font-weight: 600;
        background: transparent; border: none; padding: 0px 2px;
        text-decoration: underline;
    }}
    QPushButton#processLink:hover {{ color: {c["btn_hover"]}; text-decoration: underline; }}
    QPushButton#processCopyBtn {{
        color: {c["text_secondary"]}; font-size: 12px; font-weight: 400;
        background-color: {c["input_bg"]}; border: 1px solid {c["border"]};
        border-radius: 4px; padding: 2px 6px;
    }}
    QPushButton#processCopyBtn:hover {{ color: {c["accent"]}; border-color: {c["accent"]}; }}
    QLabel#processLabel {{
        background-color: transparent; border: none; color: {c["text"]};
        font-size: 14px; padding: 4px 0;
    }}
    QLabel#processText {{ color: {c["text_secondary"]}; font-size: 14px; padding: 8px; }}
    QTableWidget#attrTable {{
        background-color: transparent; border: 1px solid {c["border"]};
        border-radius: 6px; color: {c["text"]}; font-size: 13px; gridline-color: transparent;
    }}
    QTableWidget#attrTable::item {{ padding: 4px; border: none; }}
    QTableWidget#attrTable::item:alternate {{ background-color: {c["alt_row"]}; }}
    QTableWidget#attrTable QLineEdit {{
        border: 1px solid {c["border"]}; border-radius: 3px;
        padding: 1px 2px; background: transparent; color: {c["text"]};
        margin: 1px 2px;
    }}
    QTableWidget#attrTable QDoubleSpinBox {{
        border: 1px solid {c["border"]}; border-radius: 3px;
        padding: 1px 2px; background: transparent; color: {c["text"]};
        margin: 1px 2px;
    }}
    QTableWidget#attrTable QComboBox {{
        border: 1px solid {c["border"]}; border-radius: 3px;
        padding: 1px 2px; background: transparent; color: {c["text"]};
        margin: 1px 2px;
    }}
    QTableWidget#defTable {{
        background-color: transparent; border: 1px solid {c["border"]};
        border-radius: 6px; color: {c["text"]}; font-size: 13px; gridline-color: transparent;
    }}
    QTableWidget#defTable::item {{ padding: 6px; border: none; }}
    QTableWidget#defTable::item:alternate {{ background-color: {c["alt_row"]}; }}
    QHeaderView::section {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["bg_card"]}, stop:1 {c["header_grad_end"]});
        border: none; border-right: 1px solid {c["border"]};
        border-bottom: 2px solid {c["accent"]};
        color: {c["text_secondary"]}; padding: 10px 12px; font-weight: 600; font-size: 13px;
    }}
    QHeaderView::section:last {{ border-right: none; }}
    QScrollBar:vertical {{
        background: transparent; width: 6px; border-radius: 3px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c["scrollbar_handle"]}; border-radius: 3px; min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c["scrollbar_handle_hover"]}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QScrollBar:horizontal {{ background: {c["bg"]}; height: 0px; border: none; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}

    QTabWidget::pane {{
        border: 1px solid {c["border"]};
        background-color: {c["bg_secondary"]};
        border-radius: 4px;
    }}
    QTabBar::tab {{
        background-color: {c["input_bg"]};
        color: {c["text_secondary"]};
        border: 1px solid {c["border"]};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected {{
        background-color: {c["bg_secondary"]};
        color: {c["accent"]};
        border-bottom-color: {c["bg_secondary"]};
    }}
    QTabBar::tab:hover {{
        background-color: {c["sidebar_hover"]};
        color: {c["text"]};
    }}

    QComboBox#algorithmCombo {{
        font-size: 12px;
        padding: 3px 6px;
        text-align: center;
        border: 1px solid {c["input_border"]};
        border-radius: 4px;
        background: {c["input_bg"]};
        color: {c["text"]};
    }}

    QComboBox#algorithmCombo:focus {{
        border-color: {c["input_focus"]};
    }}

    QComboBox#algorithmCombo::drop-down {{
        width: 16px;
        border: none;
    }}

    QComboBox#algorithmCombo QAbstractItemView {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 4px;
        selection-background-color: {c["sidebar_hover"]};
        selection-color: {c["accent"]};
        text-align: center;
    }}

    /* —— 弹窗样式 —— */
    QDialog {{
        background-color: {c["bg_secondary"]};
    }}
    QDialog QLabel {{
        color: {c["text"]};
    }}
    QDialog QPushButton {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 13px;
    }}
    QDialog QPushButton:hover {{
        background-color: {c["sidebar_hover"]};
        border-color: {c["accent"]};
    }}
    QDialog QListWidget {{
        background-color: {c["input_bg"]};
        border: 1px solid {c["border"]};
        border-radius: 6px;
        color: {c["text"]};
        font-size: 13px;
        padding: 4px;
    }}
    QDialog QListWidget::item {{
        padding: 8px;
        border-radius: 4px;
    }}
    QDialog QListWidget::item:hover {{
        background-color: {c["sidebar_hover"]};
    }}
    QDialog QListWidget::item:selected {{
        background-color: {c["nav_selected_bg"]};
        color: {c["accent"]};
    }}
    QInputDialog {{
        background-color: {c["bg_secondary"]};
    }}
    QInputDialog QLabel {{
        color: {c["text"]};
    }}
    QInputDialog QLineEdit {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 14px;
    }}
    QInputDialog QPushButton {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 13px;
    }}
    QInputDialog QPushButton:hover {{
        background-color: {c["sidebar_hover"]};
        border-color: {c["accent"]};
    }}
    QMessageBox {{
        background-color: {c["bg_secondary"]};
    }}
    QMessageBox QLabel {{
        color: {c["text"]};
    }}
    QMessageBox QPushButton {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 13px;
        min-width: 80px;
    }}
    QMessageBox QPushButton:hover {{
        background-color: {c["sidebar_hover"]};
        border-color: {c["accent"]};
    }}
    QFileDialog {{
        background-color: {c["bg_secondary"]};
    }}
    QFileDialog QLabel {{
        color: {c["text"]};
    }}
    QFileDialog QLineEdit {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 4px;
        padding: 6px 10px;
    }}
    QFileDialog QPushButton {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 13px;
    }}
    QFileDialog QPushButton:hover {{
        background-color: {c["sidebar_hover"]};
        border-color: {c["accent"]};
    }}
    QFileDialog QTreeView {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 4px;
    }}
    QFileDialog QTreeView::item:hover {{
        background-color: {c["sidebar_hover"]};
    }}
    QFileDialog QTreeView::item:selected {{
        background-color: {c["nav_selected_bg"]};
        color: {c["accent"]};
    }}
    QFileDialog QComboBox {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 4px;
        padding: 6px 10px;
    }}
    QFileDialog QComboBox QAbstractItemView {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        selection-background-color: {c["sidebar_hover"]};
        selection-color: {c["accent"]};
    }}
    QFileDialog QListView {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
    }}
    QFileDialog QListView::item:hover {{
        background-color: {c["sidebar_hover"]};
    }}
    QFileDialog QListView::item:selected {{
        background-color: {c["nav_selected_bg"]};
        color: {c["accent"]};
    }}

    /* —— 预设构建器 / 预设加载器 —— */
    QFrame#presetCard {{
        border: 1px solid {c["border"]}; border-radius: 10px;
        background: {c["bg_card"]};
    }}
    QFrame#presetCard:hover {{
        border-color: {c["accent"]};
        background: {c["sidebar_hover"]};
    }}
    QFrame#effectRow {{
        background: {c["input_bg"]}; border: 1px solid {c["border"]};
        border-radius: 6px;
    }}
    QFrame#effectRow:hover {{
        border-color: {c["accent"]};
    }}
    QFrame#indepGroupFrame {{
        background: {c["bg_card"]}; border: 1px solid {c["border"]};
        border-radius: 6px; padding: 6px 10px;
    }}
    QPushButton#addGreenBtn {{
        background-color: {c["add_btn"]}; color: white; border: none;
        padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;
    }}
    QPushButton#addGreenBtn:hover {{ background-color: {c["btn_hover"]}; }}
    QPushButton#delRedBtn {{
        background-color: {c["del_btn"]}; color: white; border: none;
        border-radius: 4px; font-size: 12px;
    }}
    QPushButton#delRedBtn:hover {{ background-color: {c["btn_hover"]}; }}
    QPushButton#presetSaveBtn {{
        background-color: {c["btn_bg"]}; color: white; border: none;
        padding: 6px 16px; font-size: 14px; font-weight: 600; border-radius: 8px;
    }}
    QPushButton#presetSaveBtn:hover {{ background-color: {c["btn_hover"]}; }}
    QDialog QPushButton#presetSaveBtn {{
        background-color: {c["btn_bg"]}; color: white; border: none;
        padding: 8px 24px; font-size: 14px; font-weight: 600; border-radius: 8px;
    }}
    QDialog QPushButton#presetSaveBtn:hover {{ background-color: {c["btn_hover"]}; }}
    QPushButton#presetEntryCard {{
        border: 1px solid {c["border"]}; border-radius: 14px;
        background: {c["bg_card"]};
    }}
    QPushButton#presetEntryCard:hover {{
        border-color: {c["accent"]}; background: {c["sidebar_hover"]};
    }}
    QWidget#cardTitleBar {{
        background: {c["card_title_bg"]}; border-radius: 9px 9px 0 0;
    }}
    QWidget#presetMainPage {{
        background: transparent;
    }}
    """
