# 杀戮尖塔绘画

这是一个基于 Windows 的桌面工具，支持将导入图片或中英文文字转换为线稿，在界面中实时预览，并通过鼠标自动完成绘制，可用于你画我猜，杀戮尖塔等可绘画游戏的画图使用，手残党也可以画画了。

## 功能

- 导入图片并转换为可绘制的线稿路径。
- 输入文字并转换为字体轮廓线稿。
- 在线稿生成后于右侧实时预览。
- 框选屏幕目标区域，并在保持比例的前提下适配线稿。
- 支持使用鼠标左键或右键进行自动绘制。
- 支持通过界面按钮或 `Esc` 紧急热键停止绘制。

## 环境要求

- Windows 10/11
- Python 3.10 及以上

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

```powershell
python run_mouse_draw_app.py
```
