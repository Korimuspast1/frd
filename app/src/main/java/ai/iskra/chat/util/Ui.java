package ai.iskra.chat.util;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.os.Build;
import android.view.View;
import android.widget.ImageButton;
import android.widget.TextView;

public final class Ui {
    public static final int BG = Color.rgb(11, 12, 14);
    public static final int SURFACE = Color.rgb(18, 19, 22);
    public static final int CARD = Color.rgb(26, 27, 31);
    public static final int CARD_HIGH = Color.rgb(36, 38, 43);
    public static final int VIOLET = Color.rgb(91, 156, 255);
    public static final int VIOLET_DARK = Color.rgb(63, 101, 214);
    public static final int CYAN = Color.rgb(114, 200, 255);
    public static final int TEXT = Color.rgb(245, 247, 251);
    public static final int MUTED = Color.rgb(167, 176, 192);
    public static final int DIM = Color.rgb(127, 137, 154);
    public static final int DANGER = Color.rgb(255, 107, 122);
    public static final int WARNING = Color.rgb(255, 168, 92);

    private Ui() {}

    public static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    public static Drawable rounded(int color, float radiusDp, Context context) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(context, radiusDp));
        return drawable;
    }

    public static Drawable roundedStroke(int color, int strokeColor, float radiusDp, Context context) {
        GradientDrawable drawable = (GradientDrawable) rounded(color, radiusDp, context);
        drawable.setStroke(dp(context, 1), strokeColor);
        return drawable;
    }

    public static Drawable gradient(int start, int end, float radiusDp, Context context) {
        GradientDrawable drawable = new GradientDrawable(
                GradientDrawable.Orientation.TL_BR, new int[]{start, end});
        drawable.setCornerRadius(dp(context, radiusDp));
        return drawable;
    }

    /** Semi-transparent matte surface with a bright glass rim. */
    public static Drawable glass(Context context, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                new int[]{0xB03B3C40, 0x8A28292D, 0x9A202126});
        drawable.setCornerRadius(dp(context, radiusDp));
        drawable.setStroke(Math.max(1, dp(context, 1)), 0x4AFFFFFF);
        return drawable;
    }

    public static Drawable glassSoft(Context context, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                new int[]{0x7A34363C, 0x56212329, 0x70202227});
        drawable.setCornerRadius(dp(context, radiusDp));
        drawable.setStroke(Math.max(1, dp(context, 1)), 0x32FFFFFF);
        return drawable;
    }

    public static Drawable glassBlue(Context context, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                new int[]{0xD05B9CFF, 0xCC3F65D6, 0xD3323A86});
        drawable.setCornerRadius(dp(context, radiusDp));
        drawable.setStroke(Math.max(1, dp(context, 1)), 0x66DCEBFF);
        return drawable;
    }

    public static Drawable ripple(Drawable content, int rippleColor) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            return new RippleDrawable(ColorStateList.valueOf(rippleColor), content, null);
        }
        return content;
    }

    public static void setPadding(View view, int horizontalDp, int verticalDp) {
        int h = dp(view.getContext(), horizontalDp);
        int v = dp(view.getContext(), verticalDp);
        view.setPadding(h, v, h, v);
    }

    public static TextView text(Context context, String value, float sizeSp, int color) {
        TextView view = new TextView(context);
        view.setText(value);
        view.setTextSize(sizeSp);
        view.setTextColor(color);
        view.setFontFeatureSettings("kern");
        return view;
    }

    public static ImageButton iconButton(Context context, int drawableId, String description) {
        ImageButton button = new ImageButton(context);
        button.setImageResource(drawableId);
        button.setContentDescription(description);
        button.setBackground(ripple(glass(context, 99), 0x33FFFFFF));
        button.setPadding(dp(context, 12), dp(context, 12), dp(context, 12), dp(context, 12));
        button.setScaleType(ImageButton.ScaleType.CENTER_INSIDE);
        button.setElevation(dp(context, 5));
        button.setStateListAnimator(null);
        return button;
    }
}
