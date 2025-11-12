import re
from typing import List
from rapidfuzz import process, fuzz

# ---------- EMAIL HANDLING ----------
EMAIL_TOKEN_PATTERNS = [
    (r'\b\(?(at|@)\)?\b', '@'),
    (r'\b(dot|point)\b', '.'),
    (r'\b(underscore|under score)\b', '_'),
    (r'\b(hyphen|dash)\b', '-'),
    (r'\s*@\s*', '@'),
    (r'\s*\.\s*', '.'),
]

def collapse_spelled_letters(s: str) -> str:
    # Collapse sequences like 'g m a i l' -> 'gmail'
    tokens = s.split()
    out = []
    i = 0
    while i < len(tokens):
        group = []
        while i < len(tokens) and len(tokens[i]) == 1 and tokens[i].isalpha():
            group.append(tokens[i].lower())
            i += 1
        if len(group) >= 3:
            out.append(''.join(group))
        else:
            out.extend(group)
        if i < len(tokens):
            out.append(tokens[i])
            i += 1
    return ' '.join(out)

def normalize_email_tokens(s: str) -> str:
    s2 = collapse_spelled_letters(s)
    for pat, rep in EMAIL_TOKEN_PATTERNS:
        s2 = re.sub(pat, rep, s2, flags=re.IGNORECASE)
    s2 = re.sub(r'\s*([@._-])\s*', r'\1', s2)
    s2 = re.sub(r'(@gmail)\s*(dot)?\s*(com)', r'\1.com', s2, flags=re.I)
    s2 = re.sub(r'\s+', ' ', s2)
    return s2.strip()

# ---------- NUMBERS ----------
NUM_WORD = {
    'zero':'0','oh':'0','one':'1','two':'2','three':'3','four':'4','five':'5',
    'six':'6','seven':'7','eight':'8','nine':'9'
}

def words_to_digits(seq: List[str]) -> str:
    out, i = [], 0
    while i < len(seq):
        tok = seq[i].lower()
        if tok in ('double','triple') and i+1 < len(seq):
            nxt = seq[i+1].lower()
            if nxt in NUM_WORD:
                times = 2 if tok=='double' else 3
                out.append(NUM_WORD[nxt]*times)
                i += 2
                continue
        if tok in NUM_WORD:
            out.append(NUM_WORD[tok])
        else:
            break
        i += 1
    return ''.join(out)

def normalize_numbers_spoken(s: str) -> str:
    tokens = s.split()
    out, i = [], 0
    while i < len(tokens):
        for wlen in range(8, 1, -1):  # try longest first
            window = tokens[i:i+wlen]
            wd = words_to_digits(window)
            if len(wd) >= 2:
                out.append(wd)
                i += wlen
                break
        else:
            out.append(tokens[i])
            i += 1
    return ' '.join(out)

# ---------- CURRENCY ----------
def normalize_currency(s: str) -> str:
    s = re.sub(r'\b(rs\.?|rupees?|inr)\b', '₹', s, flags=re.I)
    def indian_group(numstr: str):
        if '.' in numstr:
            main, dec = numstr.split('.', 1)
        else:
            main, dec = numstr, None
        if len(main) <= 3:
            grouped = main
        else:
            grouped = main[-3:]
            rest = main[:-3]
            while len(rest) > 2:
                grouped = rest[-2:] + ',' + grouped
                rest = rest[:-2]
            if rest:
                grouped = rest + ',' + grouped
        return grouped + ('.' + dec if dec else '')

    def repl(m):
        digits = re.sub('[^0-9.]', '', m.group(0))
        if not digits:
            return m.group(0)
        return '₹' + indian_group(digits)
    return re.sub(r'₹\s*\d[\d,\.]*', repl, s)

# ---------- NAMES ----------
def correct_names_with_lexicon(s: str, names_lex: List[str], threshold: int = 88) -> str:
    tokens = s.split()
    out = []
    for t in tokens:
        if not t.isalpha():
            out.append(t)
            continue
        best = process.extractOne(t, names_lex, scorer=fuzz.partial_ratio)
        if best and best[1] >= threshold:
            # preserve case style
            corrected = best[0].capitalize() if t[0].isupper() else best[0].lower()
            out.append(corrected)
        else:
            out.append(t)
    return ' '.join(out)

# ---------- PUNCTUATION ----------
def normalize_punctuation(s: str) -> str:
    s = re.sub(r'\s+([.,?!])', r'\1', s)
    s = re.sub(r'([.,?!])([A-Za-z])', r'\1 \2', s)
    s = re.sub(r'([?.!])\1+', r'\1', s)
    if not re.search(r'[?.!]$', s.strip()):
        if re.match(r'^(what|why|who|where|when|how)\b', s.strip(), re.I):
            s += '?'
        else:
            s += '.'
    return s.strip()

# ---------- CANDIDATE GENERATION ----------
def generate_candidates(text: str, names_lex: List[str]) -> List[str]:
    cands = set()
    base = text.strip()

    # full normalization
    t1 = normalize_punctuation(
            correct_names_with_lexicon(
                normalize_currency(
                    normalize_numbers_spoken(
                        normalize_email_tokens(base)
                    )
                ), names_lex))
    cands.add(t1)

    # variants
    cands.add(normalize_email_tokens(base))
    cands.add(normalize_currency(normalize_numbers_spoken(base)))
    cands.add(correct_names_with_lexicon(base, names_lex))
    cands.add(base)

    # keep top 5 diverse
    return sorted(list(cands), key=lambda x: len(x))[:5]
