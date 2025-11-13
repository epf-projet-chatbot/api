from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, JSONLoader, UnstructuredMarkdownLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import re
import unicodedata
from typing import List
from langchain.schema import Document
import spacy

# Load spacy model
nlp = spacy.load("fr_core_news_sm")

def load_documents(folder_path):
    """Charge tous les documents d'un dossier"""
    docs = []
    def aux_load_documents(folder, docs):
        for file in Path(folder).glob("**/*"):
            if file.is_file():
                if file.suffix == ".pdf":
                    loader = PyPDFLoader(str(file))
                    docs.extend(loader.load())
                elif file.suffix == ".md":
                    loader = UnstructuredMarkdownLoader(str(file))
                    docs.extend(loader.load())
                elif file.suffix == ".json":
                    loader = JSONLoader(str(file), jq_schema='.', text_content=False)
                    docs.extend(loader.load())
    aux_load_documents(folder_path, docs)
    return docs

def clean_text(text: str) -> str:
    """
    Nettoie le texte en supprimant les espaces inutiles, les sauts de ligne excessifs,
    les en-têtes Markdown, et les références entre crochets.
    Args:
        text (str): Le texte à nettoyer.
    Returns:
        str: Le texte nettoyé.
    """
    # Normalisation Unicode
    text = unicodedata.normalize("NFKC", text)
    # Supprimer les emojis et symboles non alphanumériques
    text = re.sub(r"[^\w\s.,;:!?()\[\]\-’\"'éèàùâêîôûçÉÈÀÙÂÊÎÔÛÇ]", "", text)
    # Supprimer les en-têtes Markdown
    text = re.sub(r"^#+\s?", "", text, flags=re.MULTILINE)
    # Supprimer les mentions de type "Page X", "Chapitre X"
    # Supprimer la table des matières (naïvement via détection de titres + numéros de pages)
    lines = text.split('\n')
    lines = [line for line in lines if not re.match(r"^[\d\s]*[A-Z][A-Za-z\s]+\.{3,}\s*\d{1,3}$", line)]
    text = "\n".join(lines)
    # Supprimer la table des matières (naïvement via détection de titres + numéros de pages)
    lines = [line for line in lines if not re.match(r"^[\d\s]*[A-Z][A-Za-z\s]+\.{3,}\s*\d{1,3}$", line)]
    text = "\n".join(lines)
    return text

def lemmatize_text(text: str) -> str:
    """Lemmatisation du texte"""
    text_doc = nlp(text)
    return " ".join([token.lemma_ for token in text_doc if not token.is_stop and not token.is_punct])

def clean_documents(docs, lemmatize=False) -> List[Document]:
    """Nettoie les documents"""
    for doc in docs:
        if doc.page_content:
            if lemmatize:
                doc.page_content = clean_text(lemmatize_text(doc.page_content))
            else:
                doc.page_content = clean_text(doc.page_content)
    
    return docs

def chunk_documents(documents, chunk_size, chunk_overlap):
    """Divise les documents en chunks"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap, 
        separators=["\n\n", "\n", ".", " "]
    )
    return text_splitter.split_documents(documents)

def process_documents(folder_path, chunk_size=1000, chunk_overlap=200, lemmatize=False):
    """Charge et divise les documents en chunks"""
    documents = load_documents(folder_path)
    documents = clean_documents(documents, lemmatize=lemmatize)
    
    if not documents:
        return []
    
    return chunk_documents(documents, chunk_size, chunk_overlap)

if __name__ == "__main__":
    chunks = process_documents("data", 1000, 200)