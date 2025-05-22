import json
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import API_TOKEN
from parsers.hh_parser import get_hh_vacancies
from analytics import analyze_vacancy

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота с FSM
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# Константы
CITIES = {
    "Москва": 1,
    "Санкт-Петербург": 2,
    "Великий Новгород": 67,
    "Калининград": 41,
    "Архангельск": 14,
    "Вологда": 25,
    "Псков": 75,
    "Коми": 1041,
    "Карелия": 1077,
    "Лен. обл.": 145,
    "Мурманск": 64
}

POSITIONS = [
    "Все должности", 
    "Менеджер", 
    "Специалист", 
    "Заместитель", 
    "Руководитель",
    "Аналитик",
    "Кредитный специалист",
    "IT-специалист"
]

BANK_MAPPING = {
    "alfa": "Альфа-Банк",
    "vtb": "ВТБ", 
    "rshb": "Россельхозбанк",
    "gazprom": "Газпромбанк",
    "tinkoff": "Тинькофф",
    "raiffeisen": "Райффайзенбанк",
    "unicredit": "ЮниКредит Банк",
    "rosbank": "Росбанк"
}

# Расширенный бенчмарк Сбербанка
SBER_BENCHMARK = {
    "salary_ranges": {
        "Специалист": {"min": 80000, "max": 120000, "avg": 100000},
        "Менеджер": {"min": 100000, "max": 150000, "avg": 125000},
        "Руководитель": {"min": 150000, "max": 250000, "avg": 200000},
        "Аналитик": {"min": 90000, "max": 140000, "avg": 115000},
        "default": {"min": 70000, "max": 130000, "avg": 100000}
    },
    "benefits": [
        "ДМС премиум-класса",
        "корпоративное обучение",
        "льготное кредитование",
        "программа развития карьеры",
        "гибкий график работы",
        "корпоративные скидки",
        "дополнительные отпуска",
        "спортивные программы"
    ],
    "tech_stack": ["Python", "SQL", "Kafka", "Docker", "Kubernetes", "Java", "React"],
    "corporate_values": [
        "стабильность крупнейшего банка России",
        "возможности для профессионального роста", 
        "сильная корпоративная культура",
        "передовые технологии",
        "социальная ответственность"
    ]
}

# FSM состояния
class BotStates(StatesGroup):
    waiting_manual_position = State()
    waiting_feedback = State()

# Класс для хранения данных пользователя
class UserSession:
    def __init__(self):
        self.city: Optional[str] = None
        self.city_id: Optional[int] = None
        self.position: Optional[str] = None
        self.bank: Optional[str] = None
        self.search_history: List[Dict] = []
        self.created_at = datetime.now()

# Хранилище сессий пользователей
user_sessions: Dict[int, UserSession] = {}

def get_user_session(user_id: int) -> UserSession:
    """Получить или создать сессию пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession()
    return user_sessions[user_id]

# Клавиатуры
def city_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора города"""
    buttons = []
    cities_list = list(CITIES.keys())
    
    # Группируем города по 2 в ряд
    for i in range(0, len(cities_list), 2):
        row = []
        for j in range(2):
            if i + j < len(cities_list):
                city = cities_list[i + j]
                row.append(InlineKeyboardButton(
                    text=city, 
                    callback_data=f"city:{city}"
                ))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="↩️ В начало", callback_data="start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def position_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора должности"""
    buttons = []
    for pos in POSITIONS:
        buttons.append([InlineKeyboardButton(text=pos, callback_data=f"pos:{pos}")])
    
    buttons.extend([
        [InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="pos:manual")],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back:city"),
            InlineKeyboardButton(text="↩️ В начало", callback_data="start")
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def bank_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора банка"""
    buttons = []
    banks_list = list(BANK_MAPPING.items())
    
    # Группируем банки по 2 в ряд
    for i in range(0, len(banks_list), 2):
        row = []
        for j in range(2):
            if i + j < len(banks_list):
                key, name = banks_list[i + j]
                row.append(InlineKeyboardButton(
                    text=name, 
                    callback_data=f"bank:{key}"
                ))
        buttons.append(row)
    
    buttons.extend([
        [InlineKeyboardButton(text="🔍 Сравнить все банки", callback_data="bank:all")],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back:position"),
            InlineKeyboardButton(text="↩️ В начало", callback_data="start")
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def action_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с дополнительными действиями"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Новый поиск", callback_data="start"),
            InlineKeyboardButton(text="📊 История поиска", callback_data="history")
        ],
        [InlineKeyboardButton(text="💬 Оставить отзыв", callback_data="feedback")]
    ])

def back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Простая клавиатура возврата в главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ В начало", callback_data="start")]
    ])

# Утилиты
def format_salary(salary: Optional[Dict]) -> Tuple[str, int]:
    """Форматировать зарплату и вернуть среднее значение"""
    if not salary:
        return "Не указана", 0
    
    from_val = salary.get('from', 0) or 0
    to_val = salary.get('to', 0) or 0
    currency = salary.get('currency', 'RUR').upper()
    
    if from_val and to_val:
        avg = (from_val + to_val) // 2
        return f"от {from_val:,} до {to_val:,} {currency}", avg
    elif from_val:
        return f"от {from_val:,} {currency}", from_val
    elif to_val:
        return f"до {to_val:,} {currency}", to_val
    else:
        return "Не указана", 0

def get_sber_benchmark_for_position(position: str) -> Dict:
    """Получить бенчмарк Сбербанка для конкретной должности"""
    position_key = None
    if position:
        for key in SBER_BENCHMARK["salary_ranges"]:
            if key.lower() in position.lower():
                position_key = key
                break
    
    return SBER_BENCHMARK["salary_ranges"].get(position_key, 
                                               SBER_BENCHMARK["salary_ranges"]["default"])

def analyze_market_position(vacancies: List[Dict], position: str) -> Dict:
    """Анализ рыночной позиции"""
    if not vacancies:
        return {}
    
    salaries = []
    for v in vacancies:
        _, avg_salary = format_salary(v.get('salary'))
        if avg_salary > 0:
            salaries.append(avg_salary)
    
    if not salaries:
        return {"message": "Недостаточно данных о зарплатах"}
    
    market_avg = sum(salaries) // len(salaries)
    market_min = min(salaries)
    market_max = max(salaries)
    
    sber_benchmark = get_sber_benchmark_for_position(position)
    sber_avg = sber_benchmark["avg"]
    
    return {
        "market_avg": market_avg,
        "market_min": market_min,
        "market_max": market_max,
        "sber_avg": sber_avg,
        "sber_vs_market": sber_avg - market_avg,
        "sber_position": "выше" if sber_avg > market_avg else "ниже" if sber_avg < market_avg else "на уровне"
    }

def generate_ceo_response(vacancy: Dict, market_analysis: Dict, position: str) -> str:
    """Генерировать персонализированный ответ от лица руководителя Сбербанка"""
    employer_name = vacancy.get('employer', {}).get('name', 'банк-конкурент')
    vacancy_name = vacancy.get('name', 'данная позиция')
    
    _, vacancy_salary = format_salary(vacancy.get('salary'))
    sber_benchmark = get_sber_benchmark_for_position(position)
    sber_avg = sber_benchmark["avg"]
    
    # Базовые аргументы
    base_arguments = [
        f"🏛️ Сбербанк — крупнейший банк России с 180-летней историей стабильности",
        f"📈 Мы инвестируем в развитие сотрудников больше любого другого банка",
        f"🎯 У нас четкая система карьерного роста и KPI",
        f"🛡️ Социальный пакет Сбербанка признан лучшим в отрасли"
    ]
    
    # Аргументы по зарплате
    salary_arguments = []
    if vacancy_salary > 0:
        salary_diff = vacancy_salary - sber_avg
        if salary_diff > 10000:
            salary_arguments.extend([
                f"💰 Готов обсудить повышение вашей зарплаты на {min(salary_diff, 30000):,} рублей",
                f"🎁 Плюс бонусная программа может добавить до 20% к окладу"
            ])
        elif salary_diff > 0:
            salary_arguments.append(f"💰 Наша зарплата уже конкурентоспособна, плюс стабильные выплаты")
        else:
            salary_arguments.append(f"💰 Наше предложение уже превышает рынок на {abs(salary_diff):,} рублей")
    
    # Аргументы по развитию
    development_arguments = [
        f"🎓 Корпоративный университет Сбербанка — возможности развития мирового уровня",
        f"🌍 Международные стажировки и обмен опытом",
        f"🤖 Работа с cutting-edge технологиями: AI, blockchain, big data"
    ]
    
    # Специфичные аргументы для разных банков
    competitor_arguments = []
    employer_lower = employer_name.lower()
    if "альфа" in employer_lower:
        competitor_arguments.append("🔒 В отличие от частных банков, у нас госгарантии стабильности")
    elif "втб" in employer_lower:
        competitor_arguments.append("📊 Мы лидеры в digital-трансформации банковского сектора")
    elif "тинькофф" in employer_lower:
        competitor_arguments.append("🏢 У нас больше возможностей для карьеры в офлайн-сегменте")
    
    # Объединяем аргументы
    all_arguments = base_arguments + salary_arguments + development_arguments + competitor_arguments
    selected_args = random.sample(all_arguments, min(4, len(all_arguments)))
    
    # Формируем ответ
    response_parts = [
        f"👋 Коллега, понимаю ваш интерес к позиции '{vacancy_name}' в {employer_name}.",
        f"",
        f"Но позвольте представить контраргументы:",
        ""
    ]
    
    for i, arg in enumerate(selected_args, 1):
        response_parts.append(f"{i}. {arg}")
    
    response_parts.extend([
        "",
        f"💼 Предлагаю встретиться на этой неделе для обсуждения ваших карьерных планов.",
        f"Уверен, мы найдем решение, которое превзойдет любые внешние предложения!",
        "",
        f"С уважением,",
        f"Руководство Сбербанка 🏛️"
    ])
    
    return "\n".join(response_parts)

def generate_detailed_report(vacancies: List[Dict], bank_name: str, city: str, position: str) -> str:
    """Генерировать детальный отчет по вакансиям"""
    if not vacancies:
        return f"😕 В городе {city} не найдено вакансий {bank_name}" + \
               (f" по позиции '{position}'" if position else "") + \
               ".\n\n🔍 Попробуйте:\n• Изменить город\n• Выбрать другую должность\n• Поискать в соседних регионах"
    
    # Анализ рынка
    market_analysis = analyze_market_position(vacancies, position)
    
    report_parts = [
        f"📊 **Аналитический отчет: {bank_name}**",
        f"🏙️ Город: {city}",
        f"👔 Позиция: {position or 'Все должности'}",
        f"📅 Дата анализа: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        f"",
        f"📈 **Рыночная аналитика:**"
    ]
    
    if market_analysis and "message" not in market_analysis:
        sber_position = market_analysis["sber_position"]
        diff = abs(market_analysis["sber_vs_market"])
        report_parts.extend([
            f"• Средняя зарплата на рынке: {market_analysis['market_avg']:,} руб.",
            f"• Вилка: от {market_analysis['market_min']:,} до {market_analysis['market_max']:,} руб.",
            f"• Позиция Сбербанка: {sber_position} рынка на {diff:,} руб.",
            f""
        ])
    
    report_parts.append(f"💼 **Найденные вакансии ({len(vacancies)}):**")
    report_parts.append("")
    
    # Показываем до 7 вакансий
    for i, vacancy in enumerate(vacancies[:7], 1):
        try:
            employer = vacancy.get('employer', {}).get('name', 'Неизвестно')
            name = vacancy.get('name', 'Без названия')
            salary_str, salary_avg = format_salary(vacancy.get('salary'))
            url = vacancy.get('alternate_url', '')
            
            # Сравнение с Сбербанком
            sber_benchmark = get_sber_benchmark_for_position(position)
            if salary_avg > 0:
                diff = salary_avg - sber_benchmark["avg"]
                if diff > 5000:
                    salary_comparison = f"(🔺 на {diff:,} выше Сбера)"
                elif diff < -5000:
                    salary_comparison = f"(🔻 на {abs(diff):,} ниже Сбера)"
                else:
                    salary_comparison = "(≈ на уровне Сбера)"
            else:
                salary_comparison = ""
            
            report_parts.extend([
                f"**{i}. {employer}**",
                f"   📌 {name}",
                f"   💰 {salary_str} {salary_comparison}",
                f"   🔗 [Открыть вакансию]({url})" if url else "   🔗 Ссылка недоступна",
                ""
            ])
            
            # Добавляем комментарий руководителя для интересных вакансий
            if (salary_avg > sber_benchmark["avg"] + 10000 or 
                random.random() < 0.3):  # 30% шанс для любой вакансии
                
                ceo_response = generate_ceo_response(vacancy, market_analysis, position)
                report_parts.extend([
                    "   📢 **Комментарий руководства Сбербанка:**",
                    "",
                    "   " + ceo_response.replace("\n", "\n   "),
                    "",
                    "   " + "─" * 50,
                    ""
                ])
                
        except Exception as e:
            logger.error(f"Ошибка при обработке вакансии: {e}")
            continue
    
    if len(vacancies) > 7:
        report_parts.append(f"... и еще {len(vacancies) - 7} вакансий")
    
    return "\n".join(report_parts)

def save_search_to_history(user_id: int, city: str, position: str, bank: str, results_count: int):
    """Сохранить поиск в историю пользователя"""
    session = get_user_session(user_id)
    search_record = {
        "timestamp": datetime.now().isoformat(),
        "city": city,
        "position": position,
        "bank": bank,
        "results_count": results_count
    }
    session.search_history.append(search_record)
    
    # Ограничиваем историю последними 10 поисками
    if len(session.search_history) > 10:
        session.search_history = session.search_history[-10:]

def format_search_history(user_id: int) -> str:
    """Форматировать историю поиска пользователя"""
    session = get_user_session(user_id)
    if not session.search_history:
        return "📝 История поиска пуста"
    
    history_parts = ["📚 **Ваша история поиска:**", ""]
    
    for i, record in enumerate(reversed(session.search_history[-5:]), 1):
        timestamp = datetime.fromisoformat(record["timestamp"])
        formatted_time = timestamp.strftime("%d.%m %H:%M")
        
        history_parts.append(
            f"{i}. **{formatted_time}** - {record['bank']} в {record['city']}\n"
            f"   Позиция: {record['position'] or 'Все'} | Найдено: {record['results_count']} вак."
        )
    
    return "\n".join(history_parts)

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда /start - начало работы с ботом"""
    user_id = message.from_user.id
    session = get_user_session(user_id)
    session.__init__()  # Сброс сессии
    
    welcome_text = (
        "🏛️ **Добро пожаловать в HR-аналитику Сбербанка!**\n\n"
        "Я помогу проанализировать вакансии банков-конкурентов и подготовить "
        "аргументы для удержания ценных сотрудников.\n\n"
        "📊 Что я умею:\n"
        "• Анализировать вакансии по городам и должностям\n"
        "• Сравнивать с условиями Сбербанка\n"
        "• Генерировать персонализированные ответы руководства\n"
        "• Проводить рыночную аналитику\n\n"
        "🎯 Для начала выберите город:"
    )
    
    await message.answer(welcome_text, reply_markup=city_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "start")
async def restart(query: CallbackQuery):
    """Перезапуск бота через кнопку"""
    user_id = query.from_user.id
    session = get_user_session(user_id)
    session.__init__()
    
    await query.message.edit_text(
        "🎯 Выберите город для анализа вакансий:",
        reply_markup=city_keyboard()
    )

@dp.callback_query(F.data.startswith("city:"))
async def choose_city(query: CallbackQuery):
    """Выбор города"""
    user_id = query.from_user.id
    city = query.data.split(":", 1)[1]
    
    session = get_user_session(user_id)
    session.city = city
    session.city_id = CITIES.get(city)
    
    await query.message.edit_text(
        f"🏙️ Выбран город: **{city}**\n\n"
        f"👔 Теперь выберите должность для анализа:",
        reply_markup=position_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("pos:"))
async def choose_position(query: CallbackQuery, state: FSMContext):
    """Выбор должности"""
    user_id = query.from_user.id
    pos = query.data.split(":", 1)[1]
    
    if pos == "manual":
        await state.set_state(BotStates.waiting_manual_position)
        await query.message.edit_text(
            "✍️ Введите название должности вручную:\n\n"
            "Например: 'Кредитный аналитик', 'Senior Java Developer', 'Менеджер по продажам'"
        )
    else:
        session = get_user_session(user_id)
        session.position = None if pos == "Все должности" else pos
        
        position_text = pos if pos != "Все должности" else "все должности"
        await query.message.edit_text(
            f"👔 Выбрана позиция: **{position_text}**\n\n"
            f"🏦 Теперь выберите банк для анализа:",
            reply_markup=bank_keyboard(),
            parse_mode="Markdown"
        )

@dp.message(BotStates.waiting_manual_position)
async def manual_position(message: types.Message, state: FSMContext):
    """Обработка ручного ввода должности"""
    user_id = message.from_user.id
    position = message.text.strip()
    
    if len(position) < 2:
        await message.answer("⚠️ Название должности слишком короткое. Попробуйте еще раз:")
        return
    
    session = get_user_session(user_id)
    session.position = position
    
    await state.clear()
    await message.answer(
        f"👔 Указана позиция: **{position}**\n\n"
        f"🏦 Теперь выберите банк для анализа:",
        reply_markup=bank_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("bank:"))
async def choose_bank(query: CallbackQuery):
    """Выбор банка и запуск анализа"""
    user_id = query.from_user.id
    bank_key = query.data.split(":", 1)[1]
    
    session = get_user_session(user_id)
    
    if bank_key == "all":
        # Анализ всех банков
        await query.message.edit_text(
            f"🔍 **Запускаю сравнительный анализ всех банков...**\n\n"
            f"📍 Город: {session.city}\n"
            f"👔 Должность: {session.position or 'Все должности'}\n\n"
            f"⏳ Это может занять некоторое время..."
        )
        
        all_results = []
        for bank_key, bank_name in BANK_MAPPING.items():
            try:
                vacancies = get_hh_vacancies(bank_name, session.city_id)
                if session.position:
                    vacancies = [v for v in vacancies 
                               if session.position.lower() in v.get('name', '').lower()]
                all_results.extend([(bank_name, v) for v in vacancies])
            except Exception as e:
                logger.error(f"Ошибка при поиске вакансий {bank_name}: {e}")
        
        if all_results:
            # Группируем по банкам и создаем сводный отчет
            bank_summary = {}
            for bank_name, vacancy in all_results:
                if bank_name not in bank_summary:
                    bank_summary[bank_name] = []
                bank_summary[bank_name].append(vacancy)
            
            summary_parts = [
                f"📊 **Сводный анализ по всем банкам**",
                f"🏙️ Город: {session.city}",
                f"👔 Позиция: {session.position or 'Все должности'}",
                f""
            ]
            
            for bank_name, vacancies in bank_summary.items():
                market_analysis = analyze_market_position(vacancies, session.position)
                avg_salary = market_analysis.get('market_avg', 0) if market_analysis else 0
                
                summary_parts.append(
                    f"🏦 **{bank_name}**: {len(vacancies)} вак., "
                    f"средняя ЗП: {avg_salary:,} руб." if avg_salary > 0 else f"{len(vacancies)} вакансий"
                )
            
            await query.message.edit_text(
                "\n".join(summary_parts),
                reply_markup=action_keyboard(),
                parse_mode="Markdown"
            )
            
            save_search_to_history(user_id, session.city, session.position, "Все банки", len(all_results))
        else:
            await query.message.edit_text(
                "😕 Не найдено вакансий по указанным критериям во всех банках.",
                reply_markup=action_keyboard()
            )
    else:
        # Анализ конкретного банка
        bank_name = BANK_MAPPING.get(bank_key)
        session.bank = bank_name
        
        await query.message.edit_text(
            f"🔍 **Анализирую вакансии {bank_name}...**\n\n"
            f"📍 Город: {session.city}\n"
            f"👔 Должность: {session.position or 'Все должности'}\n\n"
            f"⏳ Получаю данные с HeadHunter..."
        )
        
        try:
            vacancies = get_hh_vacancies(bank_name, session.city_id)
            if session.position:
                vacancies = [v for v in vacancies 
                           if session.position.lower() in v.get('name', '').lower()]