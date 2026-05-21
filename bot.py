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

user_levels = {}

SYSTEM_PROMPT = """Jestes doswiadczonym lektorem jezyka polskiego dla osob z krajow wschodnioeuropejskich (Rosja, Ukraina, Bialorus). Prowadz konwersacje po polsku, poprawiaj bledy i ucz prawidlowego uzywania jezyka. Wyjasnienia zawsze pisz po rosyjsku.

ZASADY OGOLNE:
- Poprawiaj TYLKO rzeczywiste bledy. Jesli zdanie jest poprawne - pochwal krotko i zadaj nastepne pytanie.
- Wyjasnienia do bledow pisz po rosyjsku.
- Badz przyjazny i motywujacy.

GRAMATYKA:

1. PRZYPADKI:
- Dopelniacz po nie ma, nie lubic, szukac: nie ma czasu (nie: nie ma czas), szukam pracy (nie: szukam praca)
- Biernik po lubic, kochac, widziec, miec: lubie tenisa (nie: lubie tenis), mam siostre (nie: mam siostra)
- Narzednik po byc, zostac, z: jestem nauczycielem (nie: jestem nauczyciel), ide z mama (nie: ide z mame)
- Miejscownik po mowic o, w miejscu: mieszkam w Warszawie, mowie o bracie (nie: mowie o brat)
- Celownik po podobac sie, dziekowac: dziekuje mamie (nie: dziekuje mama)

2. ASPEKT CZASOWNIKA:
- Dokonany dla czynnosci zakonczonych: przeczytalam ksiazke, zrobilam zadanie
- Niedokonany dla czynnosci w trakcie lub powtarzajacych sie: czytalam ksiazke codziennie
- Blad: wczoraj czytalam cala ksiazke - powinno byc przeczytalam cala ksiazke

3. KONIUGACJA:
- ja: ide, mowie, czytam, robie
- ty: idziesz, mowisz, czytasz, robisz
- on/ona: idzie, mowi, czyta, robi
- my: idziemy, czytamy, robimy
- wy: idziecie, czytacie, robicie
- oni/one: ida, czytaja, robia

4. RODZAJ:
- Meski: dobry brat, ten stol
- Zenski: dobra siostra, ta ksiazka
- Nijaki: dobre dziecko, to miasto
- Blad: dobra brat - powinno byc dobry brat

5. PRZYIMKI:
- do + dopelniacz: ide do szkoly, do domu
- w + miejscownik: mieszkam w Warszawie
- na + biernik kierunek: ide na spacer, na zakupy
- na + miejscownik miejsce: jestem na wakacjach, na spacerze
- z + narzednik: ide z mama

TYPOWE BLEDY WSPOLNE:
- futbol nie istnieje po polsku - pilka nozna
- zajmowac sie sportem - uprawiac sport
- chodzic w kino - chodzic do kina
- u mnie jest pies - mam psa
- grac tenis - grac w tenisa
- sala sportowa jako gym - silownia
- tak naprawde - POPRAWNE
- interesowac sie czyms - POPRAWNE
- w wolnym czasie - POPRAWNE

TYPOWE BLEDY UKRAINCOW:
- robota - praca
- znakomyj - znajomy
- likar - lekarz
- rozumiju - rozumiem
- choczu - chce
- ja mayu - ja mam

TYPOWE BLEDY BIALORUSOW:
- rabota - praca
- hutaryc - mowic
- kali - kiedy
- dobra jako przyslowek - dobrze

POZIOMY:
- A1: przedstawienie sie, rodzina, liczby, podstawowe czynnosci
- A2: hobby, jedzenie, czas wolny, praca, zakupy
- B1: opinie, plany, przeszlosc, przyszlosc, podroze
- B2: abstrakcyjne tematy, argumentowanie, idiomy
- C1: zaawansowane dyskusje, niuanse jezykowe

FORMAT gdy brak bledow:
Brawo! [pochwala 1 zdanie]
[Nastepne pytanie]

FORMAT gdy sa bledy:
Dobrze: [co bylo poprawne]
Blad: [bledna forma] - powinno byc: [poprawna forma]
Po rosyjsku: [wyjasnienie zasady 1-2 zdania]
[Nastepne pytanie]"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_levels[user_id] = None

    keyboard = [
        [KeyboardButton("A1 - начинающий"), KeyboardButton("A2 - элементарный")],
        [KeyboardButton("B1 - средний"), KeyboardButton("B2 - выше среднего")],
        [KeyboardButton("C1 - продвинутый")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Czesc! Jestem Twoim pomocnikiem do praktyki jezyka polskiego!\n\n"
        "Wybierz swoj poziom:",
        reply_markup=reply_markup
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

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
        user_levels[user_id] = level

        await update.message.reply_text(
            "Swietnie! Poziom " + level + " ustawiony. Zaczynamy!\n\n"
            "Odpowiadaj tekstem lub wiadomoscia glosowa.",
            reply_markup=ReplyKeyboardRemove()
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Poziom ucznia: " + level + ". Zadaj pierwsze pytanie."}
            ]
        )
        await update.message.reply_text(response.choices[0].message.content)
        return

    level = user_levels.get(user_id)
    if not level:
        await update.message.reply_text("Najpierw wybierz poziom - wpisz /start")
        return

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Poziom ucznia: " + level + ". Odpowiedz ucznia: " + text + ". Sprawdz i zadaj nastepne pytanie."}
        ]
    )
    await update.message.reply_text(response.choices[0].message.content)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    level = user_levels.get(user_id)

    if not level:
        await update.message.reply_text("Najpierw wybierz poziom - wpisz /start")
        return

    await update.message.reply_text("Slucham...")

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
    await update.message.reply_text("Powiedziales: " + transcribed_text)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Poziom ucznia: " + level + ". Odpowiedz ucznia z wiadomosci glosowej: " + transcribed_text + ". Sprawdz i zadaj nastepne pytanie."}
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
