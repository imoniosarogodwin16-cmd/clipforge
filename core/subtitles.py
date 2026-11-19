import os
from pathlib import Path

def format_ass_timestamp(seconds: float) -> str:
    """Formats seconds into ASS timestamp format: H:MM:SS.cs"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

def generate_animated_ass(words: list, output_ass_path: str, highlight_color: str = "yellow", words_per_screen: int = 4) -> str:
    """
    Generates dynamic TikTok/Reels-style .ass subtitles with active word karaoke highlighting.
    highlight_color: 'yellow' (&H0000E5FF), 'green' (&H0000FF66), or 'cyan' (&H00FFFF00)
    """
    color_map = {
        "yellow": "&H0000E5FF&", # ASS is &HAABBGGRR
        "green": "&H0022FF22&",
        "cyan": "&H00FFFF00&",
        "pink": "&H00FF00FF&"
    }
    hl_hex = color_map.get(highlight_color.lower(), "&H0000E5FF&")
    white_hex = "&H00FFFFFF&"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ViralCaptions,Arial Black,70,{white_hex},&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,6,3,2,40,40,650,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    if not words:
        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(header)
        return output_ass_path

    # Chunk words into small visual phrases (3-4 words)
    chunks = [words[i:i + words_per_screen] for i in range(0, len(words), words_per_screen)]

    for chunk in chunks:
        for active_idx, current_w in enumerate(chunk):
            w_start = current_w["start"]
            w_end = current_w["end"]
            
            # Ensure start < end
            if w_end <= w_start:
                w_end = w_start + 0.25

            t_start = format_ass_timestamp(w_start)
            t_end = format_ass_timestamp(w_end)

            # Build line text with active word highlighted
            line_parts = []
            for idx, w in enumerate(chunk):
                w_upper = w["word"].upper()
                if idx == active_idx:
                    line_parts.append(f"{{\\c{hl_hex}\\b1}}{w_upper}{{\\c{white_hex}\\b1}}")
                else:
                    line_parts.append(f"{{\\c{white_hex}\\b1}}{w_upper}")

            line_text = " ".join(line_parts)
            events.append(f"Dialogue: 0,{t_start},{t_end},ViralCaptions,,0,0,0,,{line_text}")

    content = header + "\n".join(events) + "\n"
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_ass_path
