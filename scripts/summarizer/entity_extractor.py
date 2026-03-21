#!/usr/bin/env python3
"""
Entity Extractor for High-Signal News

Extracts key entities (companies, people, technologies, topics) from news articles.
Uses pattern matching and keyword extraction for lightweight entity recognition.
"""

import re
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional


@dataclass
class ExtractedEntity:
    """An extracted entity from text."""
    name: str
    entity_type: str  # 'company', 'person', 'technology', 'product', 'topic', 'location'
    confidence: float  # 0.1 to 1.0
    mention_count: int = 1
    context_snippets: list[str] = field(default_factory=list)


class EntityExtractor:
    """Extract named entities and key topics from news content."""
    
    # Known company patterns
    COMPANY_PATTERNS = [
        r'\bOpenAI\b', r'\bGoogle\b', r'\bMicrosoft\b', r'\bApple\b', r'\bAmazon\b',
        r'\bMeta\b', r'\bFacebook\b', r'\bTwitter\b', r'\bX\.com\b', r'\bTesla\b',
        r'\bNVIDIA\b', r'\bIntel\b', r'\bAMD\b', r'\bQualcomm\b', r'\bSamsung\b',
        r'\bAnthropic\b', r'\bCohere\b', r'\bStability AI\b', r'\bMidjourney\b',
        r'\bHugging Face\b', r'\bGitHub\b', r'\bGitLab\b', r'\bBitbucket\b',
        r'\bCloudflare\b', r'\bStripe\b', r'\bSquare\b', r'\bShopify\b',
        r'\bUber\b', r'\bLyft\b', r'\bAirbnb\b', r'\bNetflix\b', r'\bSpotify\b',
        r'\bSnowflake\b', r'\bDatabricks\b', r'\bPalantir\b', r'\bScale AI\b',
        r'\bAndreessen Horowitz\b', r'\bSequoia\b', r'\bY Combinator\b',
    ]
    
    # Technology/product patterns
    TECH_PATTERNS = [
        r'\bGPT-[34]\b', r'\bGPT-4[Oo]', r'\bGPT-5\b', r'\bClaude\b', r'\bGemini\b',
        r'\bLlama\s*3\b', r'\bLlama\s*2\b', r'\bMistral\b', r'\bMixtral\b',
        r'\bPython\b', r'\bJavaScript\b', r'\bTypeScript\b', r'\bRust\b', r'\bGo\b',
        r'\bJava\b', r'\bKotlin\b', r'\bSwift\b', r'\bC\+\+\b', r'\bC#\b',
        r'\bReact\b', r'\bVue\b', r'\bAngular\b', r'\bSvelte\b', r'\bNext\.js\b',
        r'\bDjango\b', r'\bFlask\b', r'\bFastAPI\b', r'\bRails\b', r'\bSpring\b',
        r'\bKubernetes\b', r'\bDocker\b', r'\bTerraform\b', r'\bAWS\b', r'\bAzure\b',
        r'\bGCP\b', r'\bLambda\b', r'\bEC2\b', r'\bS3\b', r'\bCloud Run\b',
        r'\bPostgreSQL\b', r'\bMySQL\b', r'\bMongoDB\b', r'\bRedis\b', r'\bSQLite\b',
        r'\bTensorFlow\b', r'\bPyTorch\b', r'\bJAX\b', r'\bScikit-learn\b',
        r'\bLLM\b', r'\bRAG\b', r'\bTransformer\b', r'\bDiffusion\b',
        r'\bBlockchain\b', r'\bCryptocurrency\b', r'\bBitcoin\b', r'\bEthereum\b',
    ]
    
    # AI/ML specific terms
    AI_TERMS = [
        r'\bmachine learning\b', r'\bdeep learning\b', r'\bneural network\b',
        r'\bnatural language processing\b', r'\bcomputer vision\b',
        r'\bgenerative AI\b', r'\bartificial intelligence\b', r'\bAGI\b',
        r'\breinforcement learning\b', r'\bfine-tuning\b', r'\btraining\b',
        r'\binference\b', r'\bembedding\b', r'\btokeniz\w+\b', r'\bprompt\w*\b',
        r'\bmultimodal\b', r'\bagent\w*\b', r'\borchestration\b',
    ]
    
    # Financial/investment terms
    FINANCE_TERMS = [
        r'\bIPO\b', r'\bfunding round\b', r'\bSeries [ABC]\b', r'\bvaluation\b',
        r'\bacquisition\b', r'\bmerger\b', r'\bstock\b', r'\bshares\b',
        r'\brevenue\b', r'\bearnings\b', r'\bprofit\b', r'\bloss\b',
        r'\binvestment\b', r'\binvestor\b', r'\bventure capital\b', r'\bVC\b',
        r'\bprivate equity\b', r'\bpublic market\b', r'\btrading\b',
    ]
    
    def __init__(self):
        """Initialize the entity extractor."""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self.company_regex = re.compile('|'.join(self.COMPANY_PATTERNS), re.IGNORECASE)
        self.tech_regex = re.compile('|'.join(self.TECH_PATTERNS), re.IGNORECASE)
        self.ai_regex = re.compile('|'.join(self.AI_TERMS), re.IGNORECASE)
        self.finance_regex = re.compile('|'.join(self.FINANCE_TERMS), re.IGNORECASE)
        
        # Person name pattern (simplified - looks for capitalized words that could be names)
        self.person_regex = re.compile(
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+(?:said|says|announced|founded|CEO|CTO|lead|head))',
            re.MULTILINE
        )
    
    def extract_entities(self, title: str, content: str, source: str = "") -> list[ExtractedEntity]:
        """
        Extract entities from article title and content.
        
        Args:
            title: Article title
            content: Article content
            source: Source publication (optional)
        
        Returns:
            List of ExtractedEntity objects sorted by confidence
        """
        full_text = f"{title} {content}"
        entities = {}
        
        # Extract companies
        for match in self.company_regex.finditer(full_text):
            name = match.group(0)
            normalized = self._normalize_company_name(name)
            
            if normalized not in entities:
                entities[normalized] = ExtractedEntity(
                    name=normalized,
                    entity_type='company',
                    confidence=0.9,
                    context_snippets=[self._extract_context(full_text, match.start())]
                )
            else:
                entities[normalized].mention_count += 1
        
        # Extract technologies/products
        for match in self.tech_regex.finditer(full_text):
            name = match.group(0)
            normalized = name.strip()
            
            if normalized not in entities:
                entities[normalized] = ExtractedEntity(
                    name=normalized,
                    entity_type='technology',
                    confidence=0.85,
                    context_snippets=[self._extract_context(full_text, match.start())]
                )
            else:
                entities[normalized].mention_count += 1
        
        # Extract AI/ML topics
        for match in self.ai_regex.finditer(full_text):
            name = match.group(0).lower()
            
            if name not in entities:
                entities[name] = ExtractedEntity(
                    name=name,
                    entity_type='topic',
                    confidence=0.75,
                    context_snippets=[self._extract_context(full_text, match.start())]
                )
            else:
                entities[name].mention_count += 1
        
        # Extract financial terms
        for match in self.finance_regex.finditer(full_text):
            name = match.group(0).lower()
            
            if name not in entities:
                entities[name] = ExtractedEntity(
                    name=name,
                    entity_type='topic',
                    confidence=0.7,
                    context_snippets=[self._extract_context(full_text, match.start())]
                )
            else:
                entities[name].mention_count += 1
        
        # Extract potential person names (with lower confidence)
        for match in self.person_regex.finditer(full_text):
            name = match.group(1)
            
            # Filter out common false positives
            if not self._is_likely_name(name):
                continue
            
            if name not in entities:
                entities[name] = ExtractedEntity(
                    name=name,
                    entity_type='person',
                    confidence=0.6,
                    context_snippets=[self._extract_context(full_text, match.start())]
                )
            else:
                entities[name].mention_count += 1
        
        # Sort by mention count (descending) then confidence
        sorted_entities = sorted(
            entities.values(),
            key=lambda e: (e.mention_count, e.confidence),
            reverse=True
        )
        
        return sorted_entities
    
    def extract_topics(self, title: str, content: str, top_n: int = 5) -> list[str]:
        """
        Extract main topics/themes from content.
        
        Args:
            title: Article title
            content: Article content
            top_n: Number of top topics to return
        
        Returns:
            List of topic strings
        """
        entities = self.extract_entities(title, content)
        
        # Filter to topics and technologies
        topics = [e.name for e in entities if e.entity_type in ('topic', 'technology')]
        
        return topics[:top_n]
    
    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name variations."""
        name = name.strip()
        
        # Common normalizations
        normalizations = {
            'facebook': 'Meta',
            'twitter': 'X',
            'x.com': 'X',
            'openai': 'OpenAI',
            'github': 'GitHub',
        }
        
        lower = name.lower()
        return normalizations.get(lower, name)
    
    def _extract_context(self, text: str, position: int, window: int = 50) -> str:
        """Extract surrounding context for an entity mention."""
        start = max(0, position - window)
        end = min(len(text), position + window)
        return text[start:end].strip()
    
    def _is_likely_name(self, name: str) -> bool:
        """Check if a string is likely a person name vs a false positive."""
        # Common words that might match the pattern but aren't names
        false_positives = {
            'The Company', 'This Year', 'Last Week', 'Next Month',
            'New York', 'San Francisco', 'Silicon Valley', 'United States',
            'Artificial Intelligence', 'Machine Learning', 'Last Year',
        }
        
        return name not in false_positives


def extract_entities_batch(stories: list[dict]) -> dict[str, list[ExtractedEntity]]:
    """
    Extract entities from a batch of stories.
    
    Args:
        stories: List of story dicts with 'id', 'title', 'content'
    
    Returns:
        Dict mapping story_id to list of entities
    """
    extractor = EntityExtractor()
    results = {}
    
    for story in stories:
        story_id = story.get('id', 'unknown')
        entities = extractor.extract_entities(
            title=story.get('title', ''),
            content=story.get('content', ''),
            source=story.get('source', '')
        )
        results[story_id] = entities
    
    return results


if __name__ == "__main__":
    # Test the extractor
    test_title = "OpenAI Releases GPT-5 as Google and Microsoft Race to Compete"
    test_content = """
    OpenAI announced GPT-5 today, featuring significant improvements in reasoning
    and multimodal capabilities. The model demonstrates advances in code generation,
    mathematical reasoning, and natural language processing.
    
    Sam Altman, CEO of OpenAI, said the new model represents a major step toward
    artificial general intelligence. The announcement comes as Google prepares to
    launch its next Gemini model and Microsoft integrates AI deeper into its products.
    
    Investors reacted positively, with AI-related stocks gaining in pre-market trading.
    Venture capital firms are closely watching the competitive dynamics in the generative
    AI space.
    """
    
    extractor = EntityExtractor()
    entities = extractor.extract_entities(test_title, test_content)
    
    print("Extracted Entities:")
    print("-" * 60)
    for entity in entities:
        print(f"  {entity.name} ({entity.entity_type})")
        print(f"    Confidence: {entity.confidence:.2f}, Mentions: {entity.mention_count}")
    
    topics = extractor.extract_topics(test_title, test_content)
    print(f"\nTop Topics: {', '.join(topics)}")
