"""
安卓专属桥接层（pyjnius）。
- is_android(): 判断是否运行在安卓
- AndroidScreen: MediaProjection 实时抓取前台画面 -> numpy BGR
- set_overlay_window(): 把 Kivy 窗口设为透明、可穿透悬浮窗（游戏在下方可见可点）
- request_capture_permission(): 触发系统投屏授权
桌面端导入本模块不会报错（所有安卓调用都做了保护）。
"""
import numpy as np
import cv2

try:
    from jnius import autoclass, cast
    _HAVE_JNIUS = True
except Exception:
    _HAVE_JNIUS = False


def is_android():
    if not _HAVE_JNIUS:
        return False
    try:
        autoclass('android.os.Build')
        return True
    except Exception:
        return False


class AndroidScreen:
    """通过 Java 助手 org.baccarat.overlay.ScreenCapture 取帧。"""

    def __init__(self, max_dim=1000):
        self.max_dim = max_dim
        self.SC = autoclass('org.baccarat.overlay.ScreenCapture')
        self.OA = autoclass('org.baccarat.overlay.OverlayActivity')

    def is_ready(self):
        try:
            return bool(self.SC.isReady())
        except Exception:
            return False

    def ensure_permission(self):
        """若尚未授权则拉起系统投屏授权。返回是否已就绪。"""
        if self.is_ready():
            return True
        try:
            self.OA.requestProjection()
        except Exception as e:
            print('requestProjection 失败:', e)
        return False

    def grab(self):
        if not self.is_ready():
            return None
        b = self.SC.grabRGBA()
        if not b:
            return None
        w = int(self.SC.getWidth())
        h = int(self.SC.getHeight())
        if w <= 0 or h <= 0:
            return None
        arr = np.frombuffer(bytes(b), dtype=np.uint8).reshape(h, w, 4)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        # 二次保险：缩放到工作分辨率
        m = max(bgr.shape[1], bgr.shape[0])
        if m > self.max_dim:
            s = self.max_dim / m
            bgr = cv2.resize(bgr, (int(bgr.shape[1] * s), int(bgr.shape[0] * s)),
                             interpolation=cv2.INTER_AREA)
        return bgr

    def release(self):
        try:
            self.SC.release()
        except Exception:
            pass


# ---------- 窗口悬浮化 ----------
def set_overlay_window(transparent=True):
    """把当前 Kivy Activity 设为透明、可穿透的悬浮窗。
    透明区域能看到下方游戏；控件区域正常响应触摸。"""
    if not is_android():
        return False
    try:
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        WindowManager = autoclass('android.view.WindowManager$LayoutParams')
        win = activity.getWindow()
        # 布局铺满、触摸穿透到下方（窗口内仍响应）
        win.addFlags(WindowManager.FLAG_LAYOUT_NO_LIMITS)
        win.addFlags(WindowManager.FLAG_NOT_TOUCH_MODAL)
        if transparent:
            win.addFlags(WindowManager.FLAG_LAYOUT_IN_SCREEN)
            # 透明背景
            win.setBackgroundDrawableResource(android_R_transparent())
        return True
    except Exception as e:
        print('set_overlay_window 失败:', e)
        return False


def android_R_transparent():
    try:
        R = autoclass('android.R$color')
        return R.transparent
    except Exception:
        return 0


def request_capture_permission():
    if not is_android():
        return False
    try:
        OA = autoclass('org.baccarat.overlay.OverlayActivity')
        OA.requestProjection()
        return True
    except Exception as e:
        print('request_capture_permission 失败:', e)
        return False
