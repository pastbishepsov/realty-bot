"""
Форматирование и отправка результатов поиска.
"""

import logging
import math
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

from config import config
from database.db import get_user, get_cached_listings, save_listings
from keyboards.inline import results_navigation_keyboard, back_to_menu_keyboard, main_menu_keyboard
from locales import t
from parsers.cities import get_display_name
from parsers.zametr_parser import (
    fetch_all_city_offers,
    filter_by_street,
    compute_street_analytics,
    format_offer,
)

logger = logging.getLogger(__name__)
router = Router()


def _lang(user: dict | None) -> str:
    return (user or {}).get("language") or "ru"


async def _get_offers(city_slug: str) -> list[dict]:
    cached = await get_cached_listings(city_slug)
    if cached is not None:
        return cached
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
    lang: str = "ru",
) -> None:
    user = await get_user(user_id)
    is_realtor = user and user.get("role") == "realtor"

    try:
        all_offers = await _get_offers(city_slug)
    except RuntimeError as e:
        error_text = t("results_error", lang, error=str(e))
        kb = back_to_menu_keyboard(lang)
        if message:
            await message.edit_text(error_text, reply_markup=kb)
        elif status_msg_id:
            await bot.edit_message_text(error_text, chat_id=chat_id, message_id=status_msg_id, reply_markup=kb)
        return

    filtered = filter_by_street(all_offers, street, building if building else None)
    city_label = get_display_name(city_slug)
    building_label = t("building_label", lang, building=building) if building else ""
    street_label = t("street_label", lang)

    if not filtered:
        no_results_text = t(
            "results_not_found", lang,
            city=city_label, street=f"{street_label} {street}", building=building_label,
        )
        kb = back_to_menu_keyboard(lang)
        if message:
            await message.edit_text(no_results_text, reply_markup=kb, parse_mode="HTML")
        elif status_msg_id:
            await bot.edit_message_text(
                no_results_text, chat_id=chat_id, message_id=status_msg_id,
                reply_markup=kb, parse_mode="HTML",
            )
        return

    total = len(filtered)
    total_pages = math.ceil(total / config.PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * config.PAGE_SIZE
    page_offers = filtered[start:start + config.PAGE_SIZE]

    header = t(
        "results_header", lang,
        city=city_label, street=f"{street_label} {street}", building=building_label,
        total=total, page=page + 1, total_pages=total_pages,
    ) + f"\n{'─' * 30}"

    parts = [header]
    for i, offer in enumerate(page_offers, start=start + 1):
        parts.append(f"\n<b>#{i}</b>")
        parts.append(format_offer(offer, lang=lang, is_realtor=is_realtor))

    result_text = "\n".join(parts)
    if len(result_text) > 4000:
        result_text = result_text[:3990] + "\n…"

    kb = results_navigation_keyboard(
        current_page=page,
        total_pages=total_pages,
        city_slug=city_slug,
        street=street,
        building=building,
        show_analytics=is_realtor and total > 1,
        lang=lang,
    )

    if message:
        await message.edit_text(result_text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    elif status_msg_id:
        await bot.edit_message_text(
            result_text, chat_id=chat_id, message_id=status_msg_id,
            reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True,
        )


@router.callback_query(F.data.startswith("results:"))
async def cb_results_page(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 4)
    page = int(parts[1])
    city_slug = parts[2]
    street = parts[3]
    building = parts[4] if len(parts) > 4 else ""
    user = await get_user(callback.from_user.id)
    lang = _lang(user)
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
        lang=lang,
    )


@router.callback_query(F.data.startswith("analytics:"))
async def cb_street_analytics(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 3)
    city_slug = parts[1]
    street = parts[2]
    building = parts[3] if len(parts) > 3 else ""
    user = await get_user(callback.from_user.id)
    lang = _lang(user)

    await callback.answer(t("results_loading_analytics", lang))

    try:
        all_offers = await _get_offers(city_slug)
    except RuntimeError as e:
        await callback.message.answer(t("results_analytics_error", lang, error=str(e)))
        return

    filtered = filter_by_street(all_offers, street, building if building else None)
    analytics = compute_street_analytics(filtered)
    city_label = get_display_name(city_slug)
    building_label = t("building_label", lang, building=building) if building else ""
    street_label = t("street_label", lang)

    if not analytics:
        await callback.message.answer(
            t("results_analytics_no_data", lang),
            reply_markup=back_to_menu_keyboard(lang),
        )
        return

    count = analytics["count"]
    mn = analytics["min_price_per_area"]
    mx = analytics["max_price_per_area"]
    avg = analytics["avg_price_per_area"]
    median = analytics["median_price_per_area"]
    trend = t("trend_" + analytics["trend"], lang)
    avg_change = analytics["avg_change_pct"]
    histogram = _build_histogram(filtered)

    text = (
        f"{t('analytics_title', lang)}\n"
        f"🏙 {city_label}, {street_label} {street}{building_label}\n"
        f"{'─' * 30}\n\n"
        f"{t('analytics_key_metrics', lang)}\n"
        f"   • {t('analytics_count', lang)}: <b>{count}</b>\n"
        f"   • {t('analytics_range', lang)}: <b>{mn:,} – {mx:,} PLN/m²</b>\n"
        f"   • {t('analytics_avg', lang)}: <b>{avg:,} PLN/m²</b>\n"
        f"   • {t('analytics_median', lang)}: <b>{median:,} PLN/m²</b>\n\n"
        f"{t('analytics_trend_title', lang)}\n"
        f"   • {t('analytics_trend', lang)}: {trend}\n"
        f"   • {t('analytics_avg_change', lang)}: {avg_change:+.1f}%\n\n"
    )
    if histogram:
        text += f"{t('analytics_histogram', lang)}\n<pre>{histogram}</pre>\n"

    is_realtor = user and user.get("role") == "realtor"
    await callback.message.answer(
        text,
        reply_markup=main_menu_keyboard(lang, is_realtor=is_realtor),
        parse_mode="HTML",
    )


def _build_histogram(offers: list[dict]) -> str:
    prices = [
        round(o["pricePerArea"])
        for o in offers
        if o.get("pricePerArea") and o["pricePerArea"] > 0
    ]
    if not prices or len(prices) < 3:
        return ""
    min_p, max_p = min(prices), max(prices)
    if min_p == max_p:
        return ""
    num_bins = 5
    bin_size = (max_p - min_p) / num_bins
    bins = [0] * num_bins
    for p in prices:
        bins[min(int((p - min_p) / bin_size), num_bins - 1)] += 1
    max_count = max(bins)
    lines = []
    for i, count in enumerate(bins):
        low = round(min_p + i * bin_size)
        high = round(min_p + (i + 1) * bin_size)
        bar_len = round(count / max_count * 10) if max_count else 0
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f"{low:>6}–{high:<6} {bar} {count}")
    return "\n".join(lines)
