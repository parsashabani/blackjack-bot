"""
🃏 ربات تلگرام بلک‌جک - نسخه گروهی
نصب: pip install python-telegram-bot
اجرا: python blackjack_bot.py
"""

import json
import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ─── تنظیمات ───────────────────────────────────────────────
BOT_TOKEN   = "YOUR_BOT_TOKEN_HERE"
SCORES_FILE = "scores.json"

# ─── ذخیره و لود امتیازات ───────────────────────────────────
def load_scores():
    if os.path.exists(SCORES_FILE):
        with open(SCORES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_scores(scores):
    with open(SCORES_FILE, "w") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)

def add_score(user_id, username, result):
    scores = load_scores()
    uid = str(user_id)
    if uid not in scores:
        scores[uid] = {"name": username, "wins": 0, "losses": 0, "ties": 0}
    scores[uid]["name"] = username
    scores[uid][{"win": "wins", "loss": "losses", "tie": "ties"}[result]] += 1
    save_scores(scores)

# ─── کارت‌ها ────────────────────────────────────────────────
SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def new_deck():
    deck = [{"rank": r, "suit": s} for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck

def card_value(card):
    r = card["rank"]
    if r in ("J", "Q", "K"): return 10
    if r == "A": return 11
    return int(r)

def hand_value(hand):
    total = sum(card_value(c) for c in hand)
    aces  = sum(1 for c in hand if c["rank"] == "A")
    while total > 21 and aces:
        total -= 10
        aces  -= 1
    return total

def fmt_hand(hand, hide_second=False):
    if hide_second and len(hand) > 1:
        return f"{hand[0]['rank']}{hand[0]['suit']}  🂠"
    return "  ".join(f"{c['rank']}{c['suit']}" for c in hand)

# ─── وضعیت بازی‌ها ──────────────────────────────────────────
group_games = {}   # { chat_id: { ... } }
solo_games  = {}   # { user_id: { ... } }

# ═══════════════════════════════════════════════════════════
#  بازی تکنفره (Private)
# ═══════════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🃏 *خوش اومدی به بلک‌جک!*\n\n"
        "📌 *بازی تکنفره (پیوی):*\n"
        "  /deal — شروع بازی با ربات\n\n"
        "👥 *بازی گروهی:*\n"
        "  /newgame — باز کردن لابی\n"
        "  /startgame — شروع دست توسط دیلر\n"
        "  /endgame — پایان بازی\n\n"
        "🏆 /leaderboard — جدول امتیازات"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def deal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("برای بازی تکنفره، پیوی ربات بیا!")
        return
    uid    = update.effective_user.id
    deck   = new_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    solo_games[uid] = {"deck": deck, "player": player, "dealer": dealer}

    pv = hand_value(player)
    if pv == 21:
        dv      = hand_value(dealer)
        outcome = "tie" if dv == 21 else "win"
        result  = "🤝 هر دو بلک‌جک! تساوی!" if dv == 21 else "🎉 بلک‌جک!"
        add_score(uid, update.effective_user.first_name, outcome)
        del solo_games[uid]
        await update.message.reply_text(
            f"🎴 *کارت‌های تو:*\n{fmt_hand(player)}  = {pv}\n\n"
            f"🏦 *کارت‌های دیلر:*\n{fmt_hand(dealer)}  = {dv}\n\n{result}",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        f"🎴 *کارت‌های تو:*\n{fmt_hand(player)}  = {pv}\n\n"
        f"🏦 *کارت‌های دیلر:*\n{fmt_hand(dealer, hide_second=True)}  = {card_value(dealer[0])}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🃏 Hit",   callback_data="solo_hit"),
            InlineKeyboardButton("✋ Stand", callback_data="solo_stand"),
        ]])
    )

async def solo_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    uid    = query.from_user.id
    action = query.data

    if uid not in solo_games:
        await query.edit_message_text("❗ بازی فعالی نداری! /deal بزن.")
        return

    g = solo_games[uid]
    player, dealer, deck = g["player"], g["dealer"], g["deck"]
    name = query.from_user.first_name

    if action == "solo_hit":
        player.append(deck.pop())
        pv = hand_value(player)
        if pv > 21:
            add_score(uid, name, "loss")
            del solo_games[uid]
            await query.edit_message_text(
                f"🎴 *کارت‌های تو:*\n{fmt_hand(player)}  = {pv}\n\n💥 *سوختی! باختی!*\n\n/deal برای بازی جدید",
                parse_mode="Markdown"
            )
        elif pv == 21:
            txt = _solo_resolve(g, uid, name)
            del solo_games[uid]
            await query.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query.edit_message_text(
                f"🎴 *کارت‌های تو:*\n{fmt_hand(player)}  = {pv}\n\n"
                f"🏦 *کارت‌های دیلر:*\n{fmt_hand(dealer, hide_second=True)}  = {card_value(dealer[0])}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🃏 Hit",   callback_data="solo_hit"),
                    InlineKeyboardButton("✋ Stand", callback_data="solo_stand"),
                ]])
            )

    elif action == "solo_stand":
        txt = _solo_resolve(g, uid, name)
        del solo_games[uid]
        await query.edit_message_text(txt, parse_mode="Markdown")

def _solo_resolve(g, uid, name):
    player, dealer, deck = g["player"], g["dealer"], g["deck"]
    while hand_value(dealer) < 17:
        dealer.append(deck.pop())
    pv, dv = hand_value(player), hand_value(dealer)
    if dv > 21 or pv > dv:
        result, outcome = "🏆 *تو بردی!*", "win"
    elif pv < dv:
        result, outcome = "😞 *دیلر برد!*", "loss"
    else:
        result, outcome = "🤝 *تساوی!*", "tie"
    add_score(uid, name, outcome)
    return (
        f"🎴 *کارت‌های تو:*\n{fmt_hand(player)}  = *{pv}*\n\n"
        f"🏦 *کارت‌های دیلر:*\n{fmt_hand(dealer)}  = *{dv}*\n\n"
        f"{result}\n\n/deal برای بازی جدید"
    )

# ═══════════════════════════════════════════════════════════
#  بازی گروهی
# ═══════════════════════════════════════════════════════════

async def newgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    user = update.effective_user

    if update.effective_chat.type == "private":
        await update.message.reply_text("این دستور فقط در گروه کار می‌کنه!")
        return
    if cid in group_games and group_games[cid]["phase"] != "ended":
        await update.message.reply_text("یه بازی در حال اجراست! /endgame برای پایان.")
        return

    group_games[cid] = {
        "deck":           new_deck(),
        "dealer_id":      user.id,
        "dealer_name":    user.first_name,
        "dealer_hand":    [],
        "players":        {},
        "phase":          "joining",
        "current_player": None,
        "player_order":   []
    }

    await update.message.reply_text(
        f"🃏 *بازی گروهی بلک‌جک!*\n\n"
        f"🎩 دیلر: *{user.first_name}*\n\n"
        f"بقیه روی دکمه بزنن تا بپیوندن.\n"
        f"وقتی آماده شدن، دیلر /startgame بزنه.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✋ پیوستن به بازی", callback_data="group_join")
        ]])
    )

async def group_join_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid   = update.effective_chat.id
    user  = query.from_user

    if cid not in group_games or group_games[cid]["phase"] != "joining":
        await query.answer("لابی باز نیست!", show_alert=True)
        return

    g = group_games[cid]
    if user.id == g["dealer_id"]:
        await query.answer("تو دیلری! نمی‌تونی بازیکن هم باشی.", show_alert=True)
        return
    if user.id in g["players"]:
        await query.answer("قبلاً پیوستی!", show_alert=True)
        return

    g["players"][user.id]    = {"name": user.first_name, "hand": [], "done": False}
    g["player_order"].append(user.id)

    player_list = "\n".join(f"• {p['name']}" for p in g["players"].values())
    await query.edit_message_text(
        f"🃏 *بازی گروهی بلک‌جک!*\n\n"
        f"🎩 دیلر: *{g['dealer_name']}*\n\n"
        f"👥 *بازیکنان ({len(g['players'])} نفر):*\n{player_list}\n\n"
        f"دیلر /startgame بزنه تا شروع بشه.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✋ پیوستن به بازی", callback_data="group_join")
        ]])
    )

async def startgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    user = update.effective_user

    if cid not in group_games:
        await update.message.reply_text("اول /newgame بزن!")
        return
    g = group_games[cid]
    if user.id != g["dealer_id"]:
        await update.message.reply_text("فقط دیلر می‌تونه بازی رو شروع کنه!")
        return
    if g["phase"] != "joining":
        await update.message.reply_text("بازی در حال اجراست!")
        return
    if not g["players"]:
        await update.message.reply_text("حداقل یه بازیکن لازمه!")
        return

    deck = g["deck"]
    for pid in g["player_order"]:
        g["players"][pid]["hand"] = [deck.pop(), deck.pop()]
    g["dealer_hand"]    = [deck.pop(), deck.pop()]
    g["phase"]          = "playing"
    g["current_player"] = g["player_order"][0]

    await update.message.reply_text(
        _group_status_text(g, hide_dealer=True),
        parse_mode="Markdown",
        reply_markup=_group_kb()
    )

def _group_status_text(g, hide_dealer=True):
    cur_pid = g["current_player"]
    lines   = ["🃏 *وضعیت بازی*\n",
               f"🎩 *دیلر ({g['dealer_name']}):*",
               fmt_hand(g["dealer_hand"], hide_second=hide_dealer), ""]

    for pid in g["player_order"]:
        p   = g["players"][pid]
        hv  = hand_value(p["hand"])
        tag = ""
        if hv > 21:           tag = " 💥 سوخت"
        elif p["done"]:       tag = " ✅"
        elif pid == cur_pid:  tag = " 👈 نوبت توئه!"
        lines.append(f"👤 *{p['name']}*{tag}:")
        lines.append(f"{fmt_hand(p['hand'])}  = {hv}\n")

    return "\n".join(lines)

def _group_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🃏 Hit",   callback_data="group_hit"),
        InlineKeyboardButton("✋ Stand", callback_data="group_stand"),
    ]])

async def group_play_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    cid    = update.effective_chat.id
    user   = query.from_user
    action = query.data

    if cid not in group_games or group_games[cid]["phase"] != "playing":
        await query.answer("بازی فعالی نیست!", show_alert=True)
        return

    g = group_games[cid]
    if user.id != g["current_player"]:
        await query.answer("نوبت تو نیست! صبر کن.", show_alert=True)
        return

    p = g["players"][user.id]

    if action == "group_hit":
        p["hand"].append(g["deck"].pop())
        hv = hand_value(p["hand"])
        if hv >= 21:
            p["done"] = True
            await _advance(query, ctx, cid)
        else:
            await query.edit_message_text(
                _group_status_text(g), parse_mode="Markdown", reply_markup=_group_kb()
            )

    elif action == "group_stand":
        p["done"] = True
        await _advance(query, ctx, cid)

async def _advance(query, ctx, cid):
    g     = group_games[cid]
    order = g["player_order"]
    idx   = order.index(g["current_player"])

    next_pid = None
    for i in range(idx + 1, len(order)):
        if not g["players"][order[i]]["done"]:
            next_pid = order[i]
            break

    if next_pid:
        g["current_player"] = next_pid
        await query.edit_message_text(
            _group_status_text(g), parse_mode="Markdown", reply_markup=_group_kb()
        )
    else:
        g["phase"] = "dealer_turn"
        await _dealer_turn(query, cid)

async def _dealer_turn(query, cid):
    g    = group_games[cid]
    deck = g["deck"]
    while hand_value(g["dealer_hand"]) < 17:
        g["dealer_hand"].append(deck.pop())

    dv    = hand_value(g["dealer_hand"])
    lines = ["🏁 *نتیجه بازی*\n",
             f"🎩 *دیلر ({g['dealer_name']}):* {fmt_hand(g['dealer_hand'])}  = *{dv}*\n"]

    for pid in g["player_order"]:
        p       = g["players"][pid]
        pv      = hand_value(p["hand"])
        if pv > 21:
            result, outcome = "💥 سوخت", "loss"
        elif dv > 21 or pv > dv:
            result, outcome = "🏆 برد!", "win"
        elif pv < dv:
            result, outcome = "😞 باخت", "loss"
        else:
            result, outcome = "🤝 تساوی", "tie"
        add_score(pid, p["name"], outcome)
        lines.append(f"👤 *{p['name']}*: {fmt_hand(p['hand'])}  = *{pv}* — {result}")

    g["phase"] = "ended"
    lines.append("\n/newgame برای بازی جدید")
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

async def endgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    user = update.effective_user
    if cid not in group_games:
        await update.message.reply_text("بازی فعالی نیست!")
        return
    if user.id != group_games[cid]["dealer_id"]:
        await update.message.reply_text("فقط دیلر می‌تونه بازی رو تموم کنه!")
        return
    del group_games[cid]
    await update.message.reply_text("✅ بازی پایان یافت. /newgame برای شروع مجدد.")

# ═══════════════════════════════════════════════════════════
#  لیدربورد
# ═══════════════════════════════════════════════════════════

async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    scores = load_scores()
    if not scores:
        await update.message.reply_text("هنوز کسی بازی نکرده!")
        return

    sorted_players = sorted(scores.items(), key=lambda x: x[1]["wins"], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    lines  = ["🏆 *جدول امتیازات*\n"]

    for i, (uid, data) in enumerate(sorted_players[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        w, l, t = data["wins"], data["losses"], data["ties"]
        total   = w + l + t
        rate    = f"{int(w/total*100)}%" if total > 0 else "0%"
        lines.append(f"{medal} *{data['name']}*")
        lines.append(f"   ✅ {w} برد  |  ❌ {l} باخت  |  🤝 {t} تساوی  |  📊 {rate}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════
#  اجرا
# ═══════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("deal",        deal))
    app.add_handler(CommandHandler("newgame",     newgame))
    app.add_handler(CommandHandler("startgame",   startgame))
    app.add_handler(CommandHandler("endgame",     endgame))
    app.add_handler(CommandHandler("leaderboard", leaderboard))

    app.add_handler(CallbackQueryHandler(solo_button,       pattern="^solo_"))
    app.add_handler(CallbackQueryHandler(group_join_button, pattern="^group_join$"))
    app.add_handler(CallbackQueryHandler(group_play_button, pattern="^group_(hit|stand)$"))

    print("🃏 ربات بلک‌جک گروهی در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
