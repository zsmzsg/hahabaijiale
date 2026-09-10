"""
百家乐牌点识别 · 安卓悬浮版（Kivy）
- 复用 recognizer.py 的识别引擎与 engine.py 的编排逻辑
- 安卓：MediaProjection 抓前台游戏画面 + 透明悬浮窗显示结果与概率
- 桌面：mss 抓屏（或 --source=image_folder 用示例图演示），用于开发调试
运行：python main.py            # 桌面抓屏
      python main.py --source=image_folder   # 用自带示例图演示
APK 打包见 buildozer.spec 与 README.md
"""
import os
import sys
import argparse
from pathlib import Path

import cv2
import numpy as np
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics.texture import Texture
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.utils import platform as kivy_platform

# ---------- 资源路径 ----------
HERE = Path(__file__).resolve().parent
ASSETS = Path(os.environ.get('ASSETS_DIR', str(HERE / 'assets')))

import recognizer
import engine
import capture

try:
    import overlay
    ON_ANDROID = overlay.is_android()
except Exception:
    ON_ANDROID = False


class BaccaratOverlayApp(App):
    def __init__(self, source_mode='auto', **kwargs):
        super().__init__(**kwargs)
        self.source_mode = source_mode
        self.rec = None
        self.mon = None
        self.src = None
        self.monitoring = False
        self.show_preview = not ON_ANDROID  # 悬浮模式下默认不遮挡游戏

    # ---------- 初始化 ----------
    def build(self):
        recognizer.setup_paths(ASSETS)
        self.rec = recognizer.Recognizer()
        self.mon = engine.Monitor(self.rec, num_decks=8, stable_frames=8)

        root = BoxLayout(orientation='vertical', padding=8, spacing=6)

        # 顶部按钮
        top = BoxLayout(size_hint_y=None, height=44, spacing=4)
        self.btn_start = Button(text='开始', on_press=lambda *_: self.start())
        self.btn_stop = Button(text='停止', on_press=lambda *_: self.stop())
        self.btn_undo = Button(text='撤销上一手', on_press=lambda *_: self.undo())
        self.btn_reset = Button(text='重置牌堆', on_press=lambda *_: self.reset())
        self.btn_preview = Button(text='预览:开' if self.show_preview else '预览:关',
                                  on_press=lambda *_: self.toggle_preview())
        for b in (self.btn_start, self.btn_stop, self.btn_undo, self.btn_reset, self.btn_preview):
            top.add_widget(b)
        root.add_widget(top)

        # 结果 + 状态
        self.result = Label(text='识别结果会显示在这里', font_size=26,
                            size_hint_y=None, height=40, halign='left')
        self.status = Label(text='点击"开始"抓前台游戏画面并自动识别。',
                           size_hint_y=None, height=28, halign='left')
        root.add_widget(self.result)
        root.add_widget(self.status)

        # 牌堆面板
        panel = self._build_deck_panel()
        root.add_widget(panel)

        # 预览
        self.preview = Image(size_hint_y=0.45, allow_stretch=True)
        self.preview.opacity = 1 if self.show_preview else 0
        root.add_widget(self.preview)

        # 安卓悬浮窗
        if ON_ANDROID:
            overlay.set_overlay_window(transparent=True)
            Window.clearcolor = (0, 0, 0, 0)  # 透明背景

        self.refresh_panel()
        return root

    def _build_deck_panel(self):
        box = BoxLayout(orientation='vertical', size_hint_y=None, height=360, spacing=4)

        summary = BoxLayout(size_hint_y=None, height=30, spacing=10)
        self.lbl_total = Label(text='总剩余张数: 416')
        self.lbl_pair = Label(text='出对子概率: 7.4699%', color=(0.75, 0.22, 0.17, 1))
        self.lbl_dealt = Label(text='已出牌: 0 张')
        for w in (self.lbl_total, self.lbl_pair, self.lbl_dealt):
            summary.add_widget(w)
        box.add_widget(summary)

        row2 = BoxLayout(size_hint_y=None, height=30, spacing=8)
        row2.add_widget(Label(text='本金:'))
        self.bankroll = TextInput(text='10000', multiline=False, size_hint_x=0.2, input_type='number')
        row2.add_widget(self.bankroll)
        row2.add_widget(Label(text='对子赔率(1:X):'))
        self.odds = TextInput(text='11', multiline=False, size_hint_x=0.12, input_type='number')
        row2.add_widget(self.odds)
        self.lbl_ev = Label(text='期望值: -10.3614%')
        self.lbl_bet = Label(text='建议下注: -77.399')
        row2.add_widget(self.lbl_ev)
        row2.add_widget(self.lbl_bet)
        self.bankroll.bind(text=lambda *_: self.refresh_panel())
        self.odds.bind(text=lambda *_: self.refresh_panel())
        box.add_widget(row2)

        # 每点数表格
        grid = GridLayout(cols=3, size_hint_y=None, height=13 * 24)
        grid.add_widget(Label(text='点数', bold=True))
        grid.add_widget(Label(text='剩余张数', bold=True))
        grid.add_widget(Label(text='对子概率', bold=True))
        self.rank_rows = {}
        for r in recognizer.RANKS:
            c1 = Label(text=r)
            c2 = Label(text='32')
            c3 = Label(text='0.5747%')
            grid.add_widget(c1); grid.add_widget(c2); grid.add_widget(c3)
            self.rank_rows[r] = (c2, c3)
        box.add_widget(grid)
        return box

    # ---------- 控制 ----------
    def start(self):
        if self.src is None:
            try:
                kwargs = {}
                if self.source_mode == 'video' and getattr(self, '_video_path', None):
                    kwargs['path'] = self._video_path
                elif self.source_mode == 'image_folder':
                    kwargs['folder'] = str(ASSETS / '_examples')
                self.src = capture.create_source(self.source_mode, **kwargs)
            except Exception as e:
                self.status.text = f'取帧源初始化失败: {e}'
                return
        if ON_ANDROID:
            self.status.text = '请在弹出的系统中授权"投屏/录屏"以抓取前台画面。'
            overlay.request_capture_permission()
        self.monitoring = True
        self.status.text = '监控中……牌出现后自动识别并扣牌。'
        Clock.schedule_interval(self._tick, 0.3)

    def stop(self):
        self.monitoring = False
        Clock.unschedule(self._tick)
        self.status.text = '已停止。'

    def undo(self):
        n = self.mon.undo_last()
        self.status.text = f'已撤销 {n} 张，剩余 {self.mon.deck.remaining_total()} 张。'
        self.refresh_panel()

    def reset(self):
        self.mon.reset_deck()
        self.status.text = '牌堆已重置为 8 副 416 张完整牌。'
        self.refresh_panel()

    def toggle_preview(self):
        self.show_preview = not self.show_preview
        self.preview.opacity = 1 if self.show_preview else 0
        self.btn_preview.text = '预览:开' if self.show_preview else '预览:关'

    # ---------- 主循环 ----------
    def _tick(self, dt):
        if not self.monitoring:
            return
        if self.src is not None and not self.src.is_ready():
            self.status.text = '等待投屏授权……（请授权系统弹窗）'
            return
        frame = self.src.grab() if self.src else None
        if frame is None:
            self.status.text = '等待投屏授权……（请授权系统弹窗）'
            return
        out = self.mon.process_frame(frame)
        self.result.text = out['result_text']
        self.status.text = out['status']
        self.refresh_panel()
        if self.show_preview:
            self._show_preview(recognizer.visualize(frame, out['res']))

    def refresh_panel(self):
        total, prob, rows = self.mon.deck.snapshot()
        self.lbl_total.text = f'总剩余张数: {total}'
        self.lbl_pair.text = f'出对子概率: {prob*100:.4f}%'
        self.lbl_dealt.text = f'已出牌: {len(self.mon.deck.dealt)} 张'
        for r, cnt, pr in rows:
            c2, c3 = self.rank_rows[r]
            c2.text = str(cnt)
            c3.text = f'{pr*100:.4f}%'
        try:
            bankroll = float(self.bankroll.text)
            odds = int(float(self.odds.text))
        except (ValueError, AttributeError):
            bankroll, odds = 10000, 11
        ev = self.mon.deck.expected_value(odds=odds)
        bet = self.mon.deck.suggested_bet(bankroll=bankroll, odds=odds)
        self.lbl_ev.text = f'期望值: {ev*100:+.4f}%'
        self.lbl_ev.color = (0.15, 0.6, 0.27, 1) if ev >= 0 else (0.75, 0.22, 0.17, 1)
        self.lbl_bet.text = f'建议下注: {bet:+.3f}'
        self.lbl_bet.color = (0.15, 0.6, 0.27, 1) if bet >= 0 else (0.75, 0.22, 0.17, 1)

    def _show_preview(self, img):
        if img is None:
            return
        buf = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        tex = Texture.create(size=(buf.shape[1], buf.shape[0]), colorfmt='rgb')
        tex.blit_buffer(buf.tobytes(), colorfmt='rgb', bufferfmt='ubyte')
        tex.flip_vertical()
        self.preview.texture = tex
        self.preview.canvas.ask_update()

    def on_stop(self):
        try:
            self.src.close()
        except Exception:
            pass


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--source', default='auto',
                   help='auto|android|desktop|image_folder|video')
    p.add_argument('--video', default=None, help='video 模式时的视频路径')
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    mode = args.source
    if mode == 'auto' and not ON_ANDROID:
        mode = 'desktop'
    app = BaccaratOverlayApp(source_mode=mode)
    if mode == 'video' and args.video:
        app._video_path = args.video
    app.run()
