import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# LM Studio configuration
LM_STUDIO_BASE_URL = os.environ.get('LM_STUDIO_BASE_URL', 'http://localhost:1234/v1')


class EmbeddingService:
    """Сервис для генерации векторных эмбеддингов через LM Studio"""

    EMBEDDING_MODEL = 'text-embedding-nomic-embed-text-v1.5'
    CHUNK_SIZE = 512  # максимальный размер чанка в токенах (примерно)

    def __init__(self):
        self.client = OpenAI(
            base_url=LM_STUDIO_BASE_URL,
            api_key='not-needed'
        )
        self._dimensions = None

    @property
    def dimensions(self):
        """Получить размерность эмбеддинга (кэшируется)"""
        if self._dimensions is None:
            try:
                # Генерируем тестовый эмбеддинг для определения размерности
                response = self.client.embeddings.create(
                    model=self.EMBEDDING_MODEL,
                    input="test"
                )
                self._dimensions = len(response.data[0].embedding)
                logger.info(f"Embedding dimensions: {self._dimensions}")
            except Exception as e:
                logger.error(f"Failed to get embedding dimensions: {e}")
                raise
        return self._dimensions

    def generate_embedding(self, text):
        """Генерировать эмбеддинг для одного текста"""
        try:
            text = text.strip()
            if not text:
                return None

            response = self.client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def generate_embeddings_batch(self, texts, batch_size=20):
        """
        Генерировать эмбеддинги для списка текстов.
        LM Studio может принимать массив текстов за один запрос.
        """
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch = [t.strip() for t in batch if t.strip()]
            if not batch:
                continue

            try:
                response = self.client.embeddings.create(
                    model=self.EMBEDDING_MODEL,
                    input=batch
                )
                for data in response.data:
                    results.append(data.embedding)
            except Exception as e:
                logger.error(f"Error generating batch embeddings (batch {i // batch_size}): {e}")
                # Fallback: генерируем по одному
                for text in batch:
                    try:
                        emb = self.generate_embedding(text)
                        if emb:
                            results.append(emb)
                    except Exception:
                        pass

        return results

    def chunk_text(self, text, max_chars=1000, overlap=100):
        """
        Разбить текст на чанки для индексации.
        """
        if not text or not text.strip():
            return []

        chunks = []
        start = 0
        text = text.strip()

        while start < len(text):
            end = start + max_chars
            chunk = text[start:end]

            # Пытаемся разбить по предложению/абзацу
            if end < len(text):
                # Ищем точку/перенос строки ближе к концу
                split_pos = chunk.rfind('\n\n', max_chars // 2)
                if split_pos > 0:
                    chunk = chunk[:split_pos]
                else:
                    split_pos = chunk.rfind('. ', max_chars // 2)
                    if split_pos > 0:
                        chunk = chunk[:split_pos + 1]

            if chunk.strip():
                chunks.append(chunk.strip())

            start = end - overlap

        return chunks
