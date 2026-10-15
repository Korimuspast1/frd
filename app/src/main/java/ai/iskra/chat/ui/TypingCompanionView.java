package ai.iskra.chat.ui;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.view.View;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.LinearInterpolator;

import ai.iskra.chat.util.Ui;

/** Small ambient face that quietly wakes up while the user types. */
public final class TypingCompanionView extends View {
    private final Paint glowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint facePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint featurePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint particlePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path mouth = new Path();
    private ValueAnimator animator;
    private float phase;
    private boolean typing;

    public TypingCompanionView(Context context) {
        super(context);
        facePaint.setColor(0xEE172031);
        featurePaint.setColor(0xFFEAF5FF);
        featurePaint.setStrokeCap(Paint.Cap.ROUND);
        featurePaint.setStyle(Paint.Style.STROKE);
        particlePaint.setColor(Ui.CYAN);
        setContentDescription("Спутник kvsai наблюдает за вводом");
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        setAlpha(0.78f);
    }

    public void setTyping(boolean value) {
        if (typing == value) return;
        typing = value;
        setContentDescription(value
                ? "Спутник kvsai радуется вашему сообщению"
                : "Спутник kvsai наблюдает за вводом");
        animate().cancel();
        animate().alpha(value ? 1f : 0.78f)
                .scaleX(value ? 1.08f : 1f)
                .scaleY(value ? 1.08f : 1f)
                .setDuration(240L)
                .setInterpolator(new DecelerateInterpolator())
                .start();
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float density = getResources().getDisplayMetrics().density;
        float cx = getWidth() * 0.5f;
        float idleWave = (float) Math.sin(phase * Math.PI * 2.0);
        float bob = typing ? idleWave * 1.25f * density : idleWave * 0.35f * density;
        float cy = getHeight() * 0.5f + bob;
        float radius = Math.min(getWidth(), getHeight()) * (typing ? 0.35f : 0.32f);

        glowPaint.setShader(new RadialGradient(cx, cy, radius * 1.85f,
                typing
                        ? new int[]{0x8848D9FF, 0x405A72FF, 0x006E43D8}
                        : new int[]{0x555D93FF, 0x24365DAF, 0x003B3477},
                new float[]{0f, 0.48f, 1f}, Shader.TileMode.CLAMP));
        canvas.drawCircle(cx, cy, radius * 1.85f, glowPaint);
        glowPaint.setShader(null);

        facePaint.setShader(new RadialGradient(cx - radius * 0.35f, cy - radius * 0.4f,
                radius * 1.65f, new int[]{0xFF324765, 0xFF172030, 0xFF0C111B},
                new float[]{0f, 0.62f, 1f}, Shader.TileMode.CLAMP));
        canvas.drawCircle(cx, cy, radius, facePaint);
        facePaint.setShader(null);

        float eyeHalfHeight = phase > 0.94f ? 0.35f * density : 1.45f * density;
        float eyeOffset = radius * 0.36f;
        float eyeY = cy - radius * 0.13f;
        float look = typing ? idleWave * 0.7f * density : 0f;
        featurePaint.setStyle(Paint.Style.FILL);
        canvas.drawOval(new RectF(cx - eyeOffset - 1.35f * density + look, eyeY - eyeHalfHeight,
                cx - eyeOffset + 1.35f * density + look, eyeY + eyeHalfHeight), featurePaint);
        canvas.drawOval(new RectF(cx + eyeOffset - 1.35f * density + look, eyeY - eyeHalfHeight,
                cx + eyeOffset + 1.35f * density + look, eyeY + eyeHalfHeight), featurePaint);

        featurePaint.setStyle(Paint.Style.STROKE);
        featurePaint.setStrokeWidth(1.35f * density);
        mouth.reset();
        float mouthY = cy + radius * 0.28f;
        mouth.moveTo(cx - radius * 0.29f, mouthY);
        mouth.quadTo(cx, mouthY + (typing ? radius * 0.31f : radius * 0.17f),
                cx + radius * 0.29f, mouthY);
        canvas.drawPath(mouth, featurePaint);

        if (typing) {
            for (int index = 0; index < 3; index++) {
                float wave = 0.5f + 0.5f * (float) Math.sin(
                        (phase * 3.0f - index * 0.23f) * Math.PI * 2.0);
                particlePaint.setAlpha(80 + Math.round(wave * 150f));
                canvas.drawCircle(cx + radius * 0.85f + index * 3.5f * density,
                        cy - radius * 0.75f - wave * 2.5f * density,
                        (0.75f + wave * 0.45f) * density, particlePaint);
            }
        }
    }

    @Override
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (animator == null) {
            animator = ValueAnimator.ofFloat(0f, 1f);
            animator.setDuration(2_600L);
            animator.setRepeatCount(ValueAnimator.INFINITE);
            animator.setInterpolator(new LinearInterpolator());
            animator.addUpdateListener(value -> {
                phase = (float) value.getAnimatedValue();
                invalidate();
            });
        }
        animator.start();
    }

    @Override
    protected void onDetachedFromWindow() {
        if (animator != null) animator.cancel();
        super.onDetachedFromWindow();
    }
}
