from typing import Optional

FORMAT_TO_SIZE = {
    "9:16": "720x1280",
    "16:9": "1280x720",
    "1:1":  "1024x1024",
}

def format_to_size(fmt: Optional[str]) -> str:
    if not fmt:
        return "1280x720"
    return FORMAT_TO_SIZE.get(fmt.strip(), "1280x720")

def compose_prompt(style: str, user_prompt: str) -> str:
    """
    Возвращает ТОЛЬКО стилизацию + текст пользователя.
    НИКАКИХ 'Target duration/resolution' в prompt — это исключено.
    """
    s = (style or "default").lower()
    if s == "80s":
        base = ("80s action anime: Create an anime clip in the style of 1980s Japanese animation (Akira, Ghost in the Shell 1989, Macross). "
                "Hand-drawn cel shading, grainy texture, deep shadows, vivid neon tones, sharp eyes, thick outlines, slightly slower realistic hand-drawn motion. ")
    elif s == "bleach":
        base = ("Bleach anime style: bold shonen, sharp contrast, speed lines, dramatic light streaks; strong outlines, flowing clothing, dynamic poses; "
                "energy effects, dust bursts; cool tones with glowing highlights. ")
    elif s == "modern":
        base = ("Modern 2D anime painterly: visible brushstrokes, textured backgrounds, clear hand-drawn lineart, precise facial details, glossy expressive eyes; "
                "soft but defined shading; DO NOT produce photorealism/3D/lens FX. ")
    elif s == "none":
        base = ""
    else:
        base = ("Modern 2D anime (Makoto Shinkai / Kyoto Animation): clean lines, expressive characters, bright colors, detailed backgrounds, "
                "smooth motion, dynamic poses, glowing effects. ")

    return (base + user_prompt).strip()
