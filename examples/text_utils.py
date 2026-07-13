# examples/text_utils.py
import re


def clean_html(html: str) -> str:
    """
    Extract the main content from HTML, removing headers, footers, scripts, and styles,
    and summarize the core content in a language-agnostic manner.
    """
    if not html:
        return ""

    # 1. Remove non-content elements
    # Remove script, style, head, nav, header, footer, aside, noscript, and iframe blocks
    patterns_to_remove = [
        r"<(script|style|head|nav|header|footer|aside|noscript|iframe).*?>.*?</\1>",
        r"<!--.*?-->",
    ]
    cleaned_html = html
    for pattern in patterns_to_remove:
        cleaned_html = re.sub(
            pattern, "", cleaned_html, flags=re.DOTALL | re.IGNORECASE
        )

    # 2. Extract block-level text elements (paragraphs, list items, table cells, headings, divs)
    # We replace common block tags with double newlines to separate paragraphs
    cleaned_html = re.sub(
        r"</?(p|div|li|tr|h1|h2|h3|h4|h5|h6|article|section)[^>]*>",
        "\n\n",
        cleaned_html,
        flags=re.IGNORECASE,
    )
    # Strip any other remaining tags
    text_content = re.sub(r"<.*?>", " ", cleaned_html)

    # Collapse multiple whitespaces/newlines to clean lines
    lines = []
    for line in text_content.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        # Keep lines that have some content and look like sentences/paragraphs (e.g., > 15 chars)
        # to filter out remaining navigation snippets or buttons
        if len(line) > 15:
            lines.append(line)

    main_text = "\n\n".join(lines)

    # 3. Summarize the text
    return summarize_text(main_text, num_sentences=4)


def summarize_text(text: str, num_sentences: int = 4) -> str:
    """
    Language-agnostic extractive text summarization based on token frequency scoring.
    Supports English, CJK (Chinese, Japanese, Korean), Romance languages, and more.
    """
    if not text:
        return ""

    # Split text into sentences. Works with major western & eastern sentence terminators.
    # Using \s* to split even if there's no space after punctuation (e.g., CJK)
    sentences = re.split(r"(?<=[.!?。！？\n])\s*", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

    if len(sentences) <= num_sentences:
        return "\n\n".join(sentences)

    # Language-agnostic tokenization
    # Extracts words (alphanumeric for space-separated languages) and individual CJK characters
    def tokenize(txt: str) -> list[str]:
        txt = txt.lower()
        # English/Romance words (with unicode character range for accented characters)
        words = re.findall(r"[a-zA-Z0-9\u00c0-\u00ff]+", txt)
        # CJK characters (Chinese, Japanese, Korean ranges)
        cjk = re.findall(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]", txt)
        return words + cjk

    # Build token frequency table
    freq = {}
    all_tokens = tokenize(text)
    for token in all_tokens:
        freq[token] = freq.get(token, 0) + 1

    # Score sentences
    sentence_scores = []
    for idx, sentence in enumerate(sentences):
        tokens = tokenize(sentence)
        if not tokens:
            continue
        # Score is sum of frequencies of its tokens
        score = sum(freq.get(t, 0) for t in tokens)
        # Length normalization (divide by length^0.8 to prevent bias toward long sentences)
        normalized_score = score / (len(tokens) ** 0.8)
        sentence_scores.append((normalized_score, idx, sentence))

    # Get the top N sentences
    sentence_scores.sort(key=lambda x: x[0], reverse=True)
    top_sentences = sentence_scores[:num_sentences]

    # Sort top sentences back into their original chronological order
    top_sentences.sort(key=lambda x: x[1])

    summary = "\n\n".join(s[2] for s in top_sentences)
    return summary
