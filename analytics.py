import json
import os
from datetime import datetime
from collections import Counter

LOG_FILE = "student_queries.json"

def log_query(course: str, query: str, username: str, is_anonymous: bool):
    """Logs student questions, masking identity if anonymous is selected."""
    logged_user = "Anonymous Student" if is_anonymous else username
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "course": course,
        "query": query.strip(),
        "student": logged_user
    }
    
    data = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
            
    data.append(entry)
    
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_query_analytics(course: str = None):
    """Retrieves aggregated query statistics for the professor dashboard."""
    if not os.path.exists(LOG_FILE):
        return {"total_queries": 0, "top_queries": [], "logs": []}
        
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"total_queries": 0, "top_queries": [], "logs": []}

    if course and course != "All Courses":
        filtered = [d for d in data if d.get("course") == course]
    else:
        filtered = data

    queries = [d["query"].strip() for d in filtered if "query" in d]
    counter = Counter(queries)
    
    return {
        "total_queries": len(filtered),
        "top_queries": counter.most_common(5),
        "logs": list(reversed(filtered))
    }