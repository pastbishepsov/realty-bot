"""
Хендлер /start, онбординг, профиль, выбор языка.
"""

import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import upsert_user, get_user, set_user_role, set_user_agency, set_user_language
from keyboards.inline import (
    main_menu_keyboard,
    role_keyboard,
    skip_keyboard,
    back_to_menu_keyboard,
)
from locales import t

logger = logging.getLogger(__name__)
router = Router()


class OnboardingStates(StatesGroup):
    waiting_for_agency_name = State()
    waiting_for_contact = State()


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="setlang:ru")
    builder.button(text="🇬🇧 English", callback_data="setlang:en")
    builder.button(text="🇵🇱 Polski",  callback_data="setlang:pl")
    builder.adjust(1)
    return builder.as_markup()


def _lang(user: dict | None) -> str:
    return (user or {}).get("language") or "ru"


# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_tg = message.from_user
    existing = await get_user(user_tg.id)

    if not existing:
        # Новый пользователь — создать запись, показать выбор языка
        await upsert_user(
            user_id=user_tg.id,
            username=user_tg.username,
            full_name=user_tg.full_name,
        )
        await message.answer(
            t("language_select", "ru"),
            reply_markup=language_keyboard(),
        )
    elif existing.get("role"):
        # Уже зарегистрированный пользователь — сразу в главное меню
        lang = _lang(existing)
        is_realtor = existing.get("role") == "realtor"
        await message.answer(
            t("main_menu", lang),
            reply_markup=main_menu_keyboard(lang, is_realtor=is_realtor),
        )
    else:
        # Есть в БД, но роль не выбрана — главное меню (роль опциональна)
        lang = _lang(existing)
        await message.answer(
            t("main_menu", lang),
            reply_markup=main_menu_keyboard(lang, is_realtor=False),
        )


# ─── Выбор языка при онбординге ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("setlang:"))
async def cb_set_language(callback: CallbackQuery, state: FSMContext) -> None:
    lang = callback.data.split(":")[1]
    user_id = callback.from_user.id

    await set_user_language(user_id, lang)
    await callback.answer(t("language_set", lang))

    user = await get_user(user_id)
    is_realtor = user and user.get("role") == "realtor"

    # После выбора языка всегда показываем главное меню (роль опциональна)
    await callback.message.edit_text(
        t("main_menu", lang),
        reply_markup=main_menu_keyboard(lang, is_realtor=bool(is_realtor)),
    )


# ─── /cancel — выход из любого FSM-состояния ─────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    await state.clear()
    user = await get_user(message.from_user.id)
    lang = _lang(user)
    is_realtor = user and user.get("role") == "realtor"
    if current_state is None:
        await message.answer(t("cancel_nothing", lang), reply_markup=main_menu_keyboard(lang, is_realtor=is_realtor))
    else:
        await message.answer(t("cancel_done", lang), reply_markup=main_menu_keyboard(lang, is_realtor=is_realtor))


# ─── /language — смена языка ──────────────────────────────────────────────────

@router.message(Command("language"))
async def cmd_language(message: Message) -> None:
    user = await get_user(message.from_user.id)
    lang = _lang(user)
    await message.answer(
        t("lang_current", lang),
        reply_markup=language_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "action:language")
async def cb_language_menu(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await callback.message.edit_text(
        t("lang_current", lang),
        reply_markup=language_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ─── Выбор роли ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "role:realtor")
async def cb_role_realtor(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await set_user_role(callback.from_user.id, "realtor")
    await state.set_state(OnboardingStates.waiting_for_agency_name)
    await callback.message.edit_text(
        t("role_chosen_realtor", lang),
        reply_markup=skip_keyboard("skip_agency", lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "role:user")
async def cb_role_user(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await set_user_role(callback.from_user.id, "user")
    await state.clear()
    await callback.message.edit_text(
        t("profile_created_simple", lang),
        reply_markup=main_menu_keyboard(lang, is_realtor=False),
    )
    await callback.answer()


# ─── Агентство и контакт ──────────────────────────────────────────────────────

@router.message(OnboardingStates.waiting_for_agency_name)
async def process_agency_name(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    lang = _lang(user)
    await state.update_data(agency_name=message.text.strip())
    await state.set_state(OnboardingStates.waiting_for_contact)
    await message.answer(
        t("enter_contact", lang),
        reply_markup=skip_keyboard("skip_contact", lang),
    )


@router.callback_query(F.data == "action:skip_agency")
async def cb_skip_agency(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await state.set_state(OnboardingStates.waiting_for_contact)
    await callback.message.edit_text(
        t("enter_contact", lang),
        reply_markup=skip_keyboard("skip_contact", lang),
    )
    await callback.answer()


@router.message(OnboardingStates.waiting_for_contact)
async def process_contact(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    agency_name = data.get("agency_name")
    contact = message.text.strip()
    await set_user_agency(message.from_user.id, agency_name or "", contact)
    await state.clear()
    user = await get_user(message.from_user.id)
    lang = _lang(user)
    await message.answer(
        t("profile_created", lang),
        reply_markup=main_menu_keyboard(lang, is_realtor=True),
    )


@router.callback_query(F.data == "action:skip_contact")
async def cb_skip_contact(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    agency_name = data.get("agency_name")
    await set_user_agency(callback.from_user.id, agency_name or "", None)
    await state.clear()
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await callback.message.edit_text(
        t("profile_created", lang),
        reply_markup=main_menu_keyboard(lang, is_realtor=True),
    )
    await callback.answer()


# ─── Главное меню ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "action:menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    is_realtor = user and user.get("role") == "realtor"
    await callback.message.edit_text(
        t("main_menu", lang),
        reply_markup=main_menu_keyboard(lang, is_realtor=is_realtor),
    )
    await callback.answer()


# ─── Профиль ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "action:profile")
async def cb_profile(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer(t("profile_not_found", "ru"), show_alert=True)
        return

    lang = _lang(user)
    role_label = t("role_label_realtor", lang) if user.get("role") == "realtor" else t("role_label_user", lang)
    city = user.get("default_city") or t("not_set", lang)
    agency = user.get("agency_name") or t("empty", lang)
    contact = user.get("contact") or t("empty", lang)
    lang_label = {"ru": "🇷🇺 Русский", "en": "🇬🇧 English", "pl": "🇵🇱 Polski"}.get(lang, lang)

    text = (
        f"{t('profile_title', lang)}\n\n"
        f"{t('profile_role', lang)}: {role_label}\n"
        f"{t('profile_agency', lang)}: {agency}\n"
        f"{t('profile_contact', lang)}: {contact}\n"
        f"{t('profile_city', lang)}: {city}\n"
        f"{t('profile_language', lang)}: {lang_label}\n"
    )

    from keyboards.inline import profile_keyboard
    await callback.message.edit_text(
        text,
        reply_markup=profile_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "action:change_role")
async def cb_change_role(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
    await callback.message.edit_text(
        t("welcome", lang),
        reply_markup=role_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
