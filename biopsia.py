from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from config import CHROMA_PATH, EMBEDDING_MODEL

embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings, collection_name='balanceos')

# Obtenemos los primeros 3 fragmentos para ver qué son
data = vectorstore.get(limit=3)

print("\n" + "!"*40)
print("BIOPSIA DE MEMORIA")
print("!"*40)

for i in range(len(data['documents'])):
    print(f"\n--- FRAGMENTO {i+1} ---")
    print(f"CONTENIDO: {data['documents'][i][:300]}...") # Ver primeros 300 caracteres
    print(f"METADATOS: {data['metadatas'][i]}")

print("\n" + "!"*40)