import json
import os

USERS_FILE = "users.json"

def init_users_file():
    """Initializes default accounts if the file doesn't exist."""
    if not os.path.exists(USERS_FILE):
        default_users = [
            {"username": "prof_smith", "password": "password123", "role": "Professor", "name": "Prof. Smith"},
            {"username": "student_john", "password": "password123", "role": "Student", "name": "John Doe"},
            {"username": "student_sarah", "password": "password123", "role": "Student", "name": "Sarah Lee"}
        ]
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, ensure_ascii=False, indent=2)

def authenticate_user(username, password):
    """Checks user credentials and returns user details if valid."""
    init_users_file()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        for user in users:
            if user["username"] == username and user["password"] == password:
                return user
    except Exception:
        return None
    return None