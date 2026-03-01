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
from parsers.cities import get_display_name

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("filters"))
async def cmd_filters(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(message.from_user.id)
    current = user.get("default_city") if user else None
    city_label = get_display_name(current) if current else "не выбран"

    await message.answer(
        f"🏙 <b>Настройка фильтров</b>\n\n"
        f"Текущий город по умолчанию: <b>{city_label}</b>\n\n"
        f"Выберите город из списка:",
        reply_markup=city_keyboard(page=0),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "action:filters")
async def cb_filters(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(callback.from_user.id)
    current = user.get("default_city") if user else None
    city_label = get_display_name(current) if current else "не выбран"

    await callback.message.edit_text(
        f"🏙 <b>Настройка фильтров</b>\n\n"
        f"Текущий город по умолчанию: <b>{city_label}</b>\n\n"
        f"Выберите город из списка:",
        reply_markup=city_keyboard(page=0),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("city_page:"))
async def cb_city_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=city_keyboard(page=page))
    await callback.answer()


@router.callback_query(F.data.startswith("city:"))
async def cb_city_selected_filter(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработка выбора города в режиме /filters.
    Если мы в режиме поиска — передаём управление в search.py через FSM.
    """
    slug = callback.data.split(":", 1)[1]
    fsm_state = await state.get_state()

    # Если FSM активна — это поиск, не фильтр
    if fsm_state and "SearchStates" in (fsm_state or ""):
        # Передаём управление search-хендлеру через обновление данных
        from handlers.search import handle_city_chosen
        await handle_city_chosen(callback, state, slug)
        return

    # Иначе — просто сохраняем город
    await set_user_city(callback.from_user.id, slug)
    city_label = get_display_name(slug)

    user = await get_user(callback.from_user.id)
    is_realtor = user and user.get("role") == "realtor"

    await callback.message.edit_text(
        f"✅ Город <b>{city_label}</b> сохранён как город по умолчанию!\n\n"
        f"Теперь при поиске я буду искать именно там.",
        reply_markup=main_menu_keyboard(is_realtor=is_realtor),
        parse_mode="HTML",
    )
    await callback.answer(f"Город сохранён: {city_label}")
