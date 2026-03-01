"""
Система локализации бота.
Использование: t('key', lang, param=value)
"""

from locales import ru, en, pl

_LOCALES = {
    'ru': ru.STRINGS,
    'en': en.STRINGS,
    'pl': pl.STRINGS,
}

SUPPORTED_LANGS = ('ru', 'en', 'pl')
DEFAULT_LANG = 'ru'


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """
    Вернуть переведённую строку по ключу.
    Если ключ не найден в запрошенном языке — fallback на русский.
    Поддерживает форматирование: t('results_header', lang, city='Warszawa', ...)
    """
    strings = _LOCALES.get(lang, _LOCALES[DEFAULT_LANG])
    text = strings.get(key) or _LOCALES[DEFAULT_LANG].get(key, f'[{key}]')
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text
