"""
Все inline-клавиатуры бота.
"""

import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from parsers.cities import CITIES

CITIES_PER_PAGE = 12  # Городов на странице выбора


def main_menu_keyboard(is_realtor: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Поиск", callback_data="action:search")
    builder.button(text="🏙 Мой город", callback_data="action:filters")
    if is_realtor:
        builder.button(text="📊 Аналитика улицы", callback_data="action:analytics")
    builder.button(text="👤 Профиль", callback_data="action:profile")
    builder.adjust(2)
    return builder.as_markup()


def role_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏢 Риэлтор / Агент", callback_data="role:realtor")
    builder.button(text="🏠 Частное лицо", callback_data="role:user")
    builder.adjust(1)
    return builder.as_markup()


def skip_keyboard(action: str = "skip") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Пропустить", callback_data=f"action:{action}")
    return builder.as_markup()


def yes_no_keyboard(yes_action: str, no_action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=f"action:{yes_action}")
    builder.button(text="⏭ Пропустить", callback_data=f"action:{no_action}")
    builder.adjust(2)
    return builder.as_markup()


def city_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора города с пагинацией.
    page — индекс страницы (0-based).
    """
    total_pages = math.ceil(len(CITIES) / CITIES_PER_PAGE)
    start = page * CITIES_PER_PAGE
    end = start + CITIES_PER_PAGE
    page_cities = CITIES[start:end]

    builder = InlineKeyboardBuilder()
    for name, slug in page_cities:
        builder.button(text=name, callback_data=f"city:{slug}")

    builder.adjust(3)

    # Навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"city_page:{page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️ Вперёд", callback_data=f"city_page:{page + 1}")
        )

    builder.row(*nav_buttons)
    return builder.as_markup()


def results_navigation_keyboard(
    current_page: int,
    total_pages: int,
    city_slug: str,
    street: str,
    building: str = "",
    show_analytics: bool = False,
) -> InlineKeyboardMarkup:
    """
    Пагинация результатов поиска.
    """
    builder = InlineKeyboardBuilder()

    nav_row = []
    if current_page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️ Пред.",
                callback_data=f"results:{current_page - 1}:{city_slug}:{street}:{building}",
            )
        )
    nav_row.append(
        InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="noop",
        )
    )
    if current_page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="▶️ След.",
                callback_data=f"results:{current_page + 1}:{city_slug}:{street}:{building}",
            )
        )

    if nav_row:
        builder.row(*nav_row)

    if show_analytics:
        builder.button(
            text="📊 Аналитика улицы",
            callback_data=f"analytics:{city_slug}:{street}:{building}",
        )
        builder.adjust(1)

    builder.button(text="🔍 Новый поиск", callback_data="action:search")
    builder.button(text="🏠 Главное меню", callback_data="action:menu")
    builder.adjust(2)

    return builder.as_markup()


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="action:menu")
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="action:menu")
    return builder.as_markup()
