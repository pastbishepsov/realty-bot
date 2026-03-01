"""
Все inline-клавиатуры бота. Все кнопки принимают lang для локализации.
"""

import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from parsers.cities import CITIES
from locales import t

CITIES_PER_PAGE = 12


def main_menu_keyboard(lang: str = "ru", is_realtor: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_search", lang),  callback_data="action:search")
    builder.button(text=t("btn_my_city", lang), callback_data="action:filters")
    if is_realtor:
        builder.button(text=t("btn_analytics", lang), callback_data="action:analytics")
    builder.button(text=t("btn_profile", lang),  callback_data="action:profile")
    builder.button(text=t("btn_language", lang), callback_data="action:language")
    builder.adjust(2)
    return builder.as_markup()


def role_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("role_realtor", lang), callback_data="role:realtor")
    builder.button(text=t("role_user", lang),    callback_data="role:user")
    builder.adjust(1)
    return builder.as_markup()


def skip_keyboard(action: str = "skip", lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_skip", lang), callback_data=f"action:{action}")
    return builder.as_markup()


def yes_no_keyboard(yes_action: str, no_action: str, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_yes", lang),  callback_data=f"action:{yes_action}")
    builder.button(text=t("btn_skip", lang), callback_data=f"action:{no_action}")
    builder.adjust(2)
    return builder.as_markup()


def city_keyboard(page: int = 0, lang: str = "ru") -> InlineKeyboardMarkup:
    total_pages = math.ceil(len(CITIES) / CITIES_PER_PAGE)
    start = page * CITIES_PER_PAGE
    end = start + CITIES_PER_PAGE
    page_cities = CITIES[start:end]

    builder = InlineKeyboardBuilder()
    for name, slug in page_cities:
        builder.button(text=name, callback_data=f"city:{slug}")
    builder.adjust(3)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text=t("btn_back", lang), callback_data=f"city_page:{page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text=t("btn_forward", lang), callback_data=f"city_page:{page + 1}")
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
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton(
            text=t("btn_prev", lang),
            callback_data=f"results:{current_page - 1}:{city_slug}:{street}:{building}",
        ))
    nav_row.append(InlineKeyboardButton(
        text=f"{current_page + 1}/{total_pages}", callback_data="noop",
    ))
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text=t("btn_next", lang),
            callback_data=f"results:{current_page + 1}:{city_slug}:{street}:{building}",
        ))
    if nav_row:
        builder.row(*nav_row)

    if show_analytics:
        builder.button(
            text=t("btn_street_analytics", lang),
            callback_data=f"analytics:{city_slug}:{street}:{building}",
        )
        builder.adjust(1)

    builder.button(text=t("btn_new_search", lang), callback_data="action:search")
    builder.button(text=t("btn_main_menu", lang),  callback_data="action:menu")
    builder.adjust(2)
    return builder.as_markup()


def back_to_menu_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_main_menu", lang), callback_data="action:menu")
    return builder.as_markup()


def cancel_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_cancel", lang), callback_data="action:menu")
    return builder.as_markup()
