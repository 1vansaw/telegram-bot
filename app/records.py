from aiogram import F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, FSInputFile, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from app.states import Register
from datetime import datetime
import time
from app.data_shops import shops
import pandas as pd
import os  # Для работы с файлами и папками
import logging
from dotenv import load_dotenv
import json
from app.timing import connect_to_google_sheets
from googleapiclient.discovery import build  # Для Drive API
from google.oauth2 import service_account  # Для аутентификации
import gspread
import io  # Для работы с BytesIO
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import app.keyboards as kb
import asyncio



router_records = Router()
load_dotenv('token.env')  # Загружаем переменные окружения из .env файла
logger = logging.getLogger(__name__)

# Путь к файлу, где будут храниться данные
FILE_PATH = 'json/machines_data.json'
FILE_PATH_ACCESS = 'json/access_user.json'
DRIVE_FILES_PATH = 'json/drive_files.json'
spreadsheet_id = os.getenv('GOOGLE_SHEET_KEY')
credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
# Папка для временных файлов
TEMP_DIR = 'temp files'
TEMP_FOLDER_ID = '1ihS9eD7QHZa0xsru_VKq_YKuEnN3T3iA'

# Функция для загрузки данных из JSON файла


def load_access_data():
    """Загружает данные пользователей из JSON-файла или создает структуру, если файл пуст/не существует."""
    try:
        with open(FILE_PATH_ACCESS, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Файл доступа не найден или поврежден: {e}")
        return {
            "main_admins": [],
            "admins": [],
            "users": []
        }


# Функция сохранения истории файлов в JSON


def save_drive_files(files_list):
    """Сохраняет список файлов в JSON."""
    with open(DRIVE_FILES_PATH, "w", encoding="utf-8") as file:
        json.dump(files_list, file, ensure_ascii=False, indent=4)

# функция определения уровня доступа


def get_user_role(user_id, data):
    if user_id in data['main_admins']:
        return "👑 Главный администратор!"
    elif user_id in data['admins']:
        return "🛠 Администратор!"
    elif user_id in data['users']:
        return "👥 Пользователь"
    return None



# Inline кнопка Главное меню
inline_main_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ]
)


# Функция загрузки данных из Google Sheets
def load_sheet_data(spreadsheet_id):
    client = connect_to_google_sheets()
    sheet = client.open_by_key(spreadsheet_id).sheet1
    return sheet.get_all_records()

# Функция поиска: возвращает список найденных строк (dict'ов)


def search_in_sheet(data, phrase):
    if not phrase or not phrase.strip():
        return []
    phrase_lower = phrase.lower().strip()
    results = []
    for row in data:
        if any(phrase_lower in str(value).lower() for value in row.values()):
            results.append(row)
    return results



async def run_search(phrase):
    sheet_data = load_sheet_data(spreadsheet_id)

    indexed = []
    for idx, row in enumerate(sheet_data):
        row["__row"] = idx + 2   # строки в Google начинаются с 2
        indexed.append(row)

    return search_in_sheet(indexed, phrase)

# Регистрируем шрифт DejaVu Sans (предполагаем, что файл DejaVuSans.ttf в корне проекта)
pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))

# Создаём стиль для параграфов с поддержкой кириллицы (для ячеек таблицы)
styles = getSampleStyleSheet()
normal_style = ParagraphStyle(
    'Normal',
    parent=styles['Normal'],
    fontName='DejaVuSans',  # Используем зарегистрированный шрифт
    fontSize=7,  # Уменьшаем шрифт для компактности
    leading=8,  # Межстрочный интервал
)

# Создаём стиль для заголовка (центрированный, больший шрифт, с отступами)
title_style = ParagraphStyle(
    'Title',
    parent=styles['Title'],  # Или 'Normal', если 'Title' не определён
    # Можно заменить на 'DejaVuSans-Bold' если есть файл DejaVuSans-Bold.ttf
    fontName='DejaVuSans',
    fontSize=12,  # Увеличенный шрифт для заголовка
    alignment=1,  # 1 = центр (0 = лево, 2 = право)
    spaceAfter=20,  # Отступ после заголовка (в pt, для разделения от таблицы)
    spaceBefore=0,  # Отступ перед заголовком (0 = без отступа сверху)
    textColor=colors.red,  # Цвет текста
)

# # Функция создания PDF файла


def create_pdf_file(results, filename):
    """Создает PDF файл с результатами поиска и возвращает путь к нему."""
    if not results:
        return None

    # Создаём папку, если её нет
    os.makedirs(TEMP_DIR, exist_ok=True)

    # Полный путь к файлу (меняем расширение на .pdf)
    file_path = os.path.join(TEMP_DIR, filename.replace('.csv', '.pdf'))

    # Создаём DataFrame из результатов
    df = pd.DataFrame(results)

    # Создаём PDF документ с ландшафтной ориентацией для большего пространства
    doc = SimpleDocTemplate(file_path, pagesize=landscape(A4))
    elements = []

    # Заголовок
    search_phrase = filename.split('_')[2].replace('_', ' ') if len(filename.split('_')) > 2 else 'Запрос'
    title = Paragraph(f"Результаты поиска: '{search_phrase}'", title_style)
    elements.append(title)

    # Преобразуем DataFrame в список списков с Paragraph для каждой ячейки
    data = []
    for row in [df.columns.tolist()] + df.values.tolist():  # Заголовки + данные
        data_row = []
        for cell in row:
            cell_text = str(cell) if cell is not None else ""
            data_row.append(Paragraph(cell_text, normal_style))
        data.append(data_row)

    # Создаём таблицу с фиксированной шириной столбцов
    num_cols = len(df.columns)
    col_widths = [60, 50, 180, 180, 80, 40, 40, 40, 30, 40, 40]  # Расширенные настройки ширины
    
    # Автоподбор ширины для очень длинных таблиц
    total_width = sum(col_widths)
    page_width = 770  # Ширина страницы A4 в ландшафтном режиме (примерно)
    table = Table(data, colWidths=col_widths)

    # Стиль таблицы
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        # Автоматический перенос текста в ячейках
        ('WORDWRAP', (0, 0), (-1, -1), True),
    ])
    table.setStyle(style)

    elements.append(table)

    # Генерируем PDF
    doc.build(elements)

    return file_path


# # Функция создания HTML файла с таблицей, фильтрами и базовым редактированием
# def create_html_content(results, filename):
#     if not results:
#         return None

#     # Преобразуем результаты в DataFrame для удобства
#     df = pd.DataFrame(results)

#     # HTML-шаблон с DataTables (как в оригинале)
#     html_template = """
#     <!DOCTYPE html>
#     <html lang="ru">
#     <head>
#         <meta charset="UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <title>Результаты поиска</title>
#         <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
#         <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
#         <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
#         <style>
#             body { font-family: Arial, sans-serif; margin: 20px; }
#             table { width: 100%; border-collapse: collapse; font-size: 12px; word-wrap: break-word; overflow-wrap: break-word; }
#             th, td { border: 1px solid #ddd; padding: 8px; text-align: center; vertical-align: top; }
#             th { background-color: #f2f2f2; }
#             .editable { cursor: pointer; background-color: #fff; }
#             .editable:hover { background-color: #f9f9f9; }
#             input[type="text"] { width: 100%; box-sizing: border-box; }
#         </style>
#     </head>
#     <body>
#         <h1>Результаты поиска: '{{ phrase }}'</h1>
#         <p>Используйте фильтры в заголовках таблицы для поиска и сортировки. Кликните по ячейке для редактирования (изменения не сохраняются).</p>
#         <table id="resultsTable" class="display">
#             <thead>
#                 <tr>
#                     {% for col in columns %}
#                     <th>{{ col }}</th>
#                     {% endfor %}
#                 </tr>
#             </thead>
#             <tbody>
#                 {% for row in data %}
#                 <tr>
#                     {% for cell in row %}
#                     <td class="editable">{{ cell if cell else '' }}</td>
#                     {% endfor %}
#                 </tr>
#                 {% endfor %}
#             </tbody>
#         </table>
        
#         <script>
#             $(document).ready(function() {
#                 $('#resultsTable').DataTable({
#                     "language": {
#                         "url": "//cdn.datatables.net/plug-ins/1.13.4/i18n/ru.json"
#                     },
#                     "pageLength": 50,
#                     "responsive": true,
#                     "columnDefs": [
#                         { "orderable": true, "searchable": true, "targets": "_all" }
#                     ]
#                 });
                
#                 $('.editable').on('click', function() {
#                     var $cell = $(this);
#                     var original = $cell.text();
#                     $cell.html('<input type="text" value="' + original + '">');
#                     var $input = $cell.find('input');
#                     $input.focus().on('blur keyup', function(e) {
#                         if (e.type === 'blur' || e.keyCode === 13) {
#                             var newValue = $input.val();
#                             $cell.text(newValue);
#                         }
#                     });
#                 });
#             });
#         </script>
#     </body>
#     </html>
#     """

#     # Рендерим шаблон
#     phrase = filename.split('_')[2].replace('_', ' ') if len(
#         filename.split('_')) > 2 else 'Запрос'
#     template = Template(html_template)
#     html_content = template.render(
#         columns=df.columns.tolist(), data=df.values.tolist(), phrase=phrase)

#     return html_content

def get_oauth_drive_service():
    """Возвращает аутентифицированный сервис для работы с Google Drive API через OAuth"""
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
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
    
    return build('drive', 'v3', credentials=creds)


# Функция создания Google Таблицы и сохранения копии в папку TEMP
def create_google_sheet(results, phrase, user_id):
    """Создает новую Google Таблицу с результатами поиска и сохраняет копию в папку TEMP"""
    if not results:
        logger.warning("Нет данных для создания таблицы.")
        return None

    try:
        # Аутентификация с помощью OAuth
        client = connect_to_google_sheets()
        
        # Получаем credentials напрямую из функции connect_to_google_sheets
        # Для этого нужно немного изменить connect_to_google_sheets, чтобы она возвращала и creds
        # Либо получаем creds здесь заново
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

        # Создаем низкоуровневый сервис для Sheets API
        sheets_service = build('sheets', 'v4', credentials=creds)

        # Создаем имя для таблицы
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        sheet_name = f"Результаты_поиска_{phrase}_{timestamp}"

        # Создаем новую таблицу через gspread
        new_spreadsheet = client.create(sheet_name)
        spreadsheet_id = new_spreadsheet.id
        logger.info(f"Таблица создана: {sheet_name} (ID: {spreadsheet_id})")

        # Записываем данные в таблицу
        worksheet = new_spreadsheet.sheet1
        df = pd.DataFrame(results)
        
        # # Подготавливаем данные: заголовки и строки
        data_to_update = [df.columns.values.tolist()] + df.values.tolist()
        worksheet.update(data_to_update)
        logger.info("Данные успешно записаны в таблицу.")
        sheet_id = int(worksheet.id)  # gspread возвращает реальный sheetId

        num_rows = len(data_to_update)
        num_cols = len(data_to_update[0]) if data_to_update else 0

        full_range = {
            "sheetId": sheet_id,
            "startRowIndex": 0,
            "endRowIndex": num_rows,
            "startColumnIndex": 0,
            "endColumnIndex": num_cols
        }

        header_range = {
            "sheetId": sheet_id,
            "startRowIndex": 0,
            "endRowIndex": 1,
            "startColumnIndex": 0,
            "endColumnIndex": num_cols
        }

        # ЗАМЕНА: Убираем autoResizeDimensions и добавляем индивидуальные настройки ширины
        column_width_requests = [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,  # Колонка 0: Дата
                        "endIndex": 1
                    },
                    "properties": {"pixelSize": 120},
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 1,  # Колонка 1: Исполнители
                        "endIndex": 2
                    },
                    "properties": {"pixelSize": 150},
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 2,  # Колонка 2: Описание проблемы
                        "endIndex": 3
                    },
                    "properties": {"pixelSize": 400},  # Широкая для текста
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 3,  # Колонка 3: Решение
                        "endIndex": 4
                    },
                    "properties": {"pixelSize": 400},  # Широкая для текста
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 4,  # Колонка 4: Статус
                        "endIndex": 5
                    },
                    "properties": {"pixelSize": 150},
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 5,  # Колонка 5: Начало работ
                        "endIndex": 6
                    },
                    "properties": {"pixelSize": 150},
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 6,  # Колонка 6: Окончание работ
                        "endIndex": 7
                    },
                    "properties": {"pixelSize": 150},
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 7,  # Колонка 7: Затраченное время
                        "endIndex": 8
                    },
                    "properties": {"pixelSize": 120},
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 8,  # Колонка 8: Цех
                        "endIndex": 9
                    },
                    "properties": {"pixelSize": 100},
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 9,  # Колонка 9: Станок
                        "endIndex": 10
                    },
                    "properties": {"pixelSize": 120},
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 10,  # Колонка 10: Инвентарный номер
                        "endIndex": 11
                    },
                    "properties": {"pixelSize": 180},
                    "fields": "pixelSize"
                }
            }
        ]

        requests = [
            {
                "setBasicFilter": {
                    "filter": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": num_rows,
                            "startColumnIndex": 0,
                            "endColumnIndex": num_cols
                        }
                    }
                }
            },
            {
                "repeatCell": {
                    "range": full_range,
                    "cell": {
                        "userEnteredFormat": {
                            "wrapStrategy": "WRAP",
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(wrapStrategy, horizontalAlignment, verticalAlignment)"
                }
            },
            {
                "repeatCell": {
                    "range": header_range,
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
                        }
                    },
                    "fields": "userEnteredFormat(textFormat, backgroundColor)"
                }
            },
            # ЗАМЕНА: добавляем наши индивидуальные настройки ширины
            *column_width_requests,
            {
                "addProtectedRange": {
                    "protectedRange": {
                        "range": header_range,
                        "description": "Защита строки заголовков",
                        "warningOnly": False,
                        "requestingUserCanEdit": False,
                        "editors": {
                            "users": [], 
                            "groups": [],
                            "domainUsersCanEdit": False
                        }
                    }
                }
            }
        ]

        # Выполняем batchUpdate
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()
        logger.info("Форматирование и защита заголовков успешно применены.")

        # Перемещаем файл в папку TEMP
        if TEMP_FOLDER_ID:
            try:
                drive_service = build('drive', 'v3', credentials=creds)
                
                # Перемещаем файл из корня в указанную папку
                drive_service.files().update(
                   fileId=spreadsheet_id,
                    addParents=TEMP_FOLDER_ID,
                    removeParents='root',
                    fields='id, parents'
                ).execute()
                logger.info(f"Файл успешно перемещен в папку TEMP: {TEMP_FOLDER_ID}")
                
            except Exception as move_error:
                logger.error(f"Не удалось переместить файл в папку TEMP. Ошибка: {move_error}")
        else:
            logger.warning("TEMP_FOLDER_ID не указан. Файл останется в корневой папке.")

        # Делаем таблицу доступной всем
        new_spreadsheet.share(None, perm_type='anyone', role='writer')
        logger.info("Таблица стала доступной для чтения по ссылке.")

        # Формируем ссылку вручную
        manual_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
        # return manual_url
        return {
                "url": manual_url,
                "copy_sheet_id": spreadsheet_id,
                "row_map": [row["__row"] for row in results]}  # список исходных строк
    

    except Exception as e:
        logger.error(f"Критическая ошибка при создании Google Таблицы: {e}")
        return None




def cleanup_old_files():
    """Удаляет файлы из TEMP_DIR старше 24 часов."""
    if not os.path.exists(TEMP_DIR):
        return

    now = time.time()
    for filename in os.listdir(TEMP_DIR):
        # Удаляем и .xlsx (история Google Таблиц?) и .pdf (результаты поиска)
        if filename.endswith('.pdf'):
            file_path = os.path.join(TEMP_DIR, filename)
            file_time = os.path.getctime(file_path)
            if now - file_time > 86400:
                os.remove(file_path)
                logger.info(f'Файл {filename} удален.')

    cleanup_old_files_on_drive()

def cleanup_old_files_on_drive():
    """
    Удаляет файлы из фиксированной папки на Google Диске старше 24 часов.
    """
    
    try:
        # Создаем сервис Google Drive
        service = get_oauth_drive_service()
        
        # Текущее время в секундах с эпохи Unix
        now = datetime.now().timestamp()
        
        # Ищем ВСЕ файлы в указанной папке
        query = f"'{TEMP_FOLDER_ID}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            fields="files(id, name, createdTime)",
            pageSize=1000  # Увеличиваем лимит, если файлов много
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            logger.info("В папке TEMP на Google Диске нет файлов для очистки.")
            return
            
        deleted_count = 0
        for file in files:
            # Преобразуем время создания в timestamp
            # Формат: '2023-10-05T12:30:45.123Z' → Unix timestamp
            created_time = datetime.fromisoformat(
                file['createdTime'].replace('Z', '+00:00')
            ).timestamp()
            
            # Проверяем возраст файла (24 часа = 86400 секунд)
            if now - created_time > 86400:
                try:
                    service.files().delete(fileId=file['id']).execute()
                    deleted_count += 1
                    logger.info(f'Удален файл с Google Диска: {file["name"]}')
                except Exception as e:
                    logger.error(f'Ошибка при удалении {file["name"]}: {str(e)}')
        
        logger.info(f'Очистка Google Диска завершена. Удалено файлов: {deleted_count}')
                    
    except Exception as e:
        logger.error(f'Критическая ошибка при очистке Google Диска: {str(e)}')



# Обработчик кнопки "🔍 Поиск записи" — запрашивает фразу и переходит в состояние


@router_records.message(F.text == '🔍 Поиск записи')
async def start_search(message: Message, state: FSMContext):
    data = load_access_data()  # Загружаем данные о пользователях
    user_id = message.from_user.id  # Получаем ID пользователя
    role = get_user_role(user_id, data)
    if role is None:
        await message.answer("Доступ запрещён.")
        return

    logger.info(f"Пользователь {user_id} ({role}) начал поиск записи.")
    await message.answer("Введите слово или фразу для поиска по базе (не может быть пустым):", reply_markup=ReplyKeyboardRemove())
    # Используем ваше существующее состояние
    await state.set_state(Register.search_record)


# @router_records.message(StateFilter(Register.search_record))
# async def process_search_phrase(message: Message, state: FSMContext):
#     phrase = message.text.strip()
#     if not phrase:
#         await message.answer("Фраза не может быть пустой. Введите заново:")
#         return

#     user_id = message.from_user.id

#     if not spreadsheet_id:
#         await message.answer("Ошибка: GOOGLE_SHEET_KEY не настроен в .env.")
#         await state.clear()
#         return

#     await message.answer("Ведется поиск, пожалуйста подождите... 🔍")

#     try:
#         sheet_data = load_sheet_data(spreadsheet_id)
#         results = search_in_sheet(sheet_data, phrase)

#         if not results:
#             await message.answer(f"Ничего не найдено по запросу '{phrase}'.")
#         else:
#             # Для ПРОСМОТРА создаем PDF файл
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             filename = f"Результат_{user_id}_{phrase.replace(' ', '_')}_{timestamp}.csv" # Имя с .csv для истории

#             file_path = create_pdf_file(results, filename) # Функция создаст .pdf файл

#             if file_path and os.path.exists(file_path):
#                 await message.answer_document(
#                     document=FSInputFile(file_path),
#                     caption=f"Найдено {len(results)} результатов по '{phrase}'. Формат: PDF"
#                 )
#             else:
#                 await message.answer("Ошибка: Не удалось создать файл с результатами.")

#         await state.clear()

#     except Exception as e:
#         logger.error(f"Ошибка в process_search_phrase: {e}", exc_info=True)
#         await message.answer(f"Ошибка при поиске: {str(e)}. Проверьте доступ к таблице.")
#         await state.clear()


@router_records.message(StateFilter(Register.search_record))
async def process_search_phrase(message: Message, state: FSMContext):
    phrase = message.text.strip()
    if not phrase:
        return await message.answer(
            "Фраза не может быть пустой. Введите заново:",
            reply_markup=inline_main_menu
        )

    # Отправляем первое сообщение о прогрессе
    progress_msg = await message.answer("🔍 Идёт поиск, пожалйуста подождите...")

    try:
        # Этап 1 — поиск
        results = await run_search(phrase)
        await asyncio.sleep(0.5)
        await progress_msg.edit_text("⏳ Обработка результатов...")

        if not results:
            await progress_msg.delete()
            await message.answer(
                f"По запросу '{phrase}' ничего не найдено.\nВведите новую фразу:",
                reply_markup=inline_main_menu
            )
            return

        # Этап 2 — создание PDF
        await asyncio.sleep(0.5)
        await progress_msg.edit_text("📄 Формирую файл с результатами...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Результат_{message.from_user.id}_{phrase}_{timestamp}.csv"
        file_path = create_pdf_file(results, filename)

        # Этап 3 — финал
        await asyncio.sleep(0.5)
        await progress_msg.edit_text("🧾 Подготавливаю отправку результата...")

        # Удаляем индикатор
        await progress_msg.delete()

        # Отправляем PDF
        await message.answer_document(
            document=FSInputFile(file_path),
            caption=f"По запросу '{phrase}' найдено {len(results)} результатов.",
            reply_markup=inline_main_menu
        )

        await state.clear()

    except Exception as e:
        await progress_msg.edit_text("❌ Ошибка при обработке запроса.")
        await state.clear()
        await message.answer(
            f"Ошибка: {str(e)}. Попробуйте позже.",
            reply_markup=inline_main_menu
        )

@router_records.callback_query(lambda c: c.data == "main_menu")
async def go_to_main_menu(callback: CallbackQuery):
    try:
        # Удаляем сообщение с PDF и кнопкой
        await callback.message.delete()
    except Exception as e:
        # Иногда сообщение может быть уже удалено, тогда просто логируем
        logger.warning(f"Не удалось удалить сообщение: {e}")

    # Отправляем главное меню
    await callback.message.answer(
        "Главное меню:",
        reply_markup=kb.main  # твой ReplyKeyboardMarkup
    )

    # Заканчиваем callback
    await callback.answer()


# @router_records.message(F.text == '📋 История поиска')
# async def show_search_history(message: Message):
#     data = load_access_data()
#     user_id = message.from_user.id
#     role = get_user_role(user_id, data)
#     if role is None:
#         await message.answer("Доступ запрещён.")
#         return

#     if not os.path.exists(TEMP_DIR):
#         await message.answer("Папка с историей не найдена. Сделайте поиск сначала.")
#         return

#     all_files = []
#     for filename in os.listdir(TEMP_DIR):
#         if filename.endswith('.xlsx'):
#             # Парсим имя: Результат_{user_id}_{phrase}_{timestamp}.xlsx
#             parts = filename.replace('Результат_', '').replace(
#                 '.xlsx', '').split('_',  2)
#             if len(parts) == 3:
#                 file_user_id = parts[0]
#                 phrase = parts[1].replace('_', ' ')  # Восстанавливаем пробелы
#                 timestamp_str = parts[2]
#                 try:
#                     # Парсим timestamp в читаемую дату: %Y%m%d_%H%M%S → %d.%m.%Y %H:%M:%S
#                     dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
#                     readable_time = dt.strftime("%d.%m.%Y %H:%M:%S")
#                     all_files.append({
#                         'filename': filename,
#                         'user_id': file_user_id,
#                         'phrase': phrase,
#                         'time': readable_time
#                     })
#                 except ValueError:
#                     continue  # Пропускаем некорректные файлы

#     if not all_files:
#         await message.answer("История поиска пуста.")
#         return

#     # Сортируем по времени (новые сверху)
#     all_files.sort(key=lambda x: x['time'], reverse=True)

#     # Создаём сообщение и клавиатуру
#     text = "📋 Общая история поиска (файлы хранятся 24 часа):\n\n"
#     keyboard = InlineKeyboardMarkup(inline_keyboard=[])

#     for i, file_info in enumerate(all_files[:10]):  # Лимит 10
#         # Удобное отображение: добавляем user_id для отличия
#         display = f"[{file_info['user_id']}] {file_info['phrase']} - {file_info['time']}"
#         keyboard.inline_keyboard.append([InlineKeyboardButton(
#             text=display[:50] + "..." if len(display) > 50 else display, callback_data=f"download_{i}")])

#     if len(all_files) > 10:
#         text += f"\n(Показаны последние 10 из {len(all_files)})"

#     await message.answer(text, reply_markup=keyboard)
    


# @router_records.message(F.text == '📋 История поиска')
# async def show_search_history(message: Message):
#     data = load_access_data()  # Загружаем данные о пользователях
#     user_id = message.from_user.id  # Получаем ID пользователя
#     role = get_user_role(user_id, data)
#     if role is None:
#         await message.answer("Доступ запрещён.")
#         return

#     if not os.path.exists(TEMP_DIR):
#         await message.answer("Папка с историей не найдена. Сделайте поиск сначала.")
#         return

#     all_files = []
#     for filename in os.listdir(TEMP_DIR):
#         if filename.endswith('.csv'):
#             # Парсим имя: Результат_{user_id}_{phrase}_{timestamp}.csv
#             parts = filename.replace('Результат_', '').replace(
#                 '.csv', '').split('_', 2)
#             if len(parts) == 3:
#                 file_user_id = parts[0]
#                 phrase = parts[1].replace('_', ' ')  # Восстанавливаем пробелы
#                 timestamp_str = parts[2]
#                 try:
#                     # Парсим timestamp в читаемую дату: %Y%m%d_%H%M%S → %d.%m.%Y %H:%M:%S
#                     dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
#                     readable_time = dt.strftime("%d.%m.%Y %H:%M:%S")
#                     all_files.append({
#                         'filename': filename,
#                         'user_id': file_user_id,
#                         'phrase': phrase,
#                         'time': readable_time
#                     })
#                 except ValueError:
#                     continue  # Пропускаем некорректные файлы

#     if not all_files:
#         await message.answer("История поиска пуста.")
#         return

#     # Сортируем по времени (новые сверху)
#     all_files.sort(key=lambda x: x['time'], reverse=True)

#     # Создаём сообщение и клавиатуру
#     text = "📋 Общая история поиска (файлы хранятся 24 часа):\n\n"
#     keyboard = InlineKeyboardMarkup(inline_keyboard=[])

#     for i, file_info in enumerate(all_files[:10]):  # Лимит 10 для краткости
#         # Удобное отображение: добавляем user_id для отличия (можно убрать, если не нужно)
#         display = f"[{file_info['user_id']}] {file_info['phrase']} - {file_info['time']}"
#         keyboard.inline_keyboard.append([InlineKeyboardButton(
#             text=display[:50] + "..." if len(display) > 50 else display, callback_data=f"download_{i}")])

#     if len(all_files) > 10:
#         text += f"\n(Показаны последние 10 из {len(all_files)})"

#     await message.answer(text, reply_markup=keyboard)



@router_records.message(F.text == '✏️ Изменить запись')
async def start_edit(message: Message, state: FSMContext):
    data = load_access_data()
    user_id = message.from_user.id
    role = get_user_role(user_id, data)
    if role is None:
        await message.answer("Доступ запрещён.")
        return

    logger.info(f"Пользователь {user_id} ({role}) начал редактирование записи.")
    await message.answer("Введите слово или фразу для поиска по базе (не может быть пустым):", reply_markup=ReplyKeyboardRemove())
    # Устанавливаем состояние для РЕДАКТИРОВАНИЯ
    await state.set_state(Register.edit_record)



@router_records.message(StateFilter(Register.edit_record))
async def process_edit_phrase(message: Message, state: FSMContext):
    phrase = message.text.strip()

    if not phrase:
        return await message.answer(
            "Фраза не может быть пустой. Попробуйте ещё раз:",
            reply_markup=inline_main_menu
        )

    # Показываем один индикатор
    progress = await message.answer("🔍 Идёт поиск, пожалуйста подождите...")

    try:
        # --- Поиск ---
        results = await run_search(phrase)

        if not results:
            await progress.delete()
            return await message.answer(
                f"По запросу '{phrase}' ничего не найдено.\n"
                f"Введите новую фразу или нажмите кнопку ниже:",
                reply_markup=inline_main_menu
            )

        # --- Плавное обновление статуса ---
        await progress.edit_text("⏳ Обработка данных, пожалуйста подождите...")

        # --- Создание Google-таблицы ---
        sheet_info = create_google_sheet(results, phrase, message.from_user.id)

        if not sheet_info:
            await progress.delete()
            await state.clear()
            return await message.answer(
                "Ошибка: Не удалось создать Google-таблицу. Попробуйте позже.",
                reply_markup=inline_main_menu
            )

        # Сохраняем данные
        await state.update_data(
            copy_sheet_id=sheet_info["copy_sheet_id"],
            row_map=sheet_info["row_map"]
        )

        # Клавиатура
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📊 Открыть таблицу", url=sheet_info["url"])],
                [InlineKeyboardButton(text="💾 Сохранить изменения", callback_data="save_edit")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
            ]
        )

        # Удаляем индикатор (не меняем — сразу удаляем)
        await progress.delete()

        # Финальное сообщение
        result_msg = await message.answer(
            f"Найдено {len(results)} строк по запросу '{phrase}'.\n"
            f"Откройте таблицу, внесите изменения и нажмите «Сохранить изменения».",
            reply_markup=keyboard
        )

        await state.update_data(result_message_id=result_msg.message_id)

    except Exception as e:
        logger.error(f"Ошибка в edit_record: {e}", exc_info=True)
        await progress.delete()
        await state.clear()
        await message.answer(
            f"Произошла ошибка: {str(e)}. Попробуйте позже.",
            reply_markup=inline_main_menu
        )


@router_records.callback_query(F.data == "save_edit")
async def save_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    copy_id = data["copy_sheet_id"]
    row_map = data["row_map"]

    try:
        # Сообщение о начале синхронизации
        sync_message = await callback.message.answer("💾 Идёт запись изменений… 🔄 Пожалуйста, подождите.")

        # Убираем кнопки из исходного сообщения, чтобы пользователь не нажал повторно
        await callback.message.edit_reply_markup(reply_markup=None)

        # Загружаем измененную копию
        copy_data = load_sheet_data(copy_id)

        # Загружаем оригинальные строки
        client = connect_to_google_sheets()
        main_sheet = client.open_by_key(spreadsheet_id).sheet1

        original_rows = [main_sheet.row_values(row) for row in row_map]

        # Превращаем копию в список списков (как оригинал)
        edited_rows = [[v for k, v in row.items() if k != "__row"] for row in copy_data]

        # Проверяем, есть ли хотя бы одно изменение
        if edited_rows == original_rows:
            # Удаляем копию
            drive = get_oauth_drive_service()
            drive.files().delete(fileId=copy_id).execute()

            await sync_message.edit_text("🗑️ Вы не внесли изменений. Копия удалена.")
            await state.clear()
            return

        # Изменения есть → обновляем строки
        for edited, row_number in zip(edited_rows, row_map):
            end_col_letter = chr(ord("A") + len(edited) - 1)
            main_sheet.update(f"A{row_number}:{end_col_letter}{row_number}", [edited])

        # Удаляем временную копию
        drive = get_oauth_drive_service()
        drive.files().delete(fileId=copy_id).execute()

        # Итоговое сообщение + кнопка «Назад»
        await sync_message.edit_text(
            "✅ Изменения успешно сохранены и синхронизированы! 💾✨",
            reply_markup=inline_main_menu
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при сохранении: {e}", exc_info=True)
        await callback.message.answer(
            "❌ Ошибка: изменения НЕ сохранены.\n"
            "Копия не удалена — можно попробовать снова.",
            reply_markup=inline_main_menu
        )

@router_records.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    copy_id = data.get("copy_sheet_id")

    try:
        # Убираем inline-кнопки из сообщения
        await callback.message.edit_reply_markup(reply_markup=None)

        # Удаляем временную копию таблицы, если она существует
        if copy_id:
            drive = get_oauth_drive_service()
            drive.files().delete(fileId=copy_id).execute()

        # Сообщение об отмене + кнопка назад
        await callback.message.answer(
            "❌ Редактирование отменено.\n"
            "Временная таблица удалена.",
            reply_markup=inline_main_menu  # ↩️ Кнопка назад
        )

    except Exception as e:
        logger.error(f"Ошибка при отмене: {e}", exc_info=True)
        await callback.message.answer(
            "⚠️ Произошла ошибка при отмене операции.\n"
            "Но вы можете вернуться в главное меню:",
            reply_markup=inline_main_menu
        )

    # Очищаем состояние
    await state.clear()

    # Обязательно закрываем callback, чтобы Telegram не показывал “крутилку”
    await callback.answer()


# @router_records.message(StateFilter(Register.edit_record))
# async def process_edit_phrase(message: Message, state: FSMContext):
#     phrase = message.text.strip()
#     if not phrase:
#         await message.answer("Фраза не может быть пустой. Введите заново:")
#         return

#     user_id = message.from_user.id

#     if not spreadsheet_id:
#         await message.answer("Ошибка: GOOGLE_SHEET_KEY не настроен в .env.")
#         await state.clear()
#         return

#     await message.answer("Ведется поиск, пожалуйста подождите... 🔍")

#     try:
#         sheet_data = load_sheet_data(spreadsheet_id)
#         results = search_in_sheet(sheet_data, phrase)

#         if not results:
#             await message.answer(f"Ничего не найдено по запросу '{phrase}'.")
#         else:
#             # Для РЕДАКТИРОВАНИЯ создаем Google Таблицу
#             sheet_url = create_google_sheet(results, phrase, user_id)
            
#             if sheet_url:
#                 keyboard = InlineKeyboardMarkup(
#                     inline_keyboard=[[
#                         InlineKeyboardButton(text="📊 Открыть таблицу для редактирования", url=sheet_url)
#                     ]]
#                 )
#                 await message.answer(
#                     f"✅ Найдено {len(results)} результатов по запросу '<code>{phrase}</code>'.\nНажмите на кнопку ниже, чтобы открыть таблицу для редактирования:",
#                     reply_markup=keyboard,
#                     parse_mode="HTML"
#                 )
#             else:
#                 await message.answer("Ошибка: Не удалось создать Google Таблицу.")

#         await state.clear()

#     except Exception as e:
#         logger.error(f"Ошибка в process_edit_phrase: {e}", exc_info=True)
#         await message.answer(f"Ошибка при поиске: {str(e)}. Проверьте доступ к таблице.")
#         await state.clear()