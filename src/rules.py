import re
from typing import List
from rapidfuzz import process, fuzz

# --- 1. Email Normalization ---
# Enhanced patterns to handle more spoken forms and common ASR errors.
EMAIL_TOKEN_PATTERNS = [
    (r'\s*\b(at the rate|at)\b\s*', '@'),
    (r'\s*\b(dot)\b\s*', '.'),
    (r'\s*\b(underscore)\b\s*', '_'),
    (r'\s*\b(dash|minus)\b\s*', '-'),
    (r'\s*\b(plus)\b\s*', '+'),
]

# Common TLDs that ASR might merge with the domain (e.g., "gmailcom")
COMMON_TLDS = ['com', 'net', 'org', 'in', 'co', 'gov', 'edu']

def normalize_email(text: str) -> str:
    """Normalizes a string to fix common email-related ASR errors."""
    s = text.lower()
    
    # Handle spelled-out characters like "w w w" -> "www"
    s = re.sub(r'(?:\b[a-zA-Z]\s){2,}', lambda m: m.group(0).replace(' ', ''), s)

    # Apply standard token replacements (" at " -> "@", " dot " -> ".")
    for pat, rep in EMAIL_TOKEN_PATTERNS:
        s = re.sub(pat, rep, s, flags=re.IGNORECASE)

    # Heuristic: Insert dot before a known TLD if it's attached to a word.
    # This fixes "gmailcom" -> "gmail.com"
    for tld in COMMON_TLDS:
        s = re.sub(r'([a-zA-Z0-9])(' + tld + r')\b', r'\1.\2', s)
        
    # Collapse spaces around email symbols for a clean email string
    s = re.sub(r'\s*([@\._\-])\s*', r'\1', s)
    return s

# --- 2. Number Normalization (Comprehensive) ---
# This is a robust parser for spoken numbers, including Indian system.
def convert_words_to_numbers(text: str) -> str:
    """Converts spoken numbers (including lakh, crore) into digits."""
    word_to_num = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
        'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
        'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90
    }
    multipliers = {'hundred': 100, 'thousand': 1000, 'lakh': 100000, 'crore': 10000000}
    
    words = re.findall(r'\b(?:' + '|'.join(list(word_to_num.keys()) + list(multipliers.keys())) + r')\b(?: and)?\s*', text, re.IGNORECASE)
    
    if not words:
        return text

    # Simple spoken digits (for phone numbers)
    s = text
    s = re.sub(r'\b(double)\s*([a-zA-Z]+)\b', lambda m: m.group(2) + ' ' + m.group(2), s, flags=re.IGNORECASE)
    s = re.sub(r'\b(triple)\s*([a-zA-Z]+)\b', lambda m: m.group(2) + ' ' + m.group(2) + ' ' + m.group(2), s, flags=re.IGNORECASE)
    s = re.sub(r'\b(oh|o)\b', 'zero', s, flags=re.IGNORECASE)

    def _text2int(num_words):
        current = 0
        result = 0
        for word in num_words:
            word = word.lower()
            if word in word_to_num:
                current += word_to_num[word]
            elif word in multipliers:
                current *= multipliers[word]
                if multipliers[word] >= 1000:
                    result += current
                    current = 0
            elif word == 'and':
                continue
        return result + current

    # Replace full number phrases
    def replace_num_phrase(match):
        phrase = match.group(0)
        num_words = phrase.lower().split()
        return str(_text2int(num_words))

    num_pattern = r'\b((?:' + '|'.join(list(word_to_num.keys()) + list(multipliers.keys())) + r'|and)\s*)+\b'
    s = re.sub(num_pattern, replace_num_phrase, s, flags=re.IGNORECASE).strip()

    # Replace single digits last
    for word, digit in {'zero':'0','one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7','eight':'8','nine':'9'}.items():
        s = re.sub(r'\b' + word + r'\b', digit, s, flags=re.IGNORECASE)
    
    return s.replace("  ", " ")

# --- 3. Currency Formatting ---
def format_indian_currency(num_str: str) -> str:
    """Formats a number string with Indian comma style (e.g., 1,23,456)."""
    num_str = str(num_str).strip()
    if not num_str.isdigit(): return num_str
    
    l = len(num_str)
    if l <= 3: return num_str
    
    last_three = num_str[-3:]
    rest = num_str[:-3]
    
    return re.sub(r'(\d{2})(?=\d)', r'\1,', rest) + ',' + last_three

def normalize_currency(text: str) -> str:
    """Finds numbers followed by currency words and formats them."""
    # Pattern to find a number (digits) followed by "rupees" or "rs"
    s = re.sub(r'(\d[\d,]*\.?\d*)\s*(rupees|rs)\b', r'₹\1', text, flags=re.IGNORECASE)
    
    # Pattern to find a number followed by the currency symbol
    def format_match(m):
        num_part = m.group(1).replace(',', '')
        return '₹' + format_indian_currency(num_part)
        
    s = re.sub(r'₹\s*(\d[\d,]*)', format_match, s)
    return s

# --- 4. Name Correction ---
def correct_names_with_lexicon(text: str, names_lex: List[str], threshold: int = 85) -> str:
    """Corrects misspelled names using a lexicon, focusing on capitalized words."""
    tokens = text.split()
    corrected_tokens = []
    for t in tokens:
        # Heuristic: Only try to correct words that look like names (Capitalized)
        if t.istitle():
            # extractOne returns (choice, score, index)
            best_match = process.extractOne(t, names_lex, scorer=fuzz.ratio)
            if best_match and best_match[1] >= threshold:
                corrected_tokens.append(best_match[0])
            else:
                corrected_tokens.append(t)
        else:
            corrected_tokens.append(t)
    return ' '.join(corrected_tokens)

# --- 5. Punctuation and Capitalization ---
def add_final_punctuation_and_capitalization(text: str) -> str:
    """Capitalizes the first letter and adds a final period or question mark."""
    if not text:
        return ""
    
    # Capitalize the first letter
    s = text[0].upper() + text[1:]
    
    # Add final punctuation if missing
    if not s.endswith(('.', '?', '!')):
        # Simple heuristic for questions
        if s.lower().strip().startswith(('what', 'who', 'where', 'when', 'why', 'how', 'is', 'can', 'do', 'are')):
            s += '?'
        else:
            s += '.'
            
    return s

# --- Main Candidate Generation Pipeline ---
def generate_candidates(text: str, names_lex: List[str]) -> List[str]:
    """Generates a list of correction candidates using a logical pipeline."""
    candidates = set()
    
    # Candidate 0: The original text
    candidates.add(text)
    
    # --- Start building the "best effort" candidate step-by-step ---
    
    # Step 1: Normalize emails and numbers, as they are high-confidence transforms
    c1 = normalize_email(text)
    c1 = convert_words_to_numbers(c1)
    
    # Candidate 1: After just email and number conversion
    candidates.add(c1)

    # Step 2: Apply currency formatting
    c2 = normalize_currency(c1)
    candidates.add(c2)

    # Step 3: Apply punctuation and capitalization. This is a big structural change.
    c3 = add_final_punctuation_and_capitalization(c2)
    candidates.add(c3)

    # Step 4: Apply name correction on the fully punctuated version
    # Name correction is less certain, so we do it last.
    c4 = correct_names_with_lexicon(c3, names_lex)
    candidates.add(c4)
    
    # --- Generate a few more conservative variants ---

    # Variant A: Only punctuation and capitalization on the original text
    # This is a safe bet if other rules fail.
    variant_a = add_final_punctuation_and_capitalization(text)
    candidates.add(variant_a)

    # Variant B: Punctuation on top of number/currency fixes, but no name correction
    variant_b = add_final_punctuation_and_capitalization(normalize_currency(convert_words_to_numbers(text)))
    candidates.add(variant_b)
    
    # Finalize: Remove duplicates, sort by length (heuristic for simplicity), and cap
    # The ranker will pick the most plausible one from this diverse set.
    # Convert set to list, filter out empty strings
    out = [c for c in list(candidates) if c]
    # Simple sort to have some order, then cap
    out = sorted(list(set(out)), key=len, reverse=True)[:8] 
    
    if text not in out:
        out.append(text)

    return out[:8] # Ensure cap