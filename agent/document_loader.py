"""
Document Loader for Enterprise RAG.
Loads various file types (PDF, CSV, Excel, TXT, MD) and extracts text.
"""
import logging
import os
from typing import List, Optional
import pandas as pd
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredFileLoader

logger = logging.getLogger(__name__)

def load_document(file_path: str, original_filename: str) -> List[Document]:
    """Loads a document and returns a list of LangChain Document objects."""
    logger.info("Loading document: %s", original_filename)
    docs = []
    
    ext = os.path.splitext(original_filename)[1].lower()
    
    try:
        if ext == '.pdf':
            loader = PyPDFLoader(file_path)
            docs = loader.load()
        elif ext in ['.txt', '.md']:
            loader = TextLoader(file_path, autodetect_encoding=True)
            docs = loader.load()
        elif ext == '.csv':
            df = pd.read_csv(file_path)
            for idx, row in df.iterrows():
                content = []
                for col in df.columns:
                    val = row[col]
                    if pd.notna(val):
                        content.append(f"{col}: {val}")
                if content:
                    text = "\n".join(content)
                    docs.append(Document(
                        page_content=text, 
                        metadata={
                            "source": original_filename,
                            "row": idx + 1
                        }
                    ))
        elif ext in ['.xls', '.xlsx']:
            # Load all sheets independently
            excel_data = pd.read_excel(file_path, sheet_name=None)
            for sheet_name, df in excel_data.items():
                # Get column headers
                headers = list(df.columns)
                header_str = " | ".join(str(h) for h in headers)
                
                current_batch = []
                current_chars = 0
                batch_start_row = 2 # Excel rows start at 2 (1 is header)
                
                for idx, row in df.iterrows():
                    row_num = idx + 2
                    content = []
                    for col in headers:
                        val = row[col]
                        if pd.notna(val):
                            content.append(f"{col}: {val}")
                            
                    if not content:
                        continue
                        
                    row_text = f"Row {row_num}: " + " | ".join(content)
                    
                    # If adding this row exceeds ~1000 chars and we have something, flush
                    if current_chars + len(row_text) > 1000 and current_batch:
                        batch_text = f"Workbook: {original_filename}\nWorksheet: {sheet_name}\nHeaders: {header_str}\n\n" + "\n".join(current_batch)
                        docs.append(Document(
                            page_content=batch_text,
                            metadata={
                                "source": original_filename,
                                "workbook": original_filename,
                                "sheet_name": sheet_name,
                                "row_start": batch_start_row,
                                "row_end": row_num - 1,
                                "file_type": ext
                            }
                        ))
                        current_batch = []
                        current_chars = 0
                        batch_start_row = row_num
                        
                    current_batch.append(row_text)
                    current_chars += len(row_text)
                
                # Flush remainder
                if current_batch:
                    batch_text = f"Workbook: {original_filename}\nWorksheet: {sheet_name}\nHeaders: {header_str}\n\n" + "\n".join(current_batch)
                    docs.append(Document(
                        page_content=batch_text,
                        metadata={
                            "source": original_filename,
                            "workbook": original_filename,
                            "sheet_name": sheet_name,
                            "row_start": batch_start_row,
                            "row_end": len(df) + 1,
                            "file_type": ext
                        }
                    ))
        else:
            logger.warning("Unsupported file type: %s", ext)
            # fallback to generalized unstructured loader
            try:
                loader = UnstructuredFileLoader(file_path)
                docs = loader.load()
            except Exception as e:
                logger.error("Failed unstructured load for %s: %s", original_filename, e)
                
        # Attach custom metadata
        for doc in docs:
            doc.metadata['source'] = original_filename
            doc.metadata['file_type'] = ext

        return docs
    except Exception as e:
        logger.error("Error loading document %s: %s", original_filename, e, exc_info=True)
        return []
