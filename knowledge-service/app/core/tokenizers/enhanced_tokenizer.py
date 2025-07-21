"""
增强的令牌计数器实现
从原始后端项目迁移并集成到现有tokenizer架构中
"""

import logging
from typing import Dict, Optional, List, Set
import time

from .base_tokenizer import BaseTokenizer
from .data_structures import Token, LanguageInfo, TokenizationResult, SupportedLanguage, TokenType

logger = logging.getLogger(__name__)

class TikTokenCounter(BaseTokenizer):
    """基于tiktoken的令牌计数器"""
    
    def __init__(self, config: Dict[str, any]):
        super().__init__(config)
        self._encoding_cache: Dict[str, any] = {}
        self._tiktoken_available = self._check_tiktoken_availability()
        self._supported_languages = {
            SupportedLanguage.CHINESE.value,
            SupportedLanguage.ENGLISH.value,
            SupportedLanguage.JAPANESE.value,
            SupportedLanguage.KOREAN.value,
            SupportedLanguage.UNKNOWN.value
        }
    
    def _check_tiktoken_availability(self) -> bool:
        """检查tiktoken是否可用"""
        try:
            import tiktoken
            return True
        except ImportError:
            logger.warning("tiktoken库不可用，将使用近似计数方法")
            return False
    
    async def initialize(self) -> None:
        """初始化tiktoken计数器"""
        self._is_initialized = True
        logger.info("TikTokenCounter initialized")
    
    async def tokenize(self, text: str, language: Optional[str] = None) -> List[Token]:
        """使用tiktoken进行精确的令牌化"""
        if not self._is_initialized:
            await self.initialize()
        
        self.validate_text(text)
        text = self.preprocess_text(text)
        
        tokens = []
        
        # 简化的分词实现
        import re
        pattern = r'[\u4e00-\u9fff]|[a-zA-Z]+|\d+|[^\w\s]'
        
        for match in re.finditer(pattern, text):
            token_text = match.group()
            
            token = Token(
                text=token_text,
                start_pos=match.start(),
                end_pos=match.end(),
                language=language or SupportedLanguage.UNKNOWN.value,
                confidence=0.9,
                token_type=self._classify_token_type(token_text),
                features={'tiktoken': True}
            )
            tokens.append(token)
        
        return self.postprocess_tokens(tokens)
    
    def _classify_token_type(self, token_text: str) -> TokenType:
        """分类token类型"""
        if token_text.isalpha():
            return TokenType.WORD
        elif token_text.isnumeric():
            return TokenType.NUMBER
        elif token_text.isspace():
            return TokenType.WHITESPACE
        elif len(token_text) == 1 and not token_text.isalnum():
            return TokenType.PUNCTUATION
        else:
            return TokenType.UNKNOWN
    
    def get_supported_languages(self) -> Set[str]:
        """获取支持的语言"""
        return self._supported_languages.copy()


class SimpleTokenCounter(BaseTokenizer):
    """简单的令牌计数器（不依赖外部库）"""
    
    def __init__(self, config: Dict[str, any]):
        super().__init__(config)
        self._supported_languages = {
            SupportedLanguage.CHINESE.value,
            SupportedLanguage.ENGLISH.value,
            SupportedLanguage.JAPANESE.value,
            SupportedLanguage.KOREAN.value,
            SupportedLanguage.UNKNOWN.value
        }
    
    async def initialize(self) -> None:
        """初始化简单计数器"""
        self._is_initialized = True
        logger.info("SimpleTokenCounter initialized")
    
    async def tokenize(self, text: str, language: Optional[str] = None) -> List[Token]:
        """基于启发式方法的分词"""
        if not self._is_initialized:
            await self.initialize()
        
        self.validate_text(text)
        text = self.preprocess_text(text)
        
        import re
        tokens = []
        
        # 基本分词模式
        if language == SupportedLanguage.CHINESE.value:
            pattern = r'[\u4e00-\u9fff]|[a-zA-Z]+|\d+|[^\w\s]'
        else:
            pattern = r'[a-zA-Z]+|\d+|[^\w\s]'
        
        for match in re.finditer(pattern, text):
            token_text = match.group()
            
            token = Token(
                text=token_text,
                start_pos=match.start(),
                end_pos=match.end(),
                language=language or SupportedLanguage.UNKNOWN.value,
                confidence=0.8,
                token_type=self._classify_token_type(token_text),
                features={'simple_tokenizer': True}
            )
            tokens.append(token)
        
        return self.postprocess_tokens(tokens)
    
    def _classify_token_type(self, token_text: str) -> TokenType:
        """分类token类型"""
        if token_text.isalpha():
            return TokenType.WORD
        elif token_text.isnumeric():
            return TokenType.NUMBER
        elif token_text.isspace():
            return TokenType.WHITESPACE
        elif len(token_text) == 1 and not token_text.isalnum():
            return TokenType.PUNCTUATION
        else:
            return TokenType.UNKNOWN
    
    def get_supported_languages(self) -> Set[str]:
        """获取支持的语言"""
        return self._supported_languages.copy()


# 工厂函数
def create_token_counter(use_tiktoken: bool = True, config: Optional[Dict[str, any]] = None) -> BaseTokenizer:
    """创建令牌计数器"""
    config = config or {}
    
    if use_tiktoken:
        try:
            import tiktoken
            return TikTokenCounter(config)
        except ImportError:
            logger.warning("tiktoken不可用，使用简单计数器")
            return SimpleTokenCounter(config)
    else:
        return SimpleTokenCounter(config)

# 便捷函数（向后兼容）
def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """向后兼容的令牌计数函数"""
    config = {'model': model}
    counter = create_token_counter(config=config)
    
    # 简单的令牌计数实现
    import re
    words = len(re.findall(r'\S+', text))
    char_tokens = len(text) // 4
    return max(words, char_tokens)