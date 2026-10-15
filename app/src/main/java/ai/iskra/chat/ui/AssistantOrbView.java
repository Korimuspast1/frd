package ai.iskra.chat.ui;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.view.View;
import android.view.animation.AccelerateDecelerateInterpolator;

import ai.iskra.chat.util.Ui;

/** Animated assistant mark inspired by a softly glowing glass orb. */
public final class AssistantOrbView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF eye = new RectF();
    private ValueAnimator animator;
    private float phase;

    public AssistantOrbView(Context context) {
        super(context);
        setLayerType(LAYER_TYPE_SOFTWARE, null);
        setContentDescription("kvsai — начать новый диалог");
        setClickable(true);
        setFocusable(true);
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float cx = getWidth() / 2f;
        float bob = (float) Math.sin(phase * Math.PI * 2.0) * Ui.dp(getContext(), 2.5f);
        float cy = getHeight() / 2f + bob;
        float base = Math.min(getWidth(), getHeight()) * 0.31f;
        float pulse = 1f + (float) Math.sin(phase * Math.PI * 2.0) * 0.035f;
        float radius = base * pulse;

        paint.setShader(null);
        paint.setColor(0x253A67FF);
        paint.setShadowLayer(Ui.dp(getContext(), 22), 0, Ui.dp(getContext(), 5), 0x773F72FF);
        canvas.drawCircle(cx, cy, radius * 1.18f, paint);
        paint.clearShadowLayer();

        paint.setShader(new RadialGradient(
                cx - radius * 0.28f, cy - radius * 0.35f, radius * 1.55f,
                new int[]{0xFF72C8FF, 0xFF438DF4, 0xFF4353C5, 0xFF20234A},
                new float[]{0f, 0.42f, 0.78f, 1f}, Shader.TileMode.CLAMP));
        canvas.drawCircle(cx, cy, radius, paint);

        paint.setShader(new RadialGradient(
                cx - radius * 0.35f, cy - radius * 0.55f, radius,
                new int[]{0x99FFFFFF, 0x11FFFFFF, 0x00FFFFFF},
                null, Shader.TileMode.CLAMP));
        canvas.drawCircle(cx, cy, radius * 0.96f, paint);
        paint.setShader(null);

        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(Ui.dp(getContext(), 1));
        paint.setColor(0x66D8ECFF);
        canvas.drawCircle(cx, cy, radius, paint);
        paint.setStyle(Paint.Style.FILL);

        float eyeWidth = radius * 0.18f;
        float eyeHeight = radius * 0.43f;
        float eyeY = cy - radius * 0.2f;
        paint.setColor(Color.WHITE);
        paint.setShadowLayer(Ui.dp(getContext(), 4), 0, 0, 0x88FFFFFF);
        eye.set(cx - radius * 0.42f, eyeY, cx - radius * 0.42f + eyeWidth, eyeY + eyeHeight);
        canvas.drawRoundRect(eye, eyeWidth, eyeWidth, paint);
        eye.set(cx + radius * 0.22f, eyeY, cx + radius * 0.22f + eyeWidth, eyeY + eyeHeight);
        canvas.drawRoundRect(eye, eyeWidth, eyeWidth, paint);
        paint.clearShadowLayer();
    }

    @Override protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (animator == null) {
            animator = ValueAnimator.ofFloat(0f, 1f);
            animator.setDuration(2_800);
            animator.setRepeatCount(ValueAnimator.INFINITE);
            animator.setInterpolator(new AccelerateDecelerateInterpolator());
            animator.addUpdateListener(value -> {
                phase = (float) value.getAnimatedValue();
                invalidate();
            });
        }
        animator.start();
    }

    @Override protected void onDetachedFromWindow() {
        if (animator != null) animator.cancel();
        super.onDetachedFromWindow();
    }
}
