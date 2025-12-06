# livekit_agents/rag_retriever.py
import os
import json
import logging
from typing import List, Dict, Any

from ..config import RAG_DATA_FILE # Import the file path

try:
    # Requires: pip install chromadb langchain-community
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import OllamaEmbeddings 
    from langchain_core.documents import Document
except ImportError as e:
    logging.warning(f"RAG dependencies not installed: {e}. RAG mode will not work.")
    Chroma, OllamaEmbeddings, Document = None, None, None

class RAGRetriever:
    """Handles vector store persistence, loading, and context retrieval for the RAG Engine."""

    def __init__(self, db_path: str, llm_model_name: str = "llama3"):
        if not Chroma or not OllamaEmbeddings:
            raise RuntimeError("RAG dependencies (chromadb, langchain-community) are missing.")
        
        self.logger = logging.getLogger("RAGRetriever")
        self.embedding_function = OllamaEmbeddings(model=llm_model_name)
        self.db_path = db_path
        self.vectorstore = self._load_or_create_db()
        self.k = 3 # Default context size

    def _load_data_from_file(self) -> List[Dict[str, Any]]:
        """Loads the structured interruption data from the specified JSON file."""
        if not os.path.exists(RAG_DATA_FILE):
            self.logger.error(f"Interruption data file not found at: {RAG_DATA_FILE}")
            # IMPORTANT: Fall back to an empty list to avoid crashing the indexing process
            return []
            
        with open(RAG_DATA_FILE, 'r') as f:
            # Assuming the JSON file structure is a list of [ {user:{...}}, {assistant:{...}} ] pairs
            raw_data = json.load(f)
        
        # We need to flatten the [ {user}, {assistant} ] format into a single dict per example
        processed_data = []
        for pair in raw_data:
            if len(pair) == 2 and 'user' in pair[0] and 'assistant' in pair[1]:
                user_info = pair[0]['content'].split('|')
                
                # Extract clean user content and features
                user_content = user_info[0].strip()
                features = " ".join([f.strip() for f in user_info[1:]])
                decision = pair[1]['content']
                
                processed_data.append({
                    "user_content": user_content,
                    "features": features,
                    "decision": decision
                    # Note: We skip the 'reason' field as it's not present in your preview
                })
        
        self.logger.info(f"Successfully processed {len(processed_data)} rules from {RAG_DATA_FILE}.")
        return processed_data


    def _load_or_create_db(self):
        """Loads the database if it exists, otherwise indexes the file data and persists."""
        
        collection_name = "interruption_knowledge"
        
        # 1. Check for Persistence: Load if files exist in the path
        if os.path.exists(self.db_path) and len(os.listdir(self.db_path)) > 0:
            print(f"✅ Loading existing Chroma DB from: {self.db_path}")
            return Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embedding_function,
                collection_name=collection_name
            )

        # 2. Indexing: Load file, create, and persist the new database
        print(f"🛠 Creating and persisting new Chroma DB at: {self.db_path}")
        os.makedirs(self.db_path, exist_ok=True)
        
        # Load the actual data
        structured_data = self._load_data_from_file()
        
        if not structured_data:
            print("⚠️ Cannot index: Structured data file could not be loaded or was empty. Fallback to in-memory.")
            # Fallback to an in-memory, empty store to prevent crashes
            return Chroma(embedding_function=self.embedding_function)


        documents = []
        for item in structured_data: 
            # Construct clear, instructional text for the LLM
            content = (
                f"RULE: If User Input is '{item['user_content']}' (with features: {item['features']}) "
                f"then the decision must be {item['decision']}. "
            )
            
            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "decision": item["decision"], 
                        "features": item["features"],
                        "source": "interrupt_dataset_15k"
                    }
                )
            )

        # Create the vector store
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self.embedding_function,
            collection_name=collection_name,
            persist_directory=self.db_path 
        )
        
        # Explicitly save the data to disk
        vectorstore.persist()
        print("✅ Chroma DB indexing complete and persisted.")
        return vectorstore

    async def get_relevant_context(self, query: str, k: int) -> str:
        """Retrieves top-k documents based on the user's query."""
        results = self.vectorstore.similarity_search(query, k=k)
        
        # Format the results into a single string for the LLM prompt
        context = "\n".join([doc.page_content for doc in results])
        return context