"""Intent Detector for the AI Office Assistant.

Detects user intent from natural language prompts.
Returns standardized intent objects for the Controller to process.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

INTENT_KEYWORDS: Dict[str, list[str]] = {
    "docx": ["docx", "word", "document", "write", "create doc", "GPT doc", "GPT document", "gpt"],
    "pdf": ["pdf", "portable document", "export pdf", "create pdf", "GPT pdf", "gpt"],
    "markdown": ["markdown", "md", "mark", "readme", "write md"],
    "excel": ["excel", "spreadsheet", "csv", "data table", "xlsx", "GPT spreadsheet", "gpt"],
    "text": ["text", "plain text", "output", "save as text", "GPT text", "gpt"],
    "flashcards": ["flashcard", "anki", "srs", "quiz me", "study card", "GPT flashcards", "gpt"],
    "quiz": ["quiz", "practice test", "test yourself", "practice quiz", "GPT quiz", "gpt"],
    "summary": ["summary", "summarize", "tl;dr", "overview", "recap", "GPT summary", "gpt"],
    "preference": ["I prefer", "remember", "my style", "always", "my preference"],
    "continue": ["continue", "then", "after that", "next", "afterwards"],
}

# P1: Enhanced intent patterns with weights and descriptions
INTENT_PATTERNS: Dict[str, Dict[str, Any]] = {
    "docx": {
        "keywords": ["docx", "word", "document", "write", "create doc", "word doc"],
        "weight": 1.0,
        "description": "Word document generation",
    },
    "pdf": {
        "keywords": ["pdf", "portable document", "export pdf", "create pdf"],
        "weight": 1.0,
        "description": "PDF document generation",
    },
    "markdown": {
        "keywords": ["markdown", "md", "mark", "readme", "write md"],
        "weight": 1.0,
        "description": "Markdown document generation",
    },
    "excel": {
        "keywords": ["excel", "spreadsheet", "csv", "data table", "xlsx"],
        "weight": 1.0,
        "description": "Spreadsheet/data generation",
    },
    "txt": {
        "keywords": ["txt", "text", "plain text", "output", "save as text"],
        "weight": 1.0,
        "description": "Plain text file generation",
    },
    "flashcards": {
        "keywords": ["flashcard", "anki", "srs", "quiz me", "study card"],
        "weight": 1.0,
        "description": "Flashcard/quiz generation",
    },
    "quiz": {
        "keywords": ["quiz", "practice test", "test yourself", "practice quiz"],
        "weight": 1.0,
        "description": "Quiz generation",
    },
    "summary": {
        "keywords": ["summary", "summarize", "tl;dr", "overview", "recap"],
        "weight": 1.0,
        "description": "Summary generation",
    },
    "preference": {
        "keywords": ["I prefer", "remember", "my style", "always", "my preference"],
        "weight": 1.0,
        "description": "User preference statement",
    },
    "continue": {
        "keywords": ["continue", "then", "after that", "next", "afterwards"],
        "weight": 1.0,
        "description": "Continuation of previous topic",
    },
    "help": {
        "keywords": ["help", "what can", "how do", "options", "available"],
        "weight": 1.0,
        "description": "Help/request for options",
    },
}

# P1: Style keywords for detection
STYLE_KEYWORDS: Set[str] = {
    "formal", "informal", "professional", "casual", "academic",
    "friendly", "concise", "detailed", "brief"
}

# P1: Topic-related trigger words
TOPIC_TRIGGERS: Set[str] = {
    "topic", "about", "regarding", "concerning"
}

def _build_details(best_intent: str, prompt_lower: str, prompt_words: list, prompt_len: int) -> dict[str, Any]:
    """Build details dictionary for the detected intent.
    
    Args:
        best_intent: The best matching intent key
        prompt_lower: Lowercased prompt string
        prompt_words: List of words in the prompt
        prompt_len: Number of words in the prompt
    
    Returns:
        Dictionary with intent-specific details
    """
    # Base details common to all intents
    details: dict[str, Any] = {"format": None, "style": None, "topic": None}
    
    # Extract format based on intent
    if best_intent in INTENT_KEYWORDS:
        keywords = INTENT_KEYWORDS[best_intent]
        if isinstance(keywords, list):
            # Old format - list of keywords
            for kw in keywords:
                if kw in prompt_lower:
                    details["format"] = best_intent
                    break
        elif isinstance(keywords, dict):
            # New P1 format with weight/description
            for kw in keywords.get("keywords", []):
                if kw in prompt_lower:
                    details["format"] = best_intent
                    break
    
    # Extract style preferences
    style_keywords = STYLE_KEYWORDS
    for style in style_keywords:
        if style in prompt_lower:
            details["style"] = style
            break
    
    # Extract topic triggers
    topic_triggers = TOPIC_TRIGGERS
    for topic in topic_triggers:
        if topic in prompt_lower:
            details["topic"] = topic
            break
    
    # Add confidence-based adjustments
    if prompt_len > 10:
        details["confidence_note"] = "longer prompt"
    
    return details


def detect_intent(prompt: str) -> Dict[str, Any]:
    """Detect user intent from a natural language prompt.

    P1 Enhancements:
    - Semantic phrase matching beyond single keywords
    - Adaptive confidence scoring based on prompt length
    - Enhanced style and topic extraction
    - Context-aware confidence thresholds

    Args:
        prompt: The user's natural language input

    Returns:
        Dictionary with intent, confidence, and details
    """
    if not prompt or not prompt.strip():
        return {
            "intent": "text",
            "confidence": 0.0,
            "details": {"format": "plain", "reason": "Empty prompt"},
            "raw_prompt": prompt or "",
        }

    prompt_lower = prompt.lower().strip()
    prompt_words = prompt_lower.split()
    prompt_len = len(prompt_words)

    # Check for explicit preference statements first
    if _has_preference_marker(prompt_lower):
        return _detect_preference_intent(prompt_lower, prompt_words, prompt_len)

    # Check for continuation signals with context awareness
    continuation_result = _detect_continuation_intent(prompt_lower, prompt_words, prompt_len)
    if continuation_result:
        return continuation_result

    # Check for help requests
    if any(kw in prompt_lower for kw in ["help", "what can", "how do"]):
        return {
            "intent": "help",
            "confidence": 0.6,
            "details": {"format": None, "style": None, "topic": None},
            "raw_prompt": prompt,
        }

    # Score each intent using enhanced matching
    scores = _calculate_intent_scores(INTENT_PATTERNS, prompt_lower, prompt_words, prompt_len)

    # Find best matching intent
    if not scores or scores[0][1] < _get_adaptive_threshold(prompt_len):
        return {
            "intent": "text",
            "confidence": _calculate_fallback_confidence(scores, prompt_len),
            "details": {"format": "plain", "reason": "No strong matching intent"},
            "raw_prompt": prompt,
        }

    best_intent, best_score = scores[0]

    intent_details = _build_details(best_intent, prompt_lower, prompt_words, prompt_len)

    return {
        "intent": best_intent,
        "confidence": round(best_score, 3),
        "details": intent_details,
        "raw_prompt": prompt,
    }


def _detect_preference_intent(prompt: str) -> Dict[str, Any]:
    """Detect intent when user states a preference.

    Args:
        prompt: Lowercased prompt string

    Returns:
        Intent dictionary with preference details
    """
    details = {"format": None, "style": None, "topic": None}

    # Extract preferred format
    for intent_key, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in prompt:
                prefer_idx = prompt.find("prefer")
                if prefer_idx >= 0:
                    after = prompt[prefer_idx + len("prefer"):].strip()
                    for format_kw in ["docx", "pdf", "excel", "flashcards", "quiz", "summary"]:
                        if format_kw in after:
                            details["format"] = format_kw
                            break

    # Extract style preferences
    style_kw = ["formal", "informal", "professional", "casual", "academic"]
    for sk in style_kw:
        if sk in prompt:
            details["style"] = sk

    # Extract topic
    trigger_words = ["docx", "pdf", "excel", "flashcards", "quiz", "summary", "prefer"]
    min_pos = len(prompt)
    for tw in trigger_words:
        pos = prompt.find(tw)
        if pos >= 0 and pos < min_pos:
            min_pos = pos

    if min_pos < len(prompt) - 1:
        after_prompt = prompt[min_pos + len(max(trigger_words, key=len)):].strip()
        for connector in ["for", "about", "on", "of"]:
            after_prompt = after_prompt.lstrip(connector).strip()
        details["topic"] = after_prompt[:100]

    return {
        "intent": "preference",
        "confidence": 0.95,
        "details": details,
        "raw_prompt": prompt,
    }


# Old _build_details removed - P1 enhancement uses the 4-parameter version
# defined earlier in the file (see _build_details with best_intent, prompt_lower,
# prompt_words, prompt_len parameters at lines 87-138).


def _calculate_intent_scores(
    INTENT_PATTERNS: Dict[str, Dict[str, Any]],
    prompt_lower: str,
    prompt_words: list,
    prompt_len: int,
) -> list[tuple[str, float]]:
    """Calculate intent scores for each pattern based on prompt content.

    P1 Enhancement: Adaptive confidence scoring based on prompt length and pattern matching.
    Also enhances GPT keyword detection by giving bonus when GPT appears with format keywords.

    Args:
        INTENT_PATTERNS: Dictionary of intent patterns with weights and descriptions
        prompt_lower: Lowercased prompt string
        prompt_words: List of words in the prompt
        prompt_len: Number of words in the prompt

    Returns:
        List of (intent_name, confidence) tuples, sorted by confidence descending
    """
    scores: list[tuple[str, float]] = []

    # Track which prompts have GPT + format combination
    has_gpt = any(kw in prompt_lower for kw in ["gpt", "GPT"])
    has_format = any(kw in prompt_lower for kw in [
        "docx", "pdf", "excel", "txt", "flashcards", "quiz", "summary"
    ])

    for intent_name, pattern in INTENT_PATTERNS.items():
        keywords = INTENT_KEYWORDS.get(intent_name, [])
        if not keywords:
            continue

        # Count keyword matches (case-insensitive)
        match_count = sum(1 for kw in keywords if kw.lower() in prompt_lower)

        if match_count == 0:
            scores.append((intent_name, 0.0))
            continue

        # Calculate base score based on match count and pattern weight
        weight = pattern.get("weight", 1.0)
        base_score = (match_count / len(keywords)) * weight

        # P1: Adaptive confidence based on prompt length
        # Shorter prompts with fewer words get higher per-word confidence
        length_factor = max(0.5, 1.0 - (prompt_len * 0.05))

        # P1 Enhancement: Boost confidence for GPT + format combinations
        # When GPT appears with a specific format, prioritize that intent
        gpt_bonus = 0.0
        if has_gpt and has_format:
            # Check if this intent has both GPT and format keywords
            intent_has_gpt = any("gpt" in kw.lower() or "GPT" in kw for kw in keywords)
            intent_has_format = any(
                fmt_kw in intent_name.lower() or fmt_kw in [kw.lower() for kw in keywords]
                for fmt_kw in ["docx", "pdf", "excel", "txt", "flashcards", "quiz", "summary"]
            )
            if intent_has_gpt and intent_has_format:
                gpt_bonus = 0.15  # 15% bonus for GPT + format combination

        # Final confidence
        confidence = min(1.0, base_score * length_factor + gpt_bonus)

        scores.append((intent_name, confidence))

    # Sort by confidence descending
    scores.sort(key=lambda x: x[1], reverse=True)

    return scores


def format_intent(intent_dict: Dict[str, Any]) -> str:
    """Format an intent dictionary into a human-readable string.

    Args:
        intent_dict: The intent dictionary from detect_intent()

    Returns:
        Formatted string description
    """
    intent = intent_dict.get("intent", "unknown")
    confidence = intent_dict.get("confidence", 0.0)
    details = intent_dict.get("details", {})

    parts = [f"Intent: {intent} (confidence: {confidence})"]

    if details.get("format"):
        parts.append(f"Format: {details['format']}")
    if details.get("style"):
        parts.append(f"Style: {details['style']}")
    if details.get("topic"):
        parts.append(f"Topic: {details['topic']}")

    return " | ".join(parts)


def _has_preference_marker(prompt: str) -> bool:
    """Check if the prompt contains preference markers.

    Args:
        prompt: The user's natural language input

    Returns:
        True if preference markers like 'I prefer', 'remember', 'my style' are found
    """
    preference_keywords = ["I prefer", "remember", "my style", "my preference", "always"]
    prompt_lower = prompt.lower()
    return any(kw.lower() in prompt_lower for kw in preference_keywords)


def _detect_continuation_intent(
    prompt_lower: str, prompt_words: list, prompt_len: int
) -> dict | None:
    """Detect if the prompt is a continuation of the previous topic.

    P1 Enhancement: Context-aware intent detection for follow-up queries.

    Args:
        prompt_lower: Lowercased prompt string
        prompt_words: List of words in the prompt
        prompt_len: Number of words in the prompt

    Returns:
        Intent dictionary with continuation details, or None if no continuation detected
    """
    continuation_keywords = ["continue", "then", "after that", "next", "afterwards"]

    # Check if prompt starts with continuation keywords
    for kw in continuation_keywords:
        if prompt_lower.startswith(kw + " ") or prompt_lower == kw:
            # Extract what comes after the continuation keyword
            after = prompt_lower[len(kw) :].strip()
            if after:
                return {
                    "intent": "continue",
                    "confidence": 0.8,
                    "details": {"topic": after[:100], "continuation": True},
                    "raw_prompt": "",
                }

    # Check for "continue" in the middle or end with context
    if "continue" in prompt_lower:
        pos = prompt_lower.find("continue")
        # Get context after "continue"
        after = prompt_lower[pos + len("continue") :].strip()
        if after:
            return {
                "intent": "continue",
                "confidence": 0.7,
                "details": {"topic": after, "continuation": True},
                "raw_prompt": "",
            }

    # Check for other continuation keywords
    for kw in ["then", "after that", "next", "afterwards"]:
        if kw in prompt_lower:
            pos = prompt_lower.index(kw)
            after = prompt_lower[pos + len(kw) :].strip()
            if after:
                return {
                    "intent": "continue",
                    "confidence": 0.6,
                    "details": {"topic": after[:100], "continuation": True},
                    "raw_prompt": "",
                }

    return None
def _calculate_fallback_confidence(scores: list, prompt_len: int) -> float:
    """Calculate fallback confidence when no intents match strongly.
    
    P1 Enhancement: Adaptive confidence scoring based on prompt length.
    
    Args:
        scores: List of (intent, score) tuples
        prompt_len: Number of words in the prompt
    
    Returns:
        Fallback confidence value
    """
    if not scores:
        return round(0.3 * (1.0 - min(prompt_len * 0.05, 0.7)), 2)
    return round(scores[0][1] * 0.8, 2)
def _get_adaptive_threshold(prompt_len: int) -> float:
    """Get adaptive confidence threshold based on prompt length.
    
    P1 Enhancement: Context-aware confidence thresholds that adjust
    based on the length and complexity of the prompt.
    
    Args:
        prompt_len: Number of words in the prompt
    
    Returns:
        Threshold value between 0.0 and 1.0
    """
    # Base threshold decreases with longer prompts (more context = lower bar)
    base = 0.7
    length_factor = max(0.3, 0.7 - (prompt_len * 0.05))
    return round(base * length_factor, 2)