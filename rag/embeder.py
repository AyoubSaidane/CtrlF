from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.supabase import SupabaseVectorStore
from supabase import create_client
from dotenv import load_dotenv
import os

class Embeder:
    def __init__(self):
        load_dotenv()
        
        self.SUPABASE_URL = os.getenv("SUPABASE_URL")
        self.SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        self.SUPABASE_CONNECTION_STRING = os.getenv("SUPABASE_CONNECTION_STRING")
        
        self.supabase = create_client(self.SUPABASE_URL, self.SUPABASE_KEY)
        self.embed_model = OpenAIEmbedding(model="text-embedding-ada-002")
        self.vector_store = SupabaseVectorStore(
            postgres_connection_string=self.SUPABASE_CONNECTION_STRING,
            collection_name="base_demo",
        )
        
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

    def embed_document(self, documents):
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=self.storage_context, 
            embed_model=self.embed_model
        )
        print("✅ Documents successfully embedded and stored in Supabase!")
        return index
    
    def retrieve_index(self):
        # Retrieve the index from the storage context
        index = VectorStoreIndex.from_vector_store(
            vector_store=self.vector_store,
            embed_model=self.embed_model
        )
        print("✅ Index successfully retrieved from Supabase!")
        return index

# Example usage:
if __name__ == "__main__":
    from parser import Parser
    parser = Parser()
    embeder = Embeder()
    docs = parser.parse_document(['PDF_026_investor-pulse-21-slideshow-221025.pdf'])
    index = embeder.embed_document(docs)