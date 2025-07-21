"""
智能停用词管理系统
支持多数据源停用词加载、动态管理和上下文相关判断
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Set
from collections import defaultdict
import json
import os

logger = logging.getLogger(__name__)

class StopWordsManager:
    """智能停用词管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化停用词管理器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 停用词存储：语言 -> 停用词集合
        self._stop_words: Dict[str, Set[str]] = defaultdict(set)
        
        # 领域特定停用词：领域 -> 语言 -> 停用词集合
        self._domain_stop_words: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        
        # 自定义停用词：用户ID -> 语言 -> 停用词集合
        self._custom_stop_words: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        
        # 配置选项
        self.enable_builtin = config.get('enable_builtin', True)
        self.enable_domain_specific = config.get('enable_domain_specific', True)
        self.enable_custom = config.get('enable_custom', True)
        self.enable_context_aware = config.get('enable_context_aware', False)
        
        # 数据源配置
        self.sources = config.get('sources', [])
        
        # 缓存设置
        self.enable_caching = config.get('enable_caching', True)
        self._cache_dirty = True
        
        self.logger.info(f"StopWordsManager initialized with {len(self.sources)} sources")
    
    async def initialize(self) -> None:
        """初始化停用词管理器"""
        try:
            # 加载各种数据源的停用词
            await self._load_all_sources()
            self._cache_dirty = False
            self.logger.info("StopWordsManager initialization completed")
        except Exception as e:
            self.logger.error(f"Failed to initialize StopWordsManager: {e}")
            raise
    
    async def load_stop_words(self, language: str, domain: str = None) -> Set[str]:
        """
        加载指定语言和领域的停用词
        
        Args:
            language: 语言代码
            domain: 可选的领域名称
            
        Returns:
            停用词集合
        """
        stop_words = set()
        
        # 加载基础停用词
        if self.enable_builtin and language in self._stop_words:
            stop_words.update(self._stop_words[language])
        
        # 加载领域特定停用词
        if self.enable_domain_specific and domain and domain in self._domain_stop_words:
            if language in self._domain_stop_words[domain]:
                stop_words.update(self._domain_stop_words[domain][language])
        
        return stop_words
    
    async def is_stop_word(self, word: str, language: str, context: str = None, 
                          domain: str = None, user_id: str = None) -> bool:
        """
        判断词汇是否为停用词
        
        Args:
            word: 要检查的词汇
            language: 语言代码
            context: 可选的上下文信息
            domain: 可选的领域名称
            user_id: 可选的用户ID
            
        Returns:
            是否为停用词
        """
        if not word or not word.strip():
            return True
        
        word_lower = word.lower().strip()
        
        # 检查基础停用词
        if self.enable_builtin and word_lower in self._stop_words.get(language, set()):
            return True
        
        # 检查领域特定停用词
        if (self.enable_domain_specific and domain and 
            domain in self._domain_stop_words and
            word_lower in self._domain_stop_words[domain].get(language, set())):
            return True
        
        # 检查自定义停用词
        if (self.enable_custom and user_id and 
            user_id in self._custom_stop_words and
            word_lower in self._custom_stop_words[user_id].get(language, set())):
            return True
        
        # 上下文相关判断
        if self.enable_context_aware and context:
            return await self._is_contextual_stop_word(word, language, context)
        
        return False
    
    async def add_custom_stop_words(self, words: List[str], language: str, user_id: str = "default") -> None:
        """
        添加自定义停用词
        
        Args:
            words: 停用词列表
            language: 语言代码
            user_id: 用户ID
        """
        if not self.enable_custom:
            self.logger.warning("Custom stop words are disabled")
            return
        
        # 标准化词汇
        normalized_words = {word.lower().strip() for word in words if word and word.strip()}
        
        # 添加到自定义停用词集合
        self._custom_stop_words[user_id][language].update(normalized_words)
        
        # 标记缓存为脏
        self._cache_dirty = True
        
        self.logger.info(f"Added {len(normalized_words)} custom stop words for language '{language}', user '{user_id}'")
    
    async def remove_custom_stop_words(self, words: List[str], language: str, user_id: str = "default") -> None:
        """
        移除自定义停用词
        
        Args:
            words: 要移除的停用词列表
            language: 语言代码
            user_id: 用户ID
        """
        if not self.enable_custom:
            return
        
        normalized_words = {word.lower().strip() for word in words if word and word.strip()}
        
        if user_id in self._custom_stop_words and language in self._custom_stop_words[user_id]:
            self._custom_stop_words[user_id][language] -= normalized_words
            self._cache_dirty = True
            self.logger.info(f"Removed {len(normalized_words)} custom stop words for language '{language}', user '{user_id}'")
    
    async def reload_stop_words(self) -> None:
        """重新加载所有停用词"""
        self.logger.info("Reloading all stop words...")
        
        # 清空现有数据
        self._stop_words.clear()
        self._domain_stop_words.clear()
        
        # 重新加载
        await self._load_all_sources()
        self._cache_dirty = False
        
        self.logger.info("Stop words reloaded successfully")
    
    async def _load_all_sources(self) -> None:
        """加载所有配置的数据源"""
        for source in self.sources:
            try:
                source_type = source.get('type')
                
                if source_type == 'builtin':
                    await self._load_builtin_stop_words(source)
                elif source_type == 'file':
                    await self._load_file_stop_words(source)
                elif source_type == 'domain':
                    await self._load_domain_stop_words(source)
                else:
                    self.logger.warning(f"Unknown source type: {source_type}")
                    
            except Exception as e:
                self.logger.error(f"Failed to load source {source}: {e}")
    
    async def _load_builtin_stop_words(self, source: Dict[str, Any]) -> None:
        """加载内置停用词"""
        languages = source.get('languages', ['zh', 'en'])
        
        for language in languages:
            try:
                # 尝试从NLTK加载
                stop_words = await self._load_nltk_stop_words(language)
                if stop_words:
                    self._stop_words[language].update(stop_words)
                    self.logger.debug(f"Loaded {len(stop_words)} NLTK stop words for '{language}'")
                
                # 加载自定义的基础停用词
                builtin_words = self._get_builtin_stop_words(language)
                if builtin_words:
                    self._stop_words[language].update(builtin_words)
                    self.logger.debug(f"Loaded {len(builtin_words)} builtin stop words for '{language}'")
                    
            except Exception as e:
                self.logger.error(f"Failed to load builtin stop words for '{language}': {e}")
    
    async def _load_nltk_stop_words(self, language: str) -> Optional[Set[str]]:
        """从NLTK加载停用词"""
        try:
            import nltk
            from nltk.corpus import stopwords
            
            # 语言代码映射
            lang_map = {
                'zh': 'chinese',
                'en': 'english',
                'es': 'spanish',
                'fr': 'french',
                'de': 'german',
                'ru': 'russian',
                'ar': 'arabic'
            }
            
            nltk_lang = lang_map.get(language)
            if nltk_lang:
                return set(stopwords.words(nltk_lang))
                
        except (ImportError, LookupError) as e:
            self.logger.debug(f"NLTK stop words not available for '{language}': {e}")
        
        return None
    
    def _get_builtin_stop_words(self, language: str) -> Set[str]:
        """获取内置的基础停用词"""
        builtin_stop_words = {
            'zh': {
                '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
                '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
                '自己', '这', '那', '里', '就是', '还', '把', '比', '或者', '已经', '但是',
                '因为', '所以', '如果', '虽然', '然后', '可以', '应该', '能够', '需要'
            },
            'en': {
                'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
                'in', 'on', 'at', 'to', 'for', 'with', 'by', 'of', 'about', 'from',
                'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
                'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
                'his', 'her', 'its', 'our', 'their', 'be', 'have', 'do', 'will',
                'would', 'could', 'should', 'may', 'might', 'can', 'must'
            }
        }
        
        return builtin_stop_words.get(language, set())
    
    async def _load_file_stop_words(self, source: Dict[str, Any]) -> None:
        """从文件加载停用词"""
        file_path = source.get('path')
        if not file_path or not os.path.exists(file_path):
            self.logger.warning(f"Stop words file not found: {file_path}")
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith('.json'):
                    data = json.load(f)
                    for language, words in data.items():
                        if isinstance(words, list):
                            self._stop_words[language].update(word.lower().strip() for word in words)
                else:
                    # 纯文本文件，每行一个停用词
                    language = source.get('language', 'zh')
                    words = [line.strip().lower() for line in f if line.strip()]
                    self._stop_words[language].update(words)
                    
            self.logger.info(f"Loaded stop words from file: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load stop words from file {file_path}: {e}")
    
    async def _load_domain_stop_words(self, source: Dict[str, Any]) -> None:
        """加载领域特定停用词"""
        domain = source.get('domain')
        if not domain:
            return
        
        # 预定义的领域停用词
        domain_words = {
            'technical': {
                'zh': {'技术', '系统', '方法', '实现', '功能', '模块', '接口', '配置'},
                'en': {'system', 'method', 'function', 'module', 'interface', 'config', 'implementation'}
            },
            'medical': {
                'zh': {'患者', '治疗', '症状', '诊断', '药物', '医院', '医生'},
                'en': {'patient', 'treatment', 'symptom', 'diagnosis', 'medicine', 'hospital', 'doctor'}
            },
            'legal': {
                'zh': {'法律', '条款', '规定', '合同', '协议', '当事人', '法院'},
                'en': {'law', 'clause', 'regulation', 'contract', 'agreement', 'party', 'court'}
            }
        }
        
        if domain in domain_words:
            for language, words in domain_words[domain].items():
                self._domain_stop_words[domain][language].update(words)
            
            self.logger.info(f"Loaded domain stop words for '{domain}'")
    
    async def _is_contextual_stop_word(self, word: str, language: str, context: str) -> bool:
        """基于上下文判断是否为停用词"""
        # 简化的上下文相关判断
        # 在实际应用中，这里可以使用更复杂的NLP技术
        
        word_lower = word.lower()
        context_lower = context.lower()
        
        # 如果词汇在上下文中出现频率很高，可能是停用词
        word_count = context_lower.count(word_lower)
        total_words = len(context_lower.split())
        
        if total_words > 0:
            frequency = word_count / total_words
            # 如果词汇频率超过5%，可能是停用词
            return frequency > 0.05
        
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取停用词统计信息"""
        stats = {
            'total_languages': len(self._stop_words),
            'builtin_stop_words': {lang: len(words) for lang, words in self._stop_words.items()},
            'domain_stop_words': {
                domain: {lang: len(words) for lang, words in lang_words.items()}
                for domain, lang_words in self._domain_stop_words.items()
            },
            'custom_stop_words': {
                user: {lang: len(words) for lang, words in lang_words.items()}
                for user, lang_words in self._custom_stop_words.items()
            },
            'config': {
                'enable_builtin': self.enable_builtin,
                'enable_domain_specific': self.enable_domain_specific,
                'enable_custom': self.enable_custom,
                'enable_context_aware': self.enable_context_aware
            }
        }
        
        return stats
    
    async def cleanup(self) -> None:
        """清理资源"""
        self._stop_words.clear()
        self._domain_stop_words.clear()
        self._custom_stop_words.clear()
        self.logger.info("StopWordsManager cleanup completed")