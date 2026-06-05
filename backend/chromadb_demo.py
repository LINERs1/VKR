"""
Демонстрация работы ChromaDB — семантический поиск по урокам.
"""
import chromadb
from chromadb.utils import embedding_functions

# Подключаемся к ChromaDB
client = chromadb.Client()

# Создаём коллекцию (как таблицу в обычной БД)
collection = client.create_collection(
    name="course_demo",
    embedding_function=embedding_functions.DefaultEmbeddingFunction()
)

# ── Шаг 1: Добавляем фрагменты уроков (как будто пришли с платформы) ──────────
print("=" * 60)
print("ШАГ 1: Индексируем фрагменты уроков из курса Python")
print("=" * 60)

chunks = [
    {
        "id": "python_lesson_1_chunk_1",
        "text": "Python — высокоуровневый язык программирования. Он прост в изучении и широко применяется в науке о данных, веб-разработке и автоматизации.",
        "course_id": "python",
        "lesson_id": 1,
        "lesson_title": "Введение в Python"
    },
    {
        "id": "python_lesson_2_chunk_1",
        "text": "Переменная — это именованная область памяти для хранения данных. В Python переменная создаётся в момент присваивания значения: x = 5.",
        "course_id": "python",
        "lesson_id": 2,
        "lesson_title": "Переменные и типы данных"
    },
    {
        "id": "python_lesson_2_chunk_2",
        "text": "Типы данных в Python: int (целые числа), float (дробные), str (строки), bool (логические). Тип определяется автоматически.",
        "course_id": "python",
        "lesson_id": 2,
        "lesson_title": "Переменные и типы данных"
    },
    {
        "id": "python_lesson_3_chunk_1",
        "text": "Цикл for используется для перебора элементов последовательности. Например: for i in range(5) выполнит код 5 раз.",
        "course_id": "python",
        "lesson_id": 3,
        "lesson_title": "Циклы и условия"
    },
    {
        "id": "python_lesson_3_chunk_2",
        "text": "Условный оператор if позволяет выполнять код только при выполнении условия. Пример: if x > 0: print('Положительное число')",
        "course_id": "python",
        "lesson_id": 3,
        "lesson_title": "Циклы и условия"
    },
]

collection.add(
    ids=[c["id"] for c in chunks],
    documents=[c["text"] for c in chunks],
    metadatas=[{
        "course_id": c["course_id"],
        "lesson_id": c["lesson_id"],
        "lesson_title": c["lesson_title"]
    } for c in chunks]
)

print(f"Добавлено {len(chunks)} фрагментов из 3 уроков курса Python\n")

# ── Шаг 2: Демонстрация семантического поиска ─────────────────────────────────
print("=" * 60)
print("ШАГ 2: Студент задаёт вопросы голосовому ИИ")
print("=" * 60)

queries = [
    "что такое переменная",
    "как работает цикл",
    "какие бывают типы данных",
    "что такое Python",
]

for query in queries:
    print(f"\n Вопрос студента: «{query}»")
    results = collection.query(
        query_texts=[query],
        n_results=1,
        where={"course_id": "python"}
    )
    found_text  = results["documents"][0][0]
    lesson_title = results["metadatas"][0][0]["lesson_title"]
    lesson_id    = results["metadatas"][0][0]["lesson_id"]
    distance     = round(results["distances"][0][0], 4)

    print(f"    Найдено в: Урок {lesson_id} — «{lesson_title}»")
    print(f"    Фрагмент:  {found_text[:80]}...")
    print(f"    Сходство:  {round((1 - distance) * 100, 1)}%")

print("\n" + "=" * 60)
print("Вывод: ChromaDB находит нужный урок по СМЫСЛУ вопроса,")
print("даже если слова в вопросе и тексте урока не совпадают.")
print("=" * 60)
