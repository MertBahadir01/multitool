import sqlite3

db_path = r"D:\Pyto\multitool_studio\multitool_studio.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables= ['users','sqlite_sequence','password_vault','app_settings','notebook_categories','notebook_people',
        'notebook_notes','calculator_history',]


for table in tables:
    print(f"\n--- {table} ---")
    cursor.execute(f"SELECT * FROM {table};")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

conn.close()