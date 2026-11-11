import json
import os
from datetime import datetime

QA_FILE = "direct_questions.json"

def init_qa_file():
    """Initializes the direct Q&A storage file if it doesn't exist."""
    if not os.path.exists(QA_FILE):
        with open(QA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

def submit_direct_question(course: str, question: str, username: str, is_anonymous: bool):
    """Submits a direct personal question to the professor."""
    init_qa_file()
    student_label = "Anonymous Student" if is_anonymous else username
    
    entry = {
        "id": str(datetime.now().timestamp()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "course": course,
        "student": student_label,
        "question": question.strip(),
        "answer": "",
        "status": "Pending",
        "is_highlighted": False
    }
    
    with open(QA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.append(entry)
    with open(QA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_qa_list(course: str = None):
    """Retrieves all direct questions for a course."""
    init_qa_file()
    try:
        with open(QA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
        
    if course and course != "All Courses":
        return [d for d in data if d.get("course") == course]
    return data

def update_qa_answer(qid: str, answer: str, is_highlighted: bool):
    """Allows a professor to answer a question and choose whether to highlight it."""
    init_qa_file()
    with open(QA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for item in data:
        if item["id"] == qid:
            item["answer"] = answer.strip()
            item["status"] = "Answered"
            item["is_highlighted"] = is_highlighted
            
    with open(QA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)