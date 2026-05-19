import re
from .models import BlacklistWord


def filter_text(text: str) -> str:
    """
    Заменяет слова из блэк-листа на указанные замены.
    Используется кэширование запросов для производительности.
    """
    if not text:
        return text

    if not hasattr(filter_text, '_blacklist_cache'):
        filter_text._blacklist_cache = list(
            BlacklistWord.objects.filter(is_active=True).values_list(
                'word', 'replacement', 'case_sensitive'
            )
        )

    result = text
    for word, replacement, case_sensitive in filter_text._blacklist_cache:
        if not word:
            continue
        flags = 0 if case_sensitive else re.IGNORECASE
        escaped_word = re.escape(word)
        pattern = r'\b' + escaped_word + r'\b'
        result = re.sub(pattern, replacement, result, flags=flags)
    return result