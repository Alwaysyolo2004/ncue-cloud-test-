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

def register_user(username, password, name, role="Student"):
    """Mendaftarkan akun baru dan menyimpannya ke users.json."""
    init_users_file()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        
        # Cek apakah username sudah ada
        for user in users:
            if user["username"] == username.strip():
                return False, "Username already in Used please Change into another name"
        
        # (default role adalah Student)
        new_user = {
            "username": username.strip(),
            "password": password.strip(),
            "role": role,
            "name": name.strip()
        }
        users.append(new_user)
        
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
            
        return True, "Sign in Succced please proceed to log in section"
    except Exception as e:
        return False, f"Error: {str(e)}"

def update_user_password(username, new_password):
    """change password for OTP security"""
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
        
        for user in users:
            if user["username"] == username:
                user["password"] = new_password.strip()
                user["must_change_password"] = False # status false
                break
                
        with open("users.json", "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
            
        return True, "Success CHnage the Password"
    except Exception as e:
        return False, f"Failed to Change the Password: {str(e)}"

        
