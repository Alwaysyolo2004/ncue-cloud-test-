"""帳號驗證：PBKDF2-SHA256 雜湊（標準函式庫，不用額外套件）。"""
import hashlib
import hmac
import json
import os
import secrets

import config
import db

ITERATIONS = 200_000
ROLES = ("Student", "Professor")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


_DUMMY_HASH = hash_password(secrets.token_hex(8))


def authenticate(username: str, password: str):
    user = db.get_user(username)
    if user is None:
        verify_password(password, _DUMMY_HASH)  # 讓「帳號不存在」與「密碼錯」花一樣久
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    # 回傳時包含 must_change_password 欄位，供介面判斷是否要強制改密碼
    return {k: user[k] for k in ("username", "role", "name", "must_change_password")}


def create_user(username: str, password: str, role: str, name: str, must_change_password: int = 0):
    if role not in ROLES:
        raise ValueError(f"role 必須是 {ROLES}")
    db.upsert_user(username.strip(), hash_password(password), role, name.strip(), must_change_password)


def register_student(username: str, password: str, name: str):
    """提供給學生端自行註冊的專用函式"""
    if not username.strip() or not password.strip() or not name.strip():
        raise ValueError("所有欄位皆為必填")
    if db.get_user(username.strip()) is not None:
        raise ValueError("此帳號名稱已被使用")
    create_user(username, password, role="Student", name=name, must_change_password=0)


def update_password(username: str, new_password: str):
    """更新使用者密碼並清除強制改密碼狀態"""
    if len(new_password) < 6:
        raise ValueError("密碼長度至少需要 6 碼")
    hashed = hash_password(new_password)
    db.update_user_password(username, hashed)


DEMO_USERS = [
    ("prof_smith", "Professor", "Prof. Smith", 0),
    ("student_john", "Student", "John Doe", 0),
    ("student_sarah", "Student", "Sarah Lee", 0),
]


def seed_users():
    """資料庫沒有任何帳號時：建立預設 Demo 帳號"""
    if db.count_users() > 0:
        return
    for username, role, name, mcp in DEMO_USERS:
        pw = config.DEMO_PASSWORD or "password123"
        create_user(username, pw, role, name, must_change_password=mcp)
        if not config.DEMO_PASSWORD:
            print(f"[auth] 建立預設帳號 {username} / {pw}")
