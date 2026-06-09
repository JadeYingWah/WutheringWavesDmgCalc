# -*- coding: utf-8 -*-
"""
测试运行器 — GUI 窗口版
======================
独立 PyQt6 窗口，点击按钮运行测试，实时显示结果。
不依赖主程序 WWDmgCalc.py，可单独运行。
"""

import subprocess
import sys
import os
import re

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QProgressBar, QGroupBox,
    QGridLayout, QLineEdit, QDialog, QDialogButtonBox,
    QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor

# ---- 路径配置 ----
# 脚本位于 tests/ 子目录，项目根目录为上一级
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(PROJECT_DIR, "tests")
PYTHON = sys.executable


# ---- 测试任务定义 ----
CATEGORIES = [
    ("全部测试", f'"{TESTS_DIR}" -v --tb=short --color=no'),
    ("伤害公式 (61)", f'"{TESTS_DIR}\\test_damage_formula.py" -v --tb=short --color=no'),
    ("存档格式 (16)", f'"{TESTS_DIR}\\test_save_format.py" -v --tb=short --color=no'),
    ("防御乘区", f'"{TESTS_DIR}\\test_damage_formula.py::TestDefenseZone" -v --tb=short --color=no'),
    ("抗性乘区", f'"{TESTS_DIR}\\test_damage_formula.py::TestResistanceZone" -v --tb=short --color=no'),
    ("独立乘区", f'"{TESTS_DIR}\\test_damage_formula.py::TestIndepZone" -v --tb=short --color=no'),
    ("基础乘区", f'"{TESTS_DIR}\\test_damage_formula.py::TestBaseZone" -v --tb=short --color=no'),
    ("暴击+倍率", f'"{TESTS_DIR}\\test_damage_formula.py::TestCritZone {TESTS_DIR}\\test_damage_formula.py::TestMultZone" -v --tb=short --color=no'),
    ("筛选匹配", f'"{TESTS_DIR}\\test_damage_formula.py::TestFilterMatching" -v --tb=short --color=no'),
    ("完整伤害", f'"{TESTS_DIR}\\test_damage_formula.py::TestFullDamageFormula" -v --tb=short --color=no'),
    ("边界条件", f'"{TESTS_DIR}\\test_damage_formula.py::TestEdgeCases" -v --tb=short --color=no'),
    ("常量定义", f'"{TESTS_DIR}\\test_damage_formula.py::TestGameConstants" -v --tb=short --color=no'),
]


# ============================================================
# 后台线程：跑 pytest 不卡 UI
# ============================================================

class TestRunner(QThread):
    line_ready = pyqtSignal(str)
    finished = pyqtSignal(int, str, str)  # exit_code, summary_line, full_output

    def __init__(self, args):
        super().__init__()
        self._args = args

    def run(self):
        cmd = f'"{PYTHON}" -m pytest {self._args}'
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, text=True, encoding="utf-8", errors="replace",
        )
        full_output = []
        summary = ""
        for line in proc.stdout:
            line = line.rstrip("\n").rstrip("\r")
            full_output.append(line)
            self.line_ready.emit(line)
            if "passed" in line.lower() or "failed" in line.lower():
                summary = line
        proc.wait()
        self.finished.emit(proc.returncode, summary, "\n".join(full_output))


# ============================================================
# 主窗口
# ============================================================

class TestRunnerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WutheringWavesDmgCalc — 测试运行器")
        self.setMinimumSize(900, 680)
        self.resize(1000, 720)

        # 主题色（和主程序暗色主题一致）
        self.colors = {
            "bg": "#121926",
            "surface": "#182230",
            "card": "#1e3048",
            "accent": "#e94560",
            "accent2": "#5070e8",
            "text": "#e3e5ea",
            "text2": "#939aa8",
            "green": "#4caf50",
            "red": "#f44336",
            "yellow": "#ffb74d",
            "border": "#263248",
        }

        self._runner = None
        self._build_ui()
        self._apply_theme()

    # ---- UI 构建 ----

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # === 标题行 ===
        header = QHBoxLayout()
        title = QLabel("WutheringWavesDmgCalc 测试运行器")
        title.setObjectName("windowTitle")
        title.setStyleSheet(f"font-size:18px; font-weight:700; color:{self.colors['text']};")
        header.addWidget(title)
        header.addStretch()

        self.status_label = QLabel("就绪 — 点击按钮开始测试")
        self.status_label.setStyleSheet(f"color:{self.colors['text2']}; font-size:12px;")
        header.addWidget(self.status_label)
        root.addLayout(header)

        # === 按钮区（可滚动，避免撑爆窗口高度）===
        btn_group = QGroupBox("测试类型")
        btn_group.setObjectName("testGroup")
        btn_outer = QVBoxLayout(btn_group)
        btn_outer.setContentsMargins(0, 0, 0, 0)

        btn_scroll = QScrollArea()
        btn_scroll.setObjectName("btnScroll")
        btn_scroll.setWidgetResizable(True)
        btn_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        btn_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        btn_scroll.setMaximumHeight(150)
        btn_scroll.setStyleSheet(
            f"QScrollArea#btnScroll {{ background: transparent; border: none; }}"
            f"QScrollBar:vertical {{"
            f"  background: {self.colors['surface']}; width: 6px; border-radius: 3px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {self.colors['border']}; border-radius: 3px; min-height: 30px;"
            f"}}"
            f"QScrollBar::handle:vertical:hover {{ background: {self.colors['text2']}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}"
        )

        btn_container = QWidget()
        btn_container.setObjectName("btnContainer")
        grid = QGridLayout(btn_container)
        grid.setContentsMargins(8, 2, 8, 2)
        grid.setSpacing(6)

        for i, (label, args) in enumerate(CATEGORIES):
            btn = QPushButton(label)
            btn.setObjectName("testBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda checked, a=args, l=label: self._start_test(a, l))
            row = i // 4
            col = i % 4
            grid.addWidget(btn, row, col)

        btn_scroll.setWidget(btn_container)
        btn_outer.addWidget(btn_scroll)
        root.addWidget(btn_group)

        # === 进度条 ===
        self.progress = QProgressBar()
        self.progress.setObjectName("testProgress")
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        root.addWidget(self.progress)

        # === 输出区 ===
        out_group = QGroupBox("测试输出")
        out_layout = QVBoxLayout(out_group)
        out_layout.setContentsMargins(4, 4, 4, 4)

        self.output = QTextEdit()
        self.output.setObjectName("testOutput")
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 11))
        self.output.setStyleSheet(
            f"QTextEdit#testOutput {{"
            f"  background:{self.colors['surface']};"
            f"  color:{self.colors['text']};"
            f"  border:1px solid {self.colors['border']};"
            f"  border-radius:6px;"
            f"  padding:8px;"
            f"}}"
        )
        self.output.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        out_layout.addWidget(self.output)
        root.addWidget(out_group, stretch=1)

        # === 自定义输入栏（在输出框下方）===
        custom_bar = QHBoxLayout()
        custom_bar.setSpacing(6)
        custom_label = QLabel("自定义参数:")
        custom_label.setStyleSheet(f"color:{self.colors['text2']}; font-size:12px;")
        custom_bar.addWidget(custom_label)

        self.custom_input = QLineEdit()
        self.custom_input.setObjectName("customInput")
        self.custom_input.setPlaceholderText(
            "直接输入 pytest 参数，如 -k defense --lf，回车运行"
        )
        self.custom_input.setFont(QFont("Consolas", 11))
        self.custom_input.setStyleSheet(
            f"QLineEdit#customInput {{"
            f"  background:{self.colors['surface']};"
            f"  color:{self.colors['text']};"
            f"  border:1px solid {self.colors['border']};"
            f"  border-radius:5px;"
            f"  padding:5px 10px;"
            f"}}"
            f"QLineEdit#customInput:focus {{"
            f"  border-color:{self.colors['accent']};"
            f"}}"
        )
        self.custom_input.returnPressed.connect(self._run_custom)
        custom_bar.addWidget(self.custom_input, stretch=1)

        run_custom_btn = QPushButton("运行")
        run_custom_btn.setObjectName("testBtn")
        run_custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_custom_btn.clicked.connect(self._run_custom)
        custom_bar.addWidget(run_custom_btn)
        root.addLayout(custom_bar)

        # === 底部状态 ===
        bottom = QHBoxLayout()
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color:{self.colors['text2']}; font-size:12px;")
        bottom.addWidget(self.stats_label)
        bottom.addStretch()

        manual_btn = QPushButton("使用手册")
        manual_btn.setObjectName("smallBtn")
        manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manual_btn.clicked.connect(self._show_manual)
        bottom.addWidget(manual_btn)

        clear_btn = QPushButton("清空输出")
        clear_btn.setObjectName("smallBtn")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(lambda: self.output.clear())
        bottom.addWidget(clear_btn)
        root.addLayout(bottom)

    # ---- 主题 ----

    def _apply_theme(self):
        c = self.colors
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {c['bg']};
            }}
            QGroupBox#testGroup {{
                font-size: 13px; font-weight: 600;
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 8px;
                margin-top: 12px;
                padding: 16px 12px 10px 12px;
            }}
            QGroupBox#testGroup::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {c['text2']};
            }}
            QPushButton#testBtn {{
                background: {c['card']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton#testBtn:hover {{
                background: {c['accent']};
                color: #fff;
                border-color: {c['accent']};
            }}
            QPushButton#testBtn:pressed {{
                background: {c['accent2']};
            }}
            QPushButton#smallBtn {{
                background: transparent;
                color: {c['text2']};
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 4px 14px;
                font-size: 11px;
            }}
            QPushButton#smallBtn:hover {{
                color: {c['text']};
                border-color: {c['text2']};
            }}
            QProgressBar#testProgress {{
                background: {c['surface']};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar#testProgress::chunk {{
                background: {c['accent']};
                border-radius: 3px;
            }}
        """)

    # ---- 运行测试 ----

    def _run_custom(self):
        """从输入框读取自定义 pytest 参数并执行"""
        text = self.custom_input.text().strip()
        if not text:
            return
        # 保存到历史（输入框保留内容方便重复跑）
        args = f'"{TESTS_DIR}" {text}'
        self._start_test(args, f"自定义: {text}")

    def _start_test(self, args, label):
        if self._runner and self._runner.isRunning():
            return  # 已经在跑，不重复启动

        self.output.clear()
        self.status_label.setText(f"正在运行: {label} ...")
        self.progress.setVisible(True)
        self.stats_label.setText("")

        self._runner = TestRunner(args)
        self._runner.line_ready.connect(self._on_line)
        self._runner.finished.connect(self._on_finished)
        self._runner.start()

    def _on_line(self, line):
        """实时追加一行到输出框，带颜色高亮"""
        tc = self.output.textCursor()
        tc.movePosition(QTextCursor.MoveOperation.End)

        if "PASSED" in line:
            color = self.colors["green"]
            weight = "normal"
        elif "FAILED" in line:
            color = self.colors["red"]
            weight = "bold"
        elif "ERROR" in line:
            color = self.colors["red"]
            weight = "bold"
        elif line.startswith("="):
            color = self.colors["text2"]
            weight = "normal"
        elif "passed" in line.lower() or "failed" in line.lower():
            color = self.colors["yellow"]
            weight = "bold"
        else:
            color = self.colors["text"]
            weight = "normal"

        html = f'<span style="color:{color}; font-weight:{weight};">{line}</span><br>'
        tc.insertHtml(html)

        # 自动滚动到底部
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_finished(self, exit_code, summary, full_output):
        self.progress.setVisible(False)

        # 解析 passed / failed 数量
        passed = failed = 0
        m = re.search(r'(\d+)\s+passed', summary)
        if m:
            passed = int(m.group(1))
        m = re.search(r'(\d+)\s+failed', summary)
        if m:
            failed = int(m.group(1))

        if exit_code == 0:
            self.status_label.setText(f"[OK] 全部 {passed} 个测试通过")
            self.status_label.setStyleSheet(f"color:{self.colors['green']}; font-size:12px; font-weight:600;")
        else:
            self.status_label.setText(f"[FAIL] {failed} 个失败, {passed} 个通过")
            self.status_label.setStyleSheet(f"color:{self.colors['red']}; font-size:12px; font-weight:600;")

        self.stats_label.setText(f"通过 {passed}  |  失败 {failed}  |  总计 {passed + failed}")

    # ---- 使用手册 ----

    def _show_manual(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("使用手册 — 测试运行器")
        dlg.setMinimumSize(700, 520)
        dlg.resize(760, 560)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {self.colors['bg']};
            }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        c = self.colors
        content = QTextEdit()
        content.setReadOnly(True)
        content.setFont(QFont("Microsoft YaHei", 11))
        content.setStyleSheet(
            f"QTextEdit {{"
            f"  background:{c['surface']}; color:{c['text']};"
            f"  border:1px solid {c['border']}; border-radius:6px;"
            f"  padding:14px;"
            f"}}"
        )
        content.setHtml(f"""
<h2 style='color:{c['accent']}; margin-bottom:4px;'>WutheringWavesDmgCalc 测试运行器</h2>
<p style='color:{c['text2']}; margin-top:0;'><b>版本 v1.0</b> — 为伤害计算器主程序提供自动化测试保障</p>

<hr style='border-color:{c['border']};'>

<h3 style='color:{c['accent2']};'>一、这是什么</h3>
<p>
测试运行器是 WutheringWavesDmgCalc 项目的<b>自动化验证工具</b>。
它会在后台运行 85 个测试用例，逐一检查伤害公式的每个计算环节是否正确——
防御减伤、抗性乘区、独立乘区、基础乘区（攻击/生命/防御）、加成/加深/暴击、
倍率计算、筛选匹配、存档格式等，<b>全部 0.2 秒内完成</b>。
</p>

<hr style='border-color:{c['border']};'>

<h3 style='color:{c['accent2']};'>二、为什么需要</h3>
<p>
主程序 WWDmgCalc.py 有 <b>~10850 行代码、43 个类、11 个页面</b>。
每次修改任何一个公式、常量、筛选规则，都可能<b>连锁影响多个页面的计算结果</b>。
</p>
<p><b>没有测试时：</b></p>
<ul>
  <li>改完公式 → 手动打开程序 → 填数据 → 对照预期 → 容易漏掉边界情况</li>
  <li>存档格式升级 → 旧存档加载崩溃 → 用户发现才知道</li>
  <li>改了筛选规则 → 有的词条漏算 → 数值对不上</li>
</ul>
<p><b>有测试后：</b></p>
<ul>
  <li>改完代码 → 点一下按钮 → 0.2 秒后看到结果</li>
  <li><span style='color:{c['green']};'>全绿</span> = 放心，没搞坏任何东西</li>
  <li><span style='color:{c['red']};'>有红色</span> = 精确告诉你哪个公式、哪个边界条件出问题了</li>
</ul>

<hr style='border-color:{c['border']};'>

<h3 style='color:{c['accent2']};'>三、工作原理</h3>
<p>整个流程分为<b>四层</b>，<b style='color:{c['accent']};'>测试测的是真实代码，不是副本</b>：</p>
<ol>
  <li><b>独立计算模块</b> — <code style='color:{c['accent']};'>damage_calc.py</code> 把所有伤害公式和常量从 GUI 代码中提取出来，<br>
      变成纯 Python 函数（零 GUI 依赖）。公式改了这里，主程序和测试同步生效。</li>
  <li><b>主程序引用</b> — <code style='color:{c['accent']};'>WWDmgCalc.py</code> 中 <code style='color:{c['accent']};'>import damage_calc</code>，<br>
      计算时调用 <code style='color:{c['accent']};'>damage_calc.calc_defense_zone()</code> 等函数。</li>
  <li><b>测试 import 同一模块</b> — <code style='color:{c['accent']};'>tests/test_damage_formula.py</code> 也 <code style='color:{c['accent']};'>from damage_calc import ...</code>，<br>
      用 <code style='color:{c['accent']};'>assert</code> 验证每个公式的正确性。</li>
  <li><b>pytest 自动执行</b> — 测试运行器调用 <code style='color:{c['accent']};'>python -m pytest</code>（后台线程，不卡 UI），<br>
      实时捕获每一行输出，带颜色显示。</li>
</ol>

<hr style='border-color:{c['border']};'>

<h3 style='color:{c['accent2']};'>四、怎么用</h3>

<h4 style='color:{c['text']}; margin-bottom:4px;'>4.1 窗口布局</h4>
<table style='width:100%; border-collapse:collapse; color:{c['text']}; font-size:12px;'>
<tr><td style='padding:3px 8px; width:90px;'><b>顶部标题栏</b></td>
    <td style='padding:3px 8px;'>左侧标题，右侧实时状态 — 就绪/正在运行/通过/失败</td></tr>
<tr><td style='padding:3px 8px;'><b>按钮区</b></td>
    <td style='padding:3px 8px;'>12 个分类按钮 + 可滚动（最大高度 150px），鼠标滚轮翻阅</td></tr>
<tr><td style='padding:3px 8px;'><b>进度条</b></td>
    <td style='padding:3px 8px;'>运行时显示红色滚动条，测试结束自动隐藏</td></tr>
<tr><td style='padding:3px 8px;'><b>输出区</b></td>
    <td style='padding:3px 8px;'>实时彩色输出，自动滚到底部</td></tr>
<tr><td style='padding:3px 8px;'><b>自定义输入栏</b></td>
    <td style='padding:3px 8px;'>在输出框下方，直接输 pytest 参数，回车或点"运行"执行</td></tr>
<tr><td style='padding:3px 8px;'><b>底栏</b></td>
    <td style='padding:3px 8px;'>左侧统计（通过/失败/总计），右侧 [使用手册] [清空输出]</td></tr>
</table>

<h4 style='color:{c['text']}; margin-bottom:4px;'>4.2 输出颜色含义</h4>
<table style='width:100%; border-collapse:collapse; color:{c['text']}; font-size:12px;'>
<tr><td style='padding:3px 8px;'><span style='color:{c['green']};'>■ 绿色</span></td>
    <td style='padding:3px 8px;'>PASSED — 测试通过</td></tr>
<tr><td style='padding:3px 8px;'><span style='color:{c['red']};'>■ 红色加粗</span></td>
    <td style='padding:3px 8px;'>FAILED / ERROR — 测试失败或异常</td></tr>
<tr><td style='padding:3px 8px;'><span style='color:{c['yellow']};'>■ 黄色加粗</span></td>
    <td style='padding:3px 8px;'>汇总行 — 如 "85 passed in 0.20s"</td></tr>
<tr><td style='padding:3px 8px;'><span style='color:{c['text2']};'>■ 灰色</span></td>
    <td style='padding:3px 8px;'>分隔线、框架信息</td></tr>
</table>

<h4 style='color:{c['text']}; margin-bottom:4px;'>4.3 按钮区 — 12 个快捷按钮</h4>
<table style='width:100%; border-collapse:collapse; color:{c['text']}; font-size:12px;'>
<tr><td style='padding:3px 8px;'><b>全部测试</b></td><td style='padding:3px 8px;'>跑 tests\ 下所有 85 个用例</td></tr>
<tr><td style='padding:3px 8px;'><b>伤害公式</b></td><td style='padding:3px 8px;'>仅 test_damage_formula.py（71 个）</td></tr>
<tr><td style='padding:3px 8px;'><b>存档格式</b></td><td style='padding:3px 8px;'>仅 test_save_format.py（16 个）</td></tr>
<tr><td style='padding:3px 8px;'><b>防御乘区</b></td><td style='padding:3px 8px;'>TestDefenseZone — 等级/无视/截断</td></tr>
<tr><td style='padding:3px 8px;'><b>抗性乘区</b></td><td style='padding:3px 8px;'>TestResistanceZone — 6元素/预设/clamp</td></tr>
<tr><td style='padding:3px 8px;'><b>独立乘区</b></td><td style='padding:3px 8px;'>TestIndepZone — 组加法×组间乘法</td></tr>
<tr><td style='padding:3px 8px;'><b>基础乘区</b></td><td style='padding:3px 8px;'>TestBaseZone — 攻/生/防</td></tr>
<tr><td style='padding:3px 8px;'><b>暴击+倍率</b></td><td style='padding:3px 8px;'>TestCritZone + TestMultZone</td></tr>
<tr><td style='padding:3px 8px;'><b>筛选匹配</b></td><td style='padding:3px 8px;'>TestFilterMatching — 元素/技能/效应</td></tr>
<tr><td style='padding:3px 8px;'><b>完整伤害</b></td><td style='padding:3px 8px;'>TestFullDamageFormula — 端到端</td></tr>
<tr><td style='padding:3px 8px;'><b>边界条件</b></td><td style='padding:3px 8px;'>TestEdgeCases — 负数/零值/多组</td></tr>
<tr><td style='padding:3px 8px;'><b>常量定义</b></td><td style='padding:3px 8px;'>TestGameConstants — 常量完整性</td></tr>
</table>

<h4 style='color:{c['text']}; margin-bottom:4px;'>4.4 自定义参数 — 常用 pytest 指令</h4>
<table style='width:100%; border-collapse:collapse; color:{c['text']}; font-size:12px;'>
<tr style='background:{c['surface']};'><td style='padding:4px 8px; width:180px;'><code style='color:{c['accent']};'>-k defense</code></td>
    <td style='padding:4px 8px;'>只跑名字含 "defense" 的测试（关键词匹配）</td></tr>
<tr><td style='padding:4px 8px;'><code style='color:{c['accent']};'>-k "crit or bonus"</code></td>
    <td style='padding:4px 8px;'>跑含 "crit" 或 "bonus" 的测试</td></tr>
<tr style='background:{c['surface']};'><td style='padding:4px 8px;'><code style='color:{c['accent']};'>-k "not defense"</code></td>
    <td style='padding:4px 8px;'>排除含 "defense" 的测试</td></tr>
<tr><td style='padding:4px 8px;'><code style='color:{c['accent']};'>--lf</code></td>
    <td style='padding:4px 8px;'>只跑上次失败的测试（--last-failed）</td></tr>
<tr style='background:{c['surface']};'><td style='padding:4px 8px;'><code style='color:{c['accent']};'>--ff</code></td>
    <td style='padding:4px 8px;'>先跑上次失败的，再跑其余的（--failed-first）</td></tr>
<tr><td style='padding:4px 8px;'><code style='color:{c['accent']};'>-x</code></td>
    <td style='padding:4px 8px;'>遇到第一个失败立即停止</td></tr>
<tr style='background:{c['surface']};'><td style='padding:4px 8px;'><code style='color:{c['accent']};'>--maxfail=3</code></td>
    <td style='padding:4px 8px;'>最多 3 个失败后就停止</td></tr>
<tr><td style='padding:4px 8px;'><code style='color:{c['accent']};'>-q</code></td>
    <td style='padding:4px 8px;'>静默模式，只显示点和最终汇总</td></tr>
<tr style='background:{c['surface']};'><td style='padding:4px 8px;'><code style='color:{c['accent']};'>-s</code></td>
    <td style='padding:4px 8px;'>允许 print() 输出显示（调试用）</td></tr>
<tr><td style='padding:4px 8px;'><code style='color:{c['accent']};'>--tb=long</code></td>
    <td style='padding:4px 8px;'>失败时显示完整堆栈（默认 short）</td></tr>
<tr style='background:{c['surface']};'><td style='padding:4px 8px;'><code style='color:{c['accent']};'>--tb=no</code></td>
    <td style='padding:4px 8px;'>失败时不显示堆栈，只看结果</td></tr>
<tr><td style='padding:4px 8px;'><code style='color:{c['accent']};'>--co</code></td>
    <td style='padding:4px 8px;'>只收集不运行（看看哪些测试会被选中）</td></tr>
<tr style='background:{c['surface']};'><td style='padding:4px 8px;'><code style='color:{c['accent']};'>-k defense -x -q</code></td>
    <td style='padding:4px 8px;'>组合使用：只跑防御相关，遇错即停，静默输出</td></tr>
</table>

<h4 style='color:{c['text']}; margin-bottom:4px;'>4.5 命令行快捷启动</h4>
<table style='width:100%; border-collapse:collapse; color:{c['text']}; font-size:12px;'>
<tr><td style='padding:3px 8px; width:250px;'><code style='color:{c['accent']};'>python tests/run_tests_gui.py</code></td>
    <td style='padding:3px 8px;'>打开窗口，自动跑全部测试</td></tr>
<tr><td style='padding:3px 8px;'><code style='color:{c['accent']};'>python tests/run_tests_gui.py 0</code></td>
    <td style='padding:3px 8px;'>全部测试</td></tr>
<tr><td style='padding:3px 8px;'><code style='color:{c['accent']};'>python tests/run_tests_gui.py 1</code></td>
    <td style='padding:3px 8px;'>伤害公式</td></tr>
<tr><td style='padding:3px 8px;'><code style='color:{c['accent']};'>python tests/run_tests_gui.py 2</code></td>
    <td style='padding:3px 8px;'>存档格式</td></tr>
<tr><td style='padding:3px 8px;'><code style='color:{c['accent']};'>python tests/run_tests_gui.py 3</code></td>
    <td style='padding:3px 8px;'>防御乘区</td></tr>
<tr><td style='padding:3px 8px;'><code style='color:{c['accent']};'>python tests/run_tests_gui.py 4</code></td>
    <td style='padding:3px 8px;'>抗性乘区</td></tr>
<tr><td style='padding:3px 8px;' colspan=2 style='color:{c['text2']};'>...以此类推到 11，与按钮顺序一致。</td></tr>
</table>

<hr style='border-color:{c['border']};'>

<h3 style='color:{c['accent2']};'>五、测试文件结构</h3>
<pre style='color:{c['text']}; background:{c['surface']}; padding:8px; border-radius:4px;'>
项目结构:
damage_calc.py                  # ★ 独立计算引擎（纯函数，零 GUI）
│                                 主程序和测试共同 import 这个文件
├── tests/
│   ├── __init__.py
│   ├── run_tests_gui.py          # 本程序 — GUI 测试运行器
│   ├── test_damage_formula.py    # 伤害公式测试（71 个），覆盖：
│   │   ├── TestDefenseZone       #   防御乘区（等级/无视）
│   │   ├── TestResistanceZone    #   抗性乘区（6元素/预设/clamp）
│   │   ├── TestIndepZone         #   独立乘区（组加法+组间乘法）
│   │   ├── TestBaseZone          #   基础乘区（攻/生/防）
│   │   ├── TestBonusZone         #   加成乘区
│   │   ├── TestDeepenZone        #   加深乘区
│   │   ├── TestCritZone          #   暴击乘区（150%底/5%底）
│   │   ├── TestMultZone          #   倍率乘区（增加+增幅）
│   │   ├── TestFullDamageFormula #   完整伤害端到端
│   │   ├── TestFilterMatching    #   元素/技能/效应筛选
│   │   ├── TestGameConstants     #   常量完整性
│   │   └── TestEdgeCases         #   边界条件
│   └── test_save_format.py       # 存档格式测试（14 个）
└── error_handler/
    ├── error_viewer.py            # 外部错误报告程序
    └── test_crash.py              # 闪退测试脚本

</pre>

<hr style='border-color:{c['border']};'>

<p style='color:{c['text2']}; font-size:11px;'>
<b style='color:{c['accent']};'>核心设计：</b>damage_calc.py 是唯一真相来源。
主程序（WWDmgCalc.py）和测试（tests/）都 import 它。
改了公式 → 两边同步生效 → 测试立刻能验证对错。
</p>
        """)
        layout.addWidget(content, stretch=1)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dlg.reject)
        btn_box.setStyleSheet(f"""
            QPushButton {{
                background:{c['card']}; color:{c['text']};
                border:1px solid {c['border']}; border-radius:5px;
                padding:6px 20px; font-size:12px;
            }}
            QPushButton:hover {{
                background:{c['accent']}; color:#fff; border-color:{c['accent']};
            }}
        """)
        layout.addWidget(btn_box)

        dlg.exec()


# ============================================================
# 入口
# ============================================================

def main():
    # ---- 命令行参数: python tests/run_tests_gui.py 3  →  直接跑第 3 项 ----
    auto_index = None
    if len(sys.argv) > 1:
        try:
            auto_index = int(sys.argv[1])
        except ValueError:
            print(f"用法: python tests/run_tests_gui.py [0-{len(CATEGORIES)-1}]")
            print("  0=全部测试  1=伤害公式  2=存档格式 ...")
            print("  不传参数则打开窗口")
            sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = TestRunnerWindow()
    window.show()

    if auto_index is not None and 0 <= auto_index < len(CATEGORIES):
        label, args = CATEGORIES[auto_index]
        QTimer.singleShot(200, lambda: window._start_test(args, label))
    else:
        # 默认启动时自动跑全部测试
        QTimer.singleShot(300, lambda: window._start_test(
            f'"{TESTS_DIR}" -v --tb=short --color=no', "全部测试"
        ))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
