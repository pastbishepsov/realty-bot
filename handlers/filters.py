"""
Хендлер /filters — управление постоянными фильтрами (дефолтный город).
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from database.db import get_user, set_user_city
from keyboards.inline import city_keyboard, back_to_menu_keyboard, main_menu_keyboard
from locales import t
from parsers.cities import get_display_name

logger = logging.getLogger(__name__)
router = Router()


def _lang(user: dict | None) -> str:
    return (user or {}).get("language") or "ru"


@router.message(Command("filters"))
async def cmd_filters(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(message.from_user.id)
    lang = _lang(user)
    current = user.get("default_city") if user else None
    city_label = get_display_name(current) if current else t("not_set", lang)

    await message.answer(
        f"{t('filters_title', lang)}\n\n"
        f"{t('filters_current_city', lang, city=city_label)}\n\n"
        f"{t('filters_choose_city', lang)}",
        reply_markup=city_keyboard(page=0, lang=lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "action:filters")
async def cb_filters(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    current = user.get("default_city") if user else None
    city_label = get_display_name(current) if current else t("not_set", lang)

    await callback.message.edit_text(
        f"{t('filters_title', lang)}\n\n"
        f"{t('filters_current_city', lang, city=city_label)}\n\n"
        f"{t('filters_choose_city', lang)}",
        reply_markup=city_keyboard(page=0, lang=lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("city_page:"))
async def cb_city_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await callback.message.edit_reply_markup(reply_markup=city_keyboard(page=page, lang=lang))
    await callback.answer()


@router.callback_query(F.data.startswith("city:"))
async def cb_city_selected_filter(callback: CallbackQuery, state: FSMContext) -> None:
    slug = callback.data.split(":", 1)[1]
    fsm_state = await state.get_state()

    if fsm_state and "SearchStates" in (fsm_state or ""):
        from handlers.search import handle_city_chosen
        await handle_city_chosen(callback, state, slug)
        return

    await set_user_city(callback.from_user.id, slug)
    city_label = get_display_name(slug)

    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    is_realtor = user and user.get("role") == "realtor"

    await callback.message.edit_text(
        t("filters_city_saved", lang, city=city_label),
        reply_markup=main_menu_keyboard(lang, is_realtor=is_realtor),
        parse_mode="HTML",
    )
    await callback.answer(t("filters_city_saved_alert", lang, city=city_label))
