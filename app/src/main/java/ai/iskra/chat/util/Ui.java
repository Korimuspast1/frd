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
    public static final int BG = Color.rgb(8, 11, 18);
    public static final int SURFACE = Color.rgb(14, 19, 29);
    public static final int CARD = Color.rgb(18, 25, 37);
    public static final int CARD_HIGH = Color.rgb(25, 34, 50);
    public static final int VIOLET = Color.rgb(139, 92, 246);
    public static final int VIOLET_DARK = Color.rgb(100, 55, 216);
    public static final int CYAN = Color.rgb(57, 217, 200);
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
        button.setBackground(ripple(rounded(CARD, 14, context), 0x338B5CF6));
        button.setPadding(dp(context, 12), dp(context, 12), dp(context, 12), dp(context, 12));
        button.setScaleType(ImageButton.ScaleType.CENTER_INSIDE);
        return button;
    }
}
