import sqlite3
import re
from tkinter import Tk, Label, Button, filedialog, StringVar, Frame

class LogParser:
    def __init__(self):
        self.root = Tk()
        self.root.title("Log Parser")
        self.root.geometry("400x200")
        
        self.file_path = StringVar()
        self.status = StringVar()
        self.status.set("Выберите файл для парсинга")
        
        frame = Frame(self.root, padx=10, pady=10)
        frame.pack(fill="both", expand=True)
        
        Label(frame, text="Выбранный файл:").pack(pady=5)
        Label(frame, textvariable=self.file_path).pack(pady=5)
        
        Button(frame, text="Выбрать файл", command=self.select_file).pack(pady=10)
        Button(frame, text="Парсить", command=self.parse_file).pack(pady=10)
        
        Label(frame, textvariable=self.status).pack(pady=10)
        
        self.root.mainloop()

    def select_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.file_path.set(file_path)
            self.status.set("Файл выбран. Нажмите 'Парсить'")

    def parse_file(self):
        if not self.file_path.get():
            self.status.set("Ошибка: Файл не выбран")
            return

        try:
            conn = sqlite3.connect('buildings.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS buildings (
                    id INTEGER PRIMARY KEY,
                    class TEXT,
                    name TEXT,
                    posX INTEGER,
                    posY INTEGER,
                    posZ INTEGER,
                    interior INTEGER
                )
            ''')

            # Регулярное выражение: class без кавычек, name в кавычках
            pattern = r'id=(\d+),\s*class=([^,]+),\s*name="([^"]+)",\s*pos=\[(\d+),(\d+),(\d+)\],\s*int=(true|false)'
            
            processed_count = 0
            matched_count = 0
            
            with open(self.file_path.get(), 'r', encoding='utf-8') as file:
                lines = file.readlines()
                
                for line in lines:
                    processed_count += 1
                    line = line.strip()
                    if 'id=' in line:
                        data_part = line.split(' ', 1)[1]  # Отделяем временную метку
                        match = re.search(pattern, data_part)
                        if match:
                            matched_count += 1
                            id_val, class_val, name_val, pos_x, pos_y, pos_z, int_val = match.groups()
                            int_val = 1 if int_val.lower() == 'true' else 0
                            print(f"Найдено: id={id_val}, class={class_val}, name={name_val}, pos=[{pos_x},{pos_y},{pos_z}], int={int_val}")
                            cursor.execute('''
                                INSERT OR REPLACE INTO buildings (id, class, name, posX, posY, posZ, interior)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (int(id_val), class_val, name_val, int(pos_x), int(pos_y), int(pos_z), int_val))
                        else:
                            print(f"Не удалось распарсить строку: {line}")

            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM buildings")
            db_count = cursor.fetchone()[0]
            
            conn.close()
            
            self.status.set(f"Обработано строк: {processed_count}, найдено совпадений: {matched_count}, записей в БД: {db_count}")
            
        except Exception as e:
            self.status.set(f"Ошибка: {str(e)}")
            print(f"Ошибка: {str(e)}")

if __name__ == "__main__":
    LogParser()