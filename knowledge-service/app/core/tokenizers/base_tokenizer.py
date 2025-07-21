"""
Base tokenizer interface and abstract classes.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
import logging
import time
from .data_structures import Token, LanguageInfo, TokenizationResult, SupportedLanguage


logger = logging.getLogger(__name__)


class BaseTokenizer(ABC):
    """
    Abstract base class for all tokenizers.
    
    This class defines the interface that all tokenizers must implement,
    providing common functionality and ensuring consistency across different
    tokenizer implementations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the tokenizer with configuration.
        
        Args:
            config: Configuration dictionary for the tokenizer
        """
        self.config = config
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        self._is_initialized = False
        self._supported_languages: Set[str] = set()
        
        # Common configuration options
        self.enable_pos_tagging = config.get('enable_pos_tagging', False)
        self.enable_lemmatization = config.get('enable_lemmatization', False)
        self.preserve_whitespace = config.get('preserve_whitespace', False)
        self.case_sensitive = config.get('case_sensitive', True)
        
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the tokenizer (load models, dictionaries, etc.).
        
        This method should be called before using the tokenizer.
        Implementations should set self._is_initialized = True when complete.
        """
        pass
    
    @abstractmethod
    async def tokenize(self, text: str, language: Optional[str] = None) -> List[Token]:
        """
        Tokenize the input text into a list of tokens.
        
        Args:
            text: Input text to tokenize
            language: Optional language hint for better tokenization
            
        Returns:
            List of Token objects
            
        Raises:
            ValueError: If text is empty or invalid
            RuntimeError: If tokenizer is not initialized
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> Set[str]:
        """
        Get the set of languages supported by this tokenizer.
        
        Returns:
            Set of language codes (e.g., {'zh', 'en'})
        """
        pass
    
    async def tokenize_with_timing(self, text: str, language: Optional[str] = None) -> TokenizationResult:
        """
        Tokenize text and return detailed results with timing information.
        
        Args:
            text: Input text to tokenize
            language: Optional language hint
            
        Returns:
            TokenizationResult with tokens and metadata
        """
        if not self._is_initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            tokens = await self.tokenize(text, language)
            processing_time = time.time() - start_time
            
            # Create language info (basic implementation)
            language_info = LanguageInfo(
                primary_language=language or "unknown",
                confidence=1.0 if language else 0.5,
                detected_languages=[(language or "unknown", 1.0 if language else 0.5)],
                is_mixed=False
            )
            
            result = TokenizationResult(
                tokens=tokens,
                language_info=language_info,
                processing_time=processing_time,
                tokenizer_used=self.name,
                metadata={
                    'config': self.config,
                    'text_length': len(text),
                    'tokenizer_type': self.__class__.__name__
                }
            )
            
            self.logger.debug(
                f"Tokenized {len(text)} chars into {len(tokens)} tokens in {processing_time:.3f}s"
            )
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Tokenization failed after {processing_time:.3f}s: {e}")
            raise
    
    def supports_language(self, language: str) -> bool:
        """
        Check if the tokenizer supports a specific language.
        
        Args:
            language: Language code to check
            
        Returns:
            True if language is supported, False otherwise
        """
        return language in self.get_supported_languages()
    
    def validate_text(self, text: str) -> None:
        """
        Validate input text before tokenization.
        
        Args:
            text: Text to validate
            
        Raises:
            ValueError: If text is invalid
        """
        if not text:
            raise ValueError("Input text cannot be empty")
        
        if not isinstance(text, str):
            raise ValueError("Input text must be a string")
        
        if len(text.strip()) == 0:
            raise ValueError("Input text cannot be only whitespace")
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text before tokenization.
        
        Args:
            text: Raw input text
            
        Returns:
            Preprocessed text
        """
        # Basic preprocessing - can be overridden by subclasses
        if not self.case_sensitive:
            text = text.lower()
        
        # Normalize whitespace if not preserving it
        if not self.preserve_whitespace:
            import re
            text = re.sub(r'\s+', ' ', text.strip())
        
        return text
    
    def postprocess_tokens(self, tokens: List[Token]) -> List[Token]:
        """
        Postprocess tokens after tokenization.
        
        Args:
            tokens: Raw tokens from tokenization
            
        Returns:
            Processed tokens
        """
        # Basic postprocessing - can be overridden by subclasses
        processed_tokens = []
        
        for token in tokens:
            # Skip empty tokens
            if not token.text.strip():
                continue
            
            # Add token features
            if not token.features:
                token.features = {}
            
            token.features['tokenizer'] = self.name
            token.features['is_alphabetic'] = token.is_alphabetic
            token.features['is_numeric'] = token.is_numeric
            
            processed_tokens.append(token)
        
        return processed_tokens
    
    async def cleanup(self) -> None:
        """
        Clean up resources used by the tokenizer.
        
        This method should be called when the tokenizer is no longer needed.
        """
        self._is_initialized = False
        self.logger.debug(f"Tokenizer {self.name} cleaned up")
    
    def get_statistics(self, tokens: List[Token]) -> Dict[str, Any]:
        """
        Get statistics about tokenization results.
        
        Args:
            tokens: List of tokens to analyze
            
        Returns:
            Dictionary with statistics
        """
        if not tokens:
            return {
                'total_tokens': 0,
                'unique_tokens': 0,
                'avg_token_length': 0,
                'stop_word_ratio': 0
            }
        
        total_tokens = len(tokens)
        unique_tokens = len(set(token.text.lower() for token in tokens))
        avg_token_length = sum(len(token.text) for token in tokens) / total_tokens
        stop_words = sum(1 for token in tokens if token.is_stop_word)
        stop_word_ratio = stop_words / total_tokens if total_tokens > 0 else 0
        
        # Language distribution
        language_counts = {}
        for token in tokens:
            lang = token.language
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        return {
            'total_tokens': total_tokens,
            'unique_tokens': unique_tokens,
            'avg_token_length': avg_token_length,
            'stop_word_count': stop_words,
            'stop_word_ratio': stop_word_ratio,
            'language_distribution': language_counts,
            'tokenizer_used': self.name
        }
    
    def __str__(self) -> str:
        """String representation of the tokenizer."""
        return f"{self.name}(languages={list(self.get_supported_languages())})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the tokenizer."""
        return (f"{self.name}(config={self.config}, "
                f"initialized={self._is_initialized}, "
                f"languages={list(self.get_supported_languages())})")


class FallbackTokenizer(BaseTokenizer):
    """
    Simple fallback tokenizer using basic regex patterns.
    
    This tokenizer is used when specialized tokenizers are not available
    or fail to initialize. It provides basic tokenization functionality
    using regular expressions.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._supported_languages = {
            SupportedLanguage.CHINESE.value,
            SupportedLanguage.ENGLISH.value,
            SupportedLanguage.UNKNOWN.value
        }
    
    async def initialize(self) -> None:
        """Initialize the fallback tokenizer."""
        self._is_initialized = True
        self.logger.info("FallbackTokenizer initialized")
    
    async def tokenize(self, text: str, language: Optional[str] = None) -> List[Token]:
        """
        Tokenize text using basic regex patterns.
        
        Args:
            text: Input text to tokenize
            language: Optional language hint (ignored in fallback)
            
        Returns:
            List of Token objects
        """
        if not self._is_initialized:
            await self.initialize()
        
        self.validate_text(text)
        text = self.preprocess_text(text)
        
        import re
        
        tokens = []
        
        # Basic tokenization pattern for mixed Chinese/English text
        pattern = r'[\u4e00-\u9fff]|[a-zA-Z]+|\d+|[^\w\s]'
        
        for match in re.finditer(pattern, text):
            token_text = match.group()
            start_pos = match.start()
            end_pos = match.end()
            
            # Determine token type
            if re.match(r'[\u4e00-\u9fff]', token_text):
                token_type = "word"
                token_language = SupportedLanguage.CHINESE.value
            elif re.match(r'[a-zA-Z]+', token_text):
                token_type = "word"
                token_language = SupportedLanguage.ENGLISH.value
            elif re.match(r'\d+', token_text):
                token_type = "number"
                token_language = language or SupportedLanguage.UNKNOWN.value
            else:
                token_type = "punctuation"
                token_language = language or SupportedLanguage.UNKNOWN.value
            
            token = Token(
                text=token_text,
                start_pos=start_pos,
                end_pos=end_pos,
                language=token_language,
                confidence=0.8,  # Medium confidence for fallback
                features={'token_type': token_type}
            )
            
            tokens.append(token)
        
        return self.postprocess_tokens(tokens)
    
    def get_supported_languages(self) -> Set[str]:
        """Get supported languages for fallback tokenizer."""
        return self._supported_languages.copy()