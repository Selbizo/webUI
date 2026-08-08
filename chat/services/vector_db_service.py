import os
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class VectorDBService:
    """Сервис для управления векторными базами данных с FAISS"""

    def __init__(self, vector_db_dir=None):
        if vector_db_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            vector_db_dir = project_root / 'vectorDB'

        self.vector_db_dir = Path(vector_db_dir)
        self.vector_db_dir.mkdir(parents=True, exist_ok=True)

    def create_db(self, db_name):
        db_path = self.get_db_path(db_name)
        if db_path.exists():
            raise ValueError(f"Векторная база уже существует: {db_name}")

        db_path.mkdir(parents=True, exist_ok=True)
        (db_path / 'Files').mkdir(exist_ok=True)

        metadata = {
            'name': db_name,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'description': '',
            'total_chunks': 0,
            'embedding_dimensions': 0,
            'documents': []
        }

        metadata_path = db_path / 'metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Создана векторная база: {db_name}")
        return db_name

    def get_db_path(self, db_name):
        return self.vector_db_dir / db_name

    def delete_db(self, db_name):
        db_path = self.get_db_path(db_name)
        if not db_path.exists():
            raise ValueError(f"Векторная база не найдена: {db_name}")

        import shutil
        shutil.rmtree(db_path)
        logger.info(f"Удалена векторная база: {db_name}")
        return True

    def get_db_list(self):
        databases = []
        if not self.vector_db_dir.exists():
            return databases

        for item in sorted(self.vector_db_dir.iterdir()):
            if item.is_dir() and (item / 'metadata.json').exists():
                try:
                    metadata_path = item / 'metadata.json'
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    databases.append(metadata)
                except Exception as e:
                    logger.error(f"Ошибка чтения метаданных {item}: {e}")

        return databases

    def get_db_info(self, db_name):
        db_path = self.get_db_path(db_name)
        if not db_path.exists():
            raise ValueError(f"Векторная база не найдена: {db_name}")

        metadata_path = db_path / 'metadata.json'
        if not metadata_path.exists():
            raise ValueError(f"Метаданные не найдены: {db_name}")

        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_metadata(self, db_name, metadata):
        db_path = self.get_db_path(db_name)
        metadata_path = db_path / 'metadata.json'
        metadata['updated_at'] = datetime.now().isoformat()

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def add_document(self, db_name, file_path, file_relative_path):
        db_info = self.get_db_info(db_name)

        doc_entry = {
            'file_path': file_relative_path,
            'added_at': datetime.now().isoformat(),
            'chunk_count': 0,
            'status': 'pending',
            'size_bytes': 0
        }

        db_info['documents'].append(doc_entry)
        self.save_metadata(db_name, db_info)
        return doc_entry

    def update_document_status(self, db_name, file_path, chunk_count, status='indexed', size_bytes=0):
        db_info = self.get_db_info(db_name)

        for doc in db_info['documents']:
            if doc['file_path'] == file_path:
                doc['chunk_count'] = chunk_count
                doc['status'] = status
                doc['size_bytes'] = size_bytes
                break

        self.save_metadata(db_name, db_info)
        return db_info

    def list_documents(self, db_name):
        db_info = self.get_db_info(db_name)
        return db_info.get('documents', [])

    def list_files_for_indexing(self, db_name):
        db_path = self.get_db_path(db_name)
        files_dir = db_path / 'Files'

        if not files_dir.exists():
            return []

        supported = {'.txt', '.md', '.markdown', '.json', '.csv', '.docx', '.pdf', '.xlsx', '.xls'}
        files = []

        for item in sorted(files_dir.rglob('*')):
            if item.is_file() and item.suffix.lower() in supported:
                files.append({
                    'path': str(item),
                    'name': item.name,
                    'relative_path': str(item.relative_to(db_path)),
                    'size': item.stat().st_size
                })

        return files

    def clear_documents(self, db_name):
        db_info = self.get_db_info(db_name)
        db_info['documents'] = []
        self.save_metadata(db_name, db_info)
        return True
