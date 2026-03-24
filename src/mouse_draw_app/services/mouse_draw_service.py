from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from ctypes import POINTER, Structure, Union, byref, sizeof, windll
from ctypes import wintypes

from pynput import keyboard

from mouse_draw_app.models import DrawConfig, PathStroke, Point


ULONG_PTR = wintypes.WPARAM


class _MOUSEINPUT(Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUTUNION(Union):
    _fields_ = [("mi", _MOUSEINPUT)]


class _INPUT(Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


class MouseDrawService:
    _INPUT_MOUSE = 0
    _MOUSEEVENTF_MOVE = 0x0001
    _MOUSEEVENTF_LEFTDOWN = 0x0002
    _MOUSEEVENTF_LEFTUP = 0x0004
    _MOUSEEVENTF_RIGHTDOWN = 0x0008
    _MOUSEEVENTF_RIGHTUP = 0x0010
    _MOUSEEVENTF_ABSOLUTE = 0x8000

    def __init__(self) -> None:
        self._keyboard_listener: keyboard.Listener | None = None
        self._user32 = windll.user32
        self._user32.SendInput.argtypes = (wintypes.UINT, POINTER(_INPUT), wintypes.INT)
        self._user32.SendInput.restype = wintypes.UINT
        self._user32.GetSystemMetrics.argtypes = (wintypes.INT,)
        self._user32.GetSystemMetrics.restype = wintypes.INT
        self._screen_width = max(1, self._user32.GetSystemMetrics(0) - 1)
        self._screen_height = max(1, self._user32.GetSystemMetrics(1) - 1)

    def draw_paths(
        self,
        paths: list[PathStroke],
        config: DrawConfig,
        stop_event: threading.Event,
    ) -> None:
        button_is_left = config.mouse_button == "left"
        step_delay = self._step_delay(config.move_speed)

        try:
            time.sleep(0.25)
            for stroke in paths:
                if stop_event.is_set() or len(stroke.points) < 2:
                    break

                self._move_cursor_absolute(stroke.points[0])
                time.sleep(0.05)
                self._send_button_event(button_is_left, is_press=True)
                time.sleep(0.03)

                for start, end in zip(stroke.points, stroke.points[1:]):
                    if stop_event.is_set():
                        break
                    for point in self._interpolate_segment(start, end):
                        if stop_event.is_set():
                            break
                        self._move_cursor_absolute(point)
                        time.sleep(step_delay)

                self._send_button_event(button_is_left, is_press=False)
                time.sleep(step_delay * 4)
        finally:
            try:
                self._send_button_event(button_is_left, is_press=False)
            except Exception:
                pass

    def start_emergency_stop_listener(self, stop_callback: Callable[[], None]) -> None:
        if self._keyboard_listener is not None:
            return

        def on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
            if key == keyboard.Key.esc:
                stop_callback()

        self._keyboard_listener = keyboard.Listener(on_press=on_press)
        self._keyboard_listener.daemon = True
        self._keyboard_listener.start()

    def stop_emergency_stop_listener(self) -> None:
        if self._keyboard_listener is None:
            return
        self._keyboard_listener.stop()
        self._keyboard_listener = None

    def _move_cursor_absolute(self, point: Point) -> None:
        absolute_x = round(max(0, min(point.x, self._screen_width)) * 65535 / self._screen_width)
        absolute_y = round(max(0, min(point.y, self._screen_height)) * 65535 / self._screen_height)
        self._send_mouse_input(self._MOUSEEVENTF_MOVE | self._MOUSEEVENTF_ABSOLUTE, absolute_x, absolute_y)

    def _send_button_event(self, is_left_button: bool, is_press: bool) -> None:
        if is_left_button:
            flag = self._MOUSEEVENTF_LEFTDOWN if is_press else self._MOUSEEVENTF_LEFTUP
        else:
            flag = self._MOUSEEVENTF_RIGHTDOWN if is_press else self._MOUSEEVENTF_RIGHTUP
        self._send_mouse_input(flag, 0, 0)

    def _send_mouse_input(self, flags: int, dx: int, dy: int) -> None:
        mouse_input = _MOUSEINPUT(dx, dy, 0, flags, 0, 0)
        input_union = _INPUTUNION(mi=mouse_input)
        input_struct = _INPUT(self._INPUT_MOUSE, input_union)
        sent = self._user32.SendInput(1, byref(input_struct), sizeof(_INPUT))
        if sent != 1:
            raise RuntimeError("发送鼠标输入事件失败。")

    def _interpolate_segment(self, start: Point, end: Point) -> list[Point]:
        distance = math.dist((start.x, start.y), (end.x, end.y))
        steps = max(2, int(distance / 2.0))
        points: list[Point] = []
        for index in range(1, steps + 1):
            ratio = index / steps
            points.append(
                Point(
                    x=start.x + (end.x - start.x) * ratio,
                    y=start.y + (end.y - start.y) * ratio,
                )
            )
        return points

    @staticmethod
    def _step_delay(speed: int) -> float:
        clamped = max(1, min(speed, 100))
        return max(0.0015, 0.016 - clamped * 0.0001)
