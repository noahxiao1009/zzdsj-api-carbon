"""
语言检测器
支持自动语言检测和混合语言文本处理
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
import re

from .tokenizers.data_structures import LanguageInfo, LanguageSegment, SupportedLanguage

logger = logging.getLogger(__name__)

class LanguageDetector:
    """语言检测器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化语言检测器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 配置选项
        self.primary_threshold = config.get('primary_threshold', 0.8)
        self.mixed_language_threshold = config.get('mixed_language_threshold', 0.3)
        self.supported_languages = config.get('supported_languages', ['zh', 'en', 'ja', 'ko'])
        self.enable_advanced_detection = config.get('enable_advanced_detection', False)
        
        # 语言检测可用性
        self._langdetect_available = self._check_langdetect_availability()
        
        self.logger.info(f"LanguageDetector initialized with {len(self.supported_languages)} supported languages")
    
    def _check_langdetect_availability(self) -> bool:
        """检查langdetect库是否可用"""
        try:
            import langdetect
            return True
        except ImportError:
            self.logger.warning("langdetect library not available, using heuristic detection")
            return False
    
    async def detect_language(self, text: str) -> LanguageInfo:
        """
        检测文本的主要语言
        
        Args:
            text: 输入文本
            
        Returns:
            语言信息对象
        """
        if not text or not text.strip():
            return LanguageInfo(
                primary_language=SupportedLanguage.UNKNOWN.value,
                confidence=0.0,
                detected_languages=[(SupportedLanguage.UNKNOWN.value, 0.0)],
                is_mixed=False
            )
        
        # 尝试使用langdetect进行检测
        if self._langdetect_available and self.enable_advanced_detection:
            return await self._detect_with_langdetect(text)
        else:
            return await self._detect_with_heuristics(text)
    
    async def detect_mixed_languages(self, text: str) -> List[LanguageSegment]:
        """
        检测混合语言文本并分段
        
        Args:
            text: 输入文本
            
        Returns:
            语言段落列表
        """
        if not text or not text.strip():
            return []
        
        # 简单的混合语言分段
        segments = []
        current_segment = ""
        current_language = None
        current_start = 0
        
        # 按句子分割文本
        sentences = self._split_into_sentences(text)
        char_pos = 0
        
        for sentence in sentences:
            sentence_info = await self.detect_language(sentence)
            sentence_language = sentence_info.primary_language
            
            if current_language is None:
                current_language = sentence_language
                current_segment = sentence
                current_start = char_pos
            elif current_language == sentence_language:
                current_segment += " " + sentence
            else:
                # 语言变化，保存当前段落
                if current_segment.strip():
                    segments.append(LanguageSegment(
                        text=current_segment.strip(),
                        language=current_language,
                        start_pos=current_start,
                        end_pos=char_pos,
                        confidence=0.8
                    ))
                
                # 开始新段落
                current_language = sentence_language
                current_segment = sentence
                current_start = char_pos
            
            char_pos += len(sentence) + 1  # +1 for space
        
        # 添加最后一个段落
        if current_segment.strip():
            segments.append(LanguageSegment(
                text=current_segment.strip(),
                language=current_language or SupportedLanguage.UNKNOWN.value,
                start_pos=current_start,
                end_pos=len(text),
                confidence=0.8
            ))
        
        return segments
    
    async def _detect_with_langdetect(self, text: str) -> LanguageInfo:
        """使用langdetect库进行语言检测"""
        try:
            from langdetect import detect, detect_langs
            
            # 检测主要语言
            primary_language = detect(text)
            
            # 获取所有可能的语言及其概率
            lang_probs = detect_langs(text)
            detected_languages = [(lang.lang, lang.prob) for lang in lang_probs]
            
            # 获取主要语言的置信度
            primary_confidence = next((prob for lang, prob in detected_languages if lang == primary_language), 0.0)
            
            # 判断是否为混合语言
            is_mixed = len([prob for _, prob in detected_languages if prob >= self.mixed_language_threshold]) > 1
            
            return LanguageInfo(
                primary_language=primary_language,
                confidence=primary_confidence,
                detected_languages=detected_languages,
                is_mixed=is_mixed,
                language_distribution={lang: prob for lang, prob in detected_languages}
            )
            
        except Exception as e:
            self.logger.error(f"langdetect detection failed: {e}")
            return await self._detect_with_heuristics(text)
    
    async def _detect_with_heuristics(self, text: str) -> LanguageInfo:
        """使用启发式方法进行语言检测"""
        text_lower = text.lower()
        total_chars = len(text.replace(' ', '').replace('\n', ''))
        
        if total_chars == 0:
            return LanguageInfo(
                primary_language=SupportedLanguage.UNKNOWN.value,
                confidence=0.0,
                detected_languages=[(SupportedLanguage.UNKNOWN.value, 0.0)],
                is_mixed=False
            )
        
        # 计算各种语言字符的比例
        language_scores = {}
        
        # 中文字符
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        if chinese_chars > 0:
            language_scores[SupportedLanguage.CHINESE.value] = chinese_chars / total_chars
        
        # 日文字符（平假名和片假名）
        japanese_chars = sum(1 for char in text if '\u3040' <= char <= '\u30ff')
        if japanese_chars > 0:
            language_scores[SupportedLanguage.JAPANESE.value] = japanese_chars / total_chars
        
        # 韩文字符
        korean_chars = sum(1 for char in text if '\uac00' <= char <= '\ud7a3')
        if korean_chars > 0:
            language_scores[SupportedLanguage.KOREAN.value] = korean_chars / total_chars
        
        # 西里尔字符（俄语）
        cyrillic_chars = sum(1 for char in text if '\u0400' <= char <= '\u04ff')
        if cyrillic_chars > 0:
            language_scores[SupportedLanguage.RUSSIAN.value] = cyrillic_chars / total_chars
        
        # 阿拉伯字符
        arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06ff')
        if arabic_chars > 0:
            language_scores[SupportedLanguage.ARABIC.value] = arabic_chars / total_chars
        
        # 英文和其他拉丁字符
        latin_chars = sum(1 for char in text if char.isalpha() and ord(char) < 256)
        if latin_chars > 0:
            # 进一步区分英文和其他欧洲语言
            english_score = self._calculate_english_score(text_lower)
            language_scores[SupportedLanguage.ENGLISH.value] = (latin_chars / total_chars) * english_score
            
            # 其他欧洲语言的简单检测
            if english_score < 0.8:  # 如果不太像英文
                spanish_score = self._calculate_spanish_score(text_lower)
                french_score = self._calculate_french_score(text_lower)
                german_score = self._calculate_german_score(text_lower)
                
                if spanish_score > 0.3:
                    language_scores[SupportedLanguage.SPANISH.value] = (latin_chars / total_chars) * spanish_score
                if french_score > 0.3:
                    language_scores[SupportedLanguage.FRENCH.value] = (latin_chars / total_chars) * french_score
                if german_score > 0.3:
                    language_scores[SupportedLanguage.GERMAN.value] = (latin_chars / total_chars) * german_score
        
        # 如果没有检测到任何已知语言，默认为英文
        if not language_scores:
            language_scores[SupportedLanguage.ENGLISH.value] = 0.5
        
        # 排序并获取主要语言
        sorted_languages = sorted(language_scores.items(), key=lambda x: x[1], reverse=True)
        primary_language = sorted_languages[0][0]
        primary_confidence = sorted_languages[0][1]
        
        # 判断是否为混合语言
        is_mixed = len([score for _, score in sorted_languages if score >= self.mixed_language_threshold]) > 1
        
        return LanguageInfo(
            primary_language=primary_language,
            confidence=primary_confidence,
            detected_languages=sorted_languages,
            is_mixed=is_mixed,
            language_distribution=dict(sorted_languages)
        )
    
    def _calculate_english_score(self, text: str) -> float:
        """计算英文相似度分数"""
        # 常见英文词汇
        common_english_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
        
        words = re.findall(r'\b[a-z]+\b', text)
        if not words:
            return 0.0
        
        english_word_count = sum(1 for word in words if word in common_english_words)
        return english_word_count / len(words)
    
    def _calculate_spanish_score(self, text: str) -> float:
        """计算西班牙语相似度分数"""
        spanish_indicators = ['el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en', 'con', 'por', 'para', 'que', 'es', 'son']
        words = re.findall(r'\b[a-z]+\b', text)
        if not words:
            return 0.0
        
        spanish_word_count = sum(1 for word in words if word in spanish_indicators)
        return spanish_word_count / len(words)
    
    def _calculate_french_score(self, text: str) -> float:
        """计算法语相似度分数"""
        french_indicators = ['le', 'la', 'les', 'un', 'une', 'de', 'du', 'des', 'en', 'dans', 'avec', 'pour', 'que', 'est', 'sont']
        words = re.findall(r'\b[a-z]+\b', text)
        if not words:
            return 0.0
        
        french_word_count = sum(1 for word in words if word in french_indicators)
        return french_word_count / len(words)
    
    def _calculate_german_score(self, text: str) -> float:
        """计算德语相似度分数"""
        german_indicators = ['der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einen', 'einem', 'einer', 'und', 'oder', 'aber', 'in', 'mit', 'von', 'zu', 'für', 'ist', 'sind']
        words = re.findall(r'\b[a-z]+\b', text)
        if not words:
            return 0.0
        
        german_word_count = sum(1 for word in words if word in german_indicators)
        return german_word_count / len(words)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """将文本分割为句子"""
        # 简单的句子分割
        sentence_endings = r'[.!?。！？]'
        sentences = re.split(f'({sentence_endings})', text)
        
        # 重新组合句子和标点
        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
                sentence = sentence.strip()
                if sentence:
                    result.append(sentence)
        
        # 处理最后一个句子（如果没有标点结尾）
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())
        
        return result
    
    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return self.supported_languages.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取语言检测器统计信息"""
        return {
            'supported_languages': self.supported_languages,
            'langdetect_available': self._langdetect_available,
            'enable_advanced_detection': self.enable_advanced_detection,
            'primary_threshold': self.primary_threshold,
            'mixed_language_threshold': self.mixed_language_threshold
        }