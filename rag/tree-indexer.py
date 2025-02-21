from llama_index.core import StorageContext, TreeIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.supabase import SupabaseVectorStore
from supabase import create_client
from parser import Parser

from dotenv import load_dotenv
import os

load_dotenv()

class TreeIndexer:
    def __init__(self):
        load_dotenv()
        
        self.SUPABASE_URL = os.getenv("SUPABASE_URL")
        self.SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        self.SUPABASE_CONNECTION_STRING = os.getenv("SUPABASE_CONNECTION_STRING")

        self.supabase = create_client(self.SUPABASE_URL, self.SUPABASE_KEY)
        self.vector_store = SupabaseVectorStore(
            postgres_connection_string=self.SUPABASE_CONNECTION_STRING,
            collection_name="base_demo",
        )
        
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        

    def get_node_name(self, index, node_id):
        """Returns the node name if metadata exists, otherwise a fallback label"""
        metadata = index.docstore.docs[node_id].metadata
        if metadata and len(metadata) > 0:
            return metadata['file_name'] + ':' + str(metadata['page_number'])
        return "Special_nodes"

    def print_tree(self, index, node_id, prefix="", is_last=True):
        tree = index.index_struct.node_id_to_children_ids
        # For the root call, print a special "Root" label.
        branch = "└── " if is_last else "├── "
        print(prefix + branch + self.get_node_name(index, node_id))

        children = tree.get(node_id, [])
        # Prepare the new prefix for children: if current node is last, use spaces; otherwise, use a vertical line.
        new_prefix = prefix + ("  " if is_last else "│   ")
        for i, child in enumerate(children):
            # Determine if the child is the last one in its group.
            self.print_tree(index, child, new_prefix, i == len(children) - 1)

    def retrieve_index(self):
        # Retrieve the index from the storage context
        index = TreeIndex.from_vector_store(
            vector_store=self.vector_store
        )
        print("✅ Index successfully retrieved from Supabase!")
        return index

    def index_document(self, documents):
        index = TreeIndex.from_documents(
            documents,
            storage_context=self.storage_context, 
            include_metadata=True
        )
        print("✅ Documents successfully embedded and stored in Supabase!")
        return index


if __name__ == "__main__":
    from parser import Parser
    parser = Parser()
    treeIndexer = TreeIndexer()
    parsed_documents = parser.parse_directory(os.getcwd()+'/prez')
    index = treeIndexer.index_document(parsed_documents)
    for root in index.index_struct.root_nodes.values():
        treeIndexer.print_tree(index, root)