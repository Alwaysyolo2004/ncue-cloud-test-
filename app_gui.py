# ==============================================================================
# Project: NCUE AI Academic Portal
# Author: Michael Octavianus Henlianto Muliaba
# Date: October 2026
# Description: Dual-role RAG Academic Assistant with Professor Analytics
# ==============================================================================

import streamlit as st
from backend import load_rag_pipeline, ask_rag, process_uploaded_pdf, save_professor_answer
from analytics import log_query, get_query_analytics
from qa_manager import submit_direct_question, get_qa_list, update_qa_answer
from auth import authenticate_user, register_user  # Pastikan register_user di-import

st.set_page_config(page_title="NCUE AI Academic Portal", page_icon="🎓", layout="wide")

# Initialize Session State for Authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

# ==================== LOGIN & REGISTER SCREEN ====================
if not st.session_state.authenticated:
    st.title("🎓 NCUE AI Academic Portal")
    st.caption("Akses portal akademik pintar berbasis RAG untuk mahasiswa dan dosen.")
    
    # Membuat Tab untuk Login dan Pendaftaran Akun Baru
    tab_login, tab_register = st.tabs(["🔑 Sign In (Masuk)", "📝 Register (Daftar Akun Mahasiswa)"])
    
    with tab_login:
        with st.form("login_form"):
            st.subheader("Masuk ke Akun Anda")
            username_input = st.text_input("Username:")
            password_input = st.text_input("Password:", type="password")
            login_btn = st.form_submit_button("Sign In")
            
            if login_btn:
                user = authenticate_user(username_input, password_input)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success(f"Selamat datang kembali, {user['name']}!")
                    st.rerun()
                else:
                    st.error("Username atau password salah.")
                    
    with tab_register:
        with st.form("register_form"):
            st.subheader("Buat Akun Mahasiswa Baru")
            reg_name = st.text_input("Nama Lengkap:")
            reg_username = st.text_input("Buat Username:")
            reg_password = st.text_input("Buat Password:", type="password")
            reg_btn = st.form_submit_button("Daftar Sekarang")
            
            if reg_btn:
                if reg_name and reg_username and reg_password:
                    success, message = register_user(reg_username, reg_password, reg_name, role="Student")
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.warning("Mohon isi semua kolom pendaftaran.")
                    
    st.stop()  # Menghentikan eksekusi sampai user berhasil login

# Load Backend RAG Engine
@st.cache_resource
def init_backend():
    return load_rag_pipeline()

retriever, llm = init_backend()
current_user = st.session_state.user
role = current_user["role"]

# ==================== SIDEBAR CONFIGURATION ====================
with st.sidebar:
    st.header(f"👤 {current_user['name']}")
    st.caption(f"Role: {role}")
    
    if st.button("Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.rerun()
        
    st.divider()
    st.markdown("""
        <style>
        .hidden-watermark {
            color: transparent; /* Makes text completely invisible by default */
            font-size: 0.40rem;
            text-align: center;
            padding: 4px;
            border-radius: 2px;
            transition: all 0.3s ease;
            user-select: none; /* Prevents accidental highlighting when clicking */
        }
        .hidden-watermark:hover {
            color: #FFD700; /* Text turns gold when the cursor points directly at it */
            background-color: rgba(255, 255, 255, 0.05);
            font-weight: bold;
        }
        </style>
        
        <div class="hidden-watermark">
            🔑 Unique ID: NCUE-2026-MOHM-8839<br>
            Authd 龍021-112
        </div>
    """, unsafe_allow_html=True)

    course_list = ["General Handouts", "Operating Systems", "Computer Architecture", "Data Structures"]
    
    if role == "Professor":
        st.header("⚙️ Professor Controls")
        course = st.selectbox("Select Analytics Filter:", ["All Courses"] + course_list)
    else:
        st.header("⚙️ Student Portal")
        course = st.selectbox("Select Course:", course_list)
        
        st.divider()
        st.subheader("🕶️ Privacy Settings")
        is_anonymous = st.checkbox("Submit queries anonymously", value=False)
        st.caption("Applies to both AI chat logs and direct professor questions.")
        
        st.divider()
        st.subheader("📄 Handout Management")
        uploaded_file = st.file_uploader("Upload course PDF:", type=["pdf"])
        if uploaded_file is not None:
            if st.button("Process & Index Handout", use_container_width=True):
                with st.spinner("Analyzing and embedding PDF..."):
                    chunk_count = process_uploaded_pdf(uploaded_file)
                    st.success(f"Indexed {chunk_count} chunks into {course}!")
                    st.cache_resource.clear()

        st.markdown("""
        <style>
        .hidden-watermark {
            color: transparent; /* Makes text completely invisible by default */
            font-size: 0.40rem;
            text-align: center;
            padding: 4px;
            border-radius: 2px;
            transition: all 0.3s ease;
            user-select: none; /* Prevents accidental highlighting when clicking */
        }
        .hidden-watermark:hover {
            color: #FFD700; /* Text turns gold when the cursor points directly at it */
            background-color: rgba(255, 255, 255, 0.05);
            font-weight: bold;
        }
        </style>
        
        <div class="hidden-watermark">
            🔑 Unique ID: NCUE-2026-MOHM-8839<br>
            Authd 龍021-112
        </div>
    """, unsafe_allow_html=True)

# ==================== VIEW 1: STUDENT PORTAL ====================
if role == "Student":
    st.title(f"📚 {course} Study Assistant")
    
    # Sub-tabs for AI Chat vs Office Hours Q&A
    tab_chat, tab_office_hours = st.tabs(["💬 AI Handout Chat", "📬 Office Hours & Professor Q&A"])
    
    with tab_chat:
        st.caption("Ask questions about lecture notes, exam prep, or coding handouts.")
        chat_key = f"messages_{current_user['username']}"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for message in st.session_state[chat_key]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if "docs" in message and message["docs"]:
                    with st.expander("📌 View Retrieved Handout Context"):
                        for idx, doc in enumerate(message["docs"], 1):
                            st.markdown(f"**Chunk {idx}:**")
                            st.caption(doc.page_content)

        if user_query := st.chat_input("Ask a question about this course..."):
            log_query(course, user_query, current_user["username"], is_anonymous)
            st.session_state[chat_key].append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            with st.chat_message("assistant"):
                with st.spinner("Searching course knowledge base..."):
                    answer, docs = ask_rag(retriever, llm, user_query)
                    st.markdown(answer)
                    if docs:
                        with st.expander("📌 View Retrieved Handout Context"):
                            for idx, doc in enumerate(docs, 1):
                                st.markdown(f"**Chunk {idx}:**")
                                st.caption(doc.page_content)
                    st.session_state[chat_key].append({"role": "assistant", "content": answer, "docs": docs})

    with tab_office_hours:
        st.subheader("📬 Direct Office Hours Q&A")
        st.write("Send a private or direct question to your professor regarding course material. You can also view highlighted professor answers below.")
        
        with st.form("direct_q_form"):
            direct_question = st.text_area("Your Direct Question to the Professor:")
            submit_direct = st.form_submit_button("Submit Direct Question")
            if submit_direct:
                if direct_question:
                    submit_direct_question(course, direct_question, current_user["username"], is_anonymous)
                    st.success("Your question has been sent directly to the professor!")
                else:
                    st.warning("Please type a question before submitting.")
        
        st.divider()
        st.subheader("⭐ Highlighted & Answered Q&A Feed")
        qa_items = get_qa_list(course)
        highlighted_items = [q for q in qa_items if q["is_highlighted"]]
        
        if highlighted_items:
            for item in highlighted_items:
                with st.container(border=True):
                    st.markdown(f"**Q: {item['question']}**")
                    st.caption(f"Asked by: {item['student']} | {item['timestamp']}")
                    st.info(f"**Professor's Answer:**\n\n{item['answer']}")
        else:
            st.info("No highlighted professor Q&As for this course yet.")

# ==================== VIEW 2: PROFESSOR DASHBOARD ====================
else:
    st.title("👨‍🏫 Instructor Teaching Analytics & Office Hours Manager")
    
    tab_analytics, tab_direct_qa, tab_verified = st.tabs(["📊 Analytics & Top FAQs", "📬 Direct Student Inquiries", "⭐ Verified RAG Overrides"])
    
    analytics = get_query_analytics(course)
    
    with tab_analytics:
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Total AI Queries Logged", value=analytics["total_queries"])
        with col2:
            st.metric(label="Active Course Filter", value=course)
            
        st.divider()
        st.subheader("🔥 Top Frequently Asked Questions (AI)")
        if analytics["top_queries"]:
            for query_text, count in analytics["top_queries"]:
                st.info(f"**Question:** \"{query_text}\" — **Asked {count} time(s)**")
        else:
            st.write("No query activity logged yet.")

        st.divider()
        st.subheader("📜 Recent Activity Audit Log")
        if analytics["logs"]:
            st.dataframe(analytics["logs"], use_container_width=True)
        else:
            st.write("No recent logs found.")

    with tab_direct_qa:
        st.subheader("📬 Student Direct Questions & Office Hours Inquiries")
        st.write("Review personal questions sent by students. You can reply and check **'Highlight for Students'** to pin the answer to the course feed.")
        
        qa_list = get_qa_list(course)
        if qa_list:
            for item in qa_list:
                with st.container(border=True):
                    st.markdown(f"**Course:** {item['course']} | **Student:** {item['student']} ({item['timestamp']})")
                    st.markdown(f"**Question:** {item['question']}")
                    
                    with st.form(key=f"answer_form_{item['id']}"):
                        ans_input = st.text_area("Your Official Reply:", value=item["answer"])
                        highlight_toggle = st.checkbox("⭐ Highlight/Pin this Q&A for all students", value=item["is_highlighted"])
                        reply_btn = st.form_submit_button("Send Reply & Update")
                        
                        if reply_btn:
                            update_qa_answer(item["id"], ans_input, highlight_toggle)
                            st.success("Reply saved!")
                            st.rerun()
        else:
            st.write("No direct student inquiries found.")

    with tab_verified:
        st.subheader("⭐ Publish Professor Verified Answer (RAG Override)")
        st.write("Add an official answer that takes absolute priority when students ask matching questions in the AI chat.")
        
        with st.form("prof_answer_form"):
            keyword_input = st.text_input("Target Keyword or Question Phrase (e.g., 'batch system'):")
            answer_input = st.text_area("Official Definitive Answer:")
            submit_btn = st.form_submit_button("Publish Verified Answer")
            
            if submit_btn:
                if keyword_input and answer_input:
                    save_professor_answer(keyword_input, answer_input)
                    st.success(f"Successfully published verified answer for '{keyword_input}'!")
                else:
                    st.warning("Please fill in both fields.")

    
