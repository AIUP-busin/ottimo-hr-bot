import logging
import math
import os
from datetime import datetime, date

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes,
)

import database as db

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "8473101745:AAEfYwUFy4WXoeMmuzpWJ3PCtLfisgeO6n0")
COMPANY        = "Ottimo"
OFFICE_LAT     = 41.308143
OFFICE_LON     = 69.210944
OFFICE_RADIUS  = 30          # metr
WORK_START     = int(os.getenv("WORK_START", "9"))   # 09:00
WORK_END       = int(os.getenv("WORK_END",   "18"))  # 18:00

# ── States ────────────────────────────────────────────────────────────────────
(LANG, REG_NAME, REG_BRANCH, REG_POSITION,
 MAIN_MENU,
 VAC_START, VAC_END, VAC_REASON,
 ADMIN_SET_RATE) = range(9)

# ── GPS ───────────────────────────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ── Day / Night (invisible mode) ──────────────────────────────────────────────
def is_day() -> bool:
    h = datetime.now().hour
    return WORK_START <= h < WORK_END

def time_greeting(lang: str) -> str:
    h = datetime.now().hour
    if 5 <= h < 12:
        return {"uz": "Xayrli tong", "ru": "Доброе утро"}[lang]
    if 12 <= h < 18:
        return {"uz": "Xayrli kun",  "ru": "Добрый день"}[lang]
    return {"uz": "Xayrli kech",    "ru": "Добрый вечер"}[lang]

# ── Translations ──────────────────────────────────────────────────────────────
T = {
"uz": {
"welcome":       "◈ {company}\n\n{greeting}! HR tizimiga xush kelibsiz.\n\nTilni tanlang:",
"enter_name":    "Ismingizni kiriting:",
"enter_branch":  "Filial nomini kiriting:",
"enter_position":"Lavozimingizni kiriting:",
"registered":    "◈ Ro'yxatdan o'tdingiz\n\n  Ism       {name}\n  Filial    {branch}\n  Lavozim   {position}",
"first_admin":   "Siz birinchi foydalanuvchi — Admin sifatida belgilandingiz.",
"main_menu":     "◈ {company}  ·  {greeting}",
"btn_today":     "Bugun",
"btn_history":   "Tarix",
"btn_vacation":  "Ta'til",
"btn_profile":   "Profil",
"btn_admin":     "⚙ Admin",
"btn_back":      "← Orqaga",
"btn_skip":      "O'tkazib yuborish",
# today
"today_hdr":     "◈ Bugun  ·  {date}",
"step_came":     "Keldim",
"step_lunch_out":"Tushlikka chiqdim",
"step_lunch_in": "Tushlikdan keldim",
"step_left":     "Ketdim",
"day_done":      "Ish kuni yakunlandi.",
"ask_location":  "📍 Joylashuvingizni yuboring\n(tugmani bosing yoki xaritadan tanlang):",
"loc_too_far":   "Siz ofisdan {dist:.0f}m uzoqdasiz.\nCheck‑in faqat {radius}m ichida ishlaydi.",
"loc_ok":        "✓ Joylashuv tasdiqlandi  ·  {dist:.0f}m",
"checked_in":    "✓ Keldingiz  ·  {time}",
"lunch_out_ok":  "✓ Tushlikka chiqdingiz  ·  {time}",
"lunch_in_ok":   "✓ Tushlikdan qaytdingiz  ·  {time}",
"checked_out":   "✓ Ketdingiz  ·  {time}\n\n  Ish vaqti    {hours:.1f} soat\n  Hisoblangan  {earned:,} so'm",
"late_note":     "  Kechikib keldingiz",
"no_checkin":    "Avval 'Keldim' ni qayd qiling.",
"already_done":  "Bu qadam allaqachon bajarilgan.",
"after_hours":   "Ish vaqtidan tashqari ({start}:00 – {end}:00).",
# history
"hist_hdr":      "◈ Tarix  ·  {month}\n\n  Jami       {hours:.1f} soat\n  Keldi      {came} kun\n  Kechikdi   {late} kun\n",
"hist_row":      "  {date}   {ci} → {co}   {h:.1f}h\n",
"no_records":    "  Yozuvlar yo'q.",
# vacation
"vac_hdr":       "◈ Ta'til\n\n  Jami so'rovlar: {n}",
"btn_new_vac":   "+ Yangi so'rov",
"btn_my_vacs":   "Mening so'rovlarim",
"vac_start":     "Ta'til boshlanish sanasi (KK.OO.YYYY):",
"vac_end":       "Ta'til tugash sanasi (KK.OO.YYYY):",
"vac_reason":    "Sabab (ixtiyoriy):",
"vac_sent":      "✓ So'rov yuborildi\n\n  {start} → {end}\n  Holat: kutilmoqda",
"vac_list_hdr":  "◈ Mening so'rovlarim\n",
"vac_row":       "  {start} → {end}   {status}\n",
"vac_empty":     "  So'rovlar yo'q.",
"inv_date":      "Noto'g'ri sana. Format: KK.OO.YYYY",
"s_pending":     "⏳ kutilmoqda",
"s_approved":    "✓ tasdiqlandi",
"s_rejected":    "✗ rad etildi",
# profile
"profile_hdr":   "◈ Profil  ·  {company}\n\n  Ism        {name}\n  Filial     {branch}\n  Lavozim    {position}\n  Soatlik    {rate:,} so'm\n  Rol        {role}\n  Ro'yxat    {created}",
"btn_lang":      "Tilni o'zgartirish",
"lang_changed":  "✓ Til o'zgartirildi.",
# admin
"adm_hdr":       "◈ Admin panel  ·  {company}",
"btn_emps":      "Xodimlar",
"btn_reqs":      "Ta'til so'rovlari",
"btn_report":    "Oylik hisobot",
"pick_emp":      "Xodimni tanlang:",
"emp_detail":    "◈ {name}\n\n  Filial     {branch}\n  Lavozim    {position}\n  Soatlik    {rate:,} so'm\n  Rol        {role}",
"btn_set_rate":  "Stavka belgilash",
"btn_mk_admin":  "Admin qilish",
"enter_rate":    "Yangi soatlik stavka (so'm, faqat raqam):",
"rate_set":      "✓ Stavka: {rate:,} so'm/soat",
"made_admin":    "✓ {name} endi Admin.",
"pending_hdr":   "◈ Kutilayotgan so'rovlar\n",
"vac_item":      "  {i}.  {name}  ·  {branch}\n       {start} → {end}\n       {reason}\n",
"no_pending":    "  Kutilayotgan so'rovlar yo'q.",
"approve":       "✓",
"reject":        "✗",
"vac_approved":  "✓ So'rov tasdiqlandi.",
"vac_rejected":  "✗ So'rov rad etildi.",
"ntf_approved":  "✓ Ta'til so'rovingiz tasdiqlandi\n\n  {start} → {end}",
"ntf_rejected":  "✗ Ta'til so'rovingiz rad etildi\n\n  {start} → {end}",
"report_hdr":    "◈ Oylik hisobot  ·  {month}\n\n",
"report_row":    "  {name:<20} {hours:>5.1f}h   ✓{came}  ⚠{late}\n",
"no_emps":       "  Xodimlar topilmadi.",
},
"ru": {
"welcome":       "◈ {company}\n\n{greeting}! Добро пожаловать в HR систему.\n\nВыберите язык:",
"enter_name":    "Введите ваше имя:",
"enter_branch":  "Введите название филиала:",
"enter_position":"Введите вашу должность:",
"registered":    "◈ Регистрация завершена\n\n  Имя          {name}\n  Филиал       {branch}\n  Должность    {position}",
"first_admin":   "Вы первый пользователь — назначены Администратором.",
"main_menu":     "◈ {company}  ·  {greeting}",
"btn_today":     "Сегодня",
"btn_history":   "История",
"btn_vacation":  "Отпуск",
"btn_profile":   "Профиль",
"btn_admin":     "⚙ Админ",
"btn_back":      "← Назад",
"btn_skip":      "Пропустить",
"today_hdr":     "◈ Сегодня  ·  {date}",
"step_came":     "Пришёл",
"step_lunch_out":"Ушёл на обед",
"step_lunch_in": "Вернулся с обеда",
"step_left":     "Ушёл домой",
"day_done":      "Рабочий день завершён.",
"ask_location":  "📍 Отправьте геолокацию\n(нажмите кнопку или выберите на карте):",
"loc_too_far":   "Вы в {dist:.0f}м от офиса.\nCheck‑in работает только в {radius}м.",
"loc_ok":        "✓ Геолокация подтверждена  ·  {dist:.0f}м",
"checked_in":    "✓ Приход отмечен  ·  {time}",
"lunch_out_ok":  "✓ Ушли на обед  ·  {time}",
"lunch_in_ok":   "✓ Вернулись с обеда  ·  {time}",
"checked_out":   "✓ Уход отмечен  ·  {time}\n\n  Рабочее время    {hours:.1f} ч\n  Начислено        {earned:,} сум",
"late_note":     "  Вы пришли с опозданием",
"no_checkin":    "Сначала отметьте приход.",
"already_done":  "Этот шаг уже выполнен.",
"after_hours":   "Не рабочее время ({start}:00 – {end}:00).",
"hist_hdr":      "◈ История  ·  {month}\n\n  Итого        {hours:.1f} ч\n  Пришёл       {came} дн\n  Опоздал      {late} дн\n",
"hist_row":      "  {date}   {ci} → {co}   {h:.1f}h\n",
"no_records":    "  Записей нет.",
"vac_hdr":       "◈ Отпуск\n\n  Всего заявок: {n}",
"btn_new_vac":   "+ Новая заявка",
"btn_my_vacs":   "Мои заявки",
"vac_start":     "Дата начала отпуска (ДД.ММ.ГГГГ):",
"vac_end":       "Дата окончания отпуска (ДД.ММ.ГГГГ):",
"vac_reason":    "Причина (необязательно):",
"vac_sent":      "✓ Заявка отправлена\n\n  {start} → {end}\n  Статус: ожидает",
"vac_list_hdr":  "◈ Мои заявки\n",
"vac_row":       "  {start} → {end}   {status}\n",
"vac_empty":     "  Заявок нет.",
"inv_date":      "Неверная дата. Формат: ДД.ММ.ГГГГ",
"s_pending":     "⏳ ожидает",
"s_approved":    "✓ одобрено",
"s_rejected":    "✗ отклонено",
"profile_hdr":   "◈ Профиль  ·  {company}\n\n  Имя           {name}\n  Филиал        {branch}\n  Должность     {position}\n  Почасовая     {rate:,} сум\n  Роль          {role}\n  Регистрация   {created}",
"btn_lang":      "Изменить язык",
"lang_changed":  "✓ Язык изменён.",
"adm_hdr":       "◈ Панель администратора  ·  {company}",
"btn_emps":      "Сотрудники",
"btn_reqs":      "Заявки на отпуск",
"btn_report":    "Месячный отчёт",
"pick_emp":      "Выберите сотрудника:",
"emp_detail":    "◈ {name}\n\n  Филиал        {branch}\n  Должность     {position}\n  Почасовая     {rate:,} сум\n  Роль          {role}",
"btn_set_rate":  "Установить ставку",
"btn_mk_admin":  "Сделать админом",
"enter_rate":    "Новая почасовая ставка (сум, только цифры):",
"rate_set":      "✓ Ставка: {rate:,} сум/ч",
"made_admin":    "✓ {name} теперь Администратор.",
"pending_hdr":   "◈ Заявки на рассмотрение\n",
"vac_item":      "  {i}.  {name}  ·  {branch}\n       {start} → {end}\n       {reason}\n",
"no_pending":    "  Нет заявок на рассмотрение.",
"approve":       "✓",
"reject":        "✗",
"vac_approved":  "✓ Заявка одобрена.",
"vac_rejected":  "✗ Заявка отклонена.",
"ntf_approved":  "✓ Ваша заявка на отпуск одобрена\n\n  {start} → {end}",
"ntf_rejected":  "✗ Ваша заявка на отпуск отклонена\n\n  {start} → {end}",
"report_hdr":    "◈ Месячный отчёт  ·  {month}\n\n",
"report_row":    "  {name:<20} {hours:>5.1f}h   ✓{came}  ⚠{late}\n",
"no_emps":       "  Сотрудников нет.",
},
}

def tx(lang, key, **kw):
    text = T.get(lang, T["uz"]).get(key, key)
    return text.format(**kw) if kw else text

def vstatus(lang, s):
    return {"pending": tx(lang,"s_pending"),
            "approved": tx(lang,"s_approved"),
            "rejected": tx(lang,"s_rejected")}.get(s, s)

def role_label(lang, role):
    if role == "admin":
        return "Admin"
    return {"uz": "Xodim", "ru": "Сотрудник"}[lang]

# ── Keyboards ─────────────────────────────────────────────────────────────────
def main_kb(lang, is_admin=False):
    rows = [
        [InlineKeyboardButton(tx(lang,"btn_today"),   callback_data="today"),
         InlineKeyboardButton(tx(lang,"btn_history"), callback_data="history")],
        [InlineKeyboardButton(tx(lang,"btn_vacation"),callback_data="vacation"),
         InlineKeyboardButton(tx(lang,"btn_profile"), callback_data="profile")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(tx(lang,"btn_admin"), callback_data="admin")])
    return InlineKeyboardMarkup(rows)

def back_kb(lang, cb="back_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"btn_back"), callback_data=cb)]])

def loc_kb(lang):
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📍 " + ("Joylashuvni yuborish" if lang=="uz" else "Отправить геолокацию"),
                         request_location=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )

def today_action_kb(lang, att):
    btns = []
    if not att or not att.get("check_in"):
        btns.append(InlineKeyboardButton(tx(lang,"step_came"),      callback_data="a_came"))
    elif not att.get("lunch_out"):
        btns.append(InlineKeyboardButton(tx(lang,"step_lunch_out"), callback_data="a_lunch_out"))
    elif not att.get("lunch_in"):
        btns.append(InlineKeyboardButton(tx(lang,"step_lunch_in"),  callback_data="a_lunch_in"))
    elif not att.get("check_out"):
        btns.append(InlineKeyboardButton(tx(lang,"step_left"),      callback_data="a_left"))
    rows = [btns] if btns else []
    rows.append([InlineKeyboardButton(tx(lang,"btn_back"), callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

# ── Helpers ───────────────────────────────────────────────────────────────────
def calc_hours(att) -> float:
    if not att or not att.get("check_in") or not att.get("check_out"):
        return 0.0
    fmt = "%H:%M:%S"
    i = datetime.strptime(att["check_in"],  fmt)
    o = datetime.strptime(att["check_out"], fmt)
    lunch = 0
    if att.get("lunch_out") and att.get("lunch_in"):
        lo = datetime.strptime(att["lunch_out"], fmt)
        li = datetime.strptime(att["lunch_in"],  fmt)
        lunch = (li - lo).seconds // 60
    return max(0, (o - i).seconds // 60 - lunch) / 60

def today_rows(lang, att):
    steps = [
        ("step_came",      att.get("check_in")   if att else None),
        ("step_lunch_out", att.get("lunch_out")  if att else None),
        ("step_lunch_in",  att.get("lunch_in")   if att else None),
        ("step_left",      att.get("check_out")  if att else None),
    ]
    out = ""
    for key, val in steps:
        mark = "✓" if val else "○"
        time_s = f"   {val[:5]}" if val else ""
        out += f"  {mark}  {tx(lang, key)}{time_s}\n"
    return out

def parse_date(s):
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None

# ── /start ────────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    user = db.get_employee(update.effective_user.id)
    if user:
        lang = user["language"]
        await update.message.reply_text(
            tx(lang,"main_menu", company=COMPANY, greeting=time_greeting(lang)),
            reply_markup=main_kb(lang, user["role"]=="admin"),
        )
        return MAIN_MENU
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
    ]])
    await update.message.reply_text(
        tx("uz","welcome", company=COMPANY, greeting=time_greeting("uz")),
        reply_markup=kb,
    )
    return LANG

# ── Registration ──────────────────────────────────────────────────────────────
async def cb_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = q.data.split("_")[1]
    ctx.user_data["lang"] = lang
    await q.edit_message_text(tx(lang,"enter_name"))
    return REG_NAME

async def reg_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["name"] = update.message.text.strip()
    lang = ctx.user_data.get("lang","uz")
    await update.message.reply_text(tx(lang,"enter_branch"))
    return REG_BRANCH

async def reg_branch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["branch"] = update.message.text.strip()
    lang = ctx.user_data.get("lang","uz")
    await update.message.reply_text(tx(lang,"enter_position"))
    return REG_POSITION

async def reg_position(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang   = ctx.user_data.get("lang","uz")
    name   = ctx.user_data["name"]
    branch = ctx.user_data["branch"]
    pos    = update.message.text.strip()
    tid    = update.effective_user.id
    first  = db.get_employee_count() == 0
    role   = "admin" if first else "employee"
    db.add_employee(tid, name, branch, pos, lang, role)
    await update.message.reply_text(
        tx(lang,"registered", name=name, branch=branch, position=pos)
    )
    if first:
        await update.message.reply_text(tx(lang,"first_admin"))
    await update.message.reply_text(
        tx(lang,"main_menu", company=COMPANY, greeting=time_greeting(lang)),
        reply_markup=main_kb(lang, first),
    )
    return MAIN_MENU

# ── Location handler ──────────────────────────────────────────────────────────
async def handle_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = db.get_employee(update.effective_user.id)
    lang = user["language"] if user else "uz"
    action = ctx.user_data.pop("awaiting_location", None)
    if not action:
        return MAIN_MENU

    loc  = update.message.location
    dist = haversine(loc.latitude, loc.longitude, OFFICE_LAT, OFFICE_LON)

    if dist > OFFICE_RADIUS:
        await update.message.reply_text(
            tx(lang,"loc_too_far", dist=dist, radius=OFFICE_RADIUS),
            reply_markup=ReplyKeyboardRemove(),
        )
        await update.message.reply_text(
            tx(lang,"main_menu", company=COMPANY, greeting=time_greeting(lang)),
            reply_markup=main_kb(lang, user["role"]=="admin"),
        )
        return MAIN_MENU

    # Within radius — process
    now_h  = datetime.now().hour
    is_late = 1 if now_h >= WORK_START else 0

    if action == "checkin":
        t = db.mark_check_in(user["id"], loc.latitude, loc.longitude, is_late)
        msg = tx(lang,"loc_ok", dist=dist) + "\n" + tx(lang,"checked_in", time=t)
        if is_late:
            msg += "\n" + tx(lang,"late_note")
    elif action == "checkout":
        t = db.mark_check_out(user["id"], loc.latitude, loc.longitude)
        att = db.get_today_attendance(user["id"])
        hours  = calc_hours(att)
        earned = int(hours * user["hourly_rate"])
        msg = tx(lang,"loc_ok", dist=dist) + "\n" + tx(lang,"checked_out", time=t, hours=hours, earned=earned)
    else:
        msg = "OK"

    await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(
        tx(lang,"main_menu", company=COMPANY, greeting=time_greeting(lang)),
        reply_markup=main_kb(lang, user["role"]=="admin"),
    )
    return MAIN_MENU

# ── Main menu callback ────────────────────────────────────────────────────────
async def cb_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    user = db.get_employee(update.effective_user.id)
    if not user:
        await q.edit_message_text("Avval /start bosing.")
        return LANG
    lang = user["language"]
    data = q.data

    # ── back ──
    if data == "back_main":
        await q.edit_message_text(
            tx(lang,"main_menu", company=COMPANY, greeting=time_greeting(lang)),
            reply_markup=main_kb(lang, user["role"]=="admin"),
        )
        return MAIN_MENU

    # ── today ──
    if data == "today":
        att = db.get_today_attendance(user["id"])
        rows = today_rows(lang, att)
        done = att and att.get("check_out")
        footer = tx(lang,"day_done") if done else ""
        text = tx(lang,"today_hdr", date=date.today().strftime("%d.%m.%Y"))
        text += "\n\n" + rows
        if footer:
            text += "\n" + footer
        await q.edit_message_text(text, reply_markup=today_action_kb(lang, att))
        return MAIN_MENU

    # ── attendance actions ──
    if data == "a_came":
        att = db.get_today_attendance(user["id"])
        if att and att.get("check_in"):
            await q.answer(tx(lang,"already_done"), show_alert=True)
            return MAIN_MENU
        ctx.user_data["awaiting_location"] = "checkin"
        await q.edit_message_text(tx(lang,"ask_location"))
        await ctx.bot.send_message(
            update.effective_user.id,
            tx(lang,"ask_location"),
            reply_markup=loc_kb(lang),
        )
        return MAIN_MENU

    if data == "a_lunch_out":
        att = db.get_today_attendance(user["id"])
        if not att or not att.get("check_in"):
            await q.answer(tx(lang,"no_checkin"), show_alert=True); return MAIN_MENU
        if att.get("lunch_out"):
            await q.answer(tx(lang,"already_done"), show_alert=True); return MAIN_MENU
        t = db.mark_lunch_out(user["id"])
        await q.edit_message_text(
            tx(lang,"lunch_out_ok", time=t),
            reply_markup=back_kb(lang),
        )
        return MAIN_MENU

    if data == "a_lunch_in":
        att = db.get_today_attendance(user["id"])
        if not att or not att.get("lunch_out"):
            await q.answer(tx(lang,"no_checkin"), show_alert=True); return MAIN_MENU
        if att.get("lunch_in"):
            await q.answer(tx(lang,"already_done"), show_alert=True); return MAIN_MENU
        t = db.mark_lunch_in(user["id"])
        await q.edit_message_text(
            tx(lang,"lunch_in_ok", time=t),
            reply_markup=back_kb(lang),
        )
        return MAIN_MENU

    if data == "a_left":
        att = db.get_today_attendance(user["id"])
        if not att or not att.get("check_in"):
            await q.answer(tx(lang,"no_checkin"), show_alert=True); return MAIN_MENU
        if att.get("check_out"):
            await q.answer(tx(lang,"already_done"), show_alert=True); return MAIN_MENU
        ctx.user_data["awaiting_location"] = "checkout"
        await ctx.bot.send_message(
            update.effective_user.id,
            tx(lang,"ask_location"),
            reply_markup=loc_kb(lang),
        )
        await q.edit_message_text(tx(lang,"ask_location"))
        return MAIN_MENU

    # ── history ──
    if data == "history":
        now   = datetime.now()
        stats = db.get_month_stats(user["id"], now.year, now.month)
        text  = tx(lang,"hist_hdr",
                   month=now.strftime("%B %Y"),
                   hours=stats["total_hours"],
                   came=stats["came"], late=stats["late"])
        recs  = stats["records"][:15]
        if recs:
            for r in recs:
                h = calc_hours(r)
                text += tx(lang,"hist_row",
                           date=r["work_date"],
                           ci=(r["check_in"] or "--:--")[:5],
                           co=(r["check_out"] or "--:--")[:5],
                           h=h)
        else:
            text += tx(lang,"no_records")
        await q.edit_message_text(text, reply_markup=back_kb(lang))
        return MAIN_MENU

    # ── vacation menu ──
    if data == "vacation":
        n  = len(db.get_my_vacations(user["id"]))
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx(lang,"btn_new_vac"), callback_data="vac_new"),
             InlineKeyboardButton(tx(lang,"btn_my_vacs"), callback_data="vac_list")],
            [InlineKeyboardButton(tx(lang,"btn_back"),    callback_data="back_main")],
        ])
        await q.edit_message_text(tx(lang,"vac_hdr", n=n), reply_markup=kb)
        return MAIN_MENU

    if data == "vac_list":
        vacs = db.get_my_vacations(user["id"])
        text = tx(lang,"vac_list_hdr")
        if vacs:
            for v in vacs:
                text += tx(lang,"vac_row",
                           start=v["start_date"], end=v["end_date"],
                           status=vstatus(lang, v["status"]))
        else:
            text += tx(lang,"vac_empty")
        await q.edit_message_text(text, reply_markup=back_kb(lang,"vacation"))
        return MAIN_MENU

    if data == "vac_new":
        await q.edit_message_text(tx(lang,"vac_start"))
        return VAC_START

    # ── profile ──
    if data == "profile":
        rl      = role_label(lang, user["role"])
        created = (user["created_at"] or "")[:10]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx(lang,"btn_lang"),  callback_data="change_lang")],
            [InlineKeyboardButton(tx(lang,"btn_back"),  callback_data="back_main")],
        ])
        await q.edit_message_text(
            tx(lang,"profile_hdr",
               company=COMPANY, name=user["name"], branch=user["branch"],
               position=user["position"], rate=user["hourly_rate"],
               role=rl, created=created),
            reply_markup=kb,
        )
        return MAIN_MENU

    if data == "change_lang":
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🇺🇿 O'zbek", callback_data="setlang_uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru"),
        ]])
        await q.edit_message_text(T["uz"]["welcome"].split("\n\n")[0], reply_markup=kb)
        return MAIN_MENU

    if data.startswith("setlang_"):
        nl = data.split("_")[1]
        db.update_employee_language(update.effective_user.id, nl)
        lang = nl
        await q.edit_message_text(
            tx(nl,"lang_changed") + "\n\n" +
            tx(nl,"main_menu", company=COMPANY, greeting=time_greeting(nl)),
            reply_markup=main_kb(nl, user["role"]=="admin"),
        )
        return MAIN_MENU

    # ── admin panel ──
    if data == "admin" and user["role"] == "admin":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx(lang,"btn_emps"),   callback_data="adm_emps"),
             InlineKeyboardButton(tx(lang,"btn_reqs"),   callback_data="adm_reqs")],
            [InlineKeyboardButton(tx(lang,"btn_report"), callback_data="adm_report")],
            [InlineKeyboardButton(tx(lang,"btn_back"),   callback_data="back_main")],
        ])
        await q.edit_message_text(
            tx(lang,"adm_hdr", company=COMPANY), reply_markup=kb
        )
        return MAIN_MENU

    if data == "adm_emps" and user["role"] == "admin":
        emps = db.get_all_employees()
        if not emps:
            await q.edit_message_text(tx(lang,"no_emps"), reply_markup=back_kb(lang,"admin"))
            return MAIN_MENU
        btns = [[InlineKeyboardButton(
            f"  {e['name']}  ·  {e['position']}", callback_data=f"emp_{e['id']}"
        )] for e in emps]
        btns.append([InlineKeyboardButton(tx(lang,"btn_back"), callback_data="admin")])
        await q.edit_message_text(tx(lang,"pick_emp"), reply_markup=InlineKeyboardMarkup(btns))
        return MAIN_MENU

    if data.startswith("emp_") and user["role"] == "admin":
        eid = int(data.split("_")[1])
        emp = db.get_employee_by_id(eid)
        ctx.user_data["target_emp"] = eid
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx(lang,"btn_set_rate"),  callback_data=f"setrate_{eid}"),
             InlineKeyboardButton(tx(lang,"btn_mk_admin"),  callback_data=f"mkadmin_{eid}")],
            [InlineKeyboardButton(tx(lang,"btn_back"),      callback_data="adm_emps")],
        ])
        await q.edit_message_text(
            tx(lang,"emp_detail",
               name=emp["name"], branch=emp["branch"],
               position=emp["position"], rate=emp["hourly_rate"],
               role=role_label(lang, emp["role"])),
            reply_markup=kb,
        )
        return MAIN_MENU

    if data.startswith("setrate_") and user["role"] == "admin":
        ctx.user_data["target_emp"] = int(data.split("_")[1])
        await q.edit_message_text(tx(lang,"enter_rate"))
        return ADMIN_SET_RATE

    if data.startswith("mkadmin_") and user["role"] == "admin":
        eid = int(data.split("_")[1])
        emp = db.get_employee_by_id(eid)
        db.set_admin(emp["telegram_id"])
        await q.edit_message_text(
            tx(lang,"made_admin", name=emp["name"]), reply_markup=back_kb(lang,"adm_emps")
        )
        return MAIN_MENU

    if data == "adm_reqs" and user["role"] == "admin":
        pending = db.get_pending_vacations()
        if not pending:
            await q.edit_message_text(tx(lang,"no_pending"), reply_markup=back_kb(lang,"admin"))
            return MAIN_MENU
        text  = tx(lang,"pending_hdr")
        btns  = []
        for i, v in enumerate(pending, 1):
            reason = v.get("reason") or "—"
            text += tx(lang,"vac_item", i=i, name=v["name"], branch=v["branch"],
                       start=v["start_date"], end=v["end_date"], reason=reason)
            btns.append([
                InlineKeyboardButton(f"✓ #{i}", callback_data=f"va_{v['id']}"),
                InlineKeyboardButton(f"✗ #{i}", callback_data=f"vr_{v['id']}"),
            ])
        btns.append([InlineKeyboardButton(tx(lang,"btn_back"), callback_data="admin")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(btns))
        return MAIN_MENU

    if data.startswith("va_") and user["role"] == "admin":
        await _vac_decision(update, ctx, int(data[3:]), "approved", lang, user)
        return MAIN_MENU

    if data.startswith("vr_") and user["role"] == "admin":
        await _vac_decision(update, ctx, int(data[3:]), "rejected", lang, user)
        return MAIN_MENU

    if data == "adm_report" and user["role"] == "admin":
        now   = datetime.now()
        emps  = db.get_all_employees()
        text  = tx(lang,"report_hdr", month=now.strftime("%B %Y"))
        for e in emps:
            s = db.get_month_stats(e["id"], now.year, now.month)
            text += tx(lang,"report_row",
                       name=e["name"][:18], hours=s["total_hours"],
                       came=s["came"], late=s["late"])
        await q.edit_message_text(text, reply_markup=back_kb(lang,"admin"))
        return MAIN_MENU

    return MAIN_MENU


async def _vac_decision(update, ctx, req_id, status, lang, admin_user):
    q = update.callback_query
    db.update_vacation_status(req_id, status, admin_user["id"])
    with db.get_conn() as conn:
        row = conn.execute(
            """SELECT v.start_date, v.end_date, e.telegram_id, e.language
               FROM vacation_requests v JOIN employees e ON e.id=v.employee_id
               WHERE v.id=?""", (req_id,)
        ).fetchone()
    if row:
        el = row["language"]
        key = "ntf_approved" if status=="approved" else "ntf_rejected"
        try:
            await ctx.bot.send_message(
                row["telegram_id"],
                tx(el, key, start=row["start_date"], end=row["end_date"]),
            )
        except Exception:
            pass
    msg = tx(lang,"vac_approved") if status=="approved" else tx(lang,"vac_rejected")
    await q.edit_message_text(msg, reply_markup=back_kb(lang,"adm_reqs"))

# ── Vacation conversation ─────────────────────────────────────────────────────
async def vac_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = db.get_employee(update.effective_user.id)
    lang = user["language"] if user else "uz"
    d = parse_date(update.message.text)
    if not d:
        await update.message.reply_text(tx(lang,"inv_date")); return VAC_START
    ctx.user_data["vac_start"] = d.isoformat()
    await update.message.reply_text(tx(lang,"vac_end"))
    return VAC_END

async def vac_end(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = db.get_employee(update.effective_user.id)
    lang = user["language"] if user else "uz"
    d = parse_date(update.message.text)
    if not d:
        await update.message.reply_text(tx(lang,"inv_date")); return VAC_END
    ctx.user_data["vac_end"] = d.isoformat()
    skip = ReplyKeyboardMarkup([[tx(lang,"btn_skip")]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(tx(lang,"vac_reason"), reply_markup=skip)
    return VAC_REASON

async def vac_reason(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user   = db.get_employee(update.effective_user.id)
    lang   = user["language"] if user else "uz"
    reason = "" if update.message.text == tx(lang,"btn_skip") else update.message.text
    start  = ctx.user_data["vac_start"]
    end    = ctx.user_data["vac_end"]
    db.add_vacation_request(user["id"], start, end, reason)
    await update.message.reply_text(
        tx(lang,"vac_sent", start=start, end=end),
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        tx(lang,"main_menu", company=COMPANY, greeting=time_greeting(lang)),
        reply_markup=main_kb(lang, user["role"]=="admin"),
    )
    return MAIN_MENU

# ── Admin set rate ────────────────────────────────────────────────────────────
async def admin_set_rate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = db.get_employee(update.effective_user.id)
    lang = user["language"] if user else "uz"
    try:
        rate = int(update.message.text.strip().replace(" ","").replace(",",""))
    except ValueError:
        await update.message.reply_text("Faqat raqam kiriting."); return ADMIN_SET_RATE
    db.update_employee_rate(ctx.user_data.get("target_emp"), rate)
    await update.message.reply_text(
        tx(lang,"rate_set", rate=rate),
        reply_markup=main_kb(lang, True),
    )
    return MAIN_MENU

# ── Fallback ──────────────────────────────────────────────────────────────────
async def fallback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = db.get_employee(update.effective_user.id)
    if not user:
        await cmd_start(update, ctx); return LANG
    lang = user["language"]
    await update.message.reply_text(
        tx(lang,"main_menu", company=COMPANY, greeting=time_greeting(lang)),
        reply_markup=main_kb(lang, user["role"]=="admin"),
    )
    return MAIN_MENU

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            LANG:           [CallbackQueryHandler(cb_lang, pattern="^lang_")],
            REG_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_BRANCH:     [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_branch)],
            REG_POSITION:   [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_position)],
            MAIN_MENU: [
                CallbackQueryHandler(cb_main),
                MessageHandler(filters.LOCATION, handle_location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, fallback),
            ],
            VAC_START:      [MessageHandler(filters.TEXT & ~filters.COMMAND, vac_start)],
            VAC_END:        [MessageHandler(filters.TEXT & ~filters.COMMAND, vac_end)],
            VAC_REASON:     [MessageHandler(filters.TEXT & ~filters.COMMAND, vac_reason)],
            ADMIN_SET_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_rate)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info(f"{COMPANY} HR Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
