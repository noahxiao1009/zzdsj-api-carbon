"""
文本分析工具
Text Analysis Utilities
"""

import re
import jieba
import math
from typing import List, Dict, Any, Set
from collections import Counter
import logging

logger = logging.getLogger(__name__)

class TextAnalyzer:
    """文本分析器"""
    
    def __init__(self):
        # 初始化jieba分词
        jieba.initialize()
        
        # 停用词
        self.stop_words = self._load_stop_words()
        
        # 政策相关关键词
        self.policy_keywords = {
            'policy_types': [
                '政策', '法规', '条例', '办法', '规定', '通知', '公告', '意见',
                '方案', '计划', '规划', '实施', '管理', '监督', '指导'
            ],
            'government_terms': [
                '政府', '市政府', '县政府', '区政府', '人民政府', '发改委',
                '财政局', '税务局', '工信局', '教育局', '卫健委', '住建局'
            ],
            'action_words': [
                '发布', '实施', '执行', '推进', '加强', '完善', '建立',
                '健全', '规范', '优化', '提升', '促进', '支持', '鼓励'
            ]
        }
        
        # 质量评估指标权重
        self.quality_weights = {
            'length': 0.2,          # 内容长度
            'structure': 0.3,       # 结构完整性
            'keyword_density': 0.3, # 关键词密度
            'readability': 0.2      # 可读性
        }
    
    def calculate_relevance(self, content: str, query: str) -> float:
        """计算内容与查询的相关性"""
        try:
            if not content or not query:
                return 0.0
            
            # 预处理
            content_clean = self._preprocess_text(content)
            query_clean = self._preprocess_text(query)
            
            # 分词
            content_words = self._tokenize(content_clean)
            query_words = self._tokenize(query_clean)
            
            if not content_words or not query_words:
                return 0.0
            
            # 计算TF-IDF相似度
            tf_idf_score = self._calculate_tf_idf_similarity(content_words, query_words)
            
            # 计算关键词匹配度
            keyword_score = self._calculate_keyword_matching(content_clean, query_clean)
            
            # 计算语义相似度（简化版）
            semantic_score = self._calculate_semantic_similarity(content_words, query_words)
            
            # 综合评分
            relevance_score = (tf_idf_score * 0.4 + keyword_score * 0.4 + semantic_score * 0.2)
            
            return min(1.0, max(0.0, relevance_score))
            
        except Exception as e:
            logger.warning(f"Failed to calculate relevance: {e}")
            return 0.0
    
    def calculate_content_quality(self, content: str) -> float:
        """计算内容质量评分"""
        try:
            if not content:
                return 0.0
            
            scores = {}
            
            # 1. 内容长度评分
            scores['length'] = self._score_content_length(content)
            
            # 2. 结构完整性评分
            scores['structure'] = self._score_content_structure(content)
            
            # 3. 关键词密度评分
            scores['keyword_density'] = self._score_keyword_density(content)
            
            # 4. 可读性评分
            scores['readability'] = self._score_readability(content)
            
            # 计算加权总分
            total_score = sum(
                score * self.quality_weights[metric]
                for metric, score in scores.items()
            )
            
            return min(1.0, max(0.0, total_score))
            
        except Exception as e:
            logger.warning(f"Failed to calculate content quality: {e}")
            return 0.0
    
    def extract_keywords(self, content: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """提取关键词"""
        try:
            if not content:
                return []
            
            # 预处理和分词
            content_clean = self._preprocess_text(content)
            words = self._tokenize(content_clean)
            
            if not words:
                return []
            
            # 词频统计
            word_freq = Counter(words)
            
            # 计算TF-IDF
            tf_idf_scores = self._calculate_tf_idf(words, word_freq)
            
            # 政策相关词汇加权
            policy_weighted_scores = self._apply_policy_weighting(tf_idf_scores)
            
            # 排序并返回top-k
            sorted_keywords = sorted(
                policy_weighted_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:top_k]
            
            return [
                {
                    "keyword": word,
                    "score": score,
                    "frequency": word_freq[word],
                    "is_policy_term": self._is_policy_term(word)
                }
                for word, score in sorted_keywords
            ]
            
        except Exception as e:
            logger.warning(f"Failed to extract keywords: {e}")
            return []
    
    def analyze_policy_type(self, content: str) -> Dict[str, Any]:
        """分析政策类型"""
        try:
            if not content:
                return {"type": "unknown", "confidence": 0.0}
            
            content_lower = content.lower()
            
            # 政策类型映射
            policy_type_patterns = {
                "法规条例": [r"条例", r"法规", r"法律", r"法案"],
                "通知公告": [r"通知", r"公告", r"通报", r"公示"],
                "实施办法": [r"办法", r"实施", r"细则", r"规程"],
                "发展规划": [r"规划", r"计划", r"方案", r"纲要"],
                "管理制度": [r"制度", r"管理", r"监督", r"考核"],
                "扶持政策": [r"扶持", r"支持", r"补贴", r"奖励", r"优惠"]
            }
            
            type_scores = {}
            
            # 计算各类型的匹配度
            for policy_type, patterns in policy_type_patterns.items():
                score = 0
                for pattern in patterns:
                    matches = len(re.findall(pattern, content_lower))
                    score += matches
                
                if score > 0:
                    type_scores[policy_type] = score
            
            if not type_scores:
                return {"type": "其他", "confidence": 0.0}
            
            # 找到最匹配的类型
            best_type = max(type_scores.items(), key=lambda x: x[1])
            total_score = sum(type_scores.values())
            confidence = best_type[1] / total_score if total_score > 0 else 0.0
            
            return {
                "type": best_type[0],
                "confidence": confidence,
                "all_scores": type_scores
            }
            
        except Exception as e:
            logger.warning(f"Failed to analyze policy type: {e}")
            return {"type": "unknown", "confidence": 0.0}
    
    def _preprocess_text(self, text: str) -> str:
        """文本预处理"""
        if not text:
            return ""
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除特殊字符，保留中文、英文、数字
        text = re.sub(r'[^\u4e00-\u9fff\w\s]', ' ', text)
        
        # 合并多个空格
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        if not text:
            return []
        
        # 使用jieba分词
        words = jieba.lcut(text)
        
        # 过滤停用词和短词
        filtered_words = [
            word.strip() for word in words
            if (
                len(word.strip()) >= 2 and
                word.strip() not in self.stop_words and
                not word.strip().isdigit()
            )
        ]
        
        return filtered_words
    
    def _calculate_tf_idf_similarity(self, content_words: List[str], query_words: List[str]) -> float:
        """计算TF-IDF相似度"""
        try:
            # 构建词汇表
            all_words = set(content_words + query_words)
            
            if not all_words:
                return 0.0
            
            # 计算词频
            content_tf = Counter(content_words)
            query_tf = Counter(query_words)
            
            # 简化的IDF计算（文档频率为1）
            idf = {word: 1.0 for word in all_words}
            
            # 计算TF-IDF向量
            content_tfidf = {word: (content_tf.get(word, 0) / len(content_words)) * idf[word] for word in all_words}
            query_tfidf = {word: (query_tf.get(word, 0) / len(query_words)) * idf[word] for word in all_words}
            
            # 计算余弦相似度
            dot_product = sum(content_tfidf[word] * query_tfidf[word] for word in all_words)
            content_norm = math.sqrt(sum(content_tfidf[word] ** 2 for word in all_words))
            query_norm = math.sqrt(sum(query_tfidf[word] ** 2 for word in all_words))
            
            if content_norm == 0 or query_norm == 0:
                return 0.0
            
            return dot_product / (content_norm * query_norm)
            
        except Exception:
            return 0.0
    
    def _calculate_keyword_matching(self, content: str, query: str) -> float:
        """计算关键词匹配度"""
        try:
            content_lower = content.lower()
            query_lower = query.lower()
            
            # 直接匹配
            direct_matches = 0
            query_words = query_lower.split()
            
            for word in query_words:
                if word in content_lower:
                    direct_matches += 1
            
            if not query_words:
                return 0.0
            
            return direct_matches / len(query_words)
            
        except Exception:
            return 0.0
    
    def _calculate_semantic_similarity(self, content_words: List[str], query_words: List[str]) -> float:
        """计算语义相似度（简化版）"""
        try:
            # 简化的语义相似度：基于共现词汇
            content_set = set(content_words)
            query_set = set(query_words)
            
            if not content_set or not query_set:
                return 0.0
            
            # Jaccard相似度
            intersection = len(content_set & query_set)
            union = len(content_set | query_set)
            
            return intersection / union if union > 0 else 0.0
            
        except Exception:
            return 0.0
    
    def _score_content_length(self, content: str) -> float:
        """内容长度评分"""
        length = len(content)
        
        if length < 50:
            return 0.2
        elif length < 200:
            return 0.5
        elif length < 1000:
            return 0.8
        else:
            return 1.0
    
    def _score_content_structure(self, content: str) -> float:
        """内容结构评分"""
        score = 0.0
        
        # 检查是否有标题特征
        if re.search(r'[一二三四五六七八九十]、|[1-9]\d*\.|第[一二三四五六七八九十]+[章条款]', content):
            score += 0.3
        
        # 检查是否有日期
        if re.search(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?', content):
            score += 0.2
        
        # 检查是否有发文机关
        if any(term in content for term in self.policy_keywords['government_terms']):
            score += 0.3
        
        # 检查是否有政策动词
        if any(term in content for term in self.policy_keywords['action_words']):
            score += 0.2
        
        return min(1.0, score)
    
    def _score_keyword_density(self, content: str) -> float:
        """关键词密度评分"""
        try:
            words = self._tokenize(content)
            if not words:
                return 0.0
            
            policy_word_count = 0
            for word in words:
                if self._is_policy_term(word):
                    policy_word_count += 1
            
            density = policy_word_count / len(words)
            
            # 适当的密度范围是0.1-0.3
            if 0.1 <= density <= 0.3:
                return 1.0
            elif density < 0.1:
                return density / 0.1
            else:
                return max(0.3, 1.0 - (density - 0.3) / 0.7)
                
        except Exception:
            return 0.0
    
    def _score_readability(self, content: str) -> float:
        """可读性评分"""
        try:
            # 简化的可读性评估
            sentences = re.split(r'[。！？]', content)
            if not sentences:
                return 0.0
            
            avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
            
            # 理想句子长度15-30字符
            if 15 <= avg_sentence_length <= 30:
                return 1.0
            elif avg_sentence_length < 15:
                return avg_sentence_length / 15
            else:
                return max(0.3, 1.0 - (avg_sentence_length - 30) / 70)
                
        except Exception:
            return 0.5
    
    def _calculate_tf_idf(self, words: List[str], word_freq: Counter) -> Dict[str, float]:
        """计算TF-IDF"""
        tf_idf_scores = {}
        total_words = len(words)
        
        for word, freq in word_freq.items():
            # TF (Term Frequency)
            tf = freq / total_words
            
            # 简化的IDF（假设只有一个文档）
            idf = 1.0
            
            tf_idf_scores[word] = tf * idf
        
        return tf_idf_scores
    
    def _apply_policy_weighting(self, tf_idf_scores: Dict[str, float]) -> Dict[str, float]:
        """应用政策相关词汇加权"""
        weighted_scores = tf_idf_scores.copy()
        
        for word, score in tf_idf_scores.items():
            if self._is_policy_term(word):
                weighted_scores[word] = score * 1.5  # 政策词汇加权1.5倍
        
        return weighted_scores
    
    def _is_policy_term(self, word: str) -> bool:
        """判断是否为政策相关词汇"""
        for category_words in self.policy_keywords.values():
            if word in category_words:
                return True
        return False
    
    def _load_stop_words(self) -> Set[str]:
        """加载停用词"""
        # 基础停用词列表
        stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '来',
            '个', '中', '年', '月', '日', '时', '分', '秒', '第', '等'
        }
        
        return stop_words