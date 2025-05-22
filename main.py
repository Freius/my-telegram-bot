import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import API_TOKEN
from parsers.hh_parser import get_hh_vacancies
from analytics import analyze_vacancy

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

BANK_MAPPING = {
    "🏦 Альфа-Банк": "Альфа-Банк",
    "🏛 ВТБ": "ВТБ",
    "🌾 Россельхозбанк": "Россельхозбанк",
    "⛽ Газпромбанк": "Газпромбанк",
    "💳 Тинькофф": "Тинькофф"
}

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

DEFAULT_CITY = "Великий Новгород"
DEFAULT_CITY_ID = CITIES[DEFAULT_CITY]

POSITIONS = ["Менеджер", "Специалист", "Заместитель", "Руководитель", "Ввести вручную"]

SBER_BENCHMARK = {
    "salary_avg": 120000,
    "benefits": ["медицинская страховка", "обучение", "ДМС"],
    "tech_stack": ["Python", "SQL", "Kafka"]
}

user_data = {}

def format_salary(salary: dict) -> str:
    if not salary:
        return "Не указана"
    from_s = f"от {salary['from']}" if salary.get('from') else ""
    to_s = f"до {salary['to']}" if salary.get('to') else ""
    currency = salary.get('currency', '').upper()
    return f"{from_s} {to_s} {currency}".strip()

def generate_report(vacancies: list, bank_name: str, city: str) -> str:
    if not vacancies:
        return f"😕 В {city} не найдено вакансий для {bank_name}.\nПопробуйте изменить параметры поиска."
    
    report = [f"📊 Отчет по вакансиям {bank_name} ({city}):\n"]
    
    for i, vacancy in enumerate(vacancies[:5], 1):
        try:
            analyzed = analyze_vacancy(vacancy, SBER_BENCHMARK)
            salary = format_salary(vacancy.get('salary'))
            salary_comparison = ""
            if vacancy.get('salary') and vacancy['salary'].get('from'):
                diff = vacancy['salary']['from'] - SBER_BENCHMARK['salary_avg']
                if diff > 0:
                    salary_comparison = "(🔺)"
                elif diff < 0:
                    salary_comparison = "(🔻)"
                else:
                    salary_comparison = "(≈ как в Сбере)"
            
            report.append(
                f"\n{i}. 🏦 {analyzed.get('Название банка', vacancy.get('employer', {}).get('name', 'Не указано'))}\n"
                f"   📌 Должность: {vacancy.get('name', 'Не указана')}\n"
                f"   💰 Зарплата: {salary} {salary_comparison}\n"
                f"   ✔️ Преимущества: {analyzed.get('Преимущества', 'Нет')}\n"
                f"   🎁 Соцпакет: {analyzed.get('Соцпакет', 'см. в условиях')}\n"
                f"   💻 Технологичность: {analyzed.get('Технологичность', 'Средняя')}\n"
                f"   🔍 Сравнение с Сбером: {analyzed.get('Сравнение с Сбером', 'Нет данных')}\n"
                f"   🔗 Ссылка: {vacancy.get('alternate_url', 'нет')}"
            )
        except Exception as e:
            logger.error(f"Ошибка анализа вакансии: {e}")
            continue
    return "\n".join(report)

def get_city_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for city in CITIES.keys():
        builder.add(KeyboardButton(text=city))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_position_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for pos in POSITIONS:
        builder.add(KeyboardButton(text=pos))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_bank_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for name in BANK_MAPPING.keys():
        builder.add(KeyboardButton(text=name))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id] = {}
    await message.answer("Выберите город:", reply_markup=get_city_keyboard())

@dp.message(F.text.in_(CITIES.keys()))
async def city_chosen(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id]["city"] = message.text
    await message.answer(f"Выбран город: {message.text}\nТеперь выберите должность:", reply_markup=get_position_keyboard())

@dp.message(F.text.in_(POSITIONS))
async def position_chosen(message: types.Message):
    user_id = message.from_user.id
    if message.text == "Ввести вручную":
        await message.answer("Введите должность вручную:")
        user_data[user_id]["awaiting_custom_position"] = True
    else:
        user_data[user_id]["position"] = message.text
        await message.answer("Теперь выберите банк:", reply_markup=get_bank_keyboard())

@dp.message()
async def handle_input(message: types.Message):
    user_id = message.from_user.id

    if user_data.get(user_id, {}).get("awaiting_custom_position"):
        user_data[user_id]["position"] = message.text
        user_data[user_id].pop("awaiting_custom_position")
        await message.answer("Теперь выберите банк:", reply_markup=get_bank_keyboard())
        return

    if message.text in BANK_MAPPING:
        city = user_data.get(user_id, {}).get("city", DEFAULT_CITY)
        city_id = CITIES.get(city, DEFAULT_CITY_ID)
        position = user_data.get(user_id, {}).get("position", "")
        bank_name = BANK_MAPPING[message.text]

        await message.answer(f"🔍 Ищу вакансии {bank_name} в {city} по позиции '{position}'...")
        await bot.delete_webhook(drop_pending_updates=True)

        try:
            vacancies = get_hh_vacancies(bank_name, city_id)
            if position:
                vacancies = [v for v in vacancies if position.lower() in v.get('name', '').lower()]

            report = generate_report(vacancies, bank_name, city)
            await message.answer(report, reply_markup=get_bank_keyboard(), disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Ошибка при получении вакансий: {e}")
            await message.answer("⚠️ Произошла ошибка. Попробуйте позже.", reply_markup=get_city_keyboard())

async def main():
    logger.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
