from app import db

db.init_db()
users = db.fetch_all('SELECT id, username, full_name FROM users')
for u in users:
    print(f'{u["id"]}: {u["username"]} ({u["full_name"]})')
