"""
Core data structures for tokenization and language processing.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum


class TokenType(str, Enum):
    """Token type enumeration"""
    WORD = "word"
    PUNCTUATION = "punctuation"
    WHITESPACE = "whitespace"
    NUMBER = "number"
    SYMBOL = "symbol"
    UNKNOWN = "unknown"


@dataclass
class Token:
    """
    Represents a single token with its properties.
    
    Attributes:
        text: The actual text content of the token
        start_pos: Starting character position in the original text
        end_pos: Ending character position in the original text
        pos_tag: Part-of-speech tag (optional)
        is_stop_word: Whether this token is a stop word
        language: Language of the token
        confidence: Confidence score for language detection
        token_type: Type of the token
        lemma: Lemmatized form of the token (optional)
        features: Additional linguistic features
    """
    text: str
    start_pos: int
    end_pos: int
    pos_tag: Optional[str] = None
    is_stop_word: bool = False
    language: str = "unknown"
    confidence: float = 1.0
    token_type: TokenType = TokenType.WORD
    lemma: Optional[str] = None
    features: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = {}
    
    @property
    def length(self) -> int:
        """Get the length of the token text."""
        return len(self.text)
    
    @property
    def is_alphabetic(self) -> bool:
        """Check if the token contains only alphabetic characters."""
        return self.text.isalpha()
    
    @property
    def is_numeric(self) -> bool:
        """Check if the token contains only numeric characters."""
        return self.text.isnumeric()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert token to dictionary representation."""
        return {
            'text': self.text,
            'start_pos': self.start_pos,
            'end_pos': self.end_pos,
            'pos_tag': self.pos_tag,
            'is_stop_word': self.is_stop_word,
            'language': self.language,
            'confidence': self.confidence,
            'token_type': self.token_type.value,
            'lemma': self.lemma,
            'features': self.features
        }


@dataclass
class LanguageInfo:
    """
    Information about detected language(s) in text.
    
    Attributes:
        primary_language: The most likely language
        confidence: Confidence score for primary language detection
        detected_languages: List of (language, confidence) tuples for all detected languages
        is_mixed: Whether the text contains multiple languages
        language_distribution: Distribution of languages in the text
    """
    primary_language: str
    confidence: float
    detected_languages: List[Tuple[str, float]]
    is_mixed: bool = False
    language_distribution: Dict[str, float] = None
    
    def __post_init__(self):
        if self.language_distribution is None:
            self.language_distribution = {}
    
    @property
    def is_reliable(self) -> bool:
        """Check if the language detection is reliable (confidence > 0.8)."""
        return self.confidence > 0.8
    
    @property
    def secondary_languages(self) -> List[Tuple[str, float]]:
        """Get secondary languages (excluding primary)."""
        return [(lang, conf) for lang, conf in self.detected_languages 
                if lang != self.primary_language]
    
    def get_language_confidence(self, language: str) -> float:
        """Get confidence score for a specific language."""
        for lang, conf in self.detected_languages:
            if lang == language:
                return conf
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert language info to dictionary representation."""
        return {
            'primary_language': self.primary_language,
            'confidence': self.confidence,
            'detected_languages': self.detected_languages,
            'is_mixed': self.is_mixed,
            'language_distribution': self.language_distribution
        }


@dataclass
class LanguageSegment:
    """
    Represents a segment of text in a specific language.
    
    Attributes:
        text: The text content of the segment
        language: Detected language of the segment
        start_pos: Starting character position in the original text
        end_pos: Ending character position in the original text
        confidence: Confidence score for language detection
        tokens: List of tokens in this segment (optional)
    """
    text: str
    language: str
    start_pos: int
    end_pos: int
    confidence: float
    tokens: Optional[List[Token]] = None
    
    @property
    def length(self) -> int:
        """Get the length of the segment text."""
        return len(self.text)
    
    @property
    def token_count(self) -> int:
        """Get the number of tokens in the segment."""
        return len(self.tokens) if self.tokens else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert language segment to dictionary representation."""
        return {
            'text': self.text,
            'language': self.language,
            'start_pos': self.start_pos,
            'end_pos': self.end_pos,
            'confidence': self.confidence,
            'token_count': self.token_count,
            'tokens': [token.to_dict() for token in self.tokens] if self.tokens else None
        }


@dataclass
class TokenizationResult:
    """
    Result of tokenization process.
    
    Attributes:
        tokens: List of extracted tokens
        language_info: Information about detected language(s)
        processing_time: Time taken for tokenization
        tokenizer_used: Name of the tokenizer used
        metadata: Additional metadata about the tokenization process
    """
    tokens: List[Token]
    language_info: LanguageInfo
    processing_time: float
    tokenizer_used: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def token_count(self) -> int:
        """Get the total number of tokens."""
        return len(self.tokens)
    
    @property
    def stop_word_count(self) -> int:
        """Get the number of stop words."""
        return sum(1 for token in self.tokens if token.is_stop_word)
    
    @property
    def content_word_count(self) -> int:
        """Get the number of content words (non-stop words)."""
        return self.token_count - self.stop_word_count
    
    def get_tokens_by_language(self, language: str) -> List[Token]:
        """Get tokens for a specific language."""
        return [token for token in self.tokens if token.language == language]
    
    def get_tokens_by_type(self, token_type: TokenType) -> List[Token]:
        """Get tokens of a specific type."""
        return [token for token in self.tokens if token.token_type == token_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tokenization result to dictionary representation."""
        return {
            'tokens': [token.to_dict() for token in self.tokens],
            'language_info': self.language_info.to_dict(),
            'processing_time': self.processing_time,
            'tokenizer_used': self.tokenizer_used,
            'token_count': self.token_count,
            'stop_word_count': self.stop_word_count,
            'content_word_count': self.content_word_count,
            'metadata': self.metadata
        }


class SupportedLanguage(str, Enum):
    """Supported languages enumeration"""
    CHINESE = "zh"
    ENGLISH = "en"
    JAPANESE = "ja"
    KOREAN = "ko"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    RUSSIAN = "ru"
    ARABIC = "ar"
    UNKNOWN = "unknown"
    
    @classmethod
    def is_supported(cls, language: str) -> bool:
        """Check if a language is supported."""
        return language in [lang.value for lang in cls]
    
    @classmethod
    def get_cjk_languages(cls) -> List[str]:
        """Get CJK (Chinese, Japanese, Korean) languages."""
        return [cls.CHINESE.value, cls.JAPANESE.value, cls.KOREAN.value]
    
    @classmethod
    def get_latin_languages(cls) -> List[str]:
        """Get languages using Latin script."""
        return [cls.ENGLISH.value, cls.SPANISH.value, cls.FRENCH.value, 
                cls.GERMAN.value, cls.RUSSIAN.value]