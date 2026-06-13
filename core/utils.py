import re
from datetime import datetime


def generate_filename_from_topic(topic, extension):
    safe_topic = re.sub(r"[^a-zA-Z0-9 ]", "", topic)
    safe_topic = "_".join(safe_topic.lower().split())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{safe_topic}_{timestamp}.{extension}"


def clean_script_for_tts(script):
    """Strip markdown so TTS reads naturally."""
    script = re.sub(r"\*\*(.*?)\*\*", r"\1", script)
    script = re.sub(r"\*(.*?)\*", r"\1", script)
    script = script.replace("#", "").replace("`", "").replace("_", " ")
    return script.strip()
