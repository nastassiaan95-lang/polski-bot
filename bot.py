import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

user_levels = {}

SYSTEM_PROMPT = """Jesteś doświadczonym lektorem języka polskiego dla osób rosyjskojęzycznych.

NAJWAŻNIEJSZA ZASADA: Poprawiaj TYLKO rzeczywiste błędy. Jeśli zdanie jest poprawne - pochwal i zadaj pytanie.

TYPOWE BŁĘDY ROSJAN - zawsze poprawiaj:
1. Kalki z rosyjskiego:
   - "futbol/football" → "piłka nożna"
   - "zajmować się sportem" → "uprawiać sport"
   - "chodzić na spacer" → "iść na spacer" lub "spacerować"
   - "robić gimnastykę" → "ćwiczyć" lub "uprawiać gimnastykę"
   - "w wolnym czasie" → poprawne!
   - "interesować się czymś" → poprawne!
   - "tak naprawdę" → poprawne!

2. Przyimki:
   - "na spacer" (nie "na spacerze" gdy mówimy o czynności)
   - "grać w tenisa/piłkę nożną" (nie "grać tenis")
   - "chodzić do kina/teatru" (nie "chodzić w kino")

3. Przypadki:
   - po "lubię" → biernik (lubię tenisa, nie "lubię tenis")
   - po "nie ma" → dopełniacz

4. Słownictwo sportowe:
   - "futbol" nie istnieje po polsku → "piłka nożna"
   - "siłownia" (nie "sala sportowa" gdy mówimy o gym)
   - "basen" (nie "pływalnia" w mowie potocznej - choć oba poprawne)

POZIOMY:
- A1/A2: proste pytania o codzienne życie, rodzinę, hobby
- B1/B2: bardziej złożone tematy, opinie, plany
- C1: zaawansowane dyskusje

Format gdy BRAK błędów:
✅ Brawo! (krótka pochwała)
❓ Następne pytanie

Format gdy SĄ błędy:
✅ Co było dobrze
❌ Błąd → poprawka. Wyjaśnienie po rosyjsku (1-2 zdania)
❓ Następne pytanie"""
POZIOMY:
- A1/A2: proste pytania o codzienne życie, rodzinę, hobby
- B1/B2: bardziej złożone tematy, opinie, plany
- C1: zaawansowane dyskusje

Format odpowiedzi gdy BRAK błędów:
✅ Brawo! (krótka pochwała)
❓ Następne pytanie

Format odpowiedzi gdy SĄ błędy:
✅ Co było dobrze
❌ Błąd + poprawka + krótkie wyjaśnienie po rosyjsku
❓ Następne pytanie"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_levels[user_id] = None
    await update.message.reply_text(
        "Cześć! 👋 Я ваш помощник для практики польского языка!\n\n"
        "Для начала — какой у вас уровень польского?\n\n"
        "Напишите один из вариантов:\n"
        "🟢 *A1* — начинающий\n"
        "🟡 *A2* — элементарный\n"
        "🟠 *B1* — средний\n"
        "🔵 *B2* — выше среднего\n"
        "🟣 *C1* — продвинутый",
        parse_mode="Markdown"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().upper()

    if text in ["A1", "A2", "B1", "B2", "C1"]:
        user_levels[user_id] = text
        await update.message.reply_text(
            f"Отлично! Уровень *{text}* установлен. Начинаем практику! 🎯\n\n"
            f"Буду задавать вам вопросы на польском, а вы отвечайте — текстом или голосовым сообщением.",
            parse_mode="Markdown"
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Уровень ученика: {text}. Задай первый вопрос для практики говорения."}
            ]
        )
        await update.message.reply_text(response.choices[0].message.content)
        return

    level = user_levels.get(user_id)
    if not level:
        await update.message.reply_text(
            "Сначала укажите ваш уровень: A1, A2, B1, B2 или C1"
        )
        return

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Уровень ученика: {level}. Ответ ученика: {text}. Проверь и задай следующий вопрос."}
        ]
    )
    await update.message.reply_text(response.choices[0].message.content)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    level = user_levels.get(user_id)

    if not level:
        await update.message.reply_text(
            "Сначала укажите ваш уровень: A1, A2, B1, B2 или C1"
        )
        return

    await update.message.reply_text("🎧 Слушаю ваше сообщение...")

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    with open(tmp_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="pl"
        )

    transcribed_text = transcript.text
    await update.message.reply_text(f"🗣 Вы сказали: *{transcribed_text}*", parse_mode="Markdown")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Уровень ученика: {level}. Ответ ученика (из голосового): {transcribed_text}. Проверь и задай следующий вопрос."}
        ]
    )
    await update.message.reply_text(response.choices[0].message.content)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.run_polling()

if __name__ == "__main__":
    main()
