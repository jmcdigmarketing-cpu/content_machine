import os


def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))

    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def split_script_into_lines(script, max_words=8):
    words = script.split()
    lines = []

    for i in range(0, len(words), max_words):
        line = " ".join(words[i : i + max_words])
        lines.append(line)

    return lines


def generate_subtitle_file(script, duration):
    output_dir = os.path.join("output", "video")
    os.makedirs(output_dir, exist_ok=True)

    subtitle_path = os.path.abspath(os.path.join(output_dir, "temp_subtitles.srt"))

    lines = split_script_into_lines(script)

    if not lines:
        raise Exception("Subtitle generation failed: empty script.")

    segment_duration = duration / len(lines)

    with open(subtitle_path, "w", encoding="utf-8") as f:
        for i, line in enumerate(lines):
            start_time = format_timestamp(i * segment_duration)

            # Ensure last subtitle ends exactly at duration
            if i == len(lines) - 1:
                end_time = format_timestamp(duration)
            else:
                end_time = format_timestamp((i + 1) * segment_duration)

            f.write(f"{i + 1}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{line}\n\n")

    return subtitle_path
