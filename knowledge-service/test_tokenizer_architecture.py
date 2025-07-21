"""
Test script to verify the basic tokenizer architecture.
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.tokenizers import (
    Token, LanguageInfo, LanguageSegment, TokenizationResult,
    BaseTokenizer, TokenizerManager, SupportedLanguage
)


async def test_data_structures():
    """Test the core data structures."""
    print("Testing data structures...")
    
    # Test Token
    token = Token(
        text="测试",
        start_pos=0,
        end_pos=2,
        language="zh",
        confidence=0.9
    )
    
    print(f"Token: {token}")
    print(f"Token dict: {token.to_dict()}")
    print(f"Token is alphabetic: {token.is_alphabetic}")
    print(f"Token length: {token.length}")
    
    # Test LanguageInfo
    lang_info = LanguageInfo(
        primary_language="zh",
        confidence=0.85,
        detected_languages=[("zh", 0.85), ("en", 0.15)]
    )
    
    print(f"Language info: {lang_info}")
    print(f"Is reliable: {lang_info.is_reliable}")
    print(f"Secondary languages: {lang_info.secondary_languages}")
    
    # Test LanguageSegment
    segment = LanguageSegment(
        text="Hello world",
        language="en",
        start_pos=0,
        end_pos=11,
        confidence=0.9
    )
    
    print(f"Language segment: {segment}")
    print(f"Segment dict: {segment.to_dict()}")
    
    print("✓ Data structures test passed\n")


async def test_fallback_tokenizer():
    """Test the fallback tokenizer."""
    print("Testing fallback tokenizer...")
    
    config = {
        'enable_pos_tagging': False,
        'preserve_whitespace': False
    }
    
    tokenizer = BaseTokenizer.__subclasses__()[0](config)  # FallbackTokenizer
    await tokenizer.initialize()
    
    # Test Chinese text
    chinese_text = "这是一个测试文本。"
    tokens = await tokenizer.tokenize(chinese_text)
    
    print(f"Chinese text: {chinese_text}")
    print(f"Tokens: {[token.text for token in tokens]}")
    print(f"Token count: {len(tokens)}")
    
    # Test English text
    english_text = "This is a test sentence."
    tokens = await tokenizer.tokenize(english_text)
    
    print(f"English text: {english_text}")
    print(f"Tokens: {[token.text for token in tokens]}")
    print(f"Token count: {len(tokens)}")
    
    # Test mixed text
    mixed_text = "Hello 世界! This is 测试 123."
    result = await tokenizer.tokenize_with_timing(mixed_text)
    
    print(f"Mixed text: {mixed_text}")
    print(f"Tokens: {[token.text for token in result.tokens]}")
    print(f"Processing time: {result.processing_time:.3f}s")
    print(f"Statistics: {tokenizer.get_statistics(result.tokens)}")
    
    await tokenizer.cleanup()
    print("✓ Fallback tokenizer test passed\n")


async def test_tokenizer_manager():
    """Test the tokenizer manager."""
    print("Testing tokenizer manager...")
    
    config = {
        'enable_language_detection': True,
        'default_language': 'zh',
        'enable_lazy_loading': True,
        'enable_tokenizer_pooling': True,
        'fallback': {}
    }
    
    manager = TokenizerManager(config)
    await manager.initialize()
    
    # Test basic tokenization
    text = "这是一个测试文本，包含中文和English words."
    result = await manager.tokenize(text)
    
    print(f"Text: {text}")
    print(f"Detected language: {result.language_info.primary_language}")
    print(f"Token count: {result.token_count}")
    print(f"Stop word count: {result.stop_word_count}")
    print(f"Processing time: {result.processing_time:.3f}s")
    
    # Test supported languages
    supported = manager.get_supported_languages()
    print(f"Supported languages: {supported}")
    
    # Test statistics
    stats = manager.get_statistics()
    print(f"Manager statistics: {stats}")
    
    await manager.cleanup()
    print("✓ Tokenizer manager test passed\n")


async def test_supported_languages():
    """Test the supported languages enum."""
    print("Testing supported languages...")
    
    print(f"All supported languages: {[lang.value for lang in SupportedLanguage]}")
    print(f"CJK languages: {SupportedLanguage.get_cjk_languages()}")
    print(f"Latin languages: {SupportedLanguage.get_latin_languages()}")
    print(f"Is 'zh' supported: {SupportedLanguage.is_supported('zh')}")
    print(f"Is 'xx' supported: {SupportedLanguage.is_supported('xx')}")
    
    print("✓ Supported languages test passed\n")


async def main():
    """Run all tests."""
    print("=== Testing Tokenizer Architecture ===\n")
    
    try:
        await test_data_structures()
        await test_fallback_tokenizer()
        await test_tokenizer_manager()
        await test_supported_languages()
        
        print("=== All tests passed! ===")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)