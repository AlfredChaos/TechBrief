from __future__ import annotations

from collections.abc import Iterable

THEME_TOKENS = {
    "colors": {
        "surface": "#fcf8fb",
        "surface-dim": "#dcd9dc",
        "surface-bright": "#fcf8fb",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f6f3f5",
        "surface-container": "#f0edef",
        "surface-container-high": "#eae7ea",
        "surface-container-highest": "#e4e2e4",
        "on-surface": "#1b1b1d",
        "on-surface-variant": "#414755",
        "inverse-surface": "#303032",
        "inverse-on-surface": "#f3f0f2",
        "outline": "#717786",
        "outline-variant": "#c1c6d7",
        "surface-tint": "#005bc1",
        "primary": "#0058bc",
        "on-primary": "#ffffff",
        "primary-container": "#0070eb",
        "on-primary-container": "#fefcff",
        "inverse-primary": "#adc6ff",
        "secondary": "#bc000a",
        "on-secondary": "#ffffff",
        "secondary-container": "#e2241f",
        "on-secondary-container": "#fffbff",
        "tertiary": "#9e3d00",
        "on-tertiary": "#ffffff",
        "tertiary-container": "#c64f00",
        "on-tertiary-container": "#fffbff",
        "error": "#ba1a1a",
        "on-error": "#ffffff",
        "error-container": "#ffdad6",
        "on-error-container": "#93000a",
        "background": "#fcf8fb",
        "on-background": "#1b1b1d",
        "surface-variant": "#e4e2e4",
    },
    "dark-colors": {
        "surface": "#131316",
        "surface-dim": "#131316",
        "surface-bright": "#39393c",
        "surface-container-lowest": "#0e0e11",
        "surface-container-low": "#1b1b1f",
        "surface-container": "#1f1f23",
        "surface-container-high": "#2a2a2e",
        "surface-container-highest": "#353539",
        "on-surface": "#e4e2e4",
        "on-surface-variant": "#c1c6d7",
        "inverse-surface": "#e4e2e4",
        "inverse-on-surface": "#303032",
        "outline": "#8b91a0",
        "outline-variant": "#414755",
        "surface-tint": "#adc6ff",
        "primary": "#adc6ff",
        "on-primary": "#003063",
        "primary-container": "#0070eb",
        "on-primary-container": "#d6e3ff",
        "inverse-primary": "#0058bc",
        "secondary": "#ffb4ab",
        "on-secondary": "#690005",
        "secondary-container": "#e2241f",
        "on-secondary-container": "#ffdad6",
        "tertiary": "#ffb68c",
        "on-tertiary": "#532200",
        "tertiary-container": "#c64f00",
        "on-tertiary-container": "#ffdbc9",
        "error": "#ffb4ab",
        "on-error": "#690005",
        "error-container": "#93000a",
        "on-error-container": "#ffdad6",
        "background": "#131316",
        "on-background": "#e4e2e4",
        "surface-variant": "#414755",
    },
    "typography": {
        "display-lg": {
            "font-family": "'Inter', sans-serif",
            "font-size": "48px",
            "font-weight": "700",
            "line-height": "1.1",
            "letter-spacing": "-0.02em",
        },
        "display-lg-mobile": {
            "font-size": "32px",
            "line-height": "1.2",
        },
        "headline-md": {
            "font-family": "'Inter', sans-serif",
            "font-size": "24px",
            "font-weight": "600",
            "line-height": "1.3",
            "letter-spacing": "-0.01em",
        },
        "article-body": {
            "font-family": "'Noto Serif', serif",
            "font-size": "18px",
            "font-weight": "400",
            "line-height": "1.6",
        },
        "article-body-cn": {
            "font-family": "'Noto Serif SC', serif",
            "font-size": "18px",
            "font-weight": "400",
            "line-height": "1.8",
        },
        "label-caps": {
            "font-family": "'Inter', sans-serif",
            "font-size": "12px",
            "font-weight": "600",
            "line-height": "1",
            "letter-spacing": "0.05em",
        },
    },
    "rounded": {
        "sm": "4px",
        "default": "8px",
        "md": "12px",
        "lg": "16px",
        "xl": "24px",
        "full": "9999px",
    },
    "spacing": {
        "xs": "4px",
        "sm": "12px",
        "base": "8px",
        "md": "24px",
        "lg": "48px",
        "xl": "80px",
        "container-max": "1120px",
        "gutter": "24px",
    },
}


def _flatten_tokens(prefix: str, mapping: dict) -> Iterable[str]:
    for key, value in mapping.items():
        token_name = f"{prefix}-{key}".replace("_", "-")
        if isinstance(value, dict):
            yield from _flatten_tokens(token_name, value)
        else:
            yield f"  --{token_name}: {value};"


def build_theme_css_variables() -> str:
    lines = list(_flatten_tokens("tb", THEME_TOKENS))
    return "\n".join(lines)


def build_dark_mode_css_variables() -> str:
    """Generate CSS custom properties for dark mode from THEME_TOKENS["dark-colors"]."""
    lines = list(_flatten_tokens("tb-colors", THEME_TOKENS["dark-colors"]))
    return "\n".join(lines)
