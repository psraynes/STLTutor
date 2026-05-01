import stlnode as stlnode
import random
import re

import inflect
from wordfreq import zipf_frequency

_inflect_engine = inflect.engine()

## We should list the various patterns of STL formulae that we can handle

### What do we do about nested Globally and Finally nodes? ###

patterns = []
def pattern(func):
    patterns.append(func)
    return func


def clean_for_composition(english_text):
    """Helper function to clean English text for composition in patterns.
    
    Removes trailing periods and the first occurrence of ' holds' for cleaner phrasing.
    """
    text = english_text.rstrip('.')
    # Only remove the first ' holds' to avoid over-removal
    if ' holds' in text:
        text = text.replace(' holds', '', 1)
    return text


def join_with_conjunction(items, conj='and'):
    """Join items with proper grammar using inflect if available.
    
    Examples:
        ['p', 'q'] -> 'p and q'
        ['p', 'q', 'r'] -> 'p, q, and r'
    """
    if _inflect_engine:
        return _inflect_engine.join(items, conj=conj)
    # Fallback for when inflect is not available
    if len(items) == 0:
        return ''
    elif len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return f'{items[0]} {conj} {items[1]}'
    else:
        return ', '.join(items[:-1]) + f', {conj} {items[-1]}'


def use_article(word):
    """Add appropriate article (a/an) before a word.
    
    Example: 'event' -> 'an event', 'state' -> 'a state'
    """
    if _inflect_engine:
        return _inflect_engine.a(word)
    # Simple fallback
    if word and len(word) > 0 and word[0].lower() in 'aeiou':
        return f'an {word}'
    return f'a {word}' if word else word


def _steps_phrase(count):
    """Return a human-friendly description like 'two steps'."""
    if count == 1:
        return "1 step"
    if _inflect_engine:
        return f"{_inflect_engine.number_to_words(count)} steps"
    return f"{count} steps"


def capitalize_sentence(text):
    """Capitalize the first letter of a sentence.
    
    Handles edge cases like quoted literals at the start.
    
    Examples:
        'whenever p' -> 'Whenever p'
        "'p' holds" -> "'p' holds" (don't capitalize inside quotes)
        "at all times" -> "At all times"
    """
    if not text:
        return text
    
    # Clean up any double spaces or whitespace issues
    text = ' '.join(text.split())
    
    # If text starts with a quote, don't capitalize the quoted content
    if text.startswith("'"):
        return text
    
    # Capitalize the first letter
    return text[0].upper() + text[1:] if len(text) > 1 else text.upper()


def smooth_grammar(text):
    """Apply grammar smoothing rules to improve readability.

    Fixes common awkward phrasings that arise from composition.
    """
    if not text:
        return text
    
    # Fix "both both" -> "both"
    text = text.replace("both both", "both")
    
    # Fix "either either" -> "either"  
    text = text.replace("either either", "either")
    
    # Fix "not not" -> "" (double negation in text)
    text = text.replace("not not ", "")
    
    # Fix "if if" -> "if"
    text = text.replace("if if", "if")
    
    # Fix "then then" -> "then"
    text = text.replace("then then", "then")
    
    # Fix "hold hold" or "holds holds" -> "hold" or "holds"
    text = text.replace("hold hold", "hold")
    text = text.replace("holds holds", "holds")
    
    # Fix awkward "it is the case that it is the case that"
    text = text.replace("it is the case that it is the case that", "it is the case that")
    
    # Fix "it is not the case that it is not the case that" -> ""
    text = text.replace("it is not the case that it is not the case that", "")
    
    # Fix ", ," -> ","
    text = text.replace(", ,", ",")

    # Remove redundant "the case where" before "until" (e.g., "or the case where p until q" -> "or p until q")
    # This handles patterns like "!p1 | (p0 U p2)" -> "either p1 is false or p0 until p2"
    text = re.sub(r'\b(either|or|and|both)\s+the case where\s+(\S.*?\s+until\s+)', r'\1 \2', text, flags=re.IGNORECASE)
    
    # Remove redundant "the state that" before "until" 
    text = re.sub(r'\b(either|or|and|both)\s+the state that\s+(\S.*?\s+holds\s+until\s+)', r'\1 \2', text, flags=re.IGNORECASE)
    
    # Simplify "either X or the case where Y" -> "either X or Y" when Y is already a clause
    text = re.sub(r'\b(either\s+[^,]+)\s+or\s+the case where\s+', r'\1 or ', text, flags=re.IGNORECASE)

    # Normalize mid-sentence capitalization of connectives like "If" or "Then"
    def _lowercase_mid_sentence(match):
        return match.group(1).lower()

    text = re.sub(r"(?<!^)(?<![.!?]\s)(\b(?:If|Then|When|Whenever|Where|Unless|Until|Not|Neither|Either|Both|Always|Eventually|At)\b)",
                  _lowercase_mid_sentence,
                  text)

    # Fix double spaces
    text = ' '.join(text.split())

    return text


def normalize_embedded_clause(text):
    """Make a composed clause read naturally inside a larger sentence.
    
    - Lowercase the leading word when it is embedded mid-sentence.
    - Append 'holds' after bare literals that lack a verb.
    """
    if not text:
        return text

    t = text.strip()

    # Append 'holds' if this looks like a bare literal and doesn't already have a verb
    if t.startswith("'") and "hold" not in t:
        t = f"{t} holds"

    # Lowercase initial letter when not quoted (embedded clause)
    if t and not t.startswith("'") and t[0].isupper():
        t = t[0].lower() + t[1:]

    return t


def finalize_sentence(text):
    """Apply smoothing and capitalization once, at the top level."""
    if text is None:
        return ""
    smoothed = smooth_grammar(text.strip())
    return capitalize_sentence(smoothed)


def _ngram_fluency_score(text):
    """Lightweight fluency score using token and bi-gram heuristics.
    
    The goal is to pick the most natural-sounding option from a small
    candidate set, not to be a full language model.
    """
    if not text:
        return float("-inf")

    normalized = text.lower()
    tokens = re.findall(r"[a-z']+", normalized)
    if not tokens:
        return float("-inf")

    # Encourage concise phrasing; small penalty per token
    score = -0.05 * len(tokens)

    # Penalize repeated consecutive words (kept minimal for clarity)
    for i in range(1, len(tokens)):
        if tokens[i] == tokens[i - 1]:
            score -= 0.5

    bigrams = list(zip(tokens, tokens[1:]))

    # Mild penalty for overusing "holds"
    score -= 0.1 * normalized.count("holds")

    # Frequency-based fluency cues using pre-built Zipf estimates
    token_freq_score = sum(zipf_frequency(tok, 'en') for tok in tokens) / len(tokens)
    score += 0.2 * token_freq_score

    if bigrams:
        bigram_scores = [zipf_frequency(' '.join(bg), 'en') for bg in bigrams]
        score += 0.15 * (sum(bigram_scores) / len(bigram_scores))

    return score


def choose_best_sentence(candidates):
    """Pick the most natural-sounding candidate using the fluency score.
    
    Returns a smoothed, lower-case sentence fragment (no capitalization),
    so callers can embed it and decide when to capitalize.
    """
    best = None
    best_score = float("-inf")
    for cand in candidates:
        if not cand:
            continue
        smoothed = smooth_grammar(cand)
        score = _ngram_fluency_score(smoothed)
        if score > best_score:
            best_score = score
            best = smoothed
    return best or ""


#### Precedence clarification patterns ####
# These patterns handle cases where operator precedence needs to be made explicit in English

# Pattern: (p & q) U r or (p | q) U r
# When And/Or is the left operand of Until, use natural phrasing without "the state that"
@pattern
def and_or_until_precedence_pattern(node):
    if type(node) is stlnode.UntilNode:
        if type(node.left) in (stlnode.AndNode, stlnode.OrNode):
            left_eng = clean_for_composition(node.left.__to_english__())
            right_eng = clean_for_composition(node.right.__to_english__())
            # Change "holds" to "hold" for grammatical agreement with compound subjects
            return f"{left_eng} hold until {right_eng}"
    return None


# Pattern: p & (q U r) or p | (q U r)
# When Until is an operand of And/Or, clarify with "the case where"
@pattern  
def until_in_and_precedence_pattern(node):
    if type(node) is stlnode.AndNode:
        # Until expressions are naturally clausal and don't need "the case where" wrapper
        # Only intervene if we have an Until operand to ensure consistency
        if type(node.left) is stlnode.UntilNode or type(node.right) is stlnode.UntilNode:
            left_eng = clean_for_composition(node.left.__to_english__())
            right_eng = clean_for_composition(node.right.__to_english__())
            return f"both {left_eng} and {right_eng}"
    return None


@pattern
def until_in_or_precedence_pattern(node):
    if type(node) is stlnode.OrNode:
        # Until expressions are naturally clausal and don't need "the case where" wrapper
        # Only intervene if we have an Until operand to ensure consistency
        if type(node.left) is stlnode.UntilNode or type(node.right) is stlnode.UntilNode:
            left_eng = clean_for_composition(node.left.__to_english__())
            right_eng = clean_for_composition(node.right.__to_english__())
            return f"either {left_eng} or {right_eng}"
    return None


#### Globally special cases ####

# G p (single literal)
# English: p holds at all times / p always holds
# More natural phrasings for simple globally of a literal
@pattern
def globally_literal_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.LiteralNode:
            lit_eng = clean_for_composition(op.__to_english__())
            patterns = [
                f"{lit_eng} holds at all times between {node.low} and {node.high}",
                f"{lit_eng} always holds between {node.low} and {node.high}",
                f"{lit_eng} must always hold from {node.low} to {node.high}",
                f"at all times between {node.low} and {node.high}, {lit_eng} holds"
            ]
            return choose_best_sentence(patterns)
    return None


# G (p & q) - globally conjunction
# English: always maintain both p and q / both p and q hold at all times
@pattern
def globally_and_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.AndNode:
            left_eng = clean_for_composition(op.left.__to_english__())
            right_eng = clean_for_composition(op.right.__to_english__())
            patterns = [
                f"always maintain both {left_eng} and {right_eng} from {node.low} to {node.high}",
                f"both {left_eng} and {right_eng} must always hold from {node.low} to {node.high}",
                f"at all times between {node.low} and {node.high}, both {left_eng} and {right_eng} hold"
            ]
            return choose_best_sentence(patterns)
    return None


# G (p | q) - globally disjunction
# English: always have either p or q / either p or q holds at all times
@pattern
def globally_or_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.OrNode:
            left_eng = clean_for_composition(op.left.__to_english__())
            right_eng = clean_for_composition(op.right.__to_english__())
            patterns = [
                f"always have either {left_eng} or {right_eng} from {node.low} to {node.high}",
                f"either {left_eng} or {right_eng} must always hold between {node.low} and {node.high}",
                f"at all times between {node.low} and {node.high}, either {left_eng} or {right_eng} holds"
            ]
            return choose_best_sentence(patterns)
    return None


# G G ... G p (idempotent globally - G G = G)
# English: Always p / At all times p
# Source: G is idempotent: G G p ≡ G p
@pattern
def idempotent_globally_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.GloballyNode:
            # Unwrap all consecutive Globally operators
            innermost = op.operand
            while type(innermost) is stlnode.GloballyNode:
                innermost = innermost.operand
            inner_eng = clean_for_composition(innermost.__to_english__())
            return f"at all times between {node.low} and {node.high}, {inner_eng}"
    return None


# Pattern: G ( p -> (F q) )
# English, whenever p (holds), eventually q will (hold)
# Note: We check that left is not an UntilNode to allow more specific patterns to match first

@pattern
def response_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.ImpliesNode:
            left = op.left
            right = op.right
            # Skip if left is Until - let more specific pattern handle it
            if type(left) is stlnode.UntilNode:
                return None
            if type(right) is stlnode.FinallyNode:
                left_eng = clean_for_composition(left.__to_english__())
                right_eng = clean_for_composition(right.operand.__to_english__())
                return f"from {node.low} to {node.high}, whenever {left_eng}, eventually {right_eng} between {right.low} and {right.high}"
            
    return None


# Pattern G (F p)
# English: p (happens) repeatedly
# Note: Skip if inner is AndNode to let more specific patterns handle simultaneity
# Source: This is the "recurrence" or "infinitely often" pattern from Manna & Pnueli
@pattern
def recurrence_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.FinallyNode:
            inner_op = op.operand
            # Skip if inner is AndNode - let more specific pattern handle it
            if type(inner_op) is stlnode.AndNode:
                return None
            # Handle G F (p -> q) - "infinitely often, if p then q"
            if type(inner_op) is stlnode.ImpliesNode:
                # Check for G F (p -> G q) - special case
                if type(inner_op.right) is stlnode.GloballyNode:
                    left_eng = clean_for_composition(inner_op.left.__to_english__())
                    right_eng = clean_for_composition(inner_op.right.operand.__to_english__())
                    return f"infinitely often, {left_eng} will trigger {right_eng} to hold permanently"
                left_eng = clean_for_composition(inner_op.left.__to_english__())
                right_eng = clean_for_composition(inner_op.right.__to_english__())
                return f"infinitely often, if {left_eng} then {right_eng}"
            # Handle G F G ... patterns (recurrence with nested globally)
            # G F G x = G F x by absorption (once you're in G F, adding more G F doesn't change meaning)
            # Source: Manna & Pnueli - alternating temporal operators
            if type(inner_op) is stlnode.GloballyNode:
                # Unwrap to find innermost non-G-F alternation
                innermost = inner_op.operand
                while type(innermost) is stlnode.FinallyNode or type(innermost) is stlnode.GloballyNode:
                    innermost = innermost.operand
                inner_eng = clean_for_composition(innermost.__to_english__())
                return f"{inner_eng} will happen infinitely often"
            # Handle G F F x = G F x (F F = F)
            if type(inner_op) is stlnode.FinallyNode:
                innermost = inner_op.operand
                while type(innermost) is stlnode.FinallyNode:
                    innermost = innermost.operand
                inner_eng = clean_for_composition(innermost.__to_english__())
                return f"{inner_eng} will happen infinitely often"
            inner_eng = clean_for_composition(inner_op.__to_english__())
            if type(inner_op) is stlnode.LiteralNode:
                return f"{inner_eng} will happen infinitely often"
            return f"it is always the case that eventually {inner_eng}"
    return None


#### Final State Patterns ####

def _check_final_state_pattern(node, right_node_type):
    """Helper to check if a node matches the final state pattern G(p -> Op p).
    
    Args:
        node: The node to check
        right_node_type: The expected type for the right side operator (GloballyNode)
    
    Returns:
        English translation if pattern matches, None otherwise
    """
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.ImpliesNode:
            left = op.left
            right = op.right
            if type(right) is right_node_type:
                # Check if both left and right.operand are literals with the same value
                if (type(left) is stlnode.LiteralNode and
                    type(right.operand) is stlnode.LiteralNode and
                    left.value == right.operand.value):
                    left_eng = clean_for_composition(left.__to_english__())
                    return choose_best_sentence([
                        f"once {left_eng} is true, it stays true",
                        f"once {left_eng} becomes true, it remains true",
                        f"after {left_eng} holds, it continues to hold forever"
                    ])
    return None


# Pattern: G (p -> G p)
# English: Once p (holds), it will always hold.
@pattern
def final_state_globally_pattern(node):
    return _check_final_state_pattern(node, stlnode.GloballyNode)


## Chain precedence
# Pattern G(p -> (q U r))
# English: Whenever p (happens), q will (hold) until r (holds)

@pattern
def chain_precedence_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.ImpliesNode:
            left = op.left
            right = op.right
            if type(right) is stlnode.UntilNode:
                lhs = right.left
                rhs = right.right
                left_eng = clean_for_composition(left.__to_english__())
                lhs_eng = clean_for_composition(lhs.__to_english__())
                rhs_eng = clean_for_composition(rhs.__to_english__())
                return f"from {node.low} to {node.high}, whenever {left_eng}, {lhs_eng} until {rhs_eng} between {right.low} and {right.high}"
    return None


## Chain response
# Pattern: G (p -> ( (F q) & (F r) ) )
# English: Whenever p (holds), q and r will (hold) eventually
@pattern
def chain_response_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.ImpliesNode:
            left = op.left
            right = op.right
            if type(right) is stlnode.AndNode:
                lhs = right.left
                rhs = right.right
                if type(lhs) is stlnode.FinallyNode and type(rhs) is stlnode.FinallyNode:
                    left_eng = clean_for_composition(left.__to_english__())
                    lhs_eng = clean_for_composition(lhs.operand.__to_english__())
                    rhs_eng = clean_for_composition(rhs.operand.__to_english__())
                    return f"from {node.low} to {node.high}, whenever {left_eng}, eventually, between {lhs.low} and {lhs.high}, {lhs_eng} and between {rhs.low} and {rhs.high}, {rhs_eng}"
    return None



## G !p
# English: It will never be the case that p (holds)
@pattern
def never_globally_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.NotNode:
            negated = op.operand
            negated_eng = clean_for_composition(negated.__to_english__())
            # For literals, use simpler phrasing with multiple alternatives
            if type(negated) is stlnode.LiteralNode:
                patterns = [
                    f"from {node.low} to {node.high}, {negated_eng} will never occur",
                    f"between {node.low} and {node.high}, always avoid {negated_eng}",
                    f"from {node.low} to {node.high}, never {negated_eng}",
                    f"between {node.low} and {node.high}, {negated_eng} must never happen"
                ]
                return choose_best_sentence(patterns)
            return f"from {node.low} to {node.high}, it is never the case that {negated_eng}"


#### Finally special cases ####

# F F ... F p (idempotent finally - F F = F)
# English: Eventually p
# Source: F is idempotent: F F p ≡ F p
@pattern
def idempotent_finally_pattern_to_english(node):
    if type(node) is stlnode.FinallyNode:
        op = node.operand
        if type(op) is stlnode.FinallyNode:
            # Unwrap all consecutive Finally operators
            innermost = op.operand
            while type(innermost) is stlnode.FinallyNode:
                innermost = innermost.operand
            inner_eng = clean_for_composition(innermost.__to_english__())
            return f"from {node.low} to {node.high}, eventually, {inner_eng}"
    return None


# F ( !p )
# English: Eventually, it will not be the case that p (holds)
@pattern
def finally_not_pattern_to_english(node):
    if type(node) is stlnode.FinallyNode:
        op = node.operand
        if type(op) is stlnode.NotNode:
            negated_eng = clean_for_composition(op.operand.__to_english__())
            # For literals, simpler phrasing
            if type(op.operand) is stlnode.LiteralNode:
                return f"from {node.low} to {node.high}, eventually, not {negated_eng}"
            return f"eventually, from {node.low} to {node.high}, it will not be the case that {negated_eng}"
    return None


# F (G !p)
# English: Eventually, it will never be the case that p (holds)
@pattern
def finally_never_globally_pattern_to_english(node):
    if type(node) is stlnode.FinallyNode:
        op = node.operand
        if type(op) is stlnode.GloballyNode:
            negated = op.operand
            if type(negated) is stlnode.NotNode:
                negated_eng = clean_for_composition(negated.operand.__to_english__())
                return f"eventually, between {node.low} and {node.high}, {negated_eng} will never occur again"
    return None


# F (G p)
# English: Eventually, p will always (hold)
# Note: Skip if inner is an ImpliesNode with Finally on right - let more specific pattern handle it
@pattern
def finally_globally_pattern_to_english(node):
    if type(node) is stlnode.FinallyNode:
        op = node.operand
        if type(op) is stlnode.GloballyNode:
            inner = op.operand
            # Skip if inner is implication with Finally - let more specific pattern handle it
            if type(inner) is stlnode.ImpliesNode and type(inner.right) is stlnode.FinallyNode:
                return None
            # Skip if inner is AndNode - let persistence pattern handle it
            if type(inner) is stlnode.AndNode:
                return None
            # Handle F G (p -> q) - "eventually, the rule 'if p then q' will always hold"
            if type(inner) is stlnode.ImpliesNode:
                left_eng = clean_for_composition(inner.left.__to_english__())
                right_eng = clean_for_composition(inner.right.__to_english__())
                return f"between {node.low} and {node.high}, eventually, the rule 'if {left_eng} then {right_eng}' will always hold from {op.low} to {op.high}"
            # Handle F G F ... patterns (eventual recurrence) - collapses to G F by absorption
            # Source: Manna & Pnueli - alternating F/G chains simplify
            if type(inner) is stlnode.FinallyNode:
                # F G F x = "eventually, x will happen infinitely often"
                # Keep unwinding to find the innermost
                innermost = inner.operand
                while type(innermost) is stlnode.GloballyNode or type(innermost) is stlnode.FinallyNode:
                    innermost = innermost.operand
                inner_eng = clean_for_composition(innermost.__to_english__())
                return f"between {node.low} and {node.high}, eventually, {inner_eng} will happen infinitely often"
            # Handle F G G x = F G x (G G = G)
            if type(inner) is stlnode.GloballyNode:
                innermost = inner.operand
                while type(innermost) is stlnode.GloballyNode:
                    innermost = innermost.operand
                inner_eng = clean_for_composition(innermost.__to_english__())
                return f"between {node.low} and {node.high}, eventually, {inner_eng} will become true and remain true from {inner.low} to {inner.high}"
            inner_eng = clean_for_composition(inner.__to_english__())
            return f"between {node.low} and {node.high}, eventually, {inner_eng} will be true from {op.low} to {op.high}"
    return None


## Persistence Pattern (Stability)
# Pattern: F(G p)
# English: Eventually p will become true and remain true forever
# Source: Manna, Z. and Pnueli, A. "The Temporal Logic of Reactive and Concurrent Systems" (1992)
#         Also known as "stability" - the system eventually stabilizes to a state where p holds
# Note: This is the same structure as finally_globally but with literal-specific phrasing
@pattern
def persistence_pattern_to_english(node):
    if type(node) is stlnode.FinallyNode:
        op = node.operand
        if type(op) is stlnode.GloballyNode:
            inner = op.operand
            # Only match simple literals for this specific phrasing
            if type(inner) is stlnode.LiteralNode:
                inner_eng = clean_for_composition(inner.__to_english__())
                return f"between {node.low} and {node.high}, eventually {inner_eng} will become true and stay true from {op.low} to {op.high}"
    return None


## Persistence After Trigger Pattern
# Pattern: F(p & G q)
# English: Eventually p will occur and from that point on, q will always hold
# Source: Dwyer et al. "Patterns in Property Specifications" ICSE 1999
#         This captures scenarios where a trigger event causes a permanent change
@pattern
def persistence_after_trigger_pattern_to_english(node):
    if type(node) is stlnode.FinallyNode:
        op = node.operand
        if type(op) is stlnode.AndNode:
            left = op.left
            right = op.right
            # Check for p & G q
            if type(right) is stlnode.GloballyNode:
                trigger_eng = clean_for_composition(left.__to_english__())
                persistent_eng = clean_for_composition(right.operand.__to_english__())
                return f"between {node.low} and {node.high}, eventually {trigger_eng} will occur, and from then on {persistent_eng} will always hold"
            # Check for G p & q (reversed order)
            if type(left) is stlnode.GloballyNode:
                trigger_eng = clean_for_composition(right.__to_english__())
                persistent_eng = clean_for_composition(left.operand.__to_english__())
                return f"between {node.low} and {node.high}, eventually {trigger_eng} will occur, and from then on {persistent_eng} will always hold"
    return None


## Trigger-to-Permanence Pattern
# Pattern: F(p -> G q)
# English: Eventually, once p occurs, q will hold forever after
# Source: Common requirements pattern - "eventually a trigger causes permanent behavior"
@pattern
def trigger_to_permanence_pattern_to_english(node):
    if type(node) is stlnode.FinallyNode:
        op = node.operand
        if type(op) is stlnode.ImpliesNode:
            left = op.left
            right = op.right
            if type(right) is stlnode.GloballyNode:
                trigger_eng = clean_for_composition(left.__to_english__())
                result_eng = clean_for_composition(right.operand.__to_english__())
                return f"between {node.low} and {node.high}, eventually, once {trigger_eng}, then {result_eng} will hold forever after"
    return None


# F (p & q)
# English: Eventually at the same time, p and q will (hold)
@pattern
def finally_and_pattern_to_english(node):
    if type(node) is stlnode.FinallyNode:
        op = node.operand
        if type(op) is stlnode.AndNode:
            # Skip if one side is GloballyNode - let persistence_after_trigger handle it
            if type(op.left) is stlnode.GloballyNode or type(op.right) is stlnode.GloballyNode:
                return None
            left_eng = clean_for_composition(op.left.__to_english__())
            right_eng = clean_for_composition(op.right.__to_english__())
            return f"between {node.low} and {node.high}, eventually, both {left_eng} and {right_eng} will be true simultaneously"
    return None

# ! (F p)
# English: It will never be the case that p (holds)
@pattern
def not_finally_pattern_to_english(node):
    if type(node) is stlnode.NotNode:
        op = node.operand
        if type(op) is stlnode.FinallyNode:
            inner_eng = clean_for_composition(op.operand.__to_english__())
            patterns = [
                f"from {node.low} to {node.high}, {inner_eng} will never occur",
                f"from {node.low} to {node.high}, never {inner_eng}",
                f"from {node.low} to {node.high}, {inner_eng} is impossible"
            ]
            return choose_best_sentence(patterns)
    return None

### Until special cases ###

# (p U q) U r
# English: p will (hold) until q (holds), and this will continue until r (holds)
@pattern
def nested_until_pattern_to_english(node):
    if type(node) is stlnode.UntilNode:
        left = node.left
        right = node.right
        if type(left) is stlnode.UntilNode:
            p_eng = clean_for_composition(left.left.__to_english__())
            q_eng = clean_for_composition(left.right.__to_english__())
            r_eng = clean_for_composition(right.__to_english__())
            return f"{p_eng} until {q_eng} from {left.low} to {left.high}, and from {node.low} to {node.high} this continues until {r_eng}"
    return None


#### Context-aware patterns for nested temporal operators ####
# These patterns help address deictic shift issues where temporal references can be ambiguous

# Pattern: G(F(p & q))
# English: at all times, there will eventually be a point where both p and q hold simultaneously
@pattern
def globally_finally_and_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.FinallyNode:
            inner = op.operand
            if type(inner) is stlnode.AndNode:
                left_eng = clean_for_composition(inner.left.__to_english__())
                right_eng = clean_for_composition(inner.right.__to_english__())
                return f"at all times between {node.low} and {node.high}, there will eventually be a point from {op.low} to {op.high} where both {left_eng} and {right_eng} hold simultaneously"
    return None


# Pattern: F(G(p -> F q))
# English: eventually we reach a point where, from then on, whenever p then eventually q
@pattern
def finally_globally_implies_finally_pattern_to_english(node):
    if type(node) is stlnode.FinallyNode:
        op = node.operand
        if type(op) is stlnode.GloballyNode:
            inner = op.operand
            if type(inner) is stlnode.ImpliesNode:
                if type(inner.right) is stlnode.FinallyNode:
                    left_eng = clean_for_composition(inner.left.__to_english__())
                    right_eng = clean_for_composition(inner.right.operand.__to_english__())
                    return f"eventually, between {node.low} and {node.high}, we reach a point where, between {op.low} and {op.high}, whenever {left_eng} then eventually from {inner.right.low} to {inner.right.high} {right_eng}"
    return None


# Pattern: (G p) U (F q)
# English: at all times p holds, and this continues until eventually q occurs
@pattern
def globally_until_finally_pattern_to_english(node):
    if type(node) is stlnode.UntilNode:
        left = node.left
        right = node.right
        if type(left) is stlnode.GloballyNode and type(right) is stlnode.FinallyNode:
            left_eng = clean_for_composition(left.operand.__to_english__())
            right_eng = clean_for_composition(right.operand.__to_english__())
            return f"at all times between {node.low} and {node.high}, {left_eng}, and this continues until eventually {right_eng} occurs between {right.low} and {right.high}"
    return None


# Pattern: G((p U q) -> F r)
# English: whenever p until q, eventually r will occur
@pattern
def globally_until_implies_finally_pattern_to_english(node):
    if type(node) is stlnode.GloballyNode:
        op = node.operand
        if type(op) is stlnode.ImpliesNode:
            left = op.left
            right = op.right
            if type(left) is stlnode.UntilNode and type(right) is stlnode.FinallyNode:
                p_eng = clean_for_composition(left.left.__to_english__())
                q_eng = clean_for_composition(left.right.__to_english__())
                r_eng = clean_for_composition(right.operand.__to_english__())
                return f"from {left.low} to {left.high}, whenever {p_eng} until {q_eng}, eventually, between {right.low} and {right.high}, {r_eng} will occur"
    return None


#### Propositional Logic Patterns ####
# These patterns handle common propositional logic structures that can be awkward in English
# Source: Standard logical equivalences and De Morgan's laws

# Pattern: !!p (double negation)
# English: p (simplified)
@pattern
def double_negation_pattern_to_english(node):
    if type(node) is stlnode.NotNode:
        op = node.operand
        if type(op) is stlnode.NotNode:
            inner_eng = op.operand.__to_english__()
            return inner_eng  # Already capitalized from inner call
    return None


# Pattern: !(p & q) (negated conjunction - De Morgan)
# English: not both p and q / either not p or not q
# Source: De Morgan's Laws - more natural to say "not both" than "it is not the case that both"
@pattern
def negated_and_pattern_to_english(node):
    if type(node) is stlnode.NotNode:
        op = node.operand
        if type(op) is stlnode.AndNode:
            left_eng = clean_for_composition(op.left.__to_english__())
            right_eng = clean_for_composition(op.right.__to_english__())
            return f"not both {left_eng} and {right_eng}"
    return None


# Pattern: !(p | q) (negated disjunction - De Morgan)  
# English: neither p nor q
# Source: De Morgan's Laws - "neither...nor" is the natural English form
@pattern
def negated_or_pattern_to_english(node):
    if type(node) is stlnode.NotNode:
        op = node.operand
        if type(op) is stlnode.OrNode:
            left_eng = clean_for_composition(op.left.__to_english__())
            right_eng = clean_for_composition(op.right.__to_english__())
            return f"neither {left_eng} nor {right_eng}"
    return None


# Pattern: !(p -> q) (negated implication)
# English: p but not q
# Logically equivalent to: p & !q
# Source: Material implication - negating "if p then q" means p is true but q is false
@pattern
def negated_implication_pattern_to_english(node):
    if type(node) is stlnode.NotNode:
        op = node.operand
        if type(op) is stlnode.ImpliesNode:
            left_eng = clean_for_composition(op.left.__to_english__())
            right_eng = clean_for_composition(op.right.__to_english__())
            return f"{left_eng}, but not {right_eng}"
    return None


# Pattern: p -> !q
# English: if p, then not q / p excludes q
@pattern
def implies_negation_pattern_to_english(node):
    if type(node) is stlnode.ImpliesNode:
        right = node.right
        if type(right) is stlnode.NotNode:
            left_eng = clean_for_composition(node.left.__to_english__())
            right_eng = clean_for_composition(right.operand.__to_english__())
            # For simple literals, use cleaner phrasing
            if type(node.left) is stlnode.LiteralNode and type(right.operand) is stlnode.LiteralNode:
                return f"{left_eng} excludes {right_eng}"
            return f"if {left_eng}, then not {right_eng}"
    return None


# Pattern: !p -> q  
# English: if not p, then q / q unless p
@pattern
def negation_implies_pattern_to_english(node):
    if type(node) is stlnode.ImpliesNode:
        left = node.left
        if type(left) is stlnode.NotNode:
            left_eng = clean_for_composition(left.operand.__to_english__())
            right_eng = clean_for_composition(node.right.__to_english__())
            return f"{right_eng} unless {left_eng}"
    return None


# Pattern: !p & !q
# English: neither p nor q (same as !(p | q) by De Morgan)
@pattern
def and_of_negations_pattern_to_english(node):
    if type(node) is stlnode.AndNode:
        left = node.left
        right = node.right
        if type(left) is stlnode.NotNode and type(right) is stlnode.NotNode:
            left_eng = clean_for_composition(left.operand.__to_english__())
            right_eng = clean_for_composition(right.operand.__to_english__())
            return f"neither {left_eng} nor {right_eng}"
    return None


# Pattern: !p | !q
# English: not both p and q (same as !(p & q) by De Morgan)
@pattern
def or_of_negations_pattern_to_english(node):
    if type(node) is stlnode.OrNode:
        left = node.left
        right = node.right
        if type(left) is stlnode.NotNode and type(right) is stlnode.NotNode:
            left_eng = clean_for_composition(left.operand.__to_english__())
            right_eng = clean_for_composition(right.operand.__to_english__())
            return f"not both {left_eng} and {right_eng}"
    return None


# Pattern: (p & q) -> r
# English: if both p and q, then r
@pattern
def conjunction_implies_pattern_to_english(node):
    if type(node) is stlnode.ImpliesNode:
        left = node.left
        if type(left) is stlnode.AndNode:
            p_eng = clean_for_composition(left.left.__to_english__())
            q_eng = clean_for_composition(left.right.__to_english__())
            r_eng = clean_for_composition(node.right.__to_english__())
            return f"if both {p_eng} and {q_eng}, then {r_eng}"
    return None


# Pattern: (p | q) -> r
# English: if either p or q, then r
@pattern
def disjunction_implies_pattern_to_english(node):
    if type(node) is stlnode.ImpliesNode:
        left = node.left
        if type(left) is stlnode.OrNode:
            p_eng = clean_for_composition(left.left.__to_english__())
            q_eng = clean_for_composition(left.right.__to_english__())
            r_eng = clean_for_composition(node.right.__to_english__())
            return f"if either {p_eng} or {q_eng}, then {r_eng}"
    return None


# Pattern: p -> (q & r)
# English: if p, then both q and r
@pattern
def implies_conjunction_pattern_to_english(node):
    if type(node) is stlnode.ImpliesNode:
        right = node.right
        if type(right) is stlnode.AndNode:
            # Skip if this looks like a temporal pattern (F inside)
            if type(right.left) is stlnode.FinallyNode or type(right.right) is stlnode.FinallyNode:
                return None
            p_eng = clean_for_composition(node.left.__to_english__())
            q_eng = clean_for_composition(right.left.__to_english__())
            r_eng = clean_for_composition(right.right.__to_english__())
            return f"if {p_eng}, then both {q_eng} and {r_eng}"
    return None


# Pattern: p -> (q | r)
# English: if p, then either q or r
@pattern
def implies_disjunction_pattern_to_english(node):
    if type(node) is stlnode.ImpliesNode:
        right = node.right
        if type(right) is stlnode.OrNode:
            p_eng = clean_for_composition(node.left.__to_english__())
            q_eng = clean_for_composition(right.left.__to_english__())
            r_eng = clean_for_composition(right.right.__to_english__())
            return f"if {p_eng}, then either {q_eng} or {r_eng}"
    return None


def apply_special_pattern_if_possible(node):

    for pattern in patterns:
        result = pattern(node)
        if result is not None:
            # Apply grammar smoothing but NOT capitalization (defer to finalize_sentence)
            result = smooth_grammar(result)
            return result
    return None




#import language_tool_python


def correct_grammar(text):
    return text

    # with language_tool_python.LanguageTool('en-US') as languageTool:
    #     corrected_text = languageTool.correct(text)

    # ## Now, if any text is in single quotes, make it lowecase
    # corrected_text = re.sub(r"'(.*?)'", lambda x: f"'{x.group(1).lower()}'", corrected_text)
    # return corrected_text
