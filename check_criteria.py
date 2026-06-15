import sqlite3

def check_criteria():
    print("="*50)
    print("ПРОВЕРКА КРИТЕРИЕВ КАЧЕСТВА НАВИГАЦИОННОГО ГРАФА")
    print("="*50)
    
    conn = sqlite3.connect("c:/Users/liner/Desktop/Diplom/backend/app.db")
    cursor = conn.cursor()
    
    # Критерий 2: Не менее 20 узлов
    cursor.execute("SELECT COUNT(*) FROM nav_nodes")
    node_count = cursor.fetchone()[0]
    
    print(f"\n[КРИТЕРИЙ 2] Количество узлов в графе навигации: {node_count}")
    if node_count >= 20:
        print("[+] УСПЕШНО: В графе больше 20 узлов.")
    else:
        print("[-] НЕУДАЧА: В графе меньше 20 узлов.")
        
    # Критерий 1: 5 уровней вложенности
    cursor.execute("SELECT MAX(depth) FROM nav_nodes")
    max_depth = cursor.fetchone()[0]
    
    print(f"\n[КРИТЕРИЙ 1] Максимальная глубина (уровни вложенности): {max_depth}")
    if max_depth >= 5:
        print("[+] УСПЕШНО: Система поддерживает переход по 5 и более уровням вложенности.")
    else:
        print("[-] НЕУДАЧА: Меньше 5 уровней вложенности.")
        
    conn.close()
    print("\n" + "="*50)

if __name__ == "__main__":
    check_criteria()
