package ai.iskra.chat.ui;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.view.View;
import android.view.animation.LinearInterpolator;

import ai.iskra.chat.util.Ui;

/** A calm animated status that shows high-level progress without exposing private chain-of-thought. */
public final class ThinkingIndicatorView extends View {
    private static final String[] QUICK_STEPS = {
            "Понимаю запрос", "Ищу нужное", "Готовлю ответ"
    };
    private static final String[] DEEP_STEPS = {
            "Разбираю вопрос", "Проверяю контекст", "Сверяю факты", "Формулирую ответ"
    };

    private final Paint orbPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dotPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final boolean deep;
    private ValueAnimator animator;
    private float phase;

    public ThinkingIndicatorView(Context context, boolean deep) {
        super(context);
        this.deep = deep;
        textPaint.setColor(0xFFD7DFEB);
        textPaint.setTextSize(context.getResources().getDisplayMetrics().scaledDensity * 14f);
        textPaint.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        dotPaint.setColor(Ui.CYAN);
        setContentDescription(deep ? "kvsai рассуждает и проверяет ответ" : "kvsai готовит ответ");
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
    }

    @Override protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int desiredWidth = Ui.dp(getContext(), 260);
        int width = resolveSize(desiredWidth, widthMeasureSpec);
        setMeasuredDimension(width, Ui.dp(getContext(), 58));
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float density = getResources().getDisplayMetrics().density;
        float centerX = 20f * density;
        float centerY = getHeight() / 2f;
        float pulse = 0.5f + 0.5f * (float) Math.sin(phase * Math.PI * 2.0);
        float radius = (8f + pulse * 2f) * density;
        orbPaint.setShader(new RadialGradient(centerX - radius * 0.2f, centerY - radius * 0.25f,
                radius * 1.8f, new int[]{0xFF8ED5FF, 0xFF4D8DF4, 0x003E66D8},
                new float[]{0f, 0.48f, 1f}, Shader.TileMode.CLAMP));
        canvas.drawCircle(centerX, centerY, radius, orbPaint);
        orbPaint.setShader(null);

        String[] steps = deep ? DEEP_STEPS : QUICK_STEPS;
        int step = Math.min(steps.length - 1, (int) (phase * steps.length));
        float textX = 39f * density;
        float baseline = centerY - (textPaint.ascent() + textPaint.descent()) / 2f;
        canvas.drawText(steps[step], textX, baseline, textPaint);

        float labelWidth = textPaint.measureText(steps[step]);
        for (int index = 0; index < 3; index++) {
            double wave = Math.sin((phase * 3f - index * 0.24f) * Math.PI * 2.0);
            int alpha = 75 + (int) (Math.max(0, wave) * 180);
            dotPaint.setAlpha(alpha);
            canvas.drawCircle(textX + labelWidth + (10f + index * 7f) * density,
                    centerY + 1f * density, (1.8f + Math.max(0, (float) wave) * 0.6f) * density, dotPaint);
        }
    }

    @Override protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (animator == null) {
            animator = ValueAnimator.ofFloat(0f, 1f);
            animator.setDuration(deep ? 5_600L : 3_800L);
            animator.setRepeatCount(ValueAnimator.INFINITE);
            animator.setInterpolator(new LinearInterpolator());
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
