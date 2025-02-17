from llama_cloud_services import LlamaParse
from llama_index.core import SimpleDirectoryReader
from dotenv import load_dotenv
import os

class Parser:
    def __init__(self):
        load_dotenv()
        self.llama_cloud_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.parser = self._initialize_parser()
        
    def _initialize_parser(self):
        return LlamaParse(
            api_key=self.llama_cloud_api_key,
            use_vendor_multimodal_model=True,
            vendor_multimodal_model_name="gemini-2.0-flash-001",
            system_prompt_append="give me an exhaustive description of every chart. Include everything: layout, text, images, graphs, etc. You also need to give me an explanation of the slide: what is the overall message that is conveyed.",
            result_type="markdown",
            page_prefix="START OF PAGE: {pageNumber}\n",
            page_suffix="\nEND OF PAGE: {pageNumber}\n"
        )
    
    def parse_document(self, file_path):
        file_extractor = {".pdf": self.parser}
        documents = SimpleDirectoryReader(
            input_files=file_path, 
            filename_as_id=True,
            file_extractor=file_extractor
        ).load_data()
        
        # Extraire et incrémenter le numéro de page à partir du doc_id
        for doc in documents:
            try:
                # Récupérer le dernier élément après le dernier "_"
                page_str = doc.doc_id.split('_')[-1]
                # Convertir en entier et incrémenter de 1
                doc.metadata['page_number'] = int(page_str) + 1
            except (ValueError, IndexError):
                print(f"Warning: Could not extract page number from doc_id: {doc.doc_id}")
                doc.metadata['page_number'] = 0
        
        print(f"Parsed {len(documents)} documents")
        
        return documents

    def preview_text(self, documents, preview_length=500):
        return documents[0].text[:preview_length]
    
if __name__ == "__main__":
    parser = Parser()
    docs = parser.parse_document(['PDF_026_investor-pulse-21-slideshow-221025.pdf'])
    preview = parser.preview_text(docs)
    print("Document Preview:")
    print("-" * 50)
    print(preview)
    print("-" * 50)