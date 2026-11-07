from typing import List, Tuple, Optional, Dict, Any

CONSTRAINT_PROFILES: Dict[str, Dict[str, Any]] = {
    "x": {
        "platform_name": "X (formerly Twitter)",
        "min_length": 10,
        "max_length": 280,
        "min_hashtags": 0,
        "max_hashtags": 2,
        "tone": "punchy, direct, urgent",
        "description": "Short-form news hook with max 2 hashtags and strict 280-character boundary."
    },
    "linkedin": {
        "platform_name": "LinkedIn",
        "min_length": 150,
        "max_length": 1500,
        "min_hashtags": 3,
        "max_hashtags": 5,
        "tone": "professional, analytical, structured",
        "description": "Thought leadership post with 3-5 professional topic hashtags."
    },
    "instagram": {
        "platform_name": "Instagram",
        "min_length": 100,
        "max_length": 1000,
        "min_hashtags": 5,
        "max_hashtags": 15,
        "tone": "visual, conversational, engaging",
        "description": "Storytelling caption with call to action and 5-15 discovery hashtags."
    }
}

def validate_variant_against_profile(
    platform: str,
    content: str,
    hashtags: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validates text and hashtags against the platform's constraint profile.
    Returns: (is_valid: bool, error_message: Optional[str])
    """
    plat = platform.lower()
    profile = CONSTRAINT_PROFILES.get(plat)
    if not profile:
        return False, f"Unknown platform '{platform}'. Supported platforms: {list(CONSTRAINT_PROFILES.keys())}"

    # Calculate full post text length including hashtags
    formatted_tags = [f"#{t.lstrip('#')}" for t in hashtags]
    full_text = f"{content.strip()} {' '.join(formatted_tags)}".strip()
    total_len = len(full_text)
    num_tags = len(hashtags)

    # 1. Max Length Constraint
    if total_len > profile["max_length"]:
        return (
            False,
            f"Constraint violation [{platform}]: Total character length ({total_len}) exceeds maximum limit of {profile['max_length']} characters."
        )

    # 2. Min Length Constraint
    if total_len < profile["min_length"]:
        return (
            False,
            f"Constraint violation [{platform}]: Total character length ({total_len}) is below minimum required of {profile['min_length']} characters."
        )

    # 3. Max Hashtags Constraint
    if num_tags > profile["max_hashtags"]:
        return (
            False,
            f"Constraint violation [{platform}]: Hashtag count ({num_tags}) exceeds maximum allowed of {profile['max_hashtags']}."
        )

    # 4. Min Hashtags Constraint
    if num_tags < profile["min_hashtags"]:
        return (
            False,
            f"Constraint violation [{platform}]: Hashtag count ({num_tags}) is below minimum required of {profile['min_hashtags']}."
        )

    return True, None
