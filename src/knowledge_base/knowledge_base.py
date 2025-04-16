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
        
        # 按章节分割文本
        chapters = text.split("第")
        logging.info(f"文本分割为 {len(chapters)} 个章节")
        
        # 如果没有找到章节标记，将整个文本作为一个章节处理
        if len(chapters) <= 1:
            chapters = [text]
            start_idx = 0
        else:
            # 如果找到了章节标记，跳过第一个空分片
            chapters = [f"第{chapter}" for chapter in chapters[1:]]
            start_idx = 1
            
        for chapter_idx, chapter_content in enumerate(chapters, start_idx):
            try:
                # 处理单个章节
                sentences = list(jieba.cut(chapter_content, cut_all=False))
                
                current_chunk = []
                current_length = 0
                chunk_start_idx = 0
                
                for i, sentence in enumerate(sentences):
                    current_chunk.append(sentence)
                    current_length += len(sentence)
                    
                    # 当达到目标长度时创建新块
                    if current_length >= chunk_size:
                        chunk_text = "".join(current_chunk)
                        if chunk_text.strip():  # 确保块不为空
                            chunk = TextChunk(
                                content=chunk_text,
                                chapter=chapter_idx,
                                start_idx=chunk_start_idx,
                                end_idx=i,
                                metadata={
                                    "chapter_content": chapter_content[:100] + "...",  # 只保存章节开头
                                    "previous_context": "".join(sentences[max(0, chunk_start_idx-10):chunk_start_idx]),
                                    "following_context": "".join(sentences[i+1:min(len(sentences), i+11)])
                                }
                            )
                            chunks.append(chunk)
                            logging.debug(f"创建文本块: 章节={chapter_idx}, 长度={len(chunk_text)}")
                        
                        # 保留重叠部分
                        overlap_start = max(0, len(current_chunk) - overlap)
                        current_chunk = current_chunk[overlap_start:]
                        current_length = sum(len(t) for t in current_chunk)
                        chunk_start_idx = i - len(current_chunk) + 1
                
                # 处理最后一个块
                if current_chunk:
                    chunk_text = "".join(current_chunk)
                    if chunk_text.strip():
                        chunk = TextChunk(
                            content=chunk_text,
                            chapter=chapter_idx,
                            start_idx=chunk_start_idx,
                            end_idx=len(sentences)-1,
                            metadata={
                                "chapter_content": chapter_content[:100] + "...",
                                "previous_context": "".join(sentences[max(0, chunk_start_idx-10):chunk_start_idx]),
                                "following_context": ""
                            }
                        )
                        chunks.append(chunk)
                
                # 定期清理内存
                if chapter_idx % 10 == 0:
                    del sentences
                    import gc
                    gc.collect()
                    
            except Exception as e:
                logging.error(f"处理第 {chapter_idx} 章时出错: {str(e)}")
                continue
            
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
                logging.info("成功从缓存加载知识库")
                return
            except Exception as e:
                logging.warning(f"加载缓存失败: {e}")
                
        # 分块
        self.chunks = self._chunk_text(text)
        logging.info(f"创建了 {len(self.chunks)} 个文本块")
        
        # 分批获取嵌入向量
        vectors = []
        batch_size = 100  # 每批处理100个文本块
        
        for i in range(0, len(self.chunks), batch_size):
            batch_chunks = self.chunks[i:i+batch_size]
            batch_vectors = []
            
            for j, chunk in enumerate(batch_chunks):
                try:
                    vector = self.embedding_model.embed(chunk.content)
                    if vector is None or len(vector) == 0:
                        logging.error(f"文本块 {i+j} 返回空向量")
                        continue
                    batch_vectors.append(vector)
                    logging.info(f"生成文本块 {i+j} 的向量，维度: {len(vector)}")
                except Exception as e:
                    logging.error(f"生成文本块 {i+j} 的向量时出错: {e}")
                    continue
            
            vectors.extend(batch_vectors)
            
            # 定期保存中间结果
            if i % 1000 == 0 and i > 0:
                temp_cache_path = cache_path + f".temp_{i}"
                with open(temp_cache_path, 'wb') as f:
                    pickle.dump({
                        'chunks': self.chunks[:i+batch_size],
                        'vectors': vectors
                    }, f)
                logging.info(f"保存临时进度到 {temp_cache_path}")
        
        if not vectors:
            raise ValueError("没有生成有效的向量")
        
        # 构建索引
        dimension = len(vectors[0])
        logging.info(f"构建 FAISS 索引，维度 {dimension}")
        self.index = faiss.IndexFlatL2(dimension)
        vectors_array = np.array(vectors).astype('float32')
        self.index.add(vectors_array)
        
        # 保存缓存
        with open(cache_path, 'wb') as f:
            pickle.dump({
                'index': self.index,
                'chunks': self.chunks
            }, f)
        logging.info("知识库构建完成并已缓存")
        
        # 清理临时文件
        for f in os.listdir(self.cache_dir):
            if f.startswith(os.path.basename(cache_path) + ".temp_"):
                os.remove(os.path.join(self.cache_dir, f))
        
    def search(self, query: str, k: int = 5) -> List[str]:
        """搜索相关内容"""
        if not self.index:
            raise ValueError("Knowledge base not built yet")
            
        query_vector = self.embedding_model.embed(query)
        if query_vector is None:
            return []
            
        # 搜索最相似的文本块
        query_vector_array = np.array([query_vector]).astype('float32')
        distances, indices = self.index.search(query_vector_array, k)
        
        # 返回相关文本内容
        results = []
        for idx in indices[0]:
            if idx < len(self.chunks):
                results.append(self.chunks[idx].content)
        return results

    def get_all_references(self) -> Dict[str, str]:
        """获取所有参考内容"""
        if not self.chunks:
            return {}
            
        references = {}
        for i, chunk in enumerate(self.chunks):
            key = f"ref_{i+1}"
            references[key] = chunk.content
            
            # 为了避免返回过多数据，只返回前10个参考
            if i >= 9:
                break
                
        return references
        
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