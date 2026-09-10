[app]

# ============================================================
# 基本信息
# ============================================================

title = บาคาร่า牌点识别·悬浮版

package.name = baccaratoverlay

package.domain = org.baccarat

version = 1.0


# ============================================================
# 项目源码
# ============================================================

source.dir = src

source.main = main.py

source.include_exts = py,png,jpg,jpeg,npz,json

source.include_dirs = assets


# ============================================================
# Python / Android 依赖
# ============================================================

# p4a 2026.x 默认 Python 3.14；本项目实际构建日志也已成功
# 编译 Kivy 2.3.1 / NumPy / OpenCV 到 Python 3.14。
# charset-normalizer 未被本项目代码使用，不加入 Android requirements，
# 避免额外的 pip resolver / 纯 Python 包安装干扰。

requirements = python3,kivy,numpy,opencv,pyjnius


# ============================================================
# python-for-android
# ============================================================

p4a.fork = kivy

# 使用 develop 分支上的已验证修复：
# 0382d27 = merge commit，包含“avoid pip self-upgrade corrupting the build venv”
# 这正是上一轮日志中：
# pip 26.2.1 + Python 3.14 venv -> BuildDependencyInstallError
# 的直接修复。
p4a.branch = develop
p4a.commit = 0382d27


# ============================================================
# Android 权限
# ============================================================

android.permissions = SYSTEM_ALERT_WINDOW,POST_NOTIFICATIONS,FOREGROUND_SERVICE


# ============================================================
# Android Activity
# ============================================================

android.activity_class_name = org.baccarat.overlay.OverlayActivity

android.add_src = java


# ============================================================
# Android SDK
# ============================================================

android.api = 33

android.minapi = 24


# ============================================================
# Android NDK
# ============================================================

android.ndk = 26d


# ============================================================
# Android Build Tools
# ============================================================

android.build_tools_version = 34.0.0


# ============================================================
# SDK License
# ============================================================

android.accept_sdk_license = True


# ============================================================
# Android APK 设置
# ============================================================

android.fullscreen = false

android.allow_backup = false


# ============================================================
# 屏幕方向
# ============================================================

orientation = portrait


# ============================================================
# Buildozer
# ============================================================

[buildozer]

log_level = 2

warn_on_root = 1
