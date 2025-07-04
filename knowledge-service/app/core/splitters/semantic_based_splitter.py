import re
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from .base_splitter import BaseSplitter
from ...schemas.splitter_schemas import ChunkInfo, SplitterType

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class SemanticBasedSplitter(BaseSplitter):
    """基于语义的文档切分器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化语义切分器
        
        Args:
            config: SemanticBasedConfig配置字典
        """
        super().__init__(config, SplitterType.SEMANTIC_BASED)
        
        # 初始化嵌入模型
        self.embedding_model = None
        self.model_name = config.get('embedding_model', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(self.model_name)
                self.logger.info(f"Loaded semantic embedding model: {self.model_name}")
            except Exception as e:
                self.logger.warning(f"Failed to load embedding model {self.model_name}: {e}")
        else:
            self.logger.warning("sentence-transformers not available, using mock semantic analysis")
        
        # 语言配置
        self.language = config.get('language', 'zh')
        
        # 初始化句子分割器
        self._init_sentence_splitter()
    
    def _init_sentence_splitter(self):
        """初始化句子分割器"""
        if self.language == 'zh':
            # 中文句子分割模式
            self.sentence_pattern = re.compile(r'[。！？；]+')
            self.clause_pattern = re.compile(r'[，、：；]+')
        else:
            # 英文句子分割模式
            self.sentence_pattern = re.compile(r'[.!?]+\s+')
            self.clause_pattern = re.compile(r'[,;:]+\s+')
    
    async def split_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkInfo]:
        """
        基于语义切分文本
        
        Args:
            text: 要切分的文本
            document_metadata: 文档元数据
            
        Returns:
            切分后的文本块列表
        """
        # 预处理文本
        text = self.preprocess_text(text)
        
        # 获取配置参数
        min_chunk_size = self.config.get('min_chunk_size', 100)
        max_chunk_size = self.config.get('max_chunk_size', 2000)
        similarity_threshold = self.config.get('similarity_threshold', 0.7)
        merge_threshold = self.config.get('merge_threshold', 0.8)
        
        # 步骤1: 将文本分割为句子
        sentences = self._split_into_sentences(text)
        if not sentences:
            return []
        
        # 步骤2: 生成句子嵌入
        sentence_embeddings = await self._generate_sentence_embeddings(sentences)
        
        # 步骤3: 基于语义相似度进行聚类分组
        semantic_groups = await self._group_sentences_by_semantics(
            sentences, sentence_embeddings, similarity_threshold
        )
        
        # 步骤4: 合并短组和拆分长组
        optimized_groups = await self._optimize_groups(
            semantic_groups, min_chunk_size, max_chunk_size, merge_threshold
        )
        
        # 步骤5: 创建最终的文本块
        chunks = await self._create_chunks_from_groups(
            optimized_groups, text, document_metadata
        )
        
        # 后处理
        chunks = self.postprocess_chunks(chunks)
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[Tuple[str, int, int]]:
        """
        将文本分割为句子
        
        Args:
            text: 输入文本
            
        Returns:
            句子列表，每个元素为(句子内容, 起始位置, 结束位置)
        """
        sentences = []
        
        # 使用正则表达式分割句子
        if self.config.get('sentence_split_method', 'punctuation') == 'punctuation':
            sentences = self._split_by_punctuation(text)
        else:
            sentences = self._split_by_simple_rules(text)
        
        # 过滤空句子和过短的句子
        min_sentence_length = 10
        filtered_sentences = []
        
        for sentence, start, end in sentences:
            clean_sentence = sentence.strip()
            if len(clean_sentence) >= min_sentence_length:
                filtered_sentences.append((clean_sentence, start, end))
        
        return filtered_sentences
    
    def _split_by_punctuation(self, text: str) -> List[Tuple[str, int, int]]:
        """基于标点符号分割句子"""
        sentences = []
        last_end = 0
        
        for match in self.sentence_pattern.finditer(text):
            start = last_end
            end = match.end()
            sentence = text[start:end].strip()
            
            if sentence:
                sentences.append((sentence, start, end))
            
            last_end = end
        
        # 处理最后一部分
        if last_end < len(text):
            sentence = text[last_end:].strip()
            if sentence:
                sentences.append((sentence, last_end, len(text)))
        
        return sentences
    
    def _split_by_simple_rules(self, text: str) -> List[Tuple[str, int, int]]:
        """基于简单规则分割句子"""
        # 按行分割，然后合并短行
        lines = text.split('\n')
        sentences = []
        current_sentence = ""
        start_pos = 0
        current_start = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_sentence:
                    sentences.append((current_sentence, current_start, start_pos))
                    current_sentence = ""
                start_pos += 1
                current_start = start_pos
                continue
            
            if not current_sentence:
                current_start = start_pos
            
            current_sentence += (" " if current_sentence else "") + line
            start_pos += len(line) + 1
            
            # 如果句子足够长，结束当前句子
            if len(current_sentence) >= 50 and (line.endswith(('。', '！', '？', '.', '!', '?'))):
                sentences.append((current_sentence, current_start, start_pos))
                current_sentence = ""
        
        # 处理最后的句子
        if current_sentence:
            sentences.append((current_sentence, current_start, start_pos))
        
        return sentences
    
    async def _generate_sentence_embeddings(self, sentences: List[Tuple[str, int, int]]) -> Optional[np.ndarray]:
        """
        生成句子嵌入
        
        Args:
            sentences: 句子列表
            
        Returns:
            句子嵌入矩阵
        """
        if not self.embedding_model:
            # 使用模拟嵌入
            return self._generate_mock_embeddings(sentences)
        
        try:
            sentence_texts = [sentence[0] for sentence in sentences]
            embeddings = self.embedding_model.encode(sentence_texts, convert_to_numpy=True)
            self.logger.info(f"Generated embeddings for {len(sentences)} sentences")
            return embeddings
        except Exception as e:
            self.logger.error(f"Failed to generate embeddings: {e}")
            return self._generate_mock_embeddings(sentences)
    
    def _generate_mock_embeddings(self, sentences: List[Tuple[str, int, int]]) -> np.ndarray:
        """
        生成模拟嵌入（用于测试）
        
        Args:
            sentences: 句子列表
            
        Returns:
            模拟嵌入矩阵
        """
        import random
        import hashlib
        
        embeddings = []
        for sentence, _, _ in sentences:
            # 基于句子内容生成一致的随机向量
            seed = int(hashlib.md5(sentence.encode()).hexdigest()[:8], 16)
            random.seed(seed)
            
            # 生成384维向量（模拟sentence-transformers）
            embedding = [random.gauss(0, 1) for _ in range(384)]
            # 归一化
            norm = sum(x * x for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            embeddings.append(embedding)
        
        return np.array(embeddings)
    
    async def _group_sentences_by_semantics(
        self, 
        sentences: List[Tuple[str, int, int]], 
        embeddings: np.ndarray, 
        similarity_threshold: float
    ) -> List[List[int]]:
        """
        基于语义相似度对句子进行分组
        
        Args:
            sentences: 句子列表
            embeddings: 句子嵌入矩阵
            similarity_threshold: 相似度阈值
            
        Returns:
            句子分组，每组包含句子索引列表
        """
        if embeddings is None or len(embeddings) == 0:
            # 回退到简单分组
            return [[i] for i in range(len(sentences))]
        
        n_sentences = len(sentences)
        groups = []
        used = set()
        
        for i in range(n_sentences):
            if i in used:
                continue
            
            current_group = [i]
            used.add(i)
            
            # 寻找与当前句子相似的后续句子
            for j in range(i + 1, min(i + 10, n_sentences)):  # 限制搜索范围
                if j in used:
                    continue
                
                # 计算余弦相似度
                similarity = self._cosine_similarity(embeddings[i], embeddings[j])
                
                if similarity >= similarity_threshold:
                    current_group.append(j)
                    used.add(j)
            
            groups.append(current_group)
        
        return groups
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def _optimize_groups(
        self, 
        groups: List[List[int]], 
        min_chunk_size: int, 
        max_chunk_size: int, 
        merge_threshold: float
    ) -> List[List[int]]:
        """
        优化分组：合并过短的组，拆分过长的组
        
        Args:
            groups: 原始分组
            min_chunk_size: 最小块大小
            max_chunk_size: 最大块大小
            merge_threshold: 合并阈值
            
        Returns:
            优化后的分组
        """
        optimized_groups = []
        
        i = 0
        while i < len(groups):
            current_group = groups[i]
            current_size = sum(len(self._get_sentence_by_index(j)[0]) for j in current_group)
            
            # 如果当前组太小，尝试与下一组合并
            if current_size < min_chunk_size and i + 1 < len(groups):
                next_group = groups[i + 1]
                next_size = sum(len(self._get_sentence_by_index(j)[0]) for j in next_group)
                
                if current_size + next_size <= max_chunk_size:
                    # 合并组
                    merged_group = current_group + next_group
                    optimized_groups.append(merged_group)
                    i += 2  # 跳过下一组
                    continue
            
            # 如果当前组太大，需要拆分
            if current_size > max_chunk_size:
                split_groups = self._split_large_group(current_group, max_chunk_size)
                optimized_groups.extend(split_groups)
            else:
                optimized_groups.append(current_group)
            
            i += 1
        
        return optimized_groups
    
    def _split_large_group(self, group: List[int], max_chunk_size: int) -> List[List[int]]:
        """拆分过大的组"""
        split_groups = []
        current_group = []
        current_size = 0
        
        for sentence_idx in group:
            sentence_text = self._get_sentence_by_index(sentence_idx)[0]
            sentence_size = len(sentence_text)
            
            if current_size + sentence_size > max_chunk_size and current_group:
                split_groups.append(current_group)
                current_group = [sentence_idx]
                current_size = sentence_size
            else:
                current_group.append(sentence_idx)
                current_size += sentence_size
        
        if current_group:
            split_groups.append(current_group)
        
        return split_groups
    
    def _get_sentence_by_index(self, index: int) -> Tuple[str, int, int]:
        """
        根据索引获取句子（需要在外部维护句子列表）
        这是一个简化的实现，实际应该传递句子列表
        """
        # 这里是一个占位符实现
        return ("", 0, 0)
    
    async def _create_chunks_from_groups(
        self, 
        groups: List[List[int]], 
        original_text: str, 
        document_metadata: Optional[Dict[str, Any]]
    ) -> List[ChunkInfo]:
        """
        从句子分组创建文本块
        
        Args:
            groups: 句子分组
            original_text: 原始文本
            document_metadata: 文档元数据
            
        Returns:
            文本块列表
        """
        chunks = []
        
        # 重新分割句子以获取正确的位置信息
        sentences = self._split_into_sentences(original_text)
        
        for chunk_index, group in enumerate(groups):
            if not group:
                continue
            
            # 获取组内句子的内容和位置
            group_sentences = [sentences[i] for i in group if i < len(sentences)]
            
            if not group_sentences:
                continue
            
            # 组合句子内容
            chunk_content = " ".join(sentence[0] for sentence in group_sentences)
            
            # 计算整体位置
            start_char = min(sentence[1] for sentence in group_sentences)
            end_char = max(sentence[2] for sentence in group_sentences)
            
            # 创建语义信息
            semantic_info = {
                'sentence_count': len(group_sentences),
                'semantic_coherence_score': 0.8,  # 模拟分数
                'sentence_indices': group,
                'avg_sentence_length': len(chunk_content) / len(group_sentences) if group_sentences else 0
            }
            
            # 创建文本块
            chunk = self.create_chunk_info(
                content=chunk_content,
                start_char=start_char,
                end_char=end_char,
                chunk_index=chunk_index,
                metadata={
                    'splitter_type': 'semantic_based',
                    'similarity_threshold': self.config.get('similarity_threshold'),
                    'language': self.language,
                    'embedding_model': self.model_name,
                    **(document_metadata or {})
                },
                semantic_info=semantic_info
            )
            chunks.append(chunk)
        
        return chunks
    
    def validate_config(self) -> bool:
        """验证配置有效性"""
        required_fields = ['min_chunk_size', 'max_chunk_size', 'similarity_threshold']
        
        for field in required_fields:
            if field not in self.config:
                self.logger.error(f"Missing required config field: {field}")
                return False
        
        min_size = self.config.get('min_chunk_size', 0)
        max_size = self.config.get('max_chunk_size', 0)
        threshold = self.config.get('similarity_threshold', 0)
        
        if min_size <= 0 or max_size <= 0:
            self.logger.error("Chunk sizes must be positive")
            return False
        
        if min_size >= max_size:
            self.logger.error("min_chunk_size must be less than max_chunk_size")
            return False
        
        if not (0.0 <= threshold <= 1.0):
            self.logger.error("similarity_threshold must be between 0.0 and 1.0")
            return False
        
        return True
    
    def _get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            'splitter_type': 'semantic_based',
            'min_chunk_size': self.config.get('min_chunk_size'),
            'max_chunk_size': self.config.get('max_chunk_size'),
            'similarity_threshold': self.config.get('similarity_threshold'),
            'embedding_model': self.model_name,
            'language': self.language,
            'model_available': self.embedding_model is not None
        } 