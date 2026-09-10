# 百家乐牌点识别 · 安卓悬浮版（Kivy 移植）

把原 PC 版《百家乐牌点自动识别 v0.5》移植到安卓：在**前台游戏画面上方悬浮**显示
识别结果，并实时维护 8 副牌（416 张）的**对子概率 / 期望值 / 建议下注**。

核心识别引擎（OpenCV 模板匹配）与牌堆状态机是从原版**原样复用**并已在示例图上验证
100% 匹配，未改动算法。改动只在于 **GUI（tkinter→Kivy）** 与 **截屏（mss→MediaProjection）** 两层。

---

## 目录结构

```
android_baccarat_overlay/
├── buildozer.spec          # APK 打包配置（已含权限/Java 桥接/opencv recipe）
├── requirements.txt        # 桌面开发依赖
├── java/                   # 安卓原生桥接（MediaProjection 取帧 + 授权转发）
│   └── org/baccarat/overlay/
│       ├── ScreenCapture.java     # ImageReader 抓屏 -> RGBA 字节数组
│       └── OverlayActivity.java   # 继承 PythonActivity，转发投屏授权
└── src/
    ├── main.py             # Kivy 主界面（悬浮窗 + 控制 + 概率面板）
    ├── recognizer.py       # 识别引擎 Recognizer + 牌堆 DeckState（移植自原版）
    ├── engine.py           # 实时编排：稳定帧扣牌 / 撤销 / 重置（不依赖 kivy）
    ├── capture.py          # 取帧抽象：安卓(MediaProjection)/桌面(mss)/图片/视频
    ├── overlay.py          # pyjnius 桥接：抓屏 + 透明悬浮窗
    ├── test_headless.py    # 无界面自测（识别+牌堆数学+撤销）
    └── assets/             # 随包资源：训练模板 rank_templates.npz、训练样本、示例图
```

---

## 1. 桌面演示 / 自测（无需手机）

```bash
cd src
pip install -r ../requirements.txt
python test_headless.py                 # 无界面验证识别与概率计算
python main.py --source=image_folder    # 用自带示例图演示完整界面
python main.py                          # 桌面抓屏（mss，需有显示器）
```

`test_headless.py` 输出应显示：`全部通过 ✅`，单图识别与示例标注完全一致，
初始对子概率 = 7.4699%（理论值一致），撤销后牌堆回到 416 张。

---

## 2. 怎么拿到 APK / 在手机运行

> **没有现成编译好的 APK。** 打包依赖 Android SDK/NDK（数 GB）与真机验证，
> 本开发环境无法产出可直接下载的二进制。下面两种方式都能让你拿到 APK：

### 方式 A：GitHub Actions 自动编译（推荐，零本地安装）

1. 把整个 `android_baccarat_overlay/` 目录推到你自己的 GitHub 仓库
   （工作流文件已放在 `.github/workflows/build.yml`）。
2. 仓库页 **Actions → Build Android APK → 等待完成**（首次约 10–25 分钟，
   会下载 SDK/NDK 并编译 opencv，属正常）。
3. 进入该次运行的 **Artifacts**，下载 `baccarat-overlay-apk`（即 `bin/baccaratoverlay-*-debug.apk`）。
4. 手机打开"允许安装未知来源应用"，装好 APK。

### 方式 B：本地用 Buildozer 编译（需 Linux + 网络）

```bash
pip install buildozer
cd android_baccarat_overlay
buildozer android debug        # 首次自动下载 SDK/NDK，耗时较长
# 产物：bin/baccaratoverlay-*-debug.apk
adb install bin/baccaratoverlay-*-debug.apk
```

### 手机上运行

1. 打开 App，按提示授予 **"显示在其他应用上层"** 权限（悬浮窗必需）。
2. 点 **开始** → 系统弹 **投屏/录屏授权**，点允许。
3. 回到百家乐游戏，App 以透明悬浮窗浮在游戏上，游戏画面与触摸均正常。
4. 牌出现约 2.4 秒（8 帧稳定）后自动识别并扣牌，刷新对子概率/期望值/建议下注。
5. 误识别点 **撤销上一手**；换新靴子点 **重置牌堆**；**预览** 可切换是否显示带框画面。

`buildozer.spec` 已配置好：
- `android.activity_class_name = org.baccarat.overlay.OverlayActivity`（转发投屏授权）
- `android.add_src = java`（编译 ScreenCapture / OverlayActivity）
- 权限：`SYSTEM_ALERT_WINDOW`（悬浮窗，必需）、`FOREGROUND_SERVICE`、`POST_NOTIFICATIONS`
- 依赖：`python3, kivy, numpy, opencv, pillow`（opencv 用 p4a 的 recipe）

---

## 3. 手机上使用

1. 安装 APK，首次打开会请求**"显示在其他应用上层"**权限（悬浮窗必需），请允许。
2. 点击 **开始**：系统弹出**投屏/录屏授权**对话框，点允许。
3. 回到百家乐游戏（本 App 以透明悬浮窗浮在其上，游戏画面与触摸均正常）。
4. 牌出现后自动识别，约 2.4 秒（8 帧稳定）后自动从牌堆扣除并更新概率面板。
5. 面板显示：总剩余张数、出对子概率、期望值、建议下注、本金/赔率输入、每点数剩余与概率。
6. 误识别可点 **撤销上一手**；换新靴子点 **重置牌堆**。
7. **预览** 按钮可切换是否显示带框的识别画面（悬浮模式下默认关，避免遮挡游戏）。

---

## 4. 与原 PC 版的区别

| 项目 | 原 PC 版 | 本安卓版 |
|---|---|---|
| GUI | tkinter 桌面窗口 | Kivy + 透明悬浮窗（覆盖在游戏上） |
| 截屏 | mss 抓桌面窗口 | MediaProjection 抓前台画面 |
| 监控区域 | 手动拖框选区域 | 整屏抓取（百家乐牌区固定，无需选区域） |
| 引擎/牌堆 | 相同 | 完全相同（含对子概率/EV/建议下注） |

---

## 5. 注意事项与已知限制（请务必阅读）

- **需真机验证**：MediaProjection 取帧与 `TYPE_APPLICATION_OVERLAY` 悬浮窗的行为
  与具体 Android 版本/机型相关，我无法在当前环境真机测试，请在手机上实测授权与悬浮效果。
- **识别阈值依赖分辨率**：原版检测阈值（牌面积、长宽比）按示例图（约 183×534）标定。
  手机截图分辨率更高，代码已把帧**缩放到最大边 1000px** 再检测以保持阈值稳定；
  若你的游戏牌面特别大/特别小，可在 `capture.py` 改 `WORKING_MAX_DIM`，
  或在 `recognizer.py` 的 `detect()` 调 `area / ratio` 阈值。
- **训练样本来自 PC 截图**：`rank_templates.npz` 是用 PC 游戏截图训练的。
  若手机上游戏渲染（字体/字号/配色）与 PC 不同导致识别率下降，需要**在手机截图上重新训练**：
  目前训练 UI 仅在原 PC 版提供；重新训练后把新 `rank_templates.npz` 放回 `src/assets/` 重新打包即可。
- **性能**：每 300ms 一帧 OpenCV 识别，中端手机可流畅运行；如需更省电可把 `main.py` 中
  `Clock.schedule_interval(self._tick, 0.3)` 的间隔调大。
- **隐私/合规**：仅在本机离线运行，不联网、不上传任何画面。

---

## 6. 后续可增强

- 把训练 UI 也搬上手机（截图→标记点数→本地重建模板）。
- 用前台 Service + `TYPE_APPLICATION_OVERLAY` 实现"完全不抢焦点"的真·悬浮（当前用
  透明 Activity + `FLAG_NOT_TOUCH_MODAL` 已能透过点击，可作为轻量方案）。
- 自动点击下注（需无障碍服务，超出本工具范围）。
