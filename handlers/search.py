"""
Хендлер поиска: FSM-флоу выбора города → улицы → дома.
"""

import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from database.db import get_user
from keyboards.inline import (
    city_keyboard,
    yes_no_keyboard,
    cancel_keyboard,
    back_to_menu_keyboard,
)
from parsers.cities import get_display_name

logger = logging.getLogger(__name__)
router = Router()


class SearchStates(StatesGroup):
    waiting_for_city = State()
    waiting_for_street = State()
    waiting_for_building = State()


@router.callback_query(F.data == "action:search")
async def cb_start_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(callback.from_user.id)
    default_city = user.get("default_city") if user else None

    if default_city:
        city_label = get_display_name(default_city)
        await state.update_data(city=default_city)
        await state.set_state(SearchStates.waiting_for_street)

        await callback.message.edit_text(
            f"🔍 <b>Поиск недвижимости</b>\n\n"
            f"🏙 Город: <b>{city_label}</b>\n\n"
            f"Введите название улицы:",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML",
        )
    else:
        await state.set_state(SearchStates.waiting_for_city)
        await callback.message.edit_text(
            "🔍 <b>Поиск недвижимости</b>\n\n"
            "Город по умолчанию не задан. Выберите город:",
            reply_markup=city_keyboard(page=0),
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
    """Общая функция обработки выбранного города в рамках поиска."""
    await state.update_data(city=slug)
    await state.set_state(SearchStates.waiting_for_street)
    city_label = get_display_name(slug)

    await callback.message.edit_text(
        f"🔍 <b>Поиск недвижимости</b>\n\n"
        f"🏙 Город: <b>{city_label}</b>\n\n"
        f"Введите название улицы (например: <i>Marszałkowska</i>):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("city_page:"), SearchStates.waiting_for_city)
async def cb_city_page_in_search(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=city_keyboard(page=page))
    await callback.answer()


@router.message(SearchStates.waiting_for_street)
async def process_street(message: Message, state: FSMContext) -> None:
    street = message.text.strip()
    if not street:
        await message.answer("Пожалуйста, введите название улицы.")
        return

    await state.update_data(street=street)
    await state.set_state(SearchStates.waiting_for_building)

    await message.answer(
        f"🏠 Улица: <b>{street}</b>\n\n"
        f"Добавить номер дома?",
        reply_markup=yes_no_keyboard("enter_building", "skip_building"),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "action:enter_building", SearchStates.waiting_for_building)
async def cb_enter_building(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "Введите номер дома (например: <i>15</i> или <i>15A</i>):",
        reply_markup=cancel_keyboard(),
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
    """Запустить поиск из текстового сообщения."""
    from handlers.results import show_results

    data = await state.get_data()
    await state.clear()

    status_msg = await message.answer(
        "⏳ Ищу объявления, это может занять несколько секунд..."
    )
    await show_results(
        bot=message.bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        city_slug=data["city"],
        street=data["street"],
        building=data.get("building", ""),
        page=0,
        status_msg_id=status_msg.message_id,
    )


async def _trigger_search_from_callback(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Запустить поиск из callback."""
    from handlers.results import show_results

    data = await state.get_data()
    await state.clear()

    await callback.message.edit_text(
        "⏳ Ищу объявления, это может занять несколько секунд..."
    )
    await show_results(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        city_slug=data["city"],
        street=data["street"],
        building=data.get("building", ""),
        page=0,
        message=callback.message,
    )
