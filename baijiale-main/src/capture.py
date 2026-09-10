"""
截屏/取帧抽象层。
- 安卓：通过 overlay.py 调 MediaProjection（真实抓取前台游戏画面）
- 桌面：mss 抓屏，或图片/视频源（无显示器时也能自测）
统一接口：grab() -> BGR numpy 数组（已缩放到工作分辨率），失败返回 None
"""
import platform
import numpy as np
import cv2

WORKING_MAX_DIM = 1000  # 检测前把帧缩放到最大边 <= 此值，使阈值稳定、算力可控

try:
    import mss
except Exception:
    mss = None


def _fit(frame):
    h, w = frame.shape[:2]
    m = max(w, h)
    if m > WORKING_MAX_DIM:
        s = WORKING_MAX_DIM / m
        frame = cv2.resize(frame, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return frame


class CaptureSource:
    def __init__(self):
        self.width = 0
        self.height = 0

    def grab(self):
        raise NotImplementedError

    def close(self):
        pass

    def is_ready(self):
        return True


class ImageFolderSource(CaptureSource):
    """循环读取一个目录里的图片（用于无显示器自测 / 演示）。"""

    def __init__(self, folder, loop=True):
        super().__init__()
        from pathlib import Path
        self.files = sorted(
            p for p in Path(folder).iterdir()
            if p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        )
        if not self.files:
            raise RuntimeError(f'目录为空: {folder}')
        self.i = 0
        self.loop = loop
        self._probe()

    def _probe(self):
        f = cv2.imread(str(self.files[0]))
        f = _fit(f)
        self.height, self.width = f.shape[:2]

    def grab(self):
        if self.i >= len(self.files):
            if not self.loop:
                return None
            self.i = 0
        f = cv2.imread(str(self.files[self.i]))
        self.i += 1
        return _fit(f) if f is not None else None


class VideoSource(CaptureSource):
    def __init__(self, path):
        super().__init__()
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise RuntimeError(f'无法打开视频: {path}')

    def grab(self):
        ok, f = self.cap.read()
        if not ok:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, f = self.cap.read()
        return _fit(f) if ok else None

    def close(self):
        try:
            self.cap.release()
        except Exception:
            pass


class DesktopSource(CaptureSource):
    """桌面端用 mss 抓取屏幕（或指定区域）。"""

    def __init__(self, region=None):
        super().__init__()
        if mss is None:
            raise RuntimeError('未安装 mss（桌面测试用）。pip install mss')
        self.sct = mss.mss()
        self.region = region
        if region is None:
            mon = self.sct.monitors[0]
            self.region = {'left': mon['left'], 'top': mon['top'],
                           'width': mon['width'], 'height': mon['height']}
        self.width = self.region['width']
        self.height = self.region['height']

    def grab(self):
        shot = np.array(self.sct.grab(self.region), dtype=np.uint8)
        return _fit(cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR))


class AndroidSource(CaptureSource):
    """安卓端：通过 overlay.py 的 MediaProjection 桥接抓前台画面。"""

    def __init__(self, max_dim=WORKING_MAX_DIM):
        super().__init__()
        from overlay import AndroidScreen
        self.screen = AndroidScreen(max_dim=max_dim)

    def grab(self):
        return self.screen.grab()

    def is_ready(self):
        return self.screen.is_ready()

    def close(self):
        try:
            self.screen.release()
        except Exception:
            pass


def create_source(mode='auto', **kwargs):
    """根据模式创建取帧源。mode:
    auto  -> 安卓用 AndroidSource，否则 DesktopSource
    android / desktop / image_folder / video
    """
    if mode == 'auto':
        mode = 'android' if platform.system() == 'Linux' and _looks_like_android() else 'desktop'
    if mode == 'android':
        return AndroidSource(**kwargs)
    if mode == 'desktop':
        return DesktopSource(**kwargs)
    if mode == 'image_folder':
        return ImageFolderSource(**kwargs)
    if mode == 'video':
        return VideoSource(**kwargs)
    raise ValueError(f'未知 mode: {mode}')


def _looks_like_android():
    try:
        from overlay import is_android
        return is_android()
    except Exception:
        return False
