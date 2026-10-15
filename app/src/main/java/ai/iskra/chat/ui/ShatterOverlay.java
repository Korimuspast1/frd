package ai.iskra.chat.ui;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.AccelerateInterpolator;
import android.widget.FrameLayout;

import ai.iskra.chat.util.DebugLog;
import ai.iskra.chat.util.Ui;

import java.util.Random;

/** Captures a view and breaks its snapshot into animated tiles before deletion. */
public final class ShatterOverlay extends View {
    private static final int COLS = 7;
    private static final int ROWS = 5;

    private final Bitmap snapshot;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final Paint crackPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Rect source = new Rect();
    private final RectF destination = new RectF();
    private final float[] velocityX = new float[COLS * ROWS];
    private final float[] velocityY = new float[COLS * ROWS];
    private final float[] rotation = new float[COLS * ROWS];
    private final float originX;
    private final float originY;
    private final float density;
    private float progress;

    private ShatterOverlay(Activity activity, Bitmap snapshot, float originX, float originY) {
        super(activity);
        this.snapshot = snapshot;
        this.originX = originX;
        this.originY = originY;
        density = getResources().getDisplayMetrics().density;
        setLayerType(LAYER_TYPE_HARDWARE, null);
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);

        Random random = new Random(0x4B56534149L);
        for (int row = 0; row < ROWS; row++) {
            for (int col = 0; col < COLS; col++) {
                int index = row * COLS + col;
                float direction = (col + 0.5f) / COLS - 0.5f;
                velocityX[index] = direction * (90 + random.nextFloat() * 70) +
                        (random.nextFloat() - 0.5f) * 35;
                velocityY[index] = -28 + row * 12 + random.nextFloat() * 46;
                rotation[index] = (random.nextFloat() - 0.5f) * 65;
            }
        }
        crackPaint.setColor(0xAAE8F3FF);
        crackPaint.setStrokeWidth(Math.max(1f, density * 0.65f));
        crackPaint.setStyle(Paint.Style.STROKE);
    }

    public static void shatter(Activity activity, View target, Runnable after) {
        if (target == null || target.getWidth() <= 0 || target.getHeight() <= 0) {
            if (after != null) after.run();
            return;
        }
        Bitmap bitmap;
        try {
            bitmap = Bitmap.createBitmap(target.getWidth(), target.getHeight(), Bitmap.Config.ARGB_8888);
            target.draw(new Canvas(bitmap));
        } catch (Exception error) {
            DebugLog.error("ANIMATION", error);
            if (after != null) after.run();
            return;
        }

        View decorView = activity.getWindow().getDecorView();
        if (!(decorView instanceof ViewGroup)) {
            bitmap.recycle();
            if (after != null) after.run();
            return;
        }
        int[] targetLocation = new int[2];
        int[] decorLocation = new int[2];
        target.getLocationOnScreen(targetLocation);
        decorView.getLocationOnScreen(decorLocation);
        ShatterOverlay overlay = new ShatterOverlay(activity, bitmap,
                targetLocation[0] - decorLocation[0], targetLocation[1] - decorLocation[1]);
        ViewGroup decor = (ViewGroup) decorView;
        decor.addView(overlay, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        target.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
        target.setAlpha(0f);
        DebugLog.log("ANIMATION", "Shatter animation started; tiles=" + (COLS * ROWS));

        ValueAnimator animator = ValueAnimator.ofFloat(0f, 1f);
        animator.setDuration(760);
        animator.setInterpolator(new AccelerateInterpolator(1.25f));
        animator.addUpdateListener(value -> {
            overlay.progress = (float) value.getAnimatedValue();
            overlay.invalidate();
        });
        animator.addListener(new AnimatorListenerAdapter() {
            @Override public void onAnimationEnd(Animator animation) {
                decor.removeView(overlay);
                bitmap.recycle();
                DebugLog.log("ANIMATION", "Shatter animation completed");
                if (after != null) after.run();
            }
        });
        animator.start();
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float split = Math.max(0f, (progress - 0.07f) / 0.93f);
        int tileWidth = Math.max(1, snapshot.getWidth() / COLS);
        int tileHeight = Math.max(1, snapshot.getHeight() / ROWS);
        paint.setAlpha(Math.max(0, (int) (255 * (1f - split * split))));

        for (int row = 0; row < ROWS; row++) {
            for (int col = 0; col < COLS; col++) {
                int index = row * COLS + col;
                int left = col * tileWidth;
                int top = row * tileHeight;
                int right = col == COLS - 1 ? snapshot.getWidth() : left + tileWidth;
                int bottom = row == ROWS - 1 ? snapshot.getHeight() : top + tileHeight;
                source.set(left, top, right, bottom);

                float centerX = originX + (left + right) / 2f;
                float centerY = originY + (top + bottom) / 2f;
                float dx = velocityX[index] * density * split;
                float dy = (velocityY[index] * split + 145f * split * split) * density;
                float shrink = 1f - split * 0.16f;
                float width = (right - left) * shrink;
                float height = (bottom - top) * shrink;
                destination.set(centerX - width / 2f, centerY - height / 2f,
                        centerX + width / 2f, centerY + height / 2f);
                destination.offset(dx, dy);

                canvas.save();
                canvas.rotate(rotation[index] * split, destination.centerX(), destination.centerY());
                canvas.drawBitmap(snapshot, source, destination, paint);
                canvas.restore();
            }
        }

        if (progress < 0.28f) drawCracks(canvas, 1f - progress / 0.28f);
    }

    private void drawCracks(Canvas canvas, float alpha) {
        crackPaint.setAlpha((int) (190 * alpha));
        float cx = originX + snapshot.getWidth() * 0.53f;
        float cy = originY + snapshot.getHeight() * 0.48f;
        for (int i = 0; i < 11; i++) {
            double angle = i * Math.PI * 2 / 11.0 + 0.23;
            float length = Math.min(snapshot.getWidth(), snapshot.getHeight()) * (0.28f + (i % 3) * 0.12f);
            float ex = cx + (float) Math.cos(angle) * length;
            float ey = cy + (float) Math.sin(angle) * length;
            canvas.drawLine(cx, cy, ex, ey, crackPaint);
            canvas.drawLine(ex, ey, ex + (float) Math.cos(angle + 0.9) * length * 0.25f,
                    ey + (float) Math.sin(angle + 0.9) * length * 0.25f, crackPaint);
        }
    }
}
