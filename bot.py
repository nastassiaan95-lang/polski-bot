import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

user_data = {}

def get_system_prompt(lang):
    if lang == "pl":
        lang_instruction = "Wyjaśnienia do błędów pisz ZAWSZE po polsku. To jest OBOWIĄZKOWE."
        error_format = "Wyjaśnienie: [wyjaśnienie zasady po polsku 1-2 zdania]"
    else:
        lang_instruction = "Объяснения к ошибкам пиши ВСЕГДА на русском языке (кириллицей). Это ОБЯЗАТЕЛЬНО."
        error_format = "По-русски: [объяснение правила 1-2 предложения]"

    return """Jesteś doświadczonym lektorem języka polskiego dla osób rosyjskojęzycznych. Prowadź konwersację po polsku, poprawiaj błędy i ucz prawidłowego używania języka.

""" + lang_instruction + """

ZASADY OGÓLNE:
- Poprawiaj TYLKO rzeczywiste błędy. Jeśli zdanie jest poprawne - pochwał krótko i zadaj następne pytanie.
- Bądź przyjazny i motywujący.
- Pytania zadawaj zawsze po polsku.

GRAMATYKA:

1. PRZYPADKI:
- Dopełniacz po nie ma, nie lubić, szukać: nie ma czasu (nie: nie ma czas), szukam pracy (nie: szukam praca)
- Biernik po lubić, kochać, widzieć, mieć: lubię tenisa (nie: lubię tenis), mam siostrę (nie: mam siostra)
- Narzędnik po być, zostać, z: jestem nauczycielem (nie: jestem nauczyciel), idę z mamą (nie: idę z mamę)
- Miejscownik po mówić o, w miejscu: mieszkam w Warszawie, mówię o bracie (nie: mówię o brat)
- Celownik po podobać się, dziękować: dziękuję mamie (nie: dziękuję mama)

2. ASPEKT CZASOWNIKA:
- Dokonany dla czynności zakończonych: przeczytałam książkę, zrobiłam zadanie
- Niedokonany dla czynności w trakcie lub powtarzających się: czytałam książkę codziennie
- Błąd: wczoraj czytałam całą książkę - powinno być przeczytałam całą książkę

3. KONIUGACJA:
- ja: idę, mówię, czytam, robię
- ty: idziesz, mówisz, czytasz, robisz
- on/ona: idzie, mówi, czyta, robi
- my: idziemy, czytamy, robimy
- wy: idziecie, czytacie, robicie
- oni/one: idą, czytają, robią

4. RODZAJ:
- Męski: dobry brat, ten stół
- Żeński: dobra siostra, ta książka
- Nijaki: dobre dziecko, to miasto

5. PRZYIMKI:
- do + dopełniacz: idę do szkoły, do domu
- w + miejscownik: mieszkam w Warszawie
- na + biernik kierunek: idę na spacer, na zakupy
- na + miejscownik miejsce: jestem na wakacjach, na spacerze
- z + narzędnik: idę z mamą

TYPOWE BŁĘDY:
- futbol nie istnieje po polsku - piłka nożna
- zajmować się sportem - uprawiać sport
- chodzić w kino - chodzić do kina
- u mnie jest pies - mam psa
- grać tenis - grać w tenisa
- tak naprawdę - POPRAWNE
- interesować się czymś - POPRAWNE
- w wolnym czasie - POPRAWNE

POZIOMY:
- A1: przedstawienie się, rodzina, liczby, podstawowe czynności
- A2: hobby, jedzenie, czas wolny, praca, zakupy
- B1: opinie, plany, przeszłość, przyszłość, podróże
- B2: abstrakcyjne tematy, argumentowanie, idiomy
- C1: zaawansowane dyskusje, niuanse językowe

FORMAT gdy brak błędów:
Brawo! [pochwała 1 zdanie po polsku]
[Następne pytanie po polsku]

FORMAT gdy są błędy:
Dobrze: [co było poprawne]
Błąd: [błędna forma] - powinno być: [poprawna forma]
""" + error_format + """
[Następne pytanie po polsku]"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"level": None, "lang": None, "step": "lang"}

    keyboard = [
        [KeyboardButton("Объяснения на русском"), KeyboardButton("Wyjaśnienia po polsku")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Cześć! Jestem Twoim pomocnikiem do praktyki języka polskiego!\n\n"
        "Привет! На каком языке объяснять ошибки?\n"
        "W jakim języku wyjaśniać błędy?",
        reply_markup=reply_markup
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_data:
        user_data[user_id] = {"level": None, "lang": None, "step": "lang"}

    step = user_data[user_id].get("step", "lang")

    if step == "lang":
        if text == "Объяснения на русском":
            user_data[user_id]["lang"] = "ru"
        elif text == "Wyjaśnienia po polsku":
            user_data[user_id]["lang"] = "pl"
        else:
            keyboard = [
                [KeyboardButton("Объяснения на русском"), KeyboardButton("Wyjaśnienia po polsku")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                "Выберите язык из кнопок / Wybierz język z przycisków:",
                reply_markup=reply_markup
            )
            return

        user_data[user_id]["step"] = "level"
        keyboard = [
            [KeyboardButton("A1 - начинающий"), KeyboardButton("A2 - элементарный")],
            [KeyboardButton("B1 - средний"), KeyboardButton("B2 - выше среднего")],
            [KeyboardButton("C1 - продвинутый")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Wybierz swój poziom / Выберите уровень:",
            reply_markup=reply_markup
        )
        return

    if step == "level":
        level_map = {
            "A1 - начинающий": "A1",
            "A2 - элементарный": "A2",
            "B1 - средний": "B1",
            "B2 - выше среднего": "B2",
            "C1 - продвинутый": "C1",
            "A1": "A1", "A2": "A2", "B1": "B1", "B2": "B2", "C1": "C1"
        }
        if text in level_map:
            level = level_map[text]
            user_data[user_id]["level"] = level
            user_data[user_id]["step"] = "chat"
            lang = user_data[user_id]["lang"]

            await update.message.reply_text(
                "Świetnie! Zaczynamy! Odpowiadaj tekstem lub wiadomością głosową.",
                reply_markup=ReplyKeyboardRemove()
            )
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": get_system_prompt(lang)},
                    {"role": "user", "content": "Poziom ucznia: " + level + ". Zadaj pierwsze pytanie."}
                ]
            )
            await update.message.reply_text(response.choices[0].message.content)
            return

    level = user_data[user_id].get("level")
    lang = user_data[user_id].get("lang", "ru")

    if not level:
        await update.message.reply_text("Wpisz /start aby zacząć od nowa.")
        return

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": get_system_prompt(lang)},
            {"role": "user", "content": "Poziom ucznia: " + level + ". Odpowiedź ucznia: " + text + ". Sprawdź i zadaj następne pytanie."}
        ]
    )
    await update.message.reply_text(response.choices[0].message.content)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_data:
        await update.message.reply_text("Wpisz /start aby zacząć od nowa.")
        return

    level = user_data[user_id].get("level")
    lang = user_data[user_id].get("lang", "ru")

    if not level:
        await update.message.reply_text("Wpisz /start aby zacząć od nowa.")
        return

    await update.message.reply_text("Słucham...")

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
    await update.message.reply_text("Powiedziałeś/aś: " + transcribed_text)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": get_system_prompt(lang)},
            {"role": "user", "content": "Poziom ucznia: " + level + ". Odpowiedź ucznia z wiadomości głosowej: " + transcribed_text + ". Sprawdź i zadaj następne pytanie."}
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
