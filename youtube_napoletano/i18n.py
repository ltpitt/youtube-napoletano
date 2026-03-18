"""
Internationalization (i18n) module for youtube-napoletano.
Provides multi-language support with lazy loading and fallback.
"""

import json
from pathlib import Path
from typing import Any, Optional


class I18n:
    """Handler for application translations."""

    def __init__(self, default_language: str = "nap"):
        """Initialize i18n with default language."""
        self.default_language = default_language
        self.current_language = default_language
        self.translations = {}
        self._load_all_languages()

    def _load_all_languages(self) -> None:
        """Load all available language files."""
        locales_dir = Path(__file__).parent / "locales"
        if not locales_dir.exists():
            return

        for lang_file in locales_dir.glob("*.json"):
            lang_code = lang_file.stem
            try:
                with open(lang_file, "r", encoding="utf-8") as f:
                    self.translations[lang_code] = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load {lang_file}: {e}")

    def set_language(self, language: str) -> None:
        """Set the current language."""
        if language in self.translations:
            self.current_language = language
        else:
            self.current_language = self.default_language

    def get(self, key: str, language: Optional[str] = None, **kwargs: Any) -> str:
        """
        Get translated string with support for nested keys and interpolation.

        Args:
            key: Translation key (supports nested keys like "messages.download_complete")
            language: Override language (if None, uses current_language)
            **kwargs: Variables for string interpolation

        Returns:
            Translated string or key itself if not found
        """
        lang = language or self.current_language
        lang_dict = self.translations.get(lang, {})

        # Support nested keys like "messages.download_complete"
        keys = key.split(".")
        value: Any = lang_dict
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break

        # Fallback to default language if not found
        if value is None and lang != self.default_language:
            return self.get(key, language=self.default_language, **kwargs)

        # Return key if translation not found in any language
        if value is None:
            return key

        # Perform string interpolation if kwargs provided
        if isinstance(value, str) and kwargs:
            try:
                return value.format(**kwargs)
            except KeyError:
                return value

        return str(value) if isinstance(value, str) else key

    def get_available_languages(self) -> dict[str, str]:
        """Return dictionary of language codes to language names."""
        return {
            "nap": "🌋 Napoletano",
            "en": "🇬🇧 English",
            "it": "🇮🇹 Italiano",
            "es": "🇪🇸 Español",
            "fr": "🇫🇷 Français",
            "de": "🇩🇪 Deutsch",
        }

    def __call__(self, key: str, **kwargs: Any) -> str:
        """Allow i18n to be called as function: i18n('key') instead of i18n.get('key')."""
        return self.get(key, **kwargs)


# Global i18n instance
i18n = I18n()
