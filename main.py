import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import API_TOKEN
from parsers.hh_parser import get_hh_vacancies
from analytics import analyze_vacancy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

CITIES = {
    "Великий Новгород": 67,
    "Калининград": 41,
    "Санкт-Петербург": 2,
    "Архангельск": 14,
    "Вологда": 25,
    "Псков": 75,
    "Коми": 1041,
    "Карелия": 1077,
    "Лен. обл.": 145,
    "Мурманск": 64
}

POSITIONS = ["Все должности", "Менеджер", "Специалист", "Заместитель", "Руководитель"]

BANK_MAPPING = {
    "alfa": "Альфа-Банк",
    "vtb": "ВТБ",
    "rshb": "Россельхозбанк",
    "gazprom": "Газпромбанк",
    "tinkoff": "Тинькофф"
}

SBER_BENCHMARK = {
    "salary_avg": 120000,
    "benefits": ["медицинская страховка", "обучение", "ДМС"],
    "tech_stack": ["Python", "SQL", "Kafka"]
}

user_data = {}

# Keyboards
def city_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=city, callback_data=f"city:{city}")] for city in CITIES] +
                        [[InlineKeyboardButton(text="↩️ В начало", callback_data="start")]]
    )

def position_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=pos, callback_data=f"pos:{pos}")] for pos in POSITIONS] +
                        [[InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="pos:manual")],
                         [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:city"),
                          InlineKeyboardButton(text="↩️ В начало", callback_data="start")]]
    )

def bank_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=name, callback_data=f"bank:{key}")] for key, name in BANK_MAPPING.items()] +
                        [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back:position"),
                          InlineKeyboardButton(text="↩️ В начало", callback_data="start")]]
    )

def back_to_main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="↩️ В начало", callback_data="start")]]
    )

# Helpers
def format_salary(salary: dict) -> str:
    if not salary:
        return "Не указана"
    from_s = f"от {salary['from']}" if salary.get('from') else ""
    to_s = f"до {salary['to']}" if salary.get('to') else ""
    currency = salary.get('currency', '').upper()
    return f"{from_s} {to_s} {currency}".strip()

def generate_report(vacancies: list, bank_name: str, city: str) -> str:
    if not vacancies:
        return f"😕 В {city} не найдено вакансий для {bank_name}.\nПопробуйте изменить параметры."
    report = [f"📊 Вакансии {bank_name} ({city}):"]
    for i, v in enumerate(vacancies[:10], 1):  # Увеличено до 10
        try:
            analyzed = analyze_vacancy(v, SBER_BENCHMARK)
            salary = format_salary(v.get('salary'))
            salary_cmp = ""
            if v.get('salary') and v['salary'].get('from'):
                diff = v['salary']['from'] - SBER_BENCHMARK['salary_avg']
                salary_cmp = "(🔺)" if diff > 0 else "(🔻)" if diff < 0 else "(≈ как в Сбере)"
            report.append(
                f"\n{i}. 🏦 {analyzed.get('Название банка', v.get('employer', {}).get('name', 'Не указано'))}\n"
                f"   📌 Должность: {v.get('name', 'Не указана')}\n"
                f"   💰 Зарплата: {salary} {salary_cmp}\n"
                f"   ✔️ Преимущества: {analyzed.get('Преимущества', 'Нет')}\n"
                f"   🎁 Соцпакет: {analyzed.get('Соцпакет', 'Нет данных')}\n"
                f"   💻 Технологичность: {analyzed.get('Технологичность', 'Средняя')}\n"
                f"   🔍 Сравнение с Сбером: {analyzed.get('Сравнение с Сбером', 'Нет данных')}\n"
                f"   🔗 Ссылка: {v.get('alternate_url', 'нет')}"
            )
        except Exception as e:
            logger.error(f"Ошибка анализа вакансии: {e}")
    return "\n".join(report)

# Handlers
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_data[message.from_user.id] = {}
    await message.answer("Выберите город:", reply_markup=city_keyboard())

@dp.callback_query(F.data == "start")
async def restart(query: CallbackQuery):
    user_data[query.from_user.id] = {}
    await query.message.edit_text("Выберите город:", reply_markup=city_keyboard())

@dp.callback_query(F.data.startswith("city:"))
async def choose_city(query: CallbackQuery):
    user_id = query.from_user.id
    city = query.data.split(":", 1)[1]
    user_data[user_id]["city"] = city
    await query.message.edit_text(f"Вы выбрали город: {city}\nТеперь выберите должность:", reply_markup=position_keyboard())

@dp.callback_query(F.data.startswith("pos:"))
async def choose_position(query: CallbackQuery):
    user_id = query.from_user.id
    pos = query.data.split(":", 1)[1]
    if pos == "manual":
        user_data[user_id]["awaiting_manual"] = True
        await query.message.edit_text("Введите должность вручную:")
    else:
        user_data[user_id]["position"] = None if pos == "Все должности" else pos
        await query.message.edit_text("Теперь выберите банк:", reply_markup=bank_keyboard())

@dp.message()
async def manual_position(message: types.Message):
    user_id = message.from_user.id
    if user_data.get(user_id, {}).get("awaiting_manual"):
        user_data[user_id]["position"] = message.text
        user_data[user_id].pop("awaiting_manual")
        await message.answer("Теперь выберите банк:", reply_markup=bank_keyboard())

@dp.callback_query(F.data.startswith("bank:"))
async def choose_bank(query: CallbackQuery):
    user_id = query.from_user.id
    bank_key = query.data.split(":", 1)[1]
    bank_name = BANK_MAPPING.get(bank_key)
    city = user_data[user_id].get("city")
    position = user_data[user_id].get("position")
    city_id = CITIES.get(city)

    await query.message.edit_text(f"🔍 Ищу вакансии {bank_name} в {city}{f' по должности \"{position}\"' if position else ''}...")

    try:
        vacancies = get_hh_vacancies(bank_name, city_id)
        if position:
            vacancies = [v for v in vacancies if position.lower() in v.get('name', '').lower()]
        report = generate_report(vacancies, bank_name, city)
        await query.message.answer(report, reply_markup=bank_keyboard(), disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        await query.message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=back_to_main_keyboard())

# Назад
@dp.callback_query(F.data == "back:city")
async def back_to_city(query: CallbackQuery):
    await query.message.edit_text("Выберите город:", reply_markup=city_keyboard())

@dp.callback_query(F.data == "back:position")
async def back_to_position(query: CallbackQuery):
    await query.message.edit_text("Выберите должность:", reply_markup=position_keyboard())

# Main
async def main():
    logger.info("Бот запущен.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
