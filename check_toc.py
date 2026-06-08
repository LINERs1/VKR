with open(r'C:\Users\liner\Desktop\Diplom\pdf_structure.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(115, 125):
    print(lines[i].strip())
