"""Owned gameplay backgrounds from `video/backgrounds/` (#782 #786 #955).

A topic draws footage from one folder, chosen in this order (`choose_footage`):

1. keyword - a folder name in the topic ("Fortnite reload" -> Fortnite);
2. alias - the first matching playlist row's `footage` ("NFL draft" -> Madden 26, #786);
3. domain - the topic's own domain, athlete names included (#946), to the playlist row
   carrying it ("Wemby's 40-point night" -> nba -> Basketball -> 2k26);
4. llm - the cheap tier, shown the operator's topic, which may answer NONE.

Nothing else (#955). The chain used to end in the model shown the trademark-stripped stock
rewrite, then `random.choice` over every game folder: the Wemby Short cut UFC 5 fighters and
the Clair Obscur Short cut Madden. An unmatched topic now gets no local clips, so the render
takes stock B-roll or a plain branded background - never another game. The decision is kept
per topic for the process (fast cut and the hybrid fallback read one choice) and recorded on
the background asset as `footage:<how>:<folder>` for `ops footage-gaps`.
"""

import json
import os
import random

from typing import Optional

from core import process_state

from assets.base import AssetProvider
from assets.category import detect_category
from assets.types import AssetResult
from core.logging import get_logger

logger = get_logger("assets.local")

BASE_VIDEO_DIR = os.path.join("video", "backgrounds")


def _nearest_license_file(clip_path: str) -> str | None:
    base = os.path.abspath(BASE_VIDEO_DIR)
    current = os.path.abspath(os.path.dirname(clip_path))
    while current == base or current.startswith(base + os.sep):
        candidate = os.path.join(current, "license.yaml")
        if os.path.isfile(candidate):
            return candidate
        if current == base:
            break
        current = os.path.dirname(current)
    return None


def _license_attribution(clip_path: str) -> str | None:
    sidecar = _nearest_license_file(clip_path)
    if not sidecar:
        return None
    try:
        with open(sidecar, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("expected an object")
        owner = str(data.get("owner") or "").strip()
        license_name = str(data.get("license") or "").strip()
        commercial = data.get("commercial_use")
        parts = []
        if license_name:
            parts.append(license_name)
        if owner:
            parts.append(f"owner: {owner}")
        if commercial is not None:
            parts.append(f"commercial use: {'yes' if bool(commercial) else 'no'}")
        return "; ".join(parts) or None
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Local clip license unreadable (%s): %s", sidecar, exc)
        return None


def _needs_credit(license_name: str) -> bool:
    low = license_name.lower()
    return "attribution" in low or "cc by" in low or "cc-by" in low


def clip_credit(clip_path: str) -> str | None:
    """#1019: the credit line a clip's licence requires (CC BY), else None.

    Owned footage and licences without an attribution term need no credit.
    """
    sidecar = _nearest_license_file(clip_path)
    if not sidecar:
        return None
    try:
        with open(sidecar, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, TypeError) as exc:
        logger.debug("clip credit: licence unreadable (%s): %s", sidecar, exc)
        return None
    if not isinstance(data, dict):
        return None
    license_name = str(data.get("license") or "").strip()
    if not _needs_credit(license_name):
        return None
    folder = os.path.basename(os.path.dirname(sidecar))
    short = license_name.split(";")[0].strip()
    sources = [str(s).strip() for s in data.get("sources") or [] if str(s).strip()]
    owner = str(data.get("owner") or "").strip()
    who = ", ".join(sources) if sources else owner
    return f"{folder} gameplay: {short}" + (f" - {who}" if who else "")


def clip_credits(clip_paths) -> list[str]:
    """One credit per licence folder, in first-use order (#1019)."""
    found: list[str] = []
    for path in clip_paths or []:
        line = clip_credit(path)
        if line and line not in found:
            found.append(line)
    return found


def _get_subfolders(base_path):
    folders = []
    for root, _, files in os.walk(base_path):
        if any(f.lower().endswith((".mp4", ".mov")) for f in files):
            folders.append(root)
    return folders


_GENERIC_FOLDER_NAMES = frozenset({"gaming", "sports", "general", "video", "backgrounds"})


def _keyword_choose_folder(topic: str, folders: list[str]) -> str | None:
    """Pick a library folder whose name appears in the original topic.

    Stock-query rewrite turns "Fortnite reload" into "video game gameplay
    esports", so this must run on the operator topic — not the rewrite.
    """
    hay = (topic or "").lower()
    if not hay or not folders:
        return None
    scored: list[tuple[int, str]] = []
    for folder in folders:
        name = os.path.basename(folder).lower().replace("_", " ").replace("-", " ").strip()
        if not name or name in _GENERIC_FOLDER_NAMES:
            continue
        if name in hay:
            scored.append((len(name), folder))
            continue
        tokens = [tok for tok in name.split() if len(tok) >= 3 and tok not in _GENERIC_FOLDER_NAMES]
        hits = [tok for tok in tokens if tok in hay]
        if hits:
            scored.append((max(len(tok) for tok in hits), folder))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _alias_choose_folder(topic: str, folders: list[str], channel_id=None) -> str | None:
    """The footage folder of the first franchise playlist the topic matches (#786).

    "NFL draft" names no folder, but the NFL playlist row in config/playlists.json lists
    `footage: ["Madden 26"]`, so an NFL Short cuts Madden gameplay instead of a random game.
    """
    try:
        from core.playlists import playlist_map, _matches

        rows = playlist_map(channel_id or "tapin")
    except Exception as exc:
        logger.debug("footage alias skipped: %s", exc)
        return None
    hay = (topic or "").lower()
    by_name = {os.path.basename(f).casefold(): f for f in folders}
    for row in rows:
        if not _matches(hay, [str(k) for k in row.get("keys") or []]):
            continue
        for name in row.get("footage") or []:
            folder = by_name.get(str(name).casefold())
            if folder:
                return folder
    return None


def _domain_choose_folder(topic: str, folders: list[str], channel_id=None) -> str | None:
    """The footage folder of the playlist row carrying the topic's own domain (#955).

    "Wemby's 40-point night" names no folder and no playlist key, but it reads nba (#946),
    and the Basketball row says `"domain": "nba"`, `footage: ["2k26"]`.
    """
    try:
        from apis.topic_scorer import infer_topic_domain

        domain = infer_topic_domain(topic or "")
    except Exception as exc:
        logger.debug("footage by domain skipped: %s", exc)
        return None
    return _folder_for_domain(domain, folders, channel_id)


def _folder_for_domain(domain: str, folders: list[str], channel_id=None) -> str | None:
    """The footage folder of the playlist row whose `"domain"` is `domain`, or None."""
    if not domain or domain == "neutral":
        return None
    try:
        from core.playlists import playlist_map

        rows = playlist_map(channel_id or "tapin")
    except Exception as exc:
        logger.debug("footage by domain skipped: %s", exc)
        return None
    by_name = {os.path.basename(f).casefold(): f for f in folders}
    for row in rows:
        if str(row.get("domain") or "") != domain:
            continue
        for name in row.get("footage") or []:
            folder = by_name.get(str(name).casefold())
            if folder:
                return folder
    return None


def _ai_choose_folder(topic, folders):
    """The cheap tier picks the folder whose game or sport IS the topic's subject, or none.

    It is shown the operator's topic (#955): the stock rewrite strips trademarks, so the
    model never saw "Wemby" and picked whatever looked sporty.
    """
    if not folders:
        return None

    folder_list_text = "\n".join(f"- {os.path.relpath(f, BASE_VIDEO_DIR)}" for f in folders)

    prompt = f"""
Pick the background-footage folder for a short video about this topic.

Topic:
{topic}

Folders (each holds gameplay of one game or sport):
{folder_list_text}

Answer with the exact folder path ONLY if that folder's game or sport IS the subject of the
topic. If no folder's game or sport is the subject, answer NONE. Never pick a different game or
sport because it looks similar.
"""

    try:
        from core.llm_router import complete

        # Picking a background folder from a list is trivial → cheap tier.
        choice = complete(
            prompt,
            tier="cheap",
            system="Select the matching folder from the list, or answer NONE.",
            temperature=0,
            max_tokens=120,
        ).strip()
        if choice.strip("`'\" .").upper() == "NONE":
            return None
        for folder in folders:
            if os.path.relpath(folder, BASE_VIDEO_DIR) == choice:
                return folder
    except Exception:
        pass
    return None


def choose_footage(
    topic: str, folders: list[str], channel_id=None, *, use_llm: bool = True
) -> tuple[str | None, str]:
    """(folder, how) - how is keyword / alias / domain / seed / run-domain / llm - or
    (None, "none"). `seed` and `run-domain` come from `set_footage_context` (#962)."""
    for how, pick in (
        ("keyword", lambda: _keyword_choose_folder(topic, folders)),
        ("alias", lambda: _alias_choose_folder(topic, folders, channel_id)),
        ("domain", lambda: _domain_choose_folder(topic, folders, channel_id)),
    ):
        folder = pick()
        if folder:
            return folder, how
    seed, domain = _contexts.get(topic or "", ("", ""))
    if seed and seed != topic:
        for pick in (
            lambda: _keyword_choose_folder(seed, folders),
            lambda: _alias_choose_folder(seed, folders, channel_id),
            lambda: _domain_choose_folder(seed, folders, channel_id),
        ):
            folder = pick()
            if folder:
                return folder, "seed"
    folder = _folder_for_domain(domain, folders, channel_id)
    if folder:
        return folder, "run-domain"
    if use_llm:
        folder = _ai_choose_folder(topic, folders)
        if folder:
            return folder, "llm"
    return None, "none"


_choices: dict[tuple[str, str, tuple[str, ...]], tuple[str | None, str]] = {}
# #962: angle text -> (the run's own topic, the sport its facts name). Run 113's angle had
# dropped the "NBA" the operator typed; the soccer runs named only a tournament stage.
_contexts: dict[str, tuple[str, str]] = {}


def set_footage_context(topic: str, *, seed: str = "", domain: str = "") -> None:
    """Tell the chooser what run `topic` belongs to - tried after the topic's own words."""
    _contexts[topic or ""] = (seed or "", domain or "")


def footage_context_for_run(content_run_id: int | None) -> tuple[str, str]:
    """(input topic, sport) of a saved run: the stored topic domain (#866, read with the
    pasted facts), else the input topic's own. ("", "") when there is no run."""
    if not content_run_id:
        return "", ""
    try:
        import json

        from apis.topic_scorer import infer_topic_domain
        from storage.repositories.content_runs import get_content_run_repository

        run = get_content_run_repository().get(int(content_run_id))
        if run is None:
            return "", ""
        seed = str(getattr(run, "input_topic", "") or "")
        features = json.loads(getattr(run, "features_json", "") or "{}")
        stored = (features.get("domains") or {}) if isinstance(features, dict) else {}
        domain = str(stored.get("topic") or "") if isinstance(stored, dict) else ""
        if not domain or domain == "neutral":
            domain = infer_topic_domain(seed)
        return seed, "" if domain == "neutral" else domain
    except Exception as exc:
        logger.debug("footage context for run %s skipped: %s", content_run_id, exc)
        return "", ""


def _remember(
    topic: str, channel_id, folders: tuple[str, ...], choice: tuple[str | None, str]
) -> None:
    _choices[(topic or "", str(channel_id or ""), folders)] = choice


def footage_choice(topic: str, folders: list[str], channel_id=None) -> tuple[str | None, str]:
    """`choose_footage`, decided once per topic and library for the process."""
    key = (topic or "", str(channel_id or ""), tuple(folders))
    if key not in _choices:
        _remember(topic, channel_id, tuple(folders), choose_footage(topic, folders, channel_id))
    return _choices[key]


def last_footage_choice(topic: str, channel_id=None) -> tuple[str | None, str] | None:
    """The most recent decision for `topic` on `channel_id` this process, or None."""
    for (t, c, _folders), choice in reversed(list(_choices.items())):
        if t == (topic or "") and c == str(channel_id or ""):
            return choice
    return None


def footage_source_id(folder: str | None, how: str) -> str:
    """`footage:<how>:<folder name>` - what the background asset row records (#955)."""
    return f"footage:{how}:{os.path.basename(folder) if folder else ''}"


def reset_footage_choices() -> None:
    _choices.clear()
    _contexts.clear()


process_state.register_reset("assets.local_provider.footage_choices", reset_footage_choices)


class LocalAssetProvider(AssetProvider):
    name = "local"

    def choose(self, topic: str, category: str, channel_id=None) -> tuple[str | None, str]:
        """The folder this topic's footage comes from, and how it was chosen (#955)."""
        if not os.path.exists(BASE_VIDEO_DIR):
            return None, "none"

        category_path = os.path.join(BASE_VIDEO_DIR, category)
        if not os.path.exists(category_path):
            category_path = BASE_VIDEO_DIR

        candidate_folders = _get_subfolders(category_path) or _get_subfolders(BASE_VIDEO_DIR)
        if not candidate_folders:
            return None, "none"
        return footage_choice(topic, candidate_folders, channel_id)

    def candidate_clips(self, topic: str, category: str, channel_id=None) -> list[str]:
        """Every clip in the folder this topic picks (one game), for multi-shot backgrounds
        (#782). `find_video` draws its single clip from the same list. No folder matches ->
        [] (#955): never another game's footage."""
        chosen_folder, _how = self.choose(topic, category, channel_id)
        if not chosen_folder:
            return []
        return [
            os.path.join(chosen_folder, f)
            for f in sorted(os.listdir(chosen_folder))
            if f.lower().endswith((".mp4", ".mov"))
        ]

    def find_video(self, topic: str, category: str, channel_id=None) -> Optional[AssetResult]:
        video_files = self.candidate_clips(topic, category, channel_id)
        if not video_files:
            return None

        path = random.choice(video_files)
        try:
            from assets.clip_memory import pick_unseen

            chosen = pick_unseen(video_files)
            if chosen:
                path = chosen
        except Exception as exc:
            logger.debug("clip anti-repeat skipped: %s", exc)
        folder, how = self.choose(topic, category, channel_id)
        return AssetResult(
            path=path,
            provider=self.name,
            source_id=footage_source_id(folder, how),
            query=topic,
            attribution=_license_attribution(path),
            credits=clip_credits([path]),
        )
