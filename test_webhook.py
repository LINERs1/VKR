import json
import urllib.request
from langchain_community.document_loaders import PyPDFLoader

pdf_path = r'C:\Users\liner\Desktop\Diplom\mr-osnovy-algoritmizatsii-i-programm.pdf'
print('Читаем PDF: ' + pdf_path)

try:
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    text = '\n'.join([page.page_content for page in pages])
    print(f'Извлечено {len(text)} символов.')

    payload = {
        'id': 'mr_osnovy',
        'course_id': 'python',
        'title': 'Основы алгоритмизации и программирования',
        'content': text,
        'source_type': 'methodology'
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request('http://localhost:8000/webhook/content', data=data, headers={'Content-Type': 'application/json'})

    with urllib.request.urlopen(req) as response:
        result = response.read().decode('utf-8')
        print('Ответ от AI Service: ' + result)
except Exception as e:
    print('Ошибка: ', e)
