"""SQLite 資料層：取代原本 4 個 JSON 檔。
- 交易 + WAL：多人同時寫入不會互相覆蓋
- 匿名提問只存 HMAC 雜湊，教授端與資料庫都看不到真實帳號，但學生本人仍查得到自己的問題
"""
import hashlib
import hmac
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import config

ANON_LABEL = "Anonymous Student"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('Student', 'Professor')),
    name          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS queries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    course       TEXT NOT NULL,
    query        TEXT NOT NULL,
    norm_query   TEXT NOT NULL,
    owner        TEXT NOT NULL,
    is_anonymous INTEGER NOT NULL,
    source       TEXT NOT NULL      -- professor / handout / general / error
);
CREATE INDEX IF NOT EXISTS idx_queries_course ON queries(course);
CREATE TABLE IF NOT EXISTS direct_questions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    course         TEXT NOT NULL,
    owner          TEXT NOT NULL,
    is_anonymous   INTEGER NOT NULL,
    question       TEXT NOT NULL,
    answer         TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'Pending',
    is_highlighted INTEGER NOT NULL DEFAULT 0,
    answered_ts    TEXT
);
CREATE TABLE IF NOT EXISTS verified_answers (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    course  TEXT NOT NULL,          -- 'All Courses' = 全課程通用
    keyword TEXT NOT NULL,
    answer  TEXT NOT NULL,
    ts      TEXT NOT NULL,
    UNIQUE (course, keyword)
);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def _conn():
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)


# ---------------- identity ----------------
def owner_id(username: str, is_anonymous: bool) -> str:
    if not is_anonymous:
        return username
    digest = hmac.new(config.APP_SECRET.encode(), username.encode(), hashlib.sha256).hexdigest()
    return "anon:" + digest[:20]


def owner_label(row) -> str:
    return ANON_LABEL if row["is_anonymous"] else row["owner"]


# ---------------- users ----------------
def get_user(username: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def upsert_user(username: str, password_hash: str, role: str, name: str):
    with _conn() as c:
        c.execute(
            """INSERT INTO users (username, password_hash, role, name) VALUES (?, ?, ?, ?)
               ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash,
               role = excluded.role, name = excluded.name""",
            (username, password_hash, role, name),
        )


def list_users():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT username, role, name FROM users ORDER BY role, username")]


def count_users() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ---------------- AI query log ----------------
def normalize_query(q: str) -> str:
    q = re.sub(r"\s+", " ", q.strip().lower())
    return q.rstrip("?？。.!！ ")


def log_query(course, query, username, is_anonymous, source):
    with _conn() as c:
        c.execute(
            "INSERT INTO queries (ts, course, query, norm_query, owner, is_anonymous, source) VALUES (?,?,?,?,?,?,?)",
            (_now(), course, query.strip(), normalize_query(query), owner_id(username, is_anonymous),
             int(bool(is_anonymous)), source),
        )


def _course_where(course, extra=None):
    clauses, params = [], []
    if course and course != config.ALL_COURSES:
        clauses.append("course = ?")
        params.append(course)
    if extra:
        clauses.append(extra)
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


def query_analytics(course=None):
    where, p = _course_where(course)
    gap_where, gp = _course_where(course, "source = 'general'")
    with _conn() as c:
        total = c.execute(f"SELECT COUNT(*) FROM queries {where}", p).fetchone()[0]
        askers = c.execute(f"SELECT COUNT(DISTINCT owner) FROM queries {where}", p).fetchone()[0]
        by_source = {r[0]: r[1] for r in c.execute(
            f"SELECT source, COUNT(*) FROM queries {where} GROUP BY source", p)}
        top = [dict(r) for r in c.execute(
            f"""SELECT MAX(query) AS question, COUNT(*) AS times, MAX(ts) AS last_asked
                FROM queries {where} GROUP BY norm_query
                ORDER BY times DESC, last_asked DESC LIMIT 10""", p)]
        gaps = [dict(r) for r in c.execute(
            f"SELECT ts, course, query FROM queries {gap_where} ORDER BY id DESC LIMIT 20", gp)]
        daily = [dict(r) for r in c.execute(
            f"SELECT substr(ts, 1, 10) AS day, COUNT(*) AS queries FROM queries {where} GROUP BY day ORDER BY day", p)]
        logs = [{"time": r["ts"], "course": r["course"], "student": owner_label(r),
                 "question": r["query"], "answered_from": r["source"]}
                for r in c.execute(f"SELECT * FROM queries {where} ORDER BY id DESC LIMIT 200", p)]
    return {"total": total, "askers": askers, "by_source": by_source,
            "top": top, "gaps": gaps, "daily": daily, "logs": logs}


# ---------------- direct questions ----------------
def submit_direct_question(course, question, username, is_anonymous):
    with _conn() as c:
        c.execute(
            "INSERT INTO direct_questions (ts, course, owner, is_anonymous, question) VALUES (?,?,?,?,?)",
            (_now(), course, owner_id(username, is_anonymous), int(bool(is_anonymous)), question.strip()),
        )


def list_direct_questions(course=None, pending_only=False, highlighted_only=False):
    extra = []
    if pending_only:
        extra.append("status = 'Pending'")
    if highlighted_only:
        extra.append("is_highlighted = 1")
    where, p = _course_where(course, " AND ".join(extra) if extra else None)
    with _conn() as c:
        rows = c.execute(f"SELECT * FROM direct_questions {where} ORDER BY id DESC", p).fetchall()
    return [dict(r, student=owner_label(r)) for r in rows]


def list_my_questions(username, course):
    owners = (owner_id(username, False), owner_id(username, True))
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM direct_questions WHERE course = ? AND owner IN (?, ?) ORDER BY id DESC",
            (course, *owners)).fetchall()
    return [dict(r) for r in rows]


def answer_direct_question(qid, answer, is_highlighted):
    with _conn() as c:
        c.execute(
            """UPDATE direct_questions SET answer = ?, status = ?, is_highlighted = ?, answered_ts = ?
               WHERE id = ?""",
            (answer.strip(), "Answered" if answer.strip() else "Pending", int(bool(is_highlighted)), _now(), qid),
        )


# ---------------- professor verified answers ----------------
def upsert_verified_answer(course, keyword, answer):
    with _conn() as c:
        c.execute(
            """INSERT INTO verified_answers (course, keyword, answer, ts) VALUES (?,?,?,?)
               ON CONFLICT(course, keyword) DO UPDATE SET answer = excluded.answer, ts = excluded.ts""",
            (course, keyword.strip(), answer.strip(), _now()),
        )


def list_verified_answers(course=None):
    if course and course != config.ALL_COURSES:
        sql, p = "SELECT * FROM verified_answers WHERE course IN (?, ?) ORDER BY id DESC", (course, config.ALL_COURSES)
    else:
        sql, p = "SELECT * FROM verified_answers ORDER BY id DESC", ()
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, p)]


def delete_verified_answer(vid):
    with _conn() as c:
        c.execute("DELETE FROM verified_answers WHERE id = ?", (vid,))


def _keyword_matches(keyword: str, text: str) -> bool:
    kw = keyword.lower().strip()
    if not kw:
        return False
    if re.fullmatch(r"[\x00-\x7f]+", kw):
        # 英文關鍵字要整個字比對：避免 "os" 命中 "cost"、"post"
        return re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", text) is not None
    return kw in text  # 中文沒有空白分詞，用子字串


def find_verified_answer(course, query):
    text = query.lower()
    with _conn() as c:
        rows = c.execute("SELECT keyword, answer FROM verified_answers WHERE course IN (?, ?)",
                         (course, config.ALL_COURSES)).fetchall()
    matches = [r for r in rows if _keyword_matches(r["keyword"], text)]
    if not matches:
        return None
    return max(matches, key=lambda r: len(r["keyword"]))["answer"]  # 最具體的關鍵字優先
