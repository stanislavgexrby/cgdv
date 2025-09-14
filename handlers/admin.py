from aiogram import Router, F
from aiogram.types import CallbackQuery
from datetime import datetime, timedelta
import logging

import keyboards.keyboards as kb
import config.settings as settings
import utils.texts as texts
from handlers.basic import admin_only, safe_edit_message

router = Router()
logger = logging.getLogger(__name__)

def _parse(data: str):
    # rep:<action>:<report_id>[:<user_id>[:<days>]]
    parts = data.split(":")
    action = parts[1]
    rep_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    uid = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
    days = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
    return action, rep_id, uid, days

@router.callback_query(F.data.startswith("rep:"))
@admin_only
async def admin_report_router(callback: CallbackQuery, db):
    action, report_id, user_id, days = _parse(callback.data)

    if action not in {"del", "ban", "ok", "ignore", "next"}:
        await callback.answer("❌ Неизвестное действие", show_alert=True)
        return
    if action in {"del", "ban", "ok"} and (not report_id or not user_id):
        await callback.answer("❌ Нет данных жалобы (report_id/user_id)", show_alert=True)
        return
    if action == "ban" and not days:
        days = 7

    if action == "del":
        user = await db.get_user(user_id)
        game = (user.get("current_game") if user else "dota") or "dota"
        ok1 = await db.delete_profile(user_id, game)
        ok2 = await db.update_report_status(report_id, status="resolved", admin_id=callback.from_user.id)
        await callback.answer("🗑️ Анкета удалена, жалоба закрыта" if (ok1 and ok2) else "❌ Ошибка удаления/обновления", show_alert=not (ok1 and ok2))

    elif action == "ban":
        until = datetime.utcnow() + timedelta(days=days)
        ok1 = await db.ban_user(user_id, f"нарушение правил (жалоба), {days}d", until)
        ok2 = await db.update_report_status(report_id, status="resolved", admin_id=callback.from_user.id)
        await callback.answer(f"🚫 Бан {days}д, жалоба закрыта" if (ok1 and ok2) else "❌ Ошибка при бане/закрытии", show_alert=not (ok1 and ok2))

    elif action == "ok":
        ok = await db.update_report_status(report_id, status="resolved", admin_id=callback.from_user.id)
        await callback.answer("✅ Жалоба одобрена" if ok else "❌ Не удалось обновить", show_alert=not ok)

    elif action == "ignore":
        if not report_id:
            await callback.answer("❌ Нет report_id", show_alert=True)
            return
        ok = await db.update_report_status(report_id, status="ignored", admin_id=callback.from_user.id)
        await callback.answer("🙈 Жалоба проигнорирована" if ok else "❌ Не удалось обновить", show_alert=not ok)

    elif action == "next":
        reports = await db.get_pending_reports()
        if not reports:
            await safe_edit_message(callback, "✅ Больше жалоб нет", kb.admin_back_menu())
            return
        rep = reports[0]
        game = rep.get("game", "dota")
        prof = await db.get_user_profile(rep["reported_user_id"], game)
        game_name = settings.GAMES.get(game, game)

        header = f"🚩 Жалоба #{rep['id']} | {game_name}\nСтатус: {rep.get('status','pending')}\nПричина: {rep.get('report_reason','inappropriate_content')}\n"
        if prof:
            body = "👤 Объект жалобы:\n\n" + texts.format_profile(prof, show_contact=True)
        else:
            body = f"❌ Анкета {rep['reported_user_id']} не найдена"
        text = header + "\n\n" + body

        await safe_edit_message(
            callback,
            text,
            kb.admin_report_actions(rep["reported_user_id"], rep["id"])
        )
        await callback.answer()
