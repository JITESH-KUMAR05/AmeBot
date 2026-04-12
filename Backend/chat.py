# FLOW for each user message:
#   1. Validate input
#   2. Fetch session history (needed for query rewriting)
#   3. Rewrite query if follow-up (e.g. "who founded it" → "who founded Amenify")
#   4. Retrieve relevant chunks from FAISS using the rewritten query
#   5. If no relevant chunks → return "I don't know" (NO LLM call)
#   6. Build prompt: system instructions + retrieved context + chat history
#   7. Call Azure OpenAI GPT with the ORIGINAL message (not rewritten)
#   8. Save both turns to session history
#   9. Return structured response

from openai import AzureOpenAI
from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    MAX_HISTORY
)

from retriever import retrieve
from session import create_session, get_history, add_message

_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
)

SYSTEM_PROMPT = """You are a friendly and professional customer support assistant for Amenify.
Amenify is an AI-powered resident commerce platform providing home services (cleaning, handyman, grocery delivery, dog walking, and more) for apartment residents and property managers across the United States.

STRICT RULES — you must follow these without exception:
1. Answer ONLY using the information in the CONTEXT section below.
2. Do NOT use any outside knowledge, training data, or assumptions.
3. If the context does not contain a clear answer, respond with exactly:
   "I don't have information about that. For further help, please contact Amenify support at +1-719-767-1963 or visit amenify.com/contact-us"
4. Never fabricate prices, phone numbers, dates, URLs, or coverage amounts.
5. Be concise — answer in 2-5 sentences unless a list is genuinely clearer.
6. If the user greets you (hi, hello, hey), respond warmly and ask how you can help with Amenify services.
7. Maintain the context of the conversation — refer to earlier messages when relevant.

CONTEXT (from Amenify knowledge base):
---
{context}
---"""

NO_ANSWER_RESPONSE = (
    "I don't have information about that. "
    "For further help, please contact Amenify support at +1-719-767-1963 "
    "or visit amenify.com/contact-us"
)

def _build_context(chunks: list[dict]) -> str:
    """
    Build a single context string from retrieved chunks
    """
    if not chunks:
        return "No relevant information available."
    
    # # Sort by source to keep related chunks together
    # chunks.sort(key=lambda x: x["source"])
    
    parts = []
    for i,chunk in enumerate(chunks, start=1):
        parts.append(f"[Source {i} - {chunk['source']}]\n{chunk['text']}\n")
    
    return "\n".join(parts)

def _call_llm(messages: list[dict]) -> str:
    """
    Call Azure OpenAI with the given messages
    """
    try:
        response = _client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=messages,
            temperature=0,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return NO_ANSWER_RESPONSE


def _rewrite_query(message: str, history: list[dict]) -> str:
    """
    Rewrite vague follow-up questions for better FAISS retrieval.

    FAISS embeds messages in isolation — it has no awareness of conversation
    history. So "who founded it" gets embedded as-is and may not match the
    right KB chunks because "it" is semantically empty.

    This function detects follow-up pronouns and appends the last user
    message as context so the combined query is specific enough for FAISS.

    Example:
      history[-2].content = "What is Amenify?"
      message              = "who founded it"
      result               = "who founded it What is Amenify?"
      → FAISS now finds the 'About Amenify' chunk correctly ✅

    The rewritten query is used ONLY for FAISS retrieval.
    The original message is still passed to the LLM so the conversation
    feels natural.
    """
    # Pronouns and demonstratives that signal a follow-up question
    FOLLOW_UP_WORDS = {
        'it', 'its', 'they', 'their', 'them',
        'that', 'this', 'he', 'she', 'there',
        'he\'s', 'she\'s', 'it\'s', 'they\'re',
    }

    words = set(message.lower().split())
    is_follow_up = bool(words & FOLLOW_UP_WORDS)

    if is_follow_up and len(history) >= 1:
        # Find the most recent user turn in history
        last_user_msg = ""
        for msg in reversed(history):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if last_user_msg:
            rewritten = f"{message} {last_user_msg}"
            print(f"[query rewrite] '{message}' → '{rewritten}'")
            return rewritten

    return message


def chat(message: str, session_id: str | None = None) -> dict:
    """
    Handle a chat message and return a structured response

     Returns:
        {
            "answer"      : str   — the bot's reply
            "session_id"  : str   — use this for the next message
            "sources"     : list  — KB document titles used (empty if not found)
            "found_in_kb" : bool  — False triggers "I don't know" path
        }
    """
    # 1. Session management
    if not session_id:
        session_id = create_session()

    # 2. Clean input
    message = message.strip()

    # 3. Fetch history BEFORE retrieval — needed for query rewriting
    history = get_history(session_id)

    # 4. Rewrite vague follow-up queries for better FAISS recall
    #    e.g. "who founded it" → "who founded it What is Amenify?"
    #    Only the search query is rewritten — the LLM still sees the original.
    search_query = _rewrite_query(message, history)

    # 5. Retrieve using the (possibly enriched) query
    chunks = retrieve(search_query)
    found_in_kb = len(chunks) > 0

    # 6. Short-circuit — no relevant chunks found
    if not found_in_kb:
        add_message(session_id, "user", message)
        add_message(session_id, "assistant", NO_ANSWER_RESPONSE)
        return {
            "answer": NO_ANSWER_RESPONSE,
            "session_id": session_id,
            "sources": [],
            "found_in_kb": False,
        }

    # 7. Build context string from retrieved chunks
    context = _build_context(chunks)

    # 8. Assemble messages for the LLM
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        *history,
        {"role": "user", "content": message},
    ]

    # 9. Call Azure OpenAI
    answer = _call_llm(messages)

    # 10. Persist both turns
    add_message(session_id, "user", message)
    add_message(session_id, "assistant", answer)

    # 11. Return structured response
    return {
        "answer": answer,
        "session_id": session_id,
        "sources": [chunk["source"] for chunk in chunks],
        "found_in_kb": True,
    }