from aiogram import types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from app.states import Register
from aiogram_calendar import SimpleCalendar, get_user_locale
from datetime import datetime, time
from app.data_shops import shops
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

router_time = Router()


# 10VhScErSS7c5fHTZKx5C8Bh6J1kdxSaxn0cpBFbokb8   ID файла Google
load_dotenv('token.env')  # Загружаем переменные окружения из .env файла
# Название файла для хранения данных
filename = "work_log.csv"
GOOGLE_KEY = os.getenv('GOOGLE_SHEET_KEY')

# Настройка доступа к Google Sheets


# def connect_to_google_sheets():
#     scope = ["https://spreadsheets.google.com/feeds",
#              "https://www.googleapis.com/auth/drive"]
#     creds = ServiceAccountCredentials.from_json_keyfile_name(
#         "json/credentials.json", scope)
#     client = gspread.authorize(creds)
#     return client

def connect_to_google_sheets():
    """Подключается к Google Sheets API через OAuth"""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
              'https://www.googleapis.com/auth/drive']
    
    creds = None
    token_path = 'token.json'
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'json/OAUTH.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    return gspread.authorize(creds)


def loads_machines_data():
    if os.path.exists('json/machines_data.json'):
        with open('json/machines_data.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    else:
        return {
            "maschines_1": [],
            "maschines_2": [],
            "maschines_3": [],
            "maschines_11": [],
            "maschines_15": [],
            "maschines_17": [],
            "maschines_20": [],
            "maschines_26": [],
            "maschines_kmt": [],
        }


def save_data_to_google_sheets(work_data):
    client = connect_to_google_sheets()
    sheet = client.open_by_key(GOOGLE_KEY).sheet1

    # Новый порядок заголовков
    headers = ["Дата", "Исполнители", "Описание проблемы", "Решение", "Статус неисправности", "Начало работ", "Окончание работ",
               "Затраченное время", "Цех", "Станок", "Инвентарный номер"]

    # Проверяем, есть ли заголовки (если таблица пустая, добавляем их)
    existing_data = sheet.get_all_values()
    if not existing_data:
        sheet.append_row(headers)

    # Добавляем данные в соответствии с новым порядком
    new_data = [
        work_data["date"], work_data["workers"], work_data["description"], work_data["solution"], work_data["fault_status"],
        work_data["start"], work_data["end"], work_data["duration"],
        work_data["shop"], work_data["machine"], work_data.get(
            "inventory_number", "Нет данных")
    ]

    sheet.append_row(new_data)
    print("✅ Данные сохранены в Google Таблицу")



# Функция для создания клавиатуры с цифрами 0-9
def number_keyboard(stage):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=str(i), callback_data=f"{stage}_{i}") for i in range(1, 4)],
        [InlineKeyboardButton(
            text=str(i), callback_data=f"{stage}_{i}") for i in range(4, 7)],
        [InlineKeyboardButton(
            text=str(i), callback_data=f"{stage}_{i}") for i in range(7, 10)],
        [InlineKeyboardButton(text="0", callback_data=f"{stage}_0")],
        [InlineKeyboardButton(text="⬅️ Удалить", callback_data=f"{stage}_del"),
         InlineKeyboardButton(text="✅ Готово", callback_data=f"{stage}_done")],
        [InlineKeyboardButton(
            text="↩️ Назад", callback_data="back_from_time")]
    ])
    return kb


@router_time.callback_query(F.data == 'back_from_time')
async def back_time(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == Register.time_start.state:
        await callback.message.edit_text(
            "Пожалуйста выберите дату начала работ: ",
            reply_markup=await SimpleCalendar(
                locale=await get_user_locale(callback.from_user)).start_calendar())
        await state.set_state(Register.date_start)
    elif current_state == Register.confirm_time:
        await start_cmd(callback.message, state)
        await state.set_state(Register.time_start)


@router_time.message(Register.date_to_time)
async def start_cmd(message: Message, state: FSMContext):
    data = await state.get_data()
    # ✅ Храним данные в FSMContext
    selected_date_start = data.get("selected_date_start")
    selected_date_end = data.get("selected_date_end")
    await state.update_data(hours_start="", minutes_start="")
    await message.edit_text(f"Начало: {selected_date_start.date().strftime('%d.%m.%Y')} Конец: {selected_date_end.date().strftime('%d.%m.%Y')}\n"
                            f"Введите часы начала работ (00-23):",
                            reply_markup=number_keyboard("hourstart"))
    await state.set_state(Register.time_start)


# Ввод часов начала работ
# @router_time.callback_query(F.data.startswith('hourstart_'))
# async def enter_hours_start(callback: types.CallbackQuery, state: FSMContext):
#     action = callback.data.split("_")[1]
#     data = await state.get_data()  # ✅ Получаем данные из FSMContext
#     hours_start = data.get("hours_start", "")

#     if len(hours_start) >= 2 and action not in ["del", "done"]:
#         await callback.answer("Вы не можете ввести более 2 символов для часов!")
#         return
#     if action == "del":
#         if hours_start:
#             hours_start = hours_start[:-1]
#     elif action == "done":
#         if hours_start == "" or int(hours_start) > 23:
#             await callback.answer("Введите корректные часы (00-23)!")
#             return
#         # ✅ Сохраняем в FSMContext
#         await state.update_data(hours_start=hours_start)
#         await callback.message.edit_text(f"Вы выбрали {hours_start} часов. Теперь введите минуты (00-59):",
#                                          reply_markup=number_keyboard("minutestart"))
#         return
#     else:
#         if len(hours_start) < 2:
#             hours_start += action

#     # ✅ Обновляем данные в FSMContext
#     await state.update_data(hours_start=hours_start)
#     await callback.message.edit_text(f"Часы: {hours_start}", reply_markup=number_keyboard("hourstart"))

@router_time.callback_query(F.data.startswith('hourstart_'))
async def enter_hours_start(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    data = await state.get_data()
    hours_start = data.get("hours_start", "")

    if len(hours_start) >= 2 and action not in ["del", "done"]:
        await callback.answer("Вы не можете ввести более 2 символов для часов!")
        return

    if action == "del":
        hours_start = hours_start[:-1]
    elif action == "done":
        if hours_start == "" or int(hours_start) > 23:
            await callback.answer("Введите корректные часы (00-23)!")
            return
        # Минуты = 00
        await state.update_data(hours_start=hours_start, minutes_start="00")
        await callback.message.edit_text(
            f"Вы выбрали {hours_start}:00. Теперь введите часы окончания работ (00-23):",
            reply_markup=number_keyboard("hourend")
        )
        await state.set_state(Register.time_end)
        return
    else:
        if len(hours_start) < 2:
            hours_start += action

    await state.update_data(hours_start=hours_start)
    await callback.message.edit_text(f"Часы начала: {hours_start}", reply_markup=number_keyboard("hourstart"))

# Ввод минут начала работ
# @router_time.callback_query(F.data.startswith('minutestart_'))
# async def enter_minutes_start(callback: types.CallbackQuery, state: FSMContext):
#     action = callback.data.split("_")[1]
#     data = await state.get_data()  # ✅ Получаем данные из FSMContext
#     minutes_start = data.get("minutes_start", "")

#     if len(minutes_start) >= 2 and action not in ["del", "done"]:
#         await callback.answer("Вы не можете ввести более 2 символов для минут!")
#         return
#     if action == "del":
#         if minutes_start:
#             minutes_start = minutes_start[:-1]
#     elif action == "done":
#         if minutes_start == "" or int(minutes_start) > 59:
#             await callback.answer("Введите корректные минуты (00-59)!")
#             return
#         await state.set_state(Register.time_end)
#         await end_time_func(callback, state)
#         return
#     else:
#         if len(minutes_start) < 2:
#             minutes_start += action
#     # ✅ Обновляем данные в FSMContext
#     await state.update_data(minutes_start=minutes_start)
#     await callback.message.edit_text(f"Минуты: {minutes_start}", reply_markup=number_keyboard("minutestart"))


# @router_time.callback_query(StateFilter(Register.time_end))
# async def end_time_func(callback: CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     # ✅ Храним данные в FSMContext
#     await state.update_data(hours_end="", minutes_end="")
#     await callback.message.edit_text(f"Начало: {datetime.combine(data.get('selected_date_start').date(), time(int(data.get('hours_start')), int(data.get('minutes_start')))).strftime('%d.%m.%Y %H:%M')} Конец: {data.get('selected_date_end').date().strftime('%d.%m.%Y')}\n"
#                                      f"Введите часы окончания работ (00-23):",
#                                      reply_markup=number_keyboard("hourend"))
#     await state.set_state(Register.confirm_time)


# Ввод часов окончания работ
# @router_time.callback_query(F.data.startswith('hourend_'))
# async def enter_hours_end(callback: types.CallbackQuery, state: FSMContext):
#     action = callback.data.split("_")[1]
#     data = await state.get_data()  # ✅ Получаем данные из FSMContext
#     hours_end = data.get("hours_end", "")
#     hours_start = data.get('hours_start', '00')

#     if len(hours_end) >= 2 and action not in ["del", "done"]:
#         await callback.answer("Вы не можете ввести более 2 символов для часов!")
#         return
#     if action == "del":
#         if hours_end:
#             hours_end = hours_end[:-1]
#     elif action == "done":
#         if hours_end == "" or int(hours_end) > 23:
#             await callback.answer("Введите корректные часы (00-23)!")
#             return
#         if data.get("selected_date_start").date() == data.get("selected_date_end").date():
#             if int(hours_end) < int(hours_start):
#                 await callback.answer(
#                     f"Неверный ввод (часы начала: {hours_start})")
#                 return
#         # ✅ Сохраняем в FSMContext
#         await state.update_data(hours_end=hours_end)
#         await callback.message.edit_text(f"Вы выбрали {hours_end} часов. Теперь введите минуты (00-59):",
#                                          reply_markup=number_keyboard("minuteend"))
#         return
#     else:
#         if len(hours_end) < 2:
#             hours_end += action

#     # ✅ Обновляем данные в FSMContext
#     await state.update_data(hours_end=hours_end)
#     await callback.message.edit_text(f"Часы: {hours_end}",
#                                      reply_markup=number_keyboard("hourend"))


# Вспомогательная функция для кнопок подтверждения/отмены
def confirm_cancel_keyboard(confirm_data, cancel_data):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data)
        ]
    ])


@router_time.callback_query(F.data.startswith('hourend_'))
async def enter_hours_end(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    data = await state.get_data()
    hours_end = data.get("hours_end", "")
    hours_start = data.get('hours_start', '00')

    if len(hours_end) >= 2 and action not in ["del", "done"]:
        await callback.answer("Вы не можете ввести более 2 символов для часов!")
        return

    if action == "del":
        hours_end = hours_end[:-1]
    elif action == "done":
        if hours_end == "" or int(hours_end) > 23:
            await callback.answer("Введите корректные часы (00-23)!")
            return
        if int(hours_end) < int(hours_start) and data.get("selected_date_start").date() == data.get("selected_date_end").date():
            await callback.answer(f"Часы окончания не могут быть меньше часов начала ({hours_start})!")
            return

        # Минуты = 00
        await state.update_data(hours_end=hours_end, minutes_end="00")
        await callback.message.edit_text("Введите исполнителей работ")
        await state.set_state(Register.personal)
        return
    else:
        if len(hours_end) < 2:
            hours_end += action

    await state.update_data(hours_end=hours_end)
    await callback.message.edit_text(f"Часы окончания: {hours_end}", reply_markup=number_keyboard("hourend"))

# ввод минут окончания работ
# @router_time.callback_query(F.data.startswith('minuteend_'))
# async def enter_minutes_end(callback: types.CallbackQuery, state: FSMContext):
#     action = callback.data.split("_")[1]
#     data = await state.get_data()  # ✅ Получаем данные из FSMContext
#     minutes_end = data.get("minutes_end", "")
#     selected_date_start = data.get("selected_date_start")  # datetime
#     selected_date_end = data.get("selected_date_end")  # datetime
#     hours_start = data.get('hours_start', '00')
#     hours_end = data.get("hours_end", "")
#     minutes_start = data.get('minutes_start', '00')

#     if len(minutes_end) >= 2 and action not in ["del", "done"]:
#         await callback.answer("Вы не можете ввести более 2 символов для минут!")
#         return

#     if action == "del":
#         if minutes_end:
#             minutes_end = minutes_end[:-1]
#     elif action == "done":
#         if minutes_end == "" or int(minutes_end) > 59:
#             await callback.answer("Введите корректные минуты (00-59)!")
#             return
#         if selected_date_start.date() == selected_date_end.date():
#             if int(hours_start) == int(hours_end):
#                 if int(minutes_end) <= int(minutes_start):
#                     await callback.answer(
#                         f"Неверный ввод (минуты начала: {minutes_start})")
#                     return
#         await callback.message.edit_text('Введите исполнителей работ')
#         await state.set_state(Register.personal)
#         return
#     else:
#         if len(minutes_end) < 2:
#             minutes_end += action
#     # ✅ Обновляем данные в FSMContext
#     await state.update_data(minutes_end=minutes_end)
#     await callback.message.edit_text(f"Минуты: {minutes_end}",
#                                      reply_markup=number_keyboard("minuteend"))


# Шаг 1: Ввод исполнителей работ
@router_time.message(Register.personal)
async def save_workers(message: Message, state: FSMContext):
    workers_input = message.text.strip()
    if not workers_input:
        await message.answer("Пожалуйста, введите хотя бы одного исполнителя.")
        return
    workers_list = [w.strip() for w in workers_input.split(',')]
    await state.update_data(workers=workers_list)

    # Показываем кнопки подтверждения/отмены
    keyboard = confirm_cancel_keyboard("confirm_workers", "cancel_workers")
    await message.answer(f"Исполнители: {', '.join(workers_list)}\nСохранить?", reply_markup=keyboard)


@router_time.callback_query(F.data == "confirm_workers")
async def confirm_workers(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()  # удаляем кнопки
    await callback.message.answer("Опишите проблему.")
    await state.set_state(Register.working)


@router_time.callback_query(F.data == "cancel_workers")
async def cancel_workers(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Введите исполнителей работ:")
    await state.set_state(Register.personal)


# Шаг 2: Описание проблемы
@router_time.message(Register.working)
async def save_work_description(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("Пожалуйста, введите описание проблемы.")
        return
    await state.update_data(work_description=text)

    keyboard = confirm_cancel_keyboard("confirm_work", "cancel_work")
    await message.answer(f"Описание: {text}\nСохранить?", reply_markup=keyboard)
    
    
@router_time.callback_query(F.data == "confirm_work")
async def confirm_work(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Введите решение проблемы.")
    await state.set_state(Register.working_solution)


@router_time.callback_query(F.data == "cancel_work")
async def cancel_work(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Опишите проблему:")
    await state.set_state(Register.working)


def get_inventory_number(item_name, items):
    for item in items:
        if item['name'] == item_name:
            return item['inventory_number']
    return None  # Если имя не найдено


# Шаг 3: Решение проблемы
@router_time.message(Register.working_solution)
async def save_work_solution(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("Пожалуйста, введите решение проблемы.")
        return
    await state.update_data(work_solution=text)

    keyboard = confirm_cancel_keyboard("confirm_solution", "cancel_solution")
    await message.answer(f"Решение: {text}\nСохранить?", reply_markup=keyboard)


@router_time.callback_query(F.data == "confirm_solution")
async def confirm_solution(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Введите статус неисправности.")
    await state.set_state(Register.fault_status)


@router_time.callback_query(F.data == "cancel_solution")
async def cancel_solution(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Введите решение проблемы:")
    await state.set_state(Register.working_solution)


# Новый handler для fault_status


@router_time.message(Register.fault_status)
async def save_fault_status(message: Message, state: FSMContext):
    fault_status = message.text.strip()
    if not fault_status:  # Валидация: не пустой и не только пробелы
        await message.answer("Пожалуйста, введите статус неисправности (не пустой и без лишних пробелов).")
        return

    await state.update_data(fault_status=fault_status)  # Сохраняем статус
    keyboard = confirm_cancel_keyboard("save_data_fault_status", "cancel_data_fault_status")
    await message.answer("Сохранить введенные данные?", reply_markup=keyboard)
    
# Обновленный callback для сохранения после fault_status (переименован из confirm_save_data для "save_data_solution")


@router_time.callback_query(F.data == "save_data_fault_status")
async def confirm_save_data_fault_status(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    workers = data.get('workers', [])
    workers_str = ', '.join(workers) if workers else "Не указаны"
    work_description = data.get('work_description', "Не указано")
    work_solution = data.get('work_solution', 'Не указано')
    fault_status = data.get('fault_status', 'Не указано')  # Новое поле
    hours_start = data.get('hours_start', '00')
    minutes_start = data.get('minutes_start', '00')
    hours_end = data.get('hours_end', '00')
    minutes_end = data.get('minutes_end', '00')
    selected_shop = data.get('selected_shop', "Не указан")
    selected_machine = data.get('selected_machine', "Не указан")
    selected_date_start = data.get('selected_date_start')
    selected_date_end = data.get('selected_date_end')

    shop_number = selected_shop.split('-')[0]
    machines_data = loads_machines_data()
    existing_machines = machines_data.get(f'maschines_{shop_number}', [])
    inventory_number = get_inventory_number(
        selected_machine, existing_machines)

    start_time = time(int(hours_start), int(minutes_start))
    end_time = time(int(hours_end), int(minutes_end))
    start_datetime = datetime.combine(selected_date_start.date(), start_time)
    end_datetime = datetime.combine(selected_date_end.date(), end_time)
    start_datetime_str = start_datetime.strftime('%d.%m.%Y %H:%M')
    end_datetime_str = end_datetime.strftime('%d.%m.%Y %H:%M')

    duration = end_datetime - start_datetime
    if duration.days < 1:
        duration_hours = duration.total_seconds() // 3600
        duration_minutes = (duration.total_seconds() % 3600) // 60
        result_duration = f"{int(duration_hours)} час {int(duration_minutes)} мин"
    else:
        duration_days = duration.days
        duration_hours = (duration.total_seconds() %
                          (duration_days * 86400)) // 3600
        duration_minutes = (duration.total_seconds() % 3600) // 60
        result_duration = f"{duration_days} дн. {int(duration_hours)} час. {int(duration_minutes)} мин"

    # Обновленный вывод с fault_status
    result_message = (
        f"Вы ввели данные: \n"
        f"📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"📌 <b>Исполнители работ:</b> {workers_str}\n"
        f"📝 <b>Описание проблемы:</b> {work_description}\n"
        f"📝 <b>Решение:</b> {work_solution}\n"
        f"📝 <b>Статус неисправности:</b> {fault_status}\n"  # Добавлено
        f"📅 <b>Дата начала:</b> {start_datetime_str}\n"
        f"📅 <b>Дата окончания:</b> {end_datetime_str}\n"
        f"⏳ <b>Затраченное время:</b> {result_duration}\n"
        f"🏭 <b>Цех:</b> {shops.get(selected_shop, 'Не указан')}\n"
        f"🔧 <b>Станок:</b> {selected_machine}\n"
        f"🔢 <b>Инвентарный номер:</b> {inventory_number}\n"
    )

    await callback.message.edit_text(result_message, parse_mode="HTML")
    await callback.message.answer("✅ Все данные сохранены!")

    # Данные для сохранения (добавлено fault_status)
    work_data = {
        "date": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "workers": workers_str,
        "description": work_description,
        "solution": work_solution,
        "fault_status": fault_status,  # Добавлено
        "start": start_datetime_str,
        "end": end_datetime_str,
        "duration": result_duration,
        "shop": shops.get(selected_shop, "Не указан"),
        "machine": selected_machine,
        "inventory_number": inventory_number
    }

    save_data_to_google_sheets(work_data)
    await state.clear()


# Handler для отмены после fault_status
@router_time.callback_query(F.data == "cancel_data_fault_status")
async def cancel_save_data_fault_status(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()  # Удаляем кнопки
    await callback.message.answer("Введите статус неисправности")
    await state.set_state(Register.fault_status)

