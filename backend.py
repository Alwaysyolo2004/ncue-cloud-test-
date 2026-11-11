import os
import sys
import json
import tempfile
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

PERSIST_DIR = "./chroma_db"
PROFESSOR_ANSWERS_FILE = "professor_answers.json"

def get_embeddings():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def process_uploaded_pdf(uploaded_file):
    """Saves an uploaded Streamlit file temporarily and indexes it into ChromaDB."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    try:
        loader = PyPDFLoader(tmp_path)
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = text_splitter.split_documents(documents)

        vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=get_embeddings(),
            persist_directory=PERSIST_DIR
        )
        return len(chunks)
    finally:
        os.remove(tmp_path)

def load_rag_pipeline():
    """Initializes and returns the vector database retriever and Gemini model."""
    vector_db = Chroma(
        persist_directory=PERSIST_DIR, 
        embedding_function=get_embeddings()
    )
    retriever = vector_db.as_retriever(search_kwargs={"k": 3})
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        api_key=os.getenv("GOOGLE_API_KEY")
    )
    return retriever, llm

def get_professor_answer(query: str):
    """Checks if a professor has provided a verified answer for this query topic."""
    if not os.path.exists(PROFESSOR_ANSWERS_FILE):
        return None
    try:
        with open(PROFESSOR_ANSWERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        query_lower = query.lower()
        for item in data:
            if item["keyword"].lower() in query_lower:
                return item["answer"]
    except Exception:
        return None
    return None

def save_professor_answer(keyword: str, answer: str):
    """Saves a professor's official answer to local storage."""
    data = []
    if os.path.exists(PROFESSOR_ANSWERS_FILE):
        try:
            with open(PROFESSOR_ANSWERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    data.append({"keyword": keyword.strip(), "answer": answer.strip()})
    with open(PROFESSOR_ANSWERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ask_rag(retriever, llm, query: str):
    """Executes RAG with Professor priority overrides and hybrid general knowledge fallback."""
    # 1. Check if Professor has provided a verified answer (Pillar 3)
    prof_answer = get_professor_answer(query)
    if prof_answer:
        return f"⭐ **[Professor Verified Answer]**\n\n{prof_answer}", []

    # 2. Retrieve Handout Chunks
    relevant_docs = retriever.invoke(query)
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    
    # 3. Hybrid Flexible Academic Prompt
    prompt = f"""You are an expert AI Academic Study Assistant for a university course. 
    Review the retrieved handout context below to answer the student's question.

    Retrieved Handout Context:
    {context}

    Instructions:
    - If the student asks for a summary, review, or overview of the material, synthesize the provided text chunks.
    - If the answer is directly in the context, provide a clear, well-structured explanation.
    - If the context lacks enough detail or does not cover the question, use your general academic and technical knowledge to explain the concept fully, but you MUST prepend your response with this exact note: 
      *(Note: This concept is not explicitly detailed in your current handout chunks, but generally speaking...)*

    Student Question: {query}"""
    
    response = llm.invoke(prompt)
    content = response.content
    if isinstance(content, list):
        answer = "".join(b.get("text", "") for b in content if isinstance(b, dict))
    else:
        answer = str(content)
        
    return answer, relevant_docs