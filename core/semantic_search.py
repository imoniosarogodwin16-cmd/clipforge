import re
from typing import List, Dict
from sqlmodel import Session, select
from core.database import engine
from core.models import TranscriptSegment, Stream

SYNONYM_MAP = {
    "mission": ["mission", "objective", "checkpoint", "target", "task", "infiltrate", "quest", "job", "contract", "heist", "setup"],
    "police": ["police", "cops", "cop", "chase", "wanted", "siren", "stars", "fbi", "swat", "arrest", "helicopter", "heli"],
    "heist": ["heist", "vault", "bank", "robbery", "loot", "drill", "alarm", "cash", "score", "security"],
    "crash": ["crash", "crashed", "wreck", "accident", "hit", "smash", "explode", "explosion", "flipped", "flying"],
    "funny": ["laugh", "laughing", "hilarious", "joke", "funny", "bro", "no way", "what the", "lmao", "dead", "died", "fail", "glitch", "bug"],
    "rage": ["rage", "angry", "screaming", "scream", "mad", "hate", "quit", "stupid", "broken", "why", "unbelievable"]
}

def expand_query(query: str) -> List[str]:
    """Expands user query into semantic synonym keywords."""
    q_lower = query.lower().strip()
    words = re.findall(r"\w+", q_lower)
    terms = set(words)
    terms.add(q_lower)

    for word in words:
        for key, syns in SYNONYM_MAP.items():
            if word in syns or word == key:
                terms.update(syns)
    
    return list(terms)

def search_stream_dialogue(stream_id: str = None, query: str = "", limit: int = 5) -> List[Dict]:
    """
    Searches indexed transcript segments for keywords/synonyms.
    Returns candidate timestamps with matching text snippet.
    """
    search_terms = expand_query(query)
    results = []

    with Session(engine) as session:
        # Fetch segments for this stream (or all streams if stream_id is None/empty)
        stmt = select(TranscriptSegment)
        if stream_id:
            stmt = stmt.where(TranscriptSegment.stream_id == stream_id)
        segments = session.exec(stmt).all()

        for seg in segments:
            seg_text_lower = seg.text.lower()
            match_score = 0
            matched_words = []
            for term in search_terms:
                if term in seg_text_lower:
                    match_score += (2 if term == query.lower() else 1)
                    matched_words.append(term)

            if match_score > 0:
                results.append({
                    "start": seg.start_time,
                    "end": seg.end_time,
                    "duration": round(seg.end_time - seg.start_time, 1),
                    "text": seg.text,
                    "score": min(99, 70 + (match_score * 5)),
                    "matched_terms": matched_words,
                    "label": f"Moment: '{query.title()}' ({seg.start_time:.0f}s - {seg.end_time:.0f}s)"
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
