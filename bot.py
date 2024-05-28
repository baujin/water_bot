import os
import csv
import random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode


class ConfirmOrderState(StatesGroup):
    name = State()
    phone = State()
    product_name = State()
    price = State()
    quantity = State()
    delivery = State()
    address = State()
    repeat_order = State()
    confirm_order = State()
    user_id = State()
    total_quantity = State()
    delivery_time = State()


TOKEN = '6997211828:AAFTSedi3YUYhf9P2HSHkUVNAx-jSEe4vEs'
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

product_lists = {}
selected_products = {}


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    welcome_message = f"Добро пожаловать!\n" \
                      f"Я могу помочь вам выбрать товар или услугу из нашего магазина." \
                      f"Нажмите на кнопку Заказать, чтобы начать."
    inline_markup = types.InlineKeyboardMarkup(row_width=2)
    catalog_button = types.InlineKeyboardButton(text="Заказать", callback_data='buy')
    repeat_order_button = types.InlineKeyboardButton(text="Повторить заказ", callback_data='repeat_order')
    button_text = f"Чат с оператором"
    button = types.InlineKeyboardButton(button_text, url=f"https://t.me/badmayd")
    inline_markup.add(catalog_button, repeat_order_button, button)
    await message.reply(welcome_message, reply_markup=inline_markup)


@dp.callback_query_handler(lambda c: c.data == 'buy')
async def start(callback_query: types.CallbackQuery):
    await send_groups_keyboard(callback_query.message.chat.id)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)


async def send_groups_keyboard(chat_id):
    files = os.listdir('csv_files')
    files.sort()
    keyboard = types.InlineKeyboardMarkup()
    for file in files:
        if file.endswith('.csv'):
            keyboard.add(types.InlineKeyboardButton(text=file[:-4], callback_data=file))
    keyboard.add(types.InlineKeyboardButton(text="Завершить", callback_data="finish"))
    await bot.send_message(chat_id, 'Выберите подходящий каталог:', reply_markup=keyboard)


async def update_groups_keyboard(chat_id, message_id):
    files = os.listdir('csv_files')
    files.sort()
    new_keyboard = types.InlineKeyboardMarkup()
    for file in files:
        if file.endswith('.csv'):
            new_keyboard.add(types.InlineKeyboardButton(text=file[:-4], callback_data=file))
    new_keyboard.add(types.InlineKeyboardButton(text="Завершить", callback_data="finish"))

    await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=new_keyboard)


@dp.callback_query_handler(lambda query: query.data.endswith('.csv') or query.data == 'finish')
async def process_callback(callback_query: types.CallbackQuery):
    if callback_query.data == 'finish':
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    else:
        file_name = callback_query.data
        file_path = os.path.join('csv_files', file_name)
        products = []
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            csvreader = csv.reader(csvfile)
            next(csvreader)
            products_list = []
            for idx, row in enumerate(csvreader):
                product_text = f"{row[1]}"
                products_list.append(product_text)
            product_lists[file_name] = products_list

            for idx, product_text in enumerate(products_list):
                order_callback = f'order_{file_name}_{idx}'
                products.append(
                    types.InlineKeyboardButton(text=product_text, callback_data=order_callback))

        back_button = types.InlineKeyboardButton(text="Назад", callback_data="back")
        finish_button = types.InlineKeyboardButton(text="Подтвердить", callback_data="finish_selection")
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(back_button, finish_button)
        keyboard.add(*products)
        await bot.edit_message_text(f'{file_name.split(".csv")[0]}:',
                                    chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    reply_markup=keyboard)


@dp.callback_query_handler(lambda query: query.data.startswith('order_'))
async def process_order_callback(callback_query: types.CallbackQuery, state: FSMContext):
    _, file_name, product_idx = callback_query.data.split('_')
    product_idx = int(product_idx)
    await state.update_data(product_idx=product_idx, file_name=file_name)
    await ConfirmOrderState.quantity.set()
    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    sent_message = await bot.send_message(chat_id=callback_query.message.chat.id, text="Введите количество:")
    await state.update_data(bot_message_id=sent_message.message_id)


@dp.message_handler(state=ConfirmOrderState.quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text)
        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0.")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное количество.")
        return

    data = await state.get_data()
    product_idx = data['product_idx']
    file_name = data['file_name']
    await add_to_cart(message.chat.id, product_idx, file_name, quantity, state)
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    await state.finish()


async def add_to_cart(chat_id, product_idx, file_name, quantity, state: FSMContext):
    file_path = os.path.join('csv_files', file_name)
    products_list = product_lists.get(file_name, [])
    if not products_list:
        return

    with open(file_path, 'r', encoding='utf-8') as csvfile:
        csvreader = csv.reader(csvfile)
        next(csvreader)
        for idx, row in enumerate(csvreader):
            if idx == product_idx:
                if len(row) < 3:
                    raise ValueError(f"Row does not contain enough values: {row}")
                product_name = row[1]
                price = row[2]
                if chat_id not in selected_products:
                    selected_products[chat_id] = []
                selected_products[chat_id].append((product_name, price, quantity))
                caption = f"Товар <b>{product_name}</b> в количестве <b>{quantity}</b> добавлен в корзину."
                finish_button = types.InlineKeyboardButton(text="Подтвердить", callback_data="finish_selection")
                markup = types.InlineKeyboardMarkup().add(finish_button)

                sent_message = await bot.send_message(chat_id=chat_id, text=caption, parse_mode='HTML', reply_markup=markup)

                async with state.proxy() as data:
                    if 'quantities' not in data:
                        data['quantities'] = []
                    data['quantities'].append(quantity)

                message_data = await state.get_data()
                bot_message_id = message_data.get('bot_message_id')
                if bot_message_id:
                    await bot.delete_message(chat_id=chat_id, message_id=bot_message_id)

                await state.update_data(bot_message_id=sent_message.message_id)

                break


@dp.callback_query_handler(lambda query: query.data == 'finish_selection')
async def finish_selection(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    await confirm_selection(callback_query.message.chat.id, callback_query.message.message_id, state)


async def confirm_selection(chat_id, message_id, state: FSMContext):
    if chat_id not in selected_products or not selected_products[chat_id]:
        await bot.send_message(chat_id, "Ваша корзина пуста.")
        return

    total_cost = 0
    total_quantity = 0
    product_details = ""
    for product_name, price, quantity in selected_products[chat_id]:
        product_details += f"{product_name} - {price} ₽ x {quantity}\n"
        total_cost += float(price) * quantity
        total_quantity += quantity

    caption = (f"Вы выбрали следующие товары:\n\n{product_details}\nОбщая стоимость: {total_cost} ₽\n"
               f"\nПодтвердите заказ или добавьте ещё товары.")

    confirm_button = types.InlineKeyboardButton(text="Оформить заказ", callback_data="confirm_order")
    add_more_button = types.InlineKeyboardButton(text="Добавить ещё", callback_data="buy")

    inline_markup = types.InlineKeyboardMarkup(row_width=2)
    inline_markup.add(confirm_button, add_more_button)

    async with state.proxy() as data:
        data['total_quantity'] = total_quantity
        data['total_cost'] = total_cost

    await bot.send_message(chat_id, caption, reply_markup=inline_markup)


@dp.callback_query_handler(lambda query: query.data == 'confirm_order')
async def confirm_order(callback_query: types.CallbackQuery, state: FSMContext):
    message = await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                          message_id=callback_query.message.message_id,
                                          text="Введите имя:")
    await ConfirmOrderState.name.set()
    await state.update_data(bot_message_id=message.message_id)


@dp.message_handler(state=ConfirmOrderState.name)
async def process_name_step(message: types.Message, state: FSMContext):
    name = message.text
    await state.update_data(name=name)
    message_data = await state.get_data()
    bot_message_id = message_data.get('bot_message_id')
    user_id = message.from_user.id
    await state.update_data(user_id=user_id)
    if bot_message_id:
        await bot.edit_message_text(chat_id=message.chat.id,
                                    message_id=bot_message_id,
                                    text="Введите номер телефона:")
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    await ConfirmOrderState.phone.set()


@dp.message_handler(state=ConfirmOrderState.phone)
async def process_phone_and_quantity_step(message: types.Message, state: FSMContext):
    phone = message.text
    if not phone.isdigit():
        message_data = await state.get_data()
        bot_message_id = message_data.get('bot_message_id')
        if bot_message_id:
            await bot.edit_message_text(chat_id=message.chat.id,
                                        message_id=bot_message_id,
                                        text="Пожалуйста, введите номер телефона, используя только цифры:")
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        return

    await state.update_data(phone=phone)
    data = await state.get_data()
    total_quantity = data.get('total_quantity')
    bot_message_id = data.get('bot_message_id')

    if total_quantity >= 3:  # Если количество товаров больше или равно трём
        delivery = "Центральный"
        await state.update_data(delivery=delivery)
        await ConfirmOrderState.address.set()
        text_message = "Введите полный адрес доставки:"
        if bot_message_id:
            await bot.edit_message_text(chat_id=message.chat.id, message_id=bot_message_id, text=text_message)
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    else:
        text_message = "Введите район доставки:"
        available_districts = (
            "Автодорожный",
            "Гагаринский",
            "Губинский",
            "Октябрьский",
            "Промышленный",
            "Сайсарский",
            "Строительный",
            "Центральный"
        )
        buttons = [InlineKeyboardButton(text=district, callback_data=district) for district in available_districts]
        keyboard = InlineKeyboardMarkup(row_width=2).add(*buttons)

        if bot_message_id:
            await bot.edit_message_text(chat_id=message.chat.id, message_id=bot_message_id, text=text_message, reply_markup=keyboard)
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        await ConfirmOrderState.delivery.set()


@dp.callback_query_handler(lambda c: c.data in ["Автодорожный", "Гагаринский", "Губинский", "Октябрьский", "Промышленный", "Сайсарский", "Строительный", "Центральный"], state=ConfirmOrderState.delivery)
async def process_delivery_step(callback_query: types.CallbackQuery, state: FSMContext):
    delivery = callback_query.data
    await state.update_data(delivery=delivery)
    message_data = await state.get_data()
    bot_message_id = message_data.get('bot_message_id')

    await ConfirmOrderState.address.set()
    text_message = "Введите полный адрес доставки:"
    if bot_message_id:
        await bot.edit_message_text(chat_id=callback_query.message.chat.id, message_id=bot_message_id, text=text_message)
        # await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await ConfirmOrderState.address.set()


@dp.message_handler(state=ConfirmOrderState.address)
async def process_address_step(message: types.Message, state: FSMContext):
    address = message.text
    await state.update_data(address=address)
    data = await state.get_data()
    bot_message_id = data.get('bot_message_id')
    text_message = "Выберите время доставки:"
    time_slots = ["8:00-12:00", "12:00-16:00", "16:00-20:00"]
    buttons = [InlineKeyboardButton(text=slot, callback_data=slot) for slot in time_slots]
    keyboard = InlineKeyboardMarkup(row_width=1).add(*buttons)

    await ConfirmOrderState.delivery_time.set()

    if bot_message_id:
        await bot.edit_message_text(chat_id=message.chat.id, message_id=bot_message_id, text=text_message, reply_markup=keyboard)
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)


@dp.callback_query_handler(lambda c: c.data in ["8:00-12:00", "12:00-16:00", "16:00-20:00"], state=ConfirmOrderState.delivery_time)
async def process_delivery_time_step(callback_query: types.CallbackQuery, state: FSMContext):
    delivery_time = callback_query.data
    await state.update_data(delivery_time=delivery_time)
    data = await state.get_data()
    bot_message_id = data.get('bot_message_id')

    await ConfirmOrderState.address.set()

    # Construct the final order details and save to CSV
    order_id = random.randint(100, 100000000)
    name = data['name']
    phone = data['phone']
    delivery = data.get('delivery', '')
    address = data['address']
    user_name = callback_query.from_user.username
    products_order = selected_products[callback_query.message.chat.id]
    delivery_cost = 0
    total_cost = 0
    total_quantity = 0
    order_details = []
    user_id = data['user_id']

    for product_name, price, quantity in products_order:
        order_details.append(f"{product_name} - {quantity} шт. - {float(price) * quantity} ₽")
        total_cost += float(price) * quantity
        total_quantity += quantity
        if total_quantity <= 3:
            if delivery == "Автодорожный":
                delivery_cost = 70
            elif delivery == "Гагаринский":
                delivery_cost = 70
            elif delivery == "Губинский":
                delivery_cost = 30
            elif delivery == "Октябрьский":
                delivery_cost = 30
            elif delivery == "Промышленный":
                delivery_cost = 60
            elif delivery == "Сайсарский":
                delivery_cost = 40
            elif delivery == "Строительный":
                delivery_cost = 50
    final_cost = total_cost if total_quantity >= 3 else delivery_cost + total_cost
    order_data = [order_id, name, phone, "; ".join(order_details), final_cost, delivery, address, delivery_time, user_name, user_id]

    with open('orders/orders.csv', 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(order_data)
    await state.finish()
    user_message = f"Заказ №{order_id} успешно оформлен на стоимость {final_cost} ₽ с учетом доставки в ваш район.\n" \
                   f"Время доставки: {delivery_time}\n" \
                   f"Ожидайте ответа менеджеров!"
    await bot.send_message(callback_query.from_user.id, user_message)
    manager_message = f"Получен новый заказ:\n\n" \
                      f"Номер заказа: {order_id}\n" \
                      f"Имя: {name}\n" \
                      f"Телефон: {phone}\n" \
                      f"Товары:\n" + "\n".join(order_details) + f"\n\n" \
                                                                f"Стоимость: {final_cost} ₽\n" \
                                                                f"Район доставки: {delivery}\n" \
                                                                f"Адрес: {address}\n" \
                                                                f"Время доставки: {delivery_time}"
    button_text = f"Написать"
    button = types.InlineKeyboardButton(button_text, url= f"tg://user?id={user_id}")
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(button)
    await bot.send_message(705963541, manager_message, reply_markup=keyboard)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
    selected_products.pop(callback_query.message.chat.id, None)


@dp.callback_query_handler(lambda query: query.data == 'back')
async def back_to_groups(callback_query: types.CallbackQuery):
    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    await send_groups_keyboard(callback_query.message.chat.id)


@dp.callback_query_handler(lambda c: c.data == 'repeat_order')
async def repeat_order(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
    repeat_order_message = await bot.send_message(callback_query.message.chat.id, "Введите номер заказа:")
    await ConfirmOrderState.repeat_order.set()
    await state.update_data(repeat_order_message_id=repeat_order_message.message_id)


@dp.message_handler(state=ConfirmOrderState.repeat_order)
async def process_repeat_order_step(message: types.Message, state: FSMContext):
    order_id = message.text
    repeat_order_message_id = (await state.get_data()).get('repeat_order_message_id')

    found_order = None
    with open('orders/orders.csv', 'r', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row and row[0] == order_id:
                found_order = row
                break

    if found_order:
        order_id, name, phone, product_name, cost, delivery, address, delivery_time, user_name, user_id = found_order
        new_order_id = random.randint(100, 100000000)

        with open('orders/orders.csv', 'a', newline='',  encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([new_order_id, name, phone, product_name, cost, delivery, address, delivery_time, user_name, user_id])

        await bot.edit_message_text(chat_id=message.chat.id, message_id=repeat_order_message_id,
                                    text=f"Заказ №{new_order_id} успешно оформлен на стоимость {cost} ₽, ожидайте ответа менеджеров!")
        await bot.delete_message(message.chat.id, message.message_id)

        manager_message = f"Получен новый заказ:\n\n" \
                          f"Номер заказа: {new_order_id}\n" \
                          f"Имя: {name}\n" \
                          f"Телефон: {phone}\n" \
                          f"Название продукта: {product_name}\n" \
                          f"Стоимость: {cost} ₽\n" \
                          f"Район доставки: {delivery}\n" \
                          f"Адрес: {address}"

        button_text = f"Написать"
        button = types.InlineKeyboardButton(button_text, url= f"tg://user?id={user_id}")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(button)

        await bot.send_message(705963541, manager_message, reply_markup=keyboard)
    else:
        keyboard = types.InlineKeyboardMarkup()
        repeat_order_button = types.InlineKeyboardButton(text="Повторить заказ", callback_data='repeat_order')
        keyboard.add(repeat_order_button)
        await bot.send_message(chat_id=message.chat.id, text=f"Заказ с номером {order_id} не найден.", reply_markup=keyboard)

    await state.finish()


@dp.message_handler(commands=['notify'])
async def notify_users(message: types.Message):
    if message.from_user.id != 705963541:
        await message.reply("Извините, у вас нет разрешения на выполнение этой команды.")
        return

    notification_text = message.text.replace('/notify', '').strip()
    if not notification_text:
        await message.reply("Вы не указали текст сообщения.")
        return

    user_ids = set()

    with open('orders/orders.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            user_id = row[9]
            user_ids.add(user_id)

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, notification_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")


@dp.message_handler(commands=['check'])
async def send_orders(message: types.Message):
    if message.from_user.id != 705963541:
        await message.reply("Извините, у вас нет разрешения на выполнение этой команды.")
        return
    orders_file = 'orders/orders.csv'
    try:
        await bot.send_document(message.from_user.id, types.InputFile(orders_file))
    except Exception as e:
        print(f"Не удалось отправить файл заказов пользователю {message.from_user.id}: {e}")


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
