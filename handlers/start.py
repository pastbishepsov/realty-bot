"""
Хендлер /start и онбординг.
"""

import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from database.db import upsert_user, get_user, set_user_role, set_user_agency
from keyboards.inline import (
    main_menu_keyboard,
    role_keyboard,
    skip_keyboard,
    back_to_menu_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()


class OnboardingStates(StatesGroup):
    waiting_for_agency_name = State()
    waiting_for_contact = State()


WELCOME_TEXT = (
    "👋 Добро пожаловать в <b>Realt Help</b>!\n\n"
    "Я помогаю искать и анализировать недвижимость в Польше "
    "по данным с <a href='https://zametr.pl'>zametr.pl</a>.\n\n"
    "Кто вы?"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user

    # Создаём пользователя если нет
    existing = await get_user(user.id)
    if not existing:
        await upsert_user(
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
        )

    await message.answer(
        WELCOME_TEXT,
        reply_markup=role_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "role:realtor")
async def cb_role_realtor(callback: CallbackQuery, state: FSMContext) -> None:
    await set_user_role(callback.from_user.id, "realtor")
    await state.set_state(OnboardingStates.waiting_for_agency_name)
    await callback.message.edit_text(
        "🏢 Отлично! Вы выбрали режим <b>Риэлтор/Агент</b>.\n\n"
        "Введите название вашего агентства (или нажмите «Пропустить»):",
        reply_markup=skip_keyboard("skip_agency"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "role:user")
async def cb_role_user(callback: CallbackQuery, state: FSMContext) -> None:
    await set_user_role(callback.from_user.id, "user")
    await state.clear()
    await callback.message.edit_text(
        "✅ Профиль создан!\n\nЧем займёмся?",
        reply_markup=main_menu_keyboard(is_realtor=False),
    )
    await callback.answer()


@router.message(OnboardingStates.waiting_for_agency_name)
async def process_agency_name(message: Message, state: FSMContext) -> None:
    await state.update_data(agency_name=message.text.strip())
    await state.set_state(OnboardingStates.waiting_for_contact)
    await message.answer(
        "📞 Введите контактный номер телефона или e-mail (или нажмите «Пропустить»):",
        reply_markup=skip_keyboard("skip_contact"),
    )


@router.callback_query(F.data == "action:skip_agency")
async def cb_skip_agency(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OnboardingStates.waiting_for_contact)
    await callback.message.edit_text(
        "📞 Введите контактный номер телефона или e-mail (или нажмите «Пропустить»):",
        reply_markup=skip_keyboard("skip_contact"),
    )
    await callback.answer()


@router.message(OnboardingStates.waiting_for_contact)
async def process_contact(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    agency_name = data.get("agency_name")
    contact = message.text.strip()

    await set_user_agency(message.from_user.id, agency_name or "", contact)
    await state.clear()

    await message.answer(
        "✅ Профиль создан! Готов к работе.\n\nЧем займёмся?",
        reply_markup=main_menu_keyboard(is_realtor=True),
    )


@router.callback_query(F.data == "action:skip_contact")
async def cb_skip_contact(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    agency_name = data.get("agency_name")
    await set_user_agency(callback.from_user.id, agency_name or "", None)
    await state.clear()

    await callback.message.edit_text(
        "✅ Профиль создан! Готов к работе.\n\nЧем займёмся?",
        reply_markup=main_menu_keyboard(is_realtor=True),
    )
    await callback.answer()


@router.callback_query(F.data == "action:menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(callback.from_user.id)
    is_realtor = user and user.get("role") == "realtor"

    await callback.message.edit_text(
        "🏠 Главное меню\n\nЧем займёмся?",
        reply_markup=main_menu_keyboard(is_realtor=is_realtor),
    )
    await callback.answer()


@router.callback_query(F.data == "action:profile")
async def cb_profile(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден", show_alert=True)
        return

    role_label = "Риэлтор/Агент" if user.get("role") == "realtor" else "Частное лицо"
    city = user.get("default_city") or "не выбран"
    agency = user.get("agency_name") or "—"
    contact = user.get("contact") or "—"

    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"Роль: {role_label}\n"
        f"Агентство: {agency}\n"
        f"Контакт: {contact}\n"
        f"Город по умолчанию: {city}\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
