package org.baccarat.overlay;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.util.DisplayMetrics;
import android.view.Surface;

/**
 * MediaProjection 截屏助手。
 * 由 OverlayActivity 在用户授权后调用 onProjectionResult() 初始化，
 * grabRGBA() 返回紧排的 RGBA 字节数组，供 Python 侧转成 numpy 识别。
 */
public class ScreenCapture {
    private static MediaProjection projection = null;
    private static ImageReader reader = null;
    private static VirtualDisplay vd = null;
    private static int width = 0;
    private static int height = 0;
    private static final Object lock = new Object();

    public static void onProjectionResult(Intent data, int resultCode) {
        synchronized (lock) {
            try {
                Context ctx = OverlayActivity.mActivity;
                MediaProjectionManager mpm = (MediaProjectionManager)
                        ctx.getSystemService(Context.MEDIA_PROJECTION_SERVICE);
                projection = mpm.getMediaProjection(resultCode, data);

                DisplayMetrics dm = ctx.getResources().getDisplayMetrics();
                int w = dm.widthPixels;
                int h = dm.heightPixels;
                int maxdim = 1000; // 与 capture.WORKING_MAX_DIM 对应，降低内存/算力
                float scale = Math.min(1f, (float) maxdim / Math.max(w, h));
                width = (int) (w * scale);
                height = (int) (h * scale);

                reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 3);
                Surface surface = reader.getSurface();
                vd = projection.createVirtualDisplay(
                        "baccarat_capture", width, height, dm.densityDpi,
                        DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                        surface, null, null);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    public static boolean isReady() {
        synchronized (lock) {
            return projection != null && reader != null;
        }
    }

    public static int getWidth() { return width; }
    public static int getHeight() { return height; }

    /** 返回 width*height*4 的 RGBA 紧排字节数组；无新帧返回 null。 */
    public static byte[] grabRGBA() {
        synchronized (lock) {
            if (reader == null) return null;
            Image img = null;
            try {
                img = reader.acquireLatestImage();
                if (img == null) return null;
                Image.Plane plane = img.getPlanes()[0];
                java.nio.ByteBuffer buf = plane.getBuffer();
                int pixelStride = plane.getPixelStride();   // 通常 4
                int rowStride = plane.getRowStride();
                int rowBytes = rowStride;                    // 每行字节数（可能带 padding）
                byte[] out = new byte[width * height * 4];
                byte[] line = new byte[rowBytes];
                int idx = 0;
                for (int y = 0; y < height; y++) {
                    buf.position(y * rowStride);
                    buf.get(line, 0, rowBytes);
                    for (int x = 0; x < width; x++) {
                        int o = x * pixelStride;
                        out[idx++] = line[o];       // R
                        out[idx++] = line[o + 1];   // G
                        out[idx++] = line[o + 2];   // B
                        out[idx++] = line[o + 3];   // A
                    }
                }
                return out;
            } catch (Exception e) {
                return null;
            } finally {
                if (img != null) img.close();
            }
        }
    }

    public static void release() {
        synchronized (lock) {
            try { if (vd != null) vd.release(); } catch (Exception ignored) {}
            try { if (projection != null) projection.stop(); } catch (Exception ignored) {}
            reader = null;
            projection = null;
            vd = null;
        }
    }
}
