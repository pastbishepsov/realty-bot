"""
50+ крупнейших городов Польши со slug-ами для URL zametr.pl.
Slug — это нижний регистр, без диакритических знаков, через дефис.
"""

CITIES: list[tuple[str, str]] = [
    # (display_name, url_slug)
    ("Warszawa", "warszawa"),
    ("Kraków", "krakow"),
    ("Łódź", "lodz"),
    ("Wrocław", "wroclaw"),
    ("Poznań", "poznan"),
    ("Gdańsk", "gdansk"),
    ("Szczecin", "szczecin"),
    ("Bydgoszcz", "bydgoszcz"),
    ("Lublin", "lublin"),
    ("Białystok", "bialystok"),
    ("Katowice", "katowice"),
    ("Gdynia", "gdynia"),
    ("Częstochowa", "czestochowa"),
    ("Radom", "radom"),
    ("Sosnowiec", "sosnowiec"),
    ("Toruń", "torun"),
    ("Kielce", "kielce"),
    ("Rzeszów", "rzeszow"),
    ("Gliwice", "gliwice"),
    ("Zabrze", "zabrze"),
    ("Olsztyn", "olsztyn"),
    ("Bielsko-Biała", "bielsko-biala"),
    ("Bytom", "bytom"),
    ("Zielona Góra", "zielona-gora"),
    ("Rybnik", "rybnik"),
    ("Ruda Śląska", "ruda-slaska"),
    ("Opole", "opole"),
    ("Tychy", "tychy"),
    ("Elbląg", "elblag"),
    ("Płock", "plock"),
    ("Wałbrzych", "walbrzych"),
    ("Włocławek", "wloclawek"),
    ("Tarnów", "tarnow"),
    ("Chorzów", "chorzow"),
    ("Koszalin", "koszalin"),
    ("Kalisz", "kalisz"),
    ("Legnica", "legnica"),
    ("Grudziądz", "grudziadz"),
    ("Jaworzno", "jaworzno"),
    ("Słupsk", "slupsk"),
    ("Jastrzębie-Zdrój", "jastrzebie-zdroj"),
    ("Nowy Sącz", "nowy-sacz"),
    ("Jelenia Góra", "jelenia-gora"),
    ("Siedlce", "siedlce"),
    ("Mysłowice", "myslowice"),
    ("Konin", "konin"),
    ("Piotrków Trybunalski", "piotrkow-trybunalski"),
    ("Inowrocław", "inowroclaw"),
    ("Lubin", "lubin"),
    ("Ostrów Wielkopolski", "ostrow-wielkopolski"),
    ("Suwałki", "suwalki"),
    ("Gniezno", "gniezno"),
    ("Starachowice", "starachowice"),
    ("Głogów", "glogow"),
    ("Wodzisław Śląski", "wodzislaw-slaski"),
    ("Ostrowiec Świętokrzyski", "ostrowiec-swietokrzyski"),
    ("Dąbrowa Górnicza", "dabrowa-gornicza"),
    ("Zamość", "zamosc"),
    ("Przemyśl", "przemysl"),
    ("Tarnowskie Góry", "tarnowskie-gory"),
]

# Для быстрого поиска slug по display_name
CITY_SLUG_MAP: dict[str, str] = {name: slug for name, slug in CITIES}

# Для быстрого поиска display_name по slug
SLUG_CITY_MAP: dict[str, str] = {slug: name for name, slug in CITIES}


def get_slug(city_name: str) -> str | None:
    """Вернуть slug по названию города (case-insensitive)."""
    name_lower = city_name.lower()
    for name, slug in CITIES:
        if name.lower() == name_lower or slug == name_lower:
            return slug
    return None


def get_display_name(slug: str) -> str:
    """Вернуть отображаемое название по slug."""
    return SLUG_CITY_MAP.get(slug, slug.capitalize())
