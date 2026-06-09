# -*- coding: utf-8 -*-
"""
外部错误日志测试脚本
====================

用法：
    双击运行此文件 → 弹出错误报告窗口 → 同时写入 error_log.json

验证：
    1. 运行此脚本，应看到错误报告窗口（PyQt6 / Tkinter / 记事本，三档降级）
    2. 窗口内显示时间、摘要、完整 traceback

清理：
    打开主程序 → 错误日志 → 清除日志
    或删除 config/error_log.json
"""

import sys, os, traceback, subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import WWDmgCalc as app

def _crash_handler(exc_type, exc_value, exc_tb):
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    app._add_log_entry("CRITICAL", f"程序异常退出: {exc_value}", tb_text)

    # 启动外部错误报告程序
    viewer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_viewer.py")
    try:
        subprocess.Popen([sys.executable, viewer_path, "--crash"],
                        creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass

sys.excepthook = _crash_handler

# 模拟崩溃（捕获异常避免显示 traceback，只验证处理链路）
print("=" * 50)
print("  外部错误报告 功能测试")
print("=" * 50)
print()
print("模拟闪退 → 写入 error_log.json → 启动 error_viewer.py ...")
print()

try:
    raise RuntimeError("【测试】故意触发异常，验证外部错误报告窗口是否弹出。")
except RuntimeError:
    # 手动调用 crash handler（sys.excepthook 不会在 try/except 内触发）
    _crash_handler(RuntimeError, RuntimeError("【测试】故意触发异常，验证外部错误报告窗口是否弹出。"), None)

print("测试完成。应已弹出错误报告窗口。")
print("如果没有看到窗口，可能是 PyQt6 未安装 → 降级为记事本打开 error_log.json。")
print()
input("按回车键退出...")
