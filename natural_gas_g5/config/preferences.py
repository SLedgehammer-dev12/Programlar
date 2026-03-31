"""
User preferences management.

Handles loading and saving of user preferences such as 'Don't show again' flags.
"""
import json
import os
import logging
from pathlib import Path

# Preferences file path (in user's home directory or local)
# Using local directory for portability as requested, or standard app data?
# Given the user works on Desktop/Python.py, let's keep it local to the app for now
# or better, use a standard location but simple.
# Let's use a hidden file in the same directory as the main script for portability.
PREFS_FILE = Path("user_preferences.json")

def load_preferences() -> dict:
    """
    Load user preferences from file.
    
    Returns:
        Dictionary of preferences.
    """
    if not PREFS_FILE.exists():
        return {}
    
    try:
        with open(PREFS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to load preferences: {e}")
        return {}

def save_preferences(prefs: dict) -> None:
    """
    Save user preferences to file.
    
    Args:
        prefs: Dictionary of preferences to save.
    """
    try:
        # Load existing to merge
        current = load_preferences()
        current.update(prefs)
        
        with open(PREFS_FILE, 'w', encoding='utf-8') as f:
            json.dump(current, f, indent=4)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to save preferences: {e}")

def get_preference(key: str, default=None):
    """Get a specific preference value."""
    prefs = load_preferences()
    return prefs.get(key, default)

def set_preference(key: str, value) -> None:
    """Set a specific preference value."""
    save_preferences({key: value})
