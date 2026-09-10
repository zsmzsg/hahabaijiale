package org.baccarat.overlay;

import org.kivy.android.PythonActivity;
import android.content.Intent;
import android.os.Bundle;
import android.media.projection.MediaProjectionManager;

/**
 * 自定义启动 Activity：继承 Kivy 的 PythonActivity，
 * 仅用于把 MediaProjection 的授权结果转发给 ScreenCapture。
 * 在 buildozer.spec 中通过 android.activity_class_name 指定为本类。
 */
public class OverlayActivity extends PythonActivity {
    public static final int REQUEST_MEDIA_PROJECTION = 1001;
    public static OverlayActivity mActivity;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        mActivity = this;
    }

    /** 由 Python 调用：拉起系统投屏授权对话框。 */
    public static void requestProjection() {
        if (mActivity == null) return;
        MediaProjectionManager mpm = (MediaProjectionManager)
                mActivity.getSystemService(MEDIA_PROJECTION_SERVICE);
        Intent intent = mpm.createScreenCaptureIntent();
        mActivity.startActivityForResult(intent, REQUEST_MEDIA_PROJECTION);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_MEDIA_PROJECTION) {
            if (resultCode == RESULT_OK && data != null) {
                ScreenCapture.onProjectionResult(data, resultCode);
            }
        }
    }
}
