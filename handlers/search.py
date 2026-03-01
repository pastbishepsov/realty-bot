"""
Хендлер поиска: FSM-флоу выбора города → улицы → дома.
"""

import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from database.db import get_user
from keyboards.inline import city_keyboard, yes_no_keyboard, cancel_keyboard
from locales import t
from parsers.cities import get_display_name

logger = logging.getLogger(__name__)
router = Router()


class SearchStates(StatesGroup):
    waiting_for_city = State()
    waiting_for_street = State()
    waiting_for_building = State()


def _lang(user: dict | None) -> str:
    return (user or {}).get("language") or "ru"


@router.callback_query(F.data == "action:search")
async def cb_start_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    default_city = user.get("default_city") if user else None

    if default_city:
        city_label = get_display_name(default_city)
        await state.update_data(city=default_city)
        await state.set_state(SearchStates.waiting_for_street)
        await callback.message.edit_text(
            f"{t('search_title', lang)}\n\n"
            f"{t('search_city_chosen', lang, city=city_label)}",
            reply_markup=cancel_keyboard(lang),
            parse_mode="HTML",
        )
    else:
        await state.set_state(SearchStates.waiting_for_city)
        await callback.message.edit_text(
            f"{t('search_title', lang)}\n\n"
            f"{t('search_no_city', lang)}",
            reply_markup=city_keyboard(page=0, lang=lang),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("city:"), SearchStates.waiting_for_city)
async def cb_city_in_search(callback: CallbackQuery, state: FSMContext) -> None:
    slug = callback.data.split(":", 1)[1]
    await handle_city_chosen(callback, state, slug)


async def handle_city_chosen(
    callback: CallbackQuery, state: FSMContext, slug: str
) -> None:
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await state.update_data(city=slug)
    await state.set_state(SearchStates.waiting_for_street)
    city_label = get_display_name(slug)
    await callback.message.edit_text(
        f"{t('search_title', lang)}\n\n"
        f"{t('search_city_chosen', lang, city=city_label)}",
        reply_markup=cancel_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("city_page:"), SearchStates.waiting_for_city)
async def cb_city_page_in_search(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await callback.message.edit_reply_markup(reply_markup=city_keyboard(page=page, lang=lang))
    await callback.answer()


@router.message(SearchStates.waiting_for_street)
async def process_street(message: Message, state: FSMContext) -> None:
    street = message.text.strip()
    user = await get_user(message.from_user.id)
    lang = _lang(user)
    if not street:
        await message.answer(t("search_enter_street", lang))
        return
    await state.update_data(street=street)
    await state.set_state(SearchStates.waiting_for_building)
    await message.answer(
        t("search_street_chosen", lang, street=street),
        reply_markup=yes_no_keyboard("enter_building", "skip_building", lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "action:enter_building", SearchStates.waiting_for_building)
async def cb_enter_building(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await callback.message.edit_text(
        t("search_enter_building", lang),
        reply_markup=cancel_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SearchStates.waiting_for_building)
async def process_building(message: Message, state: FSMContext) -> None:
    building = message.text.strip()
    await state.update_data(building=building)
    await _trigger_search(message, state)


@router.callback_query(F.data == "action:skip_building", SearchStates.waiting_for_building)
async def cb_skip_building(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(building="")
    await callback.answer()
    await _trigger_search_from_callback(callback, state)


async def _trigger_search(message: Message, state: FSMContext) -> None:
    from handlers.results import show_results
    data = await state.get_data()
    await state.clear()
    user = await get_user(message.from_user.id)
    lang = _lang(user)
    status_msg = await message.answer(t("search_loading", lang))
    await show_results(
        bot=message.bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        city_slug=data["city"],
        street=data["street"],
        building=data.get("building", ""),
        page=0,
        status_msg_id=status_msg.message_id,
        lang=lang,
    )


async def _trigger_search_from_callback(callback: CallbackQuery, state: FSMContext) -> None:
    from handlers.results import show_results
    data = await state.get_data()
    await state.clear()
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await callback.message.edit_text(t("search_loading", lang))
    await show_results(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        city_slug=data["city"],
        street=data["street"],
        building=data.get("building", ""),
        page=0,
        message=callback.message,
        lang=lang,
    )
