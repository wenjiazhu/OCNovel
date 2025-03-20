import os
import pickle
import hashlib
import faiss
import numpy as np
import jieba
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

@dataclass
class TextChunk:
    """文本块数据结构"""
    content: str
    chapter: int
    start_idx: int
    end_idx: int
    metadata: Dict

class KnowledgeBase:
    def __init__(self, config: Dict, embedding_model):
        self.config = config
        self.embedding_model = embedding_model
        self.chunks: List[TextChunk] = []
        self.index = None
        self.cache_dir = config["cache_dir"]
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_cache_path(self, text: str) -> str:
        """获取缓存文件路径"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"kb_{text_hash}.pkl")
        
    def _chunk_text(self, text: str) -> List[TextChunk]:
        """将文本分割成块"""
        chunk_size = self.config["chunk_size"]
        overlap = self.config["chunk_overlap"]
        chunks = []
        
        # 使用jieba分句
        sentences = list(jieba.cut(text, cut_all=False))
        logging.info(f"分词后得到 {len(sentences)} 个词语")
        
        chapter = 1
        current_chunk = []
        current_length = 0
        current_chapter_content = ""
        start_idx = 0
        
        for i, sentence in enumerate(sentences):
            current_chunk.append(sentence)
            current_length += len(sentence)
            current_chapter_content += sentence
            
            # 检测章节变化
            if "第" in sentence and "章" in sentence:
                if i > 0:  # 不是第一章
                    chapter += 1
                current_chapter_content = sentence
            
            # 当达到目标长度或遇到章节结束时创建新块
            if current_length >= chunk_size or (i == len(sentences) - 1):
                chunk_text = "".join(current_chunk)
                if chunk_text.strip():  # 确保块不为空
                    chunks.append(TextChunk(
                        content=chunk_text,
                        chapter=chapter,
                        start_idx=start_idx,
                        end_idx=i,
                        metadata={
                            "chapter_content": current_chapter_content,
                            "previous_context": "".join(sentences[max(0, start_idx-20):start_idx]),
                            "following_context": "".join(sentences[i+1:min(len(sentences), i+21)])
                        }
                    ))
                    logging.debug(f"创建文本块: 长度={len(chunk_text)}, 章节={chapter}, 起始索引={start_idx}, 结束索引={i}")
                
                # 保留重叠部分
                if i < len(sentences) - 1:
                    overlap_start = max(0, len(current_chunk) - overlap)
                    current_chunk = current_chunk[overlap_start:]
                    current_length = sum(len(t) for t in current_chunk)
                    start_idx = i - len(current_chunk) + 1
                
        logging.info(f"总共创建了 {len(chunks)} 个文本块")
        return chunks
        
    def build(self, text: str, force_rebuild: bool = False):
        """构建知识库"""
        cache_path = self._get_cache_path(text)
        
        # 检查缓存
        if not force_rebuild and os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                self.index = cached_data['index']
                self.chunks = cached_data['chunks']
                logging.info("Successfully loaded knowledge base from cache")
                return
            except Exception as e:
                logging.warning(f"Failed to load cache: {e}")
                
        # 分块
        self.chunks = self._chunk_text(text)
        logging.info(f"Created {len(self.chunks)} text chunks")
        
        # 获取嵌入向量
        vectors = []
        for i, chunk in enumerate(self.chunks):
            try:
                vector = self.embedding_model.embed(chunk.content)
                if vector is None or len(vector) == 0:
                    logging.error(f"Empty vector returned for chunk {i}")
                    continue
                vectors.append(vector)
                logging.info(f"Generated embedding for chunk {i}, vector dimension: {len(vector)}")
            except Exception as e:
                logging.error(f"Error generating embedding for chunk {i}: {e}")
                continue
                
        if not vectors:
            raise ValueError("No valid vectors generated")
            
        # 构建索引
        dimension = len(vectors[0])
        logging.info(f"Building FAISS index with dimension {dimension}")
        self.index = faiss.IndexFlatL2(dimension)
        vectors_array = np.array(vectors).astype('float32')
        self.index.add(vectors_array)
        
        # 保存缓存
        with open(cache_path, 'wb') as f:
            pickle.dump({
                'index': self.index,
                'chunks': self.chunks
            }, f)
        logging.info("Knowledge base built and cached successfully")
        
    def search(self, query: str, k: int = 5) -> List[Tuple[TextChunk, float]]:
        """搜索相关内容"""
        if not self.index:
            raise ValueError("Knowledge base not built yet")
            
        query_vector = self.embedding_model.embed(query)
        
        # 搜索最相似的向量
        distances, indices = self.index.search(
            np.array([query_vector]).astype('float32'), 
            k
        )
        
        # 返回结果
        results = []
        for distance, idx in zip(distances[0], indices[0]):
            if idx < len(self.chunks):
                results.append((self.chunks[idx], float(distance)))
                
        return results
        
    def get_context(self, chunk: TextChunk, window_size: int = 2) -> Dict:
        """获取文本块的上下文"""
        chapter = chunk.chapter
        relevant_chunks = [c for c in self.chunks if c.chapter == chapter]
        
        try:
            chunk_idx = relevant_chunks.index(chunk)
        except ValueError:
            return {"previous_chunks": [], "next_chunks": [], "chapter_summary": ""}
        
        context = {
            "previous_chunks": [],
            "next_chunks": [],
            "chapter_summary": chunk.metadata.get("chapter_content", "")
        }
        
        # 获取前文
        start_idx = max(0, chunk_idx - window_size)
        context["previous_chunks"] = relevant_chunks[start_idx:chunk_idx]
        
        # 获取后文
        end_idx = min(len(relevant_chunks), chunk_idx + window_size + 1)
        context["next_chunks"] = relevant_chunks[chunk_idx + 1:end_idx]
        
        return context 