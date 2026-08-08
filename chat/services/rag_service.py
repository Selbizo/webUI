import os
import json
import logging
import faiss
import numpy as np
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

from .embedding_service import EmbeddingService
from .document_parser import DocumentParser
from .vector_db_service import VectorDBService


class RagService:
    """
    Сервис для RAG (Retrieval-Augmented Generation).
    Объединяет: парсинг документов, генерацию эмбеддингов,
    индексацию FAISS и поиск.
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.document_parser = DocumentParser()
        self.vector_db_service = VectorDBService()

    # =================================================================
    # ИНДЕКСАЦИЯ
    # =================================================================

    def index_file(self, db_name, file_path):
        """
        Индексирует один файл в векторную базу данных.
        Возвращает словарь с информацией о чанках.
        """
        try:
            # Парсим файл
            text = self.document_parser.parse_file(file_path)
            logger.info(f"Прочитан файл {file_path}: {len(text)} символов")

            # Разбиваем на чанки
            chunks = self.embedding_service.chunk_text(text, max_chars=1000, overlap=100)
            logger.info(f"Создано чанков: {len(chunks)}")

            if not chunks:
                return {'status': 'error', 'error': 'Нет текста для индексации'}

            # Генерируем эмбеддинги
            embeddings = self.embedding_service.generate_embeddings_batch(chunks)

            if not embeddings:
                return {'status': 'error', 'error': 'Не удалось создать эмбеддинги'}

            # Вычисляем относительный путь
            db_path = self.vector_db_service.get_db_path(db_name)
            file_relative = str(Path(file_path).relative_to(db_path / 'Files'))

            # Сохраняем чанки и эмбеддинги в отдельный файл
            chunks_data = {
                'file_path': file_relative,
                'chunks': chunks,
                'embeddings': embeddings,
                'indexed_at': datetime.now().isoformat()
            }

            chunks_file = db_path / f'chunks_{hash(file_path) & 0xFFFFFFFF}.json'
            with open(chunks_file, 'w', encoding='utf-8') as f:
                # numpy arrays нельзя сериализовать через json, преобразуем
                chunks_data['embeddings'] = [list(e) for e in embeddings]
                json.dump(chunks_data, f, ensure_ascii=False, indent=2)

            # Обновляем метаданные
            self.vector_db_service.update_document_status(
                db_name, file_relative, len(chunks), 'indexed', len(text)
            )

            return {
                'status': 'success',
                'chunks_count': len(chunks),
                'embedding_dim': len(embeddings[0]) if embeddings else 0
            }

        except Exception as e:
            logger.error(f"Ошибка индексации файла {file_path}: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}

    def build_index(self, db_name, file_paths=None):
        """
        Строит полный индекс FAISS для векторной базы.
        Переиндексирует все документы.

        Args:
            db_name: Имя базы данных
            file_paths: Список файлов для индексации (если None — все файлы из Files/)
        """
        # Получаем путь к базе
        db_path = self.vector_db_service.get_db_path(db_name)
        files_dir = db_path / 'Files'

        if not files_dir.exists():
            raise ValueError(f"Директория Files не найдена: {files_dir}")

        # Собираем файлы для индексации
        if file_paths:
            files_to_index = [Path(fp) for fp in file_paths]
        else:
            supported = self.document_parser.get_supported_extensions()
            files_to_index = []
            for ext in supported:
                files_to_index.extend(files_dir.rglob(f'*{ext}'))
            files_to_index = [f for f in files_to_index if f.is_file()]

        if not files_to_index:
            raise ValueError("Нет файлов для индексации")

        logger.info(f"Начинаем индексацию {len(files_to_index)} файлов для БД: {db_name}")

        all_chunks = []
        all_embeddings = []
        chunk_metadata = []  # (file_path, chunk_index, chunk_text)
        total_chunks = 0

        for i, file_path in enumerate(files_to_index):
            logger.info(f"  [{i+1}/{len(files_to_index)}] Индексирую: {file_path.name}")

            try:
                text = self.document_parser.parse_file(file_path)
                chunks = self.embedding_service.chunk_text(text, max_chars=1000, overlap=100)

                if not chunks:
                    continue

                embeddings = self.embedding_service.generate_embeddings_batch(chunks)

                file_relative = str(file_path.relative_to(files_dir))

                for j, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                    all_chunks.append(chunk)
                    all_embeddings.append(emb)
                    chunk_metadata.append({
                        'file_path': file_relative,
                        'chunk_index': j,
                        'file_name': file_path.name
                    })

                total_chunks += len(chunks)

                # Обновляем метаданные документа
                self.vector_db_service.update_document_status(
                    db_name, file_relative, len(chunks), 'indexed', len(text)
                )

            except Exception as e:
                logger.error(f"Ошибка обработки {file_path}: {e}")
                self.vector_db_service.update_document_status(
                    db_name, str(file_path.relative_to(files_dir)), 0, 'error'
                )

        if not all_embeddings:
            raise ValueError("Нет эмбеддингов для построения индекса")

        # Преобразуем в numpy массив
        embeddings_array = np.array(all_embeddings, dtype='float32')
        logger.info(f"Всего чанков: {len(all_chunks)}, размерность: {embeddings_array.shape}")

        # Строим FAISS индекс (IVF с k-means)
        dimension = embeddings_array.shape[1]
        nlist = max(1, int(np.sqrt(len(all_embeddings))))  # количество центроидов

        # Quantizer
        quantizer = faiss.IndexFlatL2(dimension)

        # IVF indexer
        index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_L2)

        # Обучаем на данных
        if not index.is_trained:
            logger.info(f"Обучаем IVF индекс с {nlist} центроидами...")
            index.train(embeddings_array)

        # Добавляем векторы
        index.add(embeddings_array)

        # Сохраняем индекс
        index_path = db_path / 'index.faiss'
        faiss.write_index(index, str(index_path))

        # Сохраняем метаданные чанков (вместе с векторами для восстановления)
        chunks_storage = {
            'chunks': all_chunks,
            'embeddings': [list(e) for e in all_embeddings],
            'metadata': chunk_metadata,
            'dimension': dimension,
            'nlist': nlist,
            'indexed_at': datetime.now().isoformat()
        }

        storage_path = db_path / 'chunks_storage.json'
        with open(storage_path, 'w', encoding='utf-8') as f:
            json.dump(chunks_storage, f, ensure_ascii=False, indent=2)

        # Обновляем метаданные базы
        db_info = self.vector_db_service.get_db_info(db_name)
        db_info['total_chunks'] = total_chunks
        db_info['embedding_dimensions'] = dimension
        self.vector_db_service.save_metadata(db_name, db_info)

        logger.info(f"Индекс построен: {total_chunks} чанков, {index_path}")
        return {
            'total_chunks': total_chunks,
            'embedding_dimensions': dimension,
            'files_indexed': len(files_to_index)
        }

    def rebuild_index(self, db_name):
        """Полная перестройка индекса (удаляет старый и строит заново)"""
        db_path = self.vector_db_service.get_db_path(db_name)

        # Удаляем старый индекс
        for f in ['index.faiss', 'chunks_storage.json']:
            path = db_path / f
            if path.exists():
                path.unlink()

        # Очищаем старые статусы документов
        db_info = self.vector_db_service.get_db_info(db_name)
        for doc in db_info['documents']:
            doc['status'] = 'pending'
            doc['chunk_count'] = 0
        self.vector_db_service.save_metadata(db_name, db_info)

        return self.build_index(db_name)

    # =================================================================
    # ПОИСК
    # =================================================================

    def load_index(self, db_name):
        """Загружает индекс FAISS и метаданные из файла"""
        db_path = self.vector_db_service.get_db_path(db_name)

        index_path = db_path / 'index.faiss'
        storage_path = db_path / 'chunks_storage.json'

        if not index_path.exists():
            raise ValueError(f"Индекс не найден: {index_path}. Сначала постройте индекс.")

        if not storage_path.exists():
            raise ValueError(f"Хранилище чанков не найдено: {storage_path}")

        # Загружаем индекс
        index = faiss.read_index(str(index_path))

        # Загружаем метаданные
        with open(storage_path, 'r', encoding='utf-8') as f:
            storage = json.load(f)

        # Восстанавливаем numpy массив
        embeddings_array = np.array(storage['embeddings'], dtype='float32')
        chunks = storage['chunks']
        metadata = storage['metadata']
        dimension = storage['dimension']

        return index, chunks, metadata, dimension

    def search(self, db_name, query, top_k=5):
        """
        Поиск наиболее релевантных чанков по запросу.

        Args:
            db_name: Имя базы данных
            query: Текстовый запрос
            top_k: Количество результатов

        Returns:
            Список найденных чанков с метаданными
        """
        # Загружаем индекс
        index, chunks, metadata, dimension = self.load_index(db_name)

        # Генерируем эмбеддинг для запроса
        query_embedding = self.embedding_service.generate_embedding(query)

        if query_embedding is None:
            return []

        # Преобразуем в numpy
        query_vector = np.array([query_embedding], dtype='float32')

        # Ищем
        distances, indices = index.search(query_vector, min(top_k, len(chunks)))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS возвращает -1 для недостающих
                continue

            results.append({
                'chunk': chunks[idx],
                'metadata': metadata[idx],
                'distance': float(dist),
                'score': 1.0 / (1.0 + dist)  # Преобразуем расстояние в相似度
            })

        return results

    def search_and_format(self, db_name, query, top_k=5, include_source=True):
        """
        Поиск и форматирование результатов для подстановки в промпт.

        Returns:
            Строка с релевантными чанками, готовая для вставки в промпт
        """
        results = self.search(db_name, query, top_k)

        if not results:
            return ""

        parts = []
        for i, result in enumerate(results, 1):
            source = ""
            if include_source:
                file_name = result['metadata'].get('file_name', 'Неизвестно')
                source = f"\n[Источник: {file_name},相似度: {result['score']:.3f}]"

            parts.append(
                f"### Результат {i}{source}\n{result['chunk']}"
            )

        return "\n\n".join(parts)

    # =================================================================
    # API HELPERS
    # =================================================================

    def get_ready_databases(self):
        """Возвращает список всех готовых БД с информацией о наличии индекса"""
        databases = self.vector_db_service.get_db_list()
        ready = []

        for db in databases:
            db_path = self.vector_db_service.get_db_path(db['name'])
            has_index = (db_path / 'index.faiss').exists()

            ready.append({
                **db,
                'has_index': has_index,
                'index_ready': has_index and db.get('total_chunks', 0) > 0
            })

        return ready
