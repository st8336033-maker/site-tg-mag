import json, os, asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

URL = "http://127.0.0.1:5000"

class ShopStates(StatesGroup):
    add_name = State()
    add_price = State()
    add_cat = State()
    add_desc = State()
    add_sizes = State()
    add_images = State()
    delete_mode = State() # Стан для вибору товару на видалення

# --- КЛАВІАТУРИ ---

def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="➕ Додати товар"), KeyboardButton(text="🗑️ Видалити товар")]], 
        resize_keyboard=True
    )

def get_delete_kb():
    """Створює клавіатуру зі списком усіх товарів для видалення"""
    if not os.path.exists('products.json'):
        return None
    
    with open('products.json', 'r', encoding='utf-8') as f:
        products = json.load(f)
    
    if not products:
        return None

    # Створюємо кнопки з назвами товарів
    buttons = [[KeyboardButton(text=p['name'])] for p in products]
    buttons.append([KeyboardButton(text="❌ Скасувати")]) # Кнопка для відміни
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_cat_kb():
    cats = ["Верхній одяг", "Кофти", "Штани", "Аксесуари", "Взуття"]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=c)] for c in cats], resize_keyboard=True)

def get_sizes_kb():
    sizes = ["S", "M", "L", "XL", "Універсальний", "Вписати свій ✏️"]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=s)] for s in sizes], resize_keyboard=True)

# --- ХЕНДЛЕРИ ВИДАЛЕННЯ (КНОПКАМИ) ---

@dp.message(F.text == "🗑️ Видалити товар")
async def start_delete(m: Message, state: FSMContext):
    await state.clear()
    kb = get_delete_kb()
    
    if kb is None:
        return await m.answer("Список товарів порожній, нічого видаляти.", reply_markup=get_main_kb())
    
    await m.answer("Оберіть товар зі списку для видалення:", reply_markup=kb)
    await state.set_state(ShopStates.delete_mode)

@dp.message(ShopStates.delete_mode)
async def process_delete(m: Message, state: FSMContext):
    if m.text == "❌ Скасувати":
        await state.clear()
        return await m.answer("Видалення скасовано.", reply_markup=get_main_kb())

    name_to_delete = m.text
    with open('products.json', 'r', encoding='utf-8') as f:
        products = json.load(f)

    # Фільтруємо: залишаємо всі, крім обраного
    new_products = [p for p in products if p.get('name') != name_to_delete]

    with open('products.json', 'w', encoding='utf-8') as f:
        json.dump(new_products, f, ensure_ascii=False, indent=2)
    
    await m.answer(f"✅ Товар '{name_to_delete}' видалено з бази!", reply_markup=get_main_kb())
    await state.clear()

# --- ХЕНДЛЕРИ ДОДАВАННЯ ---

@dp.message(Command("start"))
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Менеджер магазину активований.", reply_markup=get_main_kb())

@dp.message(F.text == "➕ Додати товар")
async def start_add(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("1. Введіть назву товару:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ShopStates.add_name)

@dp.message(ShopStates.add_name)
async def add_n(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("2. Оберіть категорію:", reply_markup=get_cat_kb())
    await state.set_state(ShopStates.add_cat)

@dp.message(ShopStates.add_cat)
async def add_c(m: Message, state: FSMContext):
    await state.update_data(cat=m.text)
    await m.answer("3. Введіть ціну цифрами:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ShopStates.add_price)

@dp.message(ShopStates.add_price)
async def add_p(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return await m.answer("Будь ласка, введіть число!")
    await state.update_data(price=int(m.text))
    await m.answer("4. Введіть опис товару:")
    await state.set_state(ShopStates.add_desc)

@dp.message(ShopStates.add_desc)
async def add_d(m: Message, state: FSMContext):
    await state.update_data(desc=m.text)
    await m.answer("5. Оберіть розмір:", reply_markup=get_sizes_kb())
    await state.set_state(ShopStates.add_sizes)

@dp.message(ShopStates.add_sizes)
async def add_s(m: Message, state: FSMContext):
    if m.text == "Вписати свій ✏️":
        return await m.answer("Напишіть розмір вручну:")
    
    sizes = [s.strip() for s in m.text.replace("✏️", "").split(",")]
    await state.update_data(sizes=sizes)
    
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ ГОТОВО")]], resize_keyboard=True)
    await m.answer("6. Надсилайте фото. Потім натисніть ✅ ГОТОВО", reply_markup=kb)
    await state.set_state(ShopStates.add_images)

@dp.message(ShopStates.add_images, F.photo)
async def add_i(m: Message, state: FSMContext):
    data = await state.get_data()
    file = await bot.get_file(m.photo[-1].file_id)
    fname = f"{file.file_id}.jpg"
    path = 'static/uploads'
    if not os.path.exists(path): os.makedirs(path, exist_ok=True)
    await bot.download_file(file.file_path, f"{path}/{fname}")
    imgs = data.get('images', [])
    imgs.append(f"{URL}/static/uploads/{fname}")
    await state.update_data(images=imgs)
    await m.answer(f"📸 Додано фото ({len(imgs)})")

@dp.message(ShopStates.add_images, F.text == "✅ ГОТОВО")
async def add_f(m: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get('images'): return await m.answer("Додайте хоча б одне фото!")
    
    all_p = []
    if os.path.exists('products.json'):
        with open('products.json', 'r', encoding='utf-8') as f:
            all_p = json.load(f)
    
    all_p.append(data)
    with open('products.json', 'w', encoding='utf-8') as f:
        json.dump(all_p, f, ensure_ascii=False, indent=2)
        
    await m.answer("✅ Товар додано на сайт!", reply_markup=get_main_kb())
    await state.clear()

async def main():
    print("Бот запущений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())