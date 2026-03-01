"""
Форматирование и отправка результатов поиска.
Пагинация результатов и аналитика улицы.
"""

import logging
import math
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

from config import config
from database.db import get_user, get_cached_listings, save_listings
from keyboards.inline import (
    results_navigation_keyboard,
    back_to_menu_keyboard,
    main_menu_keyboard,
)
from parsers.cities import get_display_name
from parsers.zametr_parser import (
    fetch_all_city_offers,
    filter_by_street,
    compute_street_analytics,
    format_offer,
)

logger = logging.getLogger(__name__)
router = Router()


async def _get_offers(city_slug: str) -> list[dict]:
    """Получить объявления города: сначала из кеша, потом с сайта."""
    cached = await get_cached_listings(city_slug)
    if cached is not None:
        logger.info("Using cached data for city=%s (%d offers)", city_slug, len(cached))
        return cached

    logger.info("Fetching live data for city=%s", city_slug)
    offers = await fetch_all_city_offers(city_slug)
    if offers:
        await save_listings(city_slug, offers)
    return offers


async def show_results(
    bot: Bot,
    chat_id: int,
    user_id: int,
    city_slug: str,
    street: str,
    building: str = "",
    page: int = 0,
    status_msg_id: Optional[int] = None,
    message: Optional[Message] = None,
) -> None:
    """
    Главная функция отображения результатов.
    Либо редактирует существующее сообщение, либо отправляет новое.
    """
    user = await get_user(user_id)
    is_realtor = user and user.get("role") == "realtor"

    try:
        all_offers = await _get_offers(city_slug)
    except RuntimeError as e:
        error_text = (
            f"❌ Не удалось получить данные:\n\n{e}\n\n"
            "Попробуйте позже или выберите другой город."
        )
        if message:
            await message.edit_text(error_text, reply_markup=back_to_menu_keyboard())
        elif status_msg_id:
            await bot.edit_message_text(
                error_text,
                chat_id=chat_id,
                message_id=status_msg_id,
                reply_markup=back_to_menu_keyboard(),
            )
        return

    filtered = filter_by_street(all_offers, street, building if building else None)

    city_label = get_display_name(city_slug)
    building_label = f", д. {building}" if building else ""

    if not filtered:
        no_results_text = (
            f"🔍 <b>Результаты поиска</b>\n\n"
            f"🏙 {city_label}, ул. {street}{building_label}\n\n"
            f"😕 Объявлений не найдено.\n\n"
            f"Попробуйте:\n"
            f"• Проверить написание улицы\n"
            f"• Убрать номер дома\n"
            f"• Выбрать другой город"
        )
        kb = back_to_menu_keyboard()
        if message:
            await message.edit_text(no_results_text, reply_markup=kb, parse_mode="HTML")
        elif status_msg_id:
            await bot.edit_message_text(
                no_results_text,
                chat_id=chat_id,
                message_id=status_msg_id,
                reply_markup=kb,
                parse_mode="HTML",
            )
        return

    total = len(filtered)
    total_pages = math.ceil(total / config.PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * config.PAGE_SIZE
    end = start + config.PAGE_SIZE
    page_offers = filtered[start:end]

    header = (
        f"🔍 <b>Результаты поиска</b>\n"
        f"🏙 {city_label}, ул. {street}{building_label}\n"
        f"📊 Найдено: {total} объявлений (стр. {page + 1}/{total_pages})\n"
        f"{'─' * 30}"
    )

    parts = [header]
    for i, offer in enumerate(page_offers, start=start + 1):
        parts.append(f"\n<b>#{i}</b>")
        parts.append(format_offer(offer, is_realtor=is_realtor))

    result_text = "\n".join(parts)

    # Telegram лимит 4096 символов
    if len(result_text) > 4000:
        result_text = result_text[:3990] + "\n…"

    kb = results_navigation_keyboard(
        current_page=page,
        total_pages=total_pages,
        city_slug=city_slug,
        street=street,
        building=building,
        show_analytics=is_realtor and total > 1,
    )

    if message:
        await message.edit_text(result_text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    elif status_msg_id:
        await bot.edit_message_text(
            result_text,
            chat_id=chat_id,
            message_id=status_msg_id,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


# ─── Пагинация через callback ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("results:"))
async def cb_results_page(callback: CallbackQuery) -> None:
    """
    callback_data формат: results:{page}:{city}:{street}:{building}
    """
    parts = callback.data.split(":", 4)
    page = int(parts[1])
    city_slug = parts[2]
    street = parts[3]
    building = parts[4] if len(parts) > 4 else ""

    await callback.answer()
    await show_results(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        city_slug=city_slug,
        street=street,
        building=building,
        page=page,
        message=callback.message,
    )


# ─── Аналитика улицы ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("analytics:"))
async def cb_street_analytics(callback: CallbackQuery) -> None:
    """
    callback_data формат: analytics:{city}:{street}:{building}
    """
    parts = callback.data.split(":", 3)
    city_slug = parts[1]
    street = parts[2]
    building = parts[3] if len(parts) > 3 else ""

    await callback.answer("Загружаю аналитику…")

    try:
        all_offers = await _get_offers(city_slug)
    except RuntimeError as e:
        await callback.message.answer(f"❌ Ошибка загрузки данных: {e}")
        return

    filtered = filter_by_street(all_offers, street, building if building else None)
    analytics = compute_street_analytics(filtered)
    city_label = get_display_name(city_slug)
    building_label = f", д. {building}" if building else ""

    if not analytics:
        await callback.message.answer(
            "📊 Недостаточно данных для аналитики.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    count = analytics["count"]
    mn = analytics["min_price_per_area"]
    mx = analytics["max_price_per_area"]
    avg = analytics["avg_price_per_area"]
    median = analytics["median_price_per_area"]
    trend = analytics["trend"]
    avg_change = analytics["avg_change_pct"]

    # Мини-гистограмма
    histogram = _build_histogram(filtered)

    text = (
        f"📊 <b>Аналитика улицы</b>\n"
        f"🏙 {city_label}, ул. {street}{building_label}\n"
        f"{'─' * 30}\n\n"
        f"📋 <b>Основные показатели:</b>\n"
        f"   • Объявлений на улице: <b>{count}</b>\n"
        f"   • Диапазон цен: <b>{mn:,} – {mx:,} PLN/m²</b>\n"
        f"   • Среднее: <b>{avg:,} PLN/m²</b>\n"
        f"   • Медиана: <b>{median:,} PLN/m²</b>\n\n"
        f"📈 <b>Ценовой тренд:</b>\n"
        f"   • Тренд: {trend}\n"
        f"   • Среднее изменение с публикации: {avg_change:+.1f}%\n\n"
    )

    if histogram:
        text += f"📉 <b>Распределение цен (PLN/m²):</b>\n<pre>{histogram}</pre>\n"

    user = await get_user(callback.from_user.id)
    is_realtor = user and user.get("role") == "realtor"

    await callback.message.answer(
        text,
        reply_markup=main_menu_keyboard(is_realtor=is_realtor),
        parse_mode="HTML",
    )


def _build_histogram(offers: list[dict]) -> str:
    """Построить текстовую гистограмму распределения цен по диапазонам."""
    prices = [
        round(o["pricePerArea"])
        for o in offers
        if o.get("pricePerArea") and o["pricePerArea"] > 0
    ]
    if not prices or len(prices) < 3:
        return ""

    min_p = min(prices)
    max_p = max(prices)
    if min_p == max_p:
        return ""

    num_bins = 5
    bin_size = (max_p - min_p) / num_bins
    bins = [0] * num_bins

    for p in prices:
        idx = min(int((p - min_p) / bin_size), num_bins - 1)
        bins[idx] += 1

    max_count = max(bins)
    bar_width = 10
    lines = []
    for i, count in enumerate(bins):
        low = round(min_p + i * bin_size)
        high = round(min_p + (i + 1) * bin_size)
        bar_len = round(count / max_count * bar_width) if max_count > 0 else 0
        bar = "█" * bar_len + "░" * (bar_width - bar_len)
        lines.append(f"{low:>6}–{high:<6} {bar} {count}")

    return "\n".join(lines)
