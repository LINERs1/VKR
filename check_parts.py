with open(r'C:\Users\liner\Desktop\Diplom\pdf_structure.txt', 'r', encoding='utf-8') as f:
    text = f.read()

import re
pattern = re.compile(r'(ПРАКТИЧЕСКАЯ РАБОТА №\s*\d+)')
parts = pattern.split(text)

for i in range(1, min(7, len(parts)), 2):
    print(f"Title part: {repr(parts[i])}")
    print(f"Content start: {repr(parts[i+1][:100])}")
    print("---")
