"""
Tokenizer manager for handling multiple tokenizers and language detection.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Set, Type
from collections import defaultdict
import time

from .base_tokenizer import BaseTokenizer, FallbackTokenizer
from .data_structures import (
    Token, LanguageInfo, TokenizationResult, SupportedLanguage
)


logger = logging.getLogger(__name__)


class TokenizerManager:
    """
    Manages multiple tokenizers and provides intelligent tokenizer selection
    based on language detection and availability.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the tokenizer manager.
        
        Args:
            config: Configuration dictionary containing tokenizer settings
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Tokenizer registry: language -> tokenizer instance
        self._tokenizers: Dict[str, BaseTokenizer] = {}
        
        # Tokenizer classes registry: language -> tokenizer class
        self._tokenizer_classes: Dict[str, Type[BaseTokenizer]] = {}
        
        # Fallback tokenizer
        self._fallback_tokenizer: Optional[BaseTokenizer] = None
        
        # Language detection settings
        self.enable_language_detection = config.get('enable_language_detection', True)
        self.language_detection_threshold = config.get('language_detection_threshold', 0.7)
        self.default_language = config.get('default_language', SupportedLanguage.CHINESE.value)
        
        # Performance settings
        self.enable_lazy_loading = config.get('enable_lazy_loading', True)
        self.enable_tokenizer_pooling = config.get('enable_tokenizer_pooling', True)
        self.max_pool_size = config.get('max_pool_size', 3)
        
        # Tokenizer pools for reuse
        self._tokenizer_pools: Dict[str, List[BaseTokenizer]] = defaultdict(list)
        
        # Statistics
        self._usage_stats: Dict[str, int] = defaultdict(int)
        self._error_stats: Dict[str, int] = defaultdict(int)
        
        self.logger.info(f"TokenizerManager initialized with config: {config}")
    
    async def initialize(self) -> None:
        """
        Initialize the tokenizer manager and fallback tokenizer.
        """
        try:
            # Initialize fallback tokenizer
            fallback_config = self.config.get('fallback', {})
            self._fallback_tokenizer = FallbackTokenizer(fallback_config)
            await self._fallback_tokenizer.initialize()
            
            # Pre-initialize tokenizers if lazy loading is disabled
            if not self.enable_lazy_loading:
                await self._initialize_all_tokenizers()
            
            self.logger.info("TokenizerManager initialization completed")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize TokenizerManager: {e}")
            raise
    
    def register_tokenizer(self, language: str, tokenizer_class: Type[BaseTokenizer], 
                          config: Optional[Dict[str, Any]] = None) -> None:
        """
        Register a tokenizer class for a specific language.
        
        Args:
            language: Language code (e.g., 'zh', 'en')
            tokenizer_class: Tokenizer class to register
            config: Optional configuration for the tokenizer
        """
        if not issubclass(tokenizer_class, BaseTokenizer):
            raise ValueError(f"Tokenizer class must inherit from BaseTokenizer")
        
        self._tokenizer_classes[language] = tokenizer_class
        
        # Store configuration for later use
        if config:
            tokenizer_config_key = f'tokenizers.{language}'
            if tokenizer_config_key not in self.config:
                self.config[tokenizer_config_key] = {}
            self.config[tokenizer_config_key].update(config)
        
        self.logger.info(f"Registered tokenizer {tokenizer_class.__name__} for language '{language}'")
    
    async def get_tokenizer(self, language: str) -> BaseTokenizer:
        """
        Get a tokenizer instance for the specified language.
        
        Args:
            language: Language code
            
        Returns:
            Tokenizer instance for the language
            
        Raises:
            ValueError: If language is not supported
        """
        # Check if we have a tokenizer for this language
        if language not in self._tokenizer_classes:
            self.logger.warning(f"No tokenizer registered for language '{language}', using fallback")
            return await self._get_fallback_tokenizer()
        
        # Try to get from pool first
        if self.enable_tokenizer_pooling and self._tokenizer_pools[language]:
            tokenizer = self._tokenizer_pools[language].pop()
            self.logger.debug(f"Retrieved tokenizer for '{language}' from pool")
            return tokenizer
        
        # Create new tokenizer instance
        try:
            tokenizer_class = self._tokenizer_classes[language]
            tokenizer_config = self.config.get(f'tokenizers.{language}', {})
            
            tokenizer = tokenizer_class(tokenizer_config)
            
            if not tokenizer._is_initialized:
                await tokenizer.initialize()
            
            self.logger.debug(f"Created new tokenizer for language '{language}'")
            return tokenizer
            
        except Exception as e:
            self.logger.error(f"Failed to create tokenizer for '{language}': {e}")
            self._error_stats[language] += 1
            return await self._get_fallback_tokenizer()
    
    async def return_tokenizer(self, tokenizer: BaseTokenizer, language: str) -> None:
        """
        Return a tokenizer to the pool for reuse.
        
        Args:
            tokenizer: Tokenizer instance to return
            language: Language code
        """
        if not self.enable_tokenizer_pooling:
            await tokenizer.cleanup()
            return
        
        # Add to pool if not full
        if len(self._tokenizer_pools[language]) < self.max_pool_size:
            self._tokenizer_pools[language].append(tokenizer)
            self.logger.debug(f"Returned tokenizer for '{language}' to pool")
        else:
            await tokenizer.cleanup()
            self.logger.debug(f"Pool full, cleaned up tokenizer for '{language}'")
    
    async def tokenize(self, text: str, language: Optional[str] = None) -> TokenizationResult:
        """
        Tokenize text using the appropriate tokenizer.
        
        Args:
            text: Input text to tokenize
            language: Optional language hint
            
        Returns:
            TokenizationResult with tokens and metadata
        """
        start_time = time.time()
        
        try:
            # Detect language if not provided
            if language is None and self.enable_language_detection:
                language = await self._detect_language(text)
            
            # Use default language if detection failed
            if language is None:
                language = self.default_language
            
            # Get appropriate tokenizer
            tokenizer = await self.get_tokenizer(language)
            
            try:
                # Perform tokenization
                result = await tokenizer.tokenize_with_timing(text, language)
                
                # Update usage statistics
                self._usage_stats[language] += 1
                
                # Add manager metadata
                result.metadata.update({
                    'manager_processing_time': time.time() - start_time,
                    'language_detected': language,
                    'tokenizer_manager': self.__class__.__name__
                })
                
                return result
                
            finally:
                # Return tokenizer to pool
                await self.return_tokenizer(tokenizer, language)
                
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Tokenization failed after {processing_time:.3f}s: {e}")
            raise
    
    async def tokenize_mixed_language(self, text: str) -> TokenizationResult:
        """
        Tokenize text that may contain multiple languages.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            TokenizationResult with tokens from multiple languages
        """
        # For now, use simple approach - detect primary language and tokenize
        # TODO: Implement proper mixed language segmentation
        language = await self._detect_language(text) if self.enable_language_detection else None
        result = await self.tokenize(text, language)
        
        # Mark as mixed language
        result.language_info.is_mixed = True
        result.metadata['mixed_language_processing'] = True
        
        return result
    
    async def _detect_language(self, text: str) -> Optional[str]:
        """
        Detect the primary language of the text.
        
        Args:
            text: Input text
            
        Returns:
            Detected language code or None if detection fails
        """
        try:
            # Simple heuristic-based language detection
            # TODO: Replace with proper language detection library (langdetect)
            
            # Count Chinese characters
            chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
            total_chars = len(text.replace(' ', '').replace('\n', ''))
            
            if total_chars == 0:
                return None
            
            chinese_ratio = chinese_chars / total_chars
            
            if chinese_ratio > 0.3:
                return SupportedLanguage.CHINESE.value
            elif any(char.isalpha() and ord(char) < 256 for char in text):
                return SupportedLanguage.ENGLISH.value
            else:
                return SupportedLanguage.UNKNOWN.value
                
        except Exception as e:
            self.logger.warning(f"Language detection failed: {e}")
            return None
    
    async def _get_fallback_tokenizer(self) -> BaseTokenizer:
        """
        Get the fallback tokenizer.
        
        Returns:
            Fallback tokenizer instance
        """
        if self._fallback_tokenizer is None:
            fallback_config = self.config.get('fallback', {})
            self._fallback_tokenizer = FallbackTokenizer(fallback_config)
            await self._fallback_tokenizer.initialize()
        
        return self._fallback_tokenizer
    
    async def _initialize_all_tokenizers(self) -> None:
        """
        Initialize all registered tokenizers (used when lazy loading is disabled).
        """
        for language, tokenizer_class in self._tokenizer_classes.items():
            try:
                tokenizer_config = self.config.get(f'tokenizers.{language}', {})
                tokenizer = tokenizer_class(tokenizer_config)
                await tokenizer.initialize()
                
                # Add to pool
                if self.enable_tokenizer_pooling:
                    self._tokenizer_pools[language].append(tokenizer)
                else:
                    self._tokenizers[language] = tokenizer
                
                self.logger.info(f"Pre-initialized tokenizer for language '{language}'")
                
            except Exception as e:
                self.logger.error(f"Failed to pre-initialize tokenizer for '{language}': {e}")
                self._error_stats[language] += 1
    
    def get_supported_languages(self) -> Set[str]:
        """
        Get all supported languages across all registered tokenizers.
        
        Returns:
            Set of supported language codes
        """
        supported = set(self._tokenizer_classes.keys())
        
        # Add fallback tokenizer languages
        if self._fallback_tokenizer:
            supported.update(self._fallback_tokenizer.get_supported_languages())
        
        return supported
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get usage and performance statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'registered_tokenizers': len(self._tokenizer_classes),
            'supported_languages': list(self.get_supported_languages()),
            'usage_stats': dict(self._usage_stats),
            'error_stats': dict(self._error_stats),
            'pool_sizes': {lang: len(pool) for lang, pool in self._tokenizer_pools.items()},
            'config': {
                'enable_language_detection': self.enable_language_detection,
                'enable_lazy_loading': self.enable_lazy_loading,
                'enable_tokenizer_pooling': self.enable_tokenizer_pooling,
                'default_language': self.default_language
            }
        }
    
    async def cleanup(self) -> None:
        """
        Clean up all tokenizers and resources.
        """
        # Clean up pooled tokenizers
        for language, pool in self._tokenizer_pools.items():
            for tokenizer in pool:
                await tokenizer.cleanup()
            pool.clear()
        
        # Clean up direct tokenizers
        for tokenizer in self._tokenizers.values():
            await tokenizer.cleanup()
        self._tokenizers.clear()
        
        # Clean up fallback tokenizer
        if self._fallback_tokenizer:
            await self._fallback_tokenizer.cleanup()
            self._fallback_tokenizer = None
        
        self.logger.info("TokenizerManager cleanup completed")
    
    def __str__(self) -> str:
        """String representation of the tokenizer manager."""
        return (f"TokenizerManager(languages={list(self.get_supported_languages())}, "
                f"tokenizers={len(self._tokenizer_classes)})")
    
    def __repr__(self) -> str:
        """Detailed string representation of the tokenizer manager."""
        return (f"TokenizerManager(config={self.config}, "
                f"tokenizers={list(self._tokenizer_classes.keys())}, "
                f"usage_stats={dict(self._usage_stats)})")