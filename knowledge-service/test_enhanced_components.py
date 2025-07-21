"""
测试增强的语义分词器组件
验证迁移的文本处理能力是否正常工作
"""

import asyncio
import logging
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.text_processor import (
    count_tokens, chunk_text, detect_language, extract_keywords,
    get_text_statistics, clean_text
)
from app.core.chunkers import create_chunker, SmartTextChunker, SemanticChunker
from app.core.tokenizers import create_token_counter, TikTokenCounter, SimpleTokenCounter
from app.core.stop_words_manager import StopWordsManager
from app.core.language_detector import LanguageDetector
from app.core.enhanced_semantic_splitter import EnhancedSemanticSplitter

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_text_processor():
    """测试文本处理器"""
    print("🔍 测试文本处理器...")
    
    test_text = """
    这是一个测试文档，用于验证文本处理功能。
    包含中文和English混合内容。
    
    我们需要测试以下功能：
    1. 令牌计数
    2. 文本分块
    3. 语言检测
    4. 关键词提取
    5. 文本统计
    """
    
    try:
        # 测试令牌计数
        token_count = count_tokens(test_text)
        print(f"   📊 令牌数量: {token_count}")
        
        # 测试文本分块
        chunks = chunk_text(test_text, chunk_size=100, chunk_overlap=20)
        print(f"   ✂️  文本分块: {len(chunks)} 个块")
        
        # 测试语言检测
        language = detect_language(test_text)
        print(f"   🌐 检测语言: {language}")
        
        # 测试关键词提取
        keywords = extract_keywords(test_text, max_keywords=5)
        print(f"   🔑 关键词: {keywords}")
        
        # 测试文本统计
        stats = get_text_statistics(test_text)
        print(f"   📈 文本统计: {stats}")
        
        # 测试文本清理
        cleaned = clean_text(test_text)
        print(f"   🧹 清理后长度: {len(cleaned)}")
        
        print("   ✅ 文本处理器测试通过")
        return True
        
    except Exception as e:
        print(f"   ❌ 文本处理器测试失败: {e}")
        return False

async def test_chunkers():
    """测试分块器"""
    print("🔍 测试分块器...")
    
    test_text = """
    人工智能技术的发展正在改变我们的世界。机器学习和深度学习算法使计算机能够从数据中学习。
    
    自然语言处理是人工智能的一个重要分支。它使计算机能够理解和生成人类语言。
    
    计算机视觉技术让机器能够"看见"和理解图像。这项技术在自动驾驶、医疗诊断等领域有广泛应用。
    """
    
    try:
        from app.core.text_base import ChunkConfig
        
        config = ChunkConfig(chunk_size=150, chunk_overlap=30)
        
        # 测试智能分块器
        smart_chunker = SmartTextChunker(config)
        smart_chunks = smart_chunker.chunk(test_text)
        print(f"   🧠 智能分块器: {len(smart_chunks)} 个块")
        
        # 测试语义分块器
        semantic_chunker = SemanticChunker(config)
        semantic_chunks = semantic_chunker.chunk(test_text)
        print(f"   🎯 语义分块器: {len(semantic_chunks)} 个块")
        
        # 测试工厂函数
        factory_chunker = create_chunker("smart", config)
        factory_chunks = factory_chunker.chunk(test_text)
        print(f"   🏭 工厂分块器: {len(factory_chunks)} 个块")
        
        print("   ✅ 分块器测试通过")
        return True
        
    except Exception as e:
        print(f"   ❌ 分块器测试失败: {e}")
        return False

async def test_tokenizers():
    """测试分词器"""
    print("🔍 测试分词器...")
    
    test_text = "这是一个测试文本，包含中文和English内容。"
    
    try:
        # 测试简单计数器
        simple_counter = SimpleTokenCounter({})
        await simple_counter.initialize()
        
        simple_tokens = await simple_counter.tokenize(test_text, 'zh')
        print(f"   🔤 简单分词器: {len(simple_tokens)} 个token")
        
        # 测试TikToken计数器
        tiktoken_counter = TikTokenCounter({'model': 'gpt-3.5-turbo'})
        await tiktoken_counter.initialize()
        
        tiktoken_tokens = await tiktoken_counter.tokenize(test_text, 'zh')
        print(f"   🎯 TikToken分词器: {len(tiktoken_tokens)} 个token")
        
        # 测试工厂函数
        factory_counter = create_token_counter(use_tiktoken=False)
        token_count = factory_counter.count_tokens(test_text)
        print(f"   🏭 工厂计数器: {token_count} 个token")
        
        print("   ✅ 分词器测试通过")
        return True
        
    except Exception as e:
        print(f"   ❌ 分词器测试失败: {e}")
        return False

async def test_stop_words_manager():
    """测试停用词管理器"""
    print("🔍 测试停用词管理器...")
    
    try:
        config = {
            'enable_builtin': True,
            'enable_domain_specific': True,
            'enable_custom': True,
            'sources': [
                {
                    'type': 'builtin',
                    'languages': ['zh', 'en']
                }
            ]
        }
        
        manager = StopWordsManager(config)
        await manager.initialize()
        
        # 测试停用词检测
        is_stop_zh = await manager.is_stop_word('的', 'zh')
        is_stop_en = await manager.is_stop_word('the', 'en')
        is_not_stop = await manager.is_stop_word('人工智能', 'zh')
        
        print(f"   🚫 '的' 是停用词: {is_stop_zh}")
        print(f"   🚫 'the' 是停用词: {is_stop_en}")
        print(f"   ✅ '人工智能' 是停用词: {is_not_stop}")
        
        # 测试自定义停用词
        await manager.add_custom_stop_words(['测试', 'test'], 'zh')
        is_custom_stop = await manager.is_stop_word('测试', 'zh')
        print(f"   🔧 自定义停用词 '测试': {is_custom_stop}")
        
        # 获取统计信息
        stats = manager.get_statistics()
        print(f"   📊 停用词统计: {stats['total_languages']} 种语言")
        
        await manager.cleanup()
        print("   ✅ 停用词管理器测试通过")
        return True
        
    except Exception as e:
        print(f"   ❌ 停用词管理器测试失败: {e}")
        return False

async def test_language_detector():
    """测试语言检测器"""
    print("🔍 测试语言检测器...")
    
    try:
        config = {
            'primary_threshold': 0.8,
            'mixed_language_threshold': 0.3,
            'supported_languages': ['zh', 'en', 'ja', 'ko']
        }
        
        detector = LanguageDetector(config)
        
        # 测试中文检测
        zh_text = "这是一段中文文本，用于测试语言检测功能。"
        zh_info = await detector.detect_language(zh_text)
        print(f"   🇨🇳 中文检测: {zh_info.primary_language} (置信度: {zh_info.confidence:.2f})")
        
        # 测试英文检测
        en_text = "This is an English text for testing language detection."
        en_info = await detector.detect_language(en_text)
        print(f"   🇺🇸 英文检测: {en_info.primary_language} (置信度: {en_info.confidence:.2f})")
        
        # 测试混合语言检测
        mixed_text = "这是中文。This is English. 这又是中文了。"
        mixed_segments = await detector.detect_mixed_languages(mixed_text)
        print(f"   🌐 混合语言分段: {len(mixed_segments)} 个段落")
        
        for i, segment in enumerate(mixed_segments):
            print(f"      段落{i+1}: {segment.language} - {segment.text[:20]}...")
        
        print("   ✅ 语言检测器测试通过")
        return True
        
    except Exception as e:
        print(f"   ❌ 语言检测器测试失败: {e}")
        return False

async def test_enhanced_semantic_splitter():
    """测试增强的语义分割器"""
    print("🔍 测试增强的语义分割器...")
    
    try:
        config = {
            'min_chunk_size': 100,
            'max_chunk_size': 300,
            'coherence_threshold': 0.7,
            'stop_words': {
                'enable_builtin': True,
                'sources': [
                    {
                        'type': 'builtin',
                        'languages': ['zh', 'en']
                    }
                ]
            },
            'language_detection': {
                'primary_threshold': 0.8,
                'supported_languages': ['zh', 'en']
            },
            'tokenizers': {
                'use_tiktoken': False,
                'token_counter': {'model': 'gpt-3.5-turbo'}
            }
        }
        
        splitter = EnhancedSemanticSplitter(config)
        await splitter.initialize()
        
        test_text = """
        人工智能技术正在快速发展。机器学习算法使计算机能够从大量数据中学习模式和规律。
        
        深度学习是机器学习的一个重要分支。它模仿人脑神经网络的结构，通过多层神经网络来处理复杂的数据。
        
        自然语言处理技术让计算机能够理解和生成人类语言。这项技术在搜索引擎、智能助手、机器翻译等领域有广泛应用。
        
        计算机视觉技术使机器能够识别和理解图像内容。在自动驾驶、医疗诊断、安防监控等领域发挥重要作用。
        """
        
        chunks, processing_time = await splitter.split_with_timing(test_text)
        
        print(f"   ⚡ 处理时间: {processing_time:.3f}秒")
        print(f"   📄 生成分块: {len(chunks)} 个")
        
        for i, chunk in enumerate(chunks):
            print(f"   块{i+1}: {len(chunk.content)} 字符, 连贯性: {chunk.metadata.get('coherence_score', 0):.2f}")
            print(f"      语言: {chunk.metadata.get('language', 'unknown')}")
            print(f"      关键词: {chunk.semantic_info.get('keywords', [])[:3]}")
        
        # 获取统计信息
        stats = splitter.get_statistics(chunks)
        print(f"   📊 统计信息: 平均长度 {stats['avg_chunk_length']:.0f}, 平均连贯性 {stats['avg_coherence_score']:.2f}")
        
        await splitter.cleanup()
        print("   ✅ 增强语义分割器测试通过")
        return True
        
    except Exception as e:
        print(f"   ❌ 增强语义分割器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("🚀 开始测试增强的语义分词器组件")
    print("=" * 50)
    
    tests = [
        ("文本处理器", test_text_processor),
        ("分块器", test_chunkers),
        ("分词器", test_tokenizers),
        ("停用词管理器", test_stop_words_manager),
        ("语言检测器", test_language_detector),
        ("增强语义分割器", test_enhanced_semantic_splitter),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 测试 {test_name}:")
        try:
            result = await test_func()
            if result:
                passed += 1
        except Exception as e:
            print(f"   ❌ {test_name} 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"🎯 测试完成: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！迁移的组件工作正常。")
    else:
        print("⚠️  部分测试失败，需要检查相关组件。")

if __name__ == "__main__":
    asyncio.run(main())