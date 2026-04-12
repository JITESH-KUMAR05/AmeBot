# main entry point

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os


from models import chatResponse,chatRequest, HealthResponse
from chat import chat as process_chat
from retriever import load_index, is_loaded, get_total_chunks

# we will use lifespan instead of @app.on_event("startup") to load the index
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    print("\n"+ "="*50)
    print("starting Amenify Support Bot...")
    print("="*50 + "\n")

    try:
        print("loading faiss index...")
        load_index()
        print(f"faiss index loaded successfully! total chunks: {get_total_chunks()}")
    except FileNotFoundError:
        print("faiss index not found.")
        raise

    print("\n"+ "="*50)
    print("Amenify Support Bot is ready to serve!")
    print("="*50 + "\n")
    yield
    # shutdown
    print("\n"+ "="*50)
    print("shutting down Amenify Support Bot...")
    print("="*50 + "\n")


# app creation
app = FastAPI(
    title="Amenify Support Bot",
    description=(
        "AI-powered customer support bot for Amenify. "
        "Answers questions using Amenify's knowledge base via RAG "
        "(Retrieval Augmented Generation) with Azure OpenAI."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)



# get /health for health check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    health check endpoint to check if the server is running and index is loaded
    """
    loaded = is_loaded()
    return HealthResponse(
        status="ok" if loaded else "discarded",
        index_loaded=loaded,
        total_chunks=get_total_chunks() if loaded else 0
    )

@app.post("/chat", response_model=chatResponse)
async def chat_endpoint(request: chatRequest):

    if not is_loaded():
        raise HTTPException(status_code=503, detail="Index not loaded yet. Please try again later.")
    try:
        result = process_chat(
            message=request.message,
            session_id=request.session_id,
        )

        return chatResponse(
            answer=result["answer"],
            session_id=result["session_id"],
            sources=result["sources"],
            found_in_kb=result["found_in_kb"]
        )
    except Exception as e:
        print(f"Error processing chat: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the chat.")

# entry point 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

# Mount static frontend LAST — after all API routes are registered.
# StaticFiles only handles GET/HEAD; mounting at "/" before API routes
# would intercept POST /chat and return 405 Method Not Allowed.
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")