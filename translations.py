import json, os
from functools import lru_cache

_TRANSLATIONS_FALLBACK = {
    'fr': {'ui.ready': 'Prêt.', 'group.prefix': 'Groupe'},
    'en': {'ui.ready': 'Ready.', 'group.prefix': 'Group'}
}

@lru_cache(maxsize=1)
def _load_all():
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, 'translations.json')
    if not os.path.exists(path):
        return _TRANSLATIONS_FALLBACK
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # validation légère: data doit être dict[str, dict[str,str]]
        if not isinstance(data, dict):
            return _TRANSLATIONS_FALLBACK
        return data
    except Exception:
        return _TRANSLATIONS_FALLBACK

def translate(lang: str, key: str, **fmt):
    data = _load_all()
    text = data.get(lang, {}).get(key)
    if text is None:
        text = data.get('fr', {}).get(key, key)
    try:
        return text.format(**fmt)
    except Exception:
        return text
