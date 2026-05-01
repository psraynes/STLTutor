# Description: This file contains the classes for the nodes of the STL syntax tree.

import os
import random

### TODO: Ideally, this should not be in 
### src, but mocked in the test directory.


#from spotutils import areEquivalent


from stlListener import stlListener
from antlr4 import CommonTokenStream, ParseTreeWalker
from antlr4 import ParseTreeWalker, CommonTokenStream, InputStream
from stlLexer import stlLexer
from stlParser import stlParser
from abc import ABC, abstractmethod
import stltoeng as stltoeng


SUPPORTED_SYNTAXES = ['Classic', 'Forge', 'Electrum']

## Should these come from the lexer instead of being placed here
IMPLIES_SYMBOL = '=>'
AND_SYMBOL = '&'
OR_SYMBOL = '|'
NOT_SYMBOL = '!'
GLOBALLY_SYMBOL = 'G'
FINALLY_SYMBOL = 'F'
UNTIL_SYMBOL = 'U'
LESS_THAN_SYMBOL = '<'
LESS_THAN_OR_EQUAL_SYMBOL = '<='
GREATER_THAN_SYMBOL = '>'
GREATER_THAN_OR_EQUAL_SYMBOL = '>='
EQUAL_SYMBOL = '='

# Operator precedence (higher number = binds tighter)
OPERATOR_PRECEDENCE = {
    'Until': 1,
    'Or': 2,
    'And': 3,
    'Not': 4,
    'Globally': 5,
    'Finally': 5,
    'Literal': 10
}


class STLNode(ABC):
    def __init__(self, type):
        self.type = type

    """
        STL Node in Classic/ Spot Syntax
    """
    @abstractmethod
    def __str__(self):
        pass

    """
        STL Node in English
    """
    @abstractmethod
    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        # We should draw inspiration from:
        # https://matthewbdwyer.github.io/psp/patterns/stl.html
        pass

    """
        STLNode in Forge Syntax
    """
    @abstractmethod
    def __forge__(self):
        pass
    
    """
        STLNode in Electrum Syntax
    """
    @abstractmethod
    def __electrum__(self):
        pass 


    @staticmethod
    def equiv(formula1, formula2):
        return False # Look into PyTeLo stl_distance

class stlListenerImpl(stlListener) :
    def __init__(self):
        self.stack = []

    def exitFormula(self, ctx):
        node = None
        if ctx.op.type == stlParser.AND:
            right = self.stack.pop()
            left = self.stack.pop()
            node = AndNode(left, right)
        elif ctx.op.type == stlParser.OR:
            right = self.stack.pop()
            left = self.stack.pop()
            node = OrNode(left, right)
        elif ctx.op.type == stlParser.IMPLIES:
            right = self.stack.pop()
            left = self.stack.pop()
            node = ImpliesNode(left, right)
        elif ctx.op.type == stlParser.NOT:
            operand = self.stack.pop()
            node = NotNode(operand)
        elif ctx.op.type == stlParser.EVENT:
            operand = self.stack.pop()
            node = FinallyNode(operand, ctx.low.text, ctx.high.text)
        elif ctx.op.type == stlParser.ALWAYS:
            operand = self.stack.pop()
            node = GloballyNode(operand, ctx.low.text, ctx.high.text)
        elif ctx.op.type == stlParser.UNTIL:
            right = self.stack.pop()
            left = self.stack.pop()
            node = UntilNode(left, right, ctx.low.text, ctx.high.text)

        self.stack.append(node)

    def exitExpr(self, ctx):
        value = ctx.getText()
        literalNode = LiteralNode(value)
        self.stack.append(literalNode)

    def exitBooleanExpr(self, ctx):
        right = self.stack.pop()
        left = self.stack.pop()
        node = BooleanOperatorNode(ctx.op.text, left, right)
        if ctx.op.text == LESS_THAN_SYMBOL:
            node = LessThanNode(left, right)
        elif ctx.op.text == LESS_THAN_OR_EQUAL_SYMBOL:
            node = LessThanOrEqualNode(left, right)
        elif ctx.op.text == GREATER_THAN_SYMBOL:
            node = GreaterThanNode(left, right)
        elif ctx.op.text == GREATER_THAN_OR_EQUAL_SYMBOL:
            node = GreaterThanOrEqualNode(left, right)
        elif ctx.op.text == EQUAL_SYMBOL:
            node = EqualNode(left, right)
        self.stack.append(node)

    def getRootFormula(self):
        return self.stack[-1]


class UnaryOperatorNode(STLNode):
    def __init__(self, operator, operand):
        super().__init__('UnaryOperator')
        self.operator = operator
        self.operand = operand

    def __str__(self):
        return f'({self.operator} {str(self.operand)})'
    
    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        return self.__str__()
    
    def __forge__(self):
        return f"({self.operator} {self.operand.__forge__()})"
    
    def __electrum__(self):
        return f"({self.operator} {self.operand.__electrum__()})"

class TemporalUnaryOperatorNode(UnaryOperatorNode):
    def __init__(self, operator, operand, low=None, high=None):
        super().__init__(operator, operand)
        self.low = low
        self.high = high

    def __str__(self):
        if self.low is not None and self.high is not None:
            return f'({self.operator}[{self.low},{self.high}] {str(self.operand)})'
        else:
            return f'({self.operator} {str(self.operand)})'


class BinaryOperatorNode(STLNode):
    def __init__(self, operator, left, right):
        super().__init__('BinaryOperator')
        self.operator = operator
        self.left = left
        self.right = right

    def __str__(self):
        return f'({str(self.left)} {self.operator} {str(self.right)})'
    
    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        return self.__str__()
    
    def __forge__(self):
        return f"({self.left.__forge__()} {self.operator} {self.right.__forge__()})"
    
    def __electrum__(self):
        return f"({self.left.__electrum__()} {self.operator} {self.right.__electrum__()})"

class TemporalBinaryOperatorNode(BinaryOperatorNode):
    def __init__(self, operator, left, right, low=None, high=None):
        super().__init__(operator, left, right)
        self.low = low
        self.high = high

    def __str__(self):
        if self.low is not None and self.high is not None:
            return f'({str(self.left)} {self.operator}[{self.low},{self.high}] {str(self.right)})'
        else:
            return f'({str(self.left)} {self.operator} {str(self.right)})'
    
class BooleanOperatorNode(STLNode):
    def __init__(self, operator, left, right):
        super().__init__('BinaryOperator')
        self.operator = operator
        self.left = left
        self.right = right

    def __str__(self):
        return f'({str(self.left)} {self.operator} {str(self.right)})'
    
    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        return self.__str__()
    
    def __forge__(self):
        return f"({self.left.__forge__()} {self.operator} {self.right.__forge__()})"
    
    def __electrum__(self):
        return f"({self.left.__electrum__()} {self.operator} {self.right.__electrum__()})"


class LiteralNode(STLNode):
    def __init__(self, value):
        super().__init__('Literal')
        self.value = value

    def __str__(self):
        return self.value
    
    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x

        # For literals, use simpler phrasing
        # Note: We don't capitalize here because the literal is in quotes
        # and should remain as-is per capitalize_sentence() logic
        return f"'{self.value}'"
    
    def __forge__(self):
        return self.value
    
    def __electrum__(self):
        return self.value


class UntilNode(TemporalBinaryOperatorNode):
    symbol = UNTIL_SYMBOL
    def __init__(self, left, right, low=None, high=None):
        super().__init__(UntilNode.symbol, left, right, low, high)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        lhs = self.left.__to_english__().rstrip('.')
        rhs = self.right.__to_english__().rstrip('.')
        
        # For simple literals, provide more natural alternatives
        if type(self.left) is LiteralNode and type(self.right) is LiteralNode:
            patterns = [
                f"{lhs} until {rhs}",
                f"{lhs} holds until {rhs} occurs",
                f"maintain {lhs} until {rhs}"
            ]
            return stltoeng.choose_best_sentence(patterns)
        
        return f"{lhs} until {rhs}"
    
    def __forge__(self):
        if self.low is not None and self.high is not None:
            return f'({str(self.left)} UNTIL {self.operator}[{self.low},{self.high}] {str(self.right)})'
        else:
            return f"({self.left.__forge__()} UNTIL {self.right.__forge__()})"
    
    def __electrum__(self):
        if self.low is not None and self.high is not None:
            return f'({str(self.left)} UNTIL {self.operator}[{self.low},{self.high}] {str(self.right)})'
        else:
            return f"({self.left.__forge__()} UNTIL {self.right.__forge__()})"


class GloballyNode(TemporalUnaryOperatorNode):
    symbol = GLOBALLY_SYMBOL
    def __init__(self, operand, low=None, high=None):
        super().__init__(GloballyNode.symbol, operand, low, high)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x

        op = self.operand.__to_english__().rstrip('.')
        
        # Provide more natural alternatives
        patterns = [
            f"from {self.low} to {self.high}, {op}",
            f"{op} is always true from {self.low} to {self.high}",
            f"{op} is always true between {self.low} to {self.high}",
            f"{op} holds between {self.low} to {self.high}"
        ]

        english = stltoeng.choose_best_sentence(patterns)
        return english
    
    def __forge__(self):
        if self.low is not None and self.high is not None:
            return f'(ALWAYS {str(self.operand)} FROM [{self.low},{self.high}])'
        else:
            return f"(ALWAYS {self.operand.__forge__()})"
    
    def __electrum__(self):
        if self.low is not None and self.high is not None:
            return f'(ALWAYS {str(self.operand)} FROM [{self.low},{self.high}])'
        else:
            return f"(ALWAYS {self.operand.__electrum__()})"


class FinallyNode(TemporalUnaryOperatorNode):
    symbol = FINALLY_SYMBOL
    def __init__(self, operand, low=None, high=None):
        super().__init__(FinallyNode.symbol, operand, low, high)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        op = self.operand.__to_english__().rstrip('.')

        # Provide more natural alternatives
        if type(self.operand) is LiteralNode:
            patterns = [
                f"eventually, between {self.low} and {self.high}, {op}",
                f"{op} will eventually occur between {self.low} and {self.high}",
                f"at some point from {self.low} to {self.high}, {op} will hold",
                f"at some point between {self.low} to {self.high}, {op} will hold"
            ]
            return stltoeng.choose_best_sentence(patterns)
        
        return f"eventually, between {self.low} and {self.high}, {op}"
    
    def __forge__(self):
        if self.low is not None and self.high is not None:
            return f'(EVENTUALLY {str(self.operand)} FROM [{self.low},{self.high}])'
        else:
            return f"(EVENTUALLY {self.operand.__forge__()})"
    
    def __electrum__(self):
        if self.low is not None and self.high is not None:
            return f'(EVENTUALLY {str(self.operand)} FROM [{self.low},{self.high}])'
        else:
            return f"(EVENTUALLY {self.operand.__electrum__()})"


class OrNode(BinaryOperatorNode):

    symbol = OR_SYMBOL

    def __init__(self, left, right):
        super().__init__(OrNode.symbol, left, right)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        lhs = self.left.__to_english__().rstrip('.')
        rhs = self.right.__to_english__().rstrip('.')
        
        # Provide alternatives for simple literals
        if type(self.left) is LiteralNode and type(self.right) is LiteralNode:
            patterns = [
                f"either {lhs} or {rhs}",
                f"{lhs} or {rhs}",
                f"at least one of {lhs} or {rhs}"
            ]
            return stltoeng.choose_best_sentence(patterns)
        
        return f"either {lhs} or {rhs}"
    



class AndNode(BinaryOperatorNode):
    symbol = AND_SYMBOL
    def __init__(self, left, right):
        super().__init__(AndNode.symbol, left, right)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        lhs = self.left.__to_english__().rstrip('.')
        rhs = self.right.__to_english__().rstrip('.')
        
        # Provide alternatives for simple literals
        if type(self.left) is LiteralNode and type(self.right) is LiteralNode:
            patterns = [
                f"both, {lhs} and {rhs}",
                f"{lhs} and {rhs}",
                f"{lhs} together with {rhs}"
            ]
            return stltoeng.choose_best_sentence(patterns)
        
        return f"both {lhs} and {rhs}"


class NotNode(UnaryOperatorNode):
    symbol = NOT_SYMBOL
    def __init__(self, operand):
        super().__init__(NotNode.symbol, operand)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x

        op = self.operand.__to_english__().rstrip('.')

        ## If the operand is a literal, we can just negate it with alternatives
        if isinstance(self.operand, LiteralNode):
            patterns = [
                f"not {op}",
                f"{op} does not hold",
                f"{op} is false"
            ]
            return stltoeng.choose_best_sentence(patterns)
        else:
            return f"it is not the case that {op}"

class ImpliesNode(BinaryOperatorNode):
    symbol = IMPLIES_SYMBOL
    def __init__(self, left, right):
        super().__init__(ImpliesNode.symbol, left, right)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
            
        lhs = self.left.__to_english__().rstrip('.')
        rhs = self.right.__to_english__().rstrip('.')

        lhs = stltoeng.normalize_embedded_clause(lhs)
        rhs = stltoeng.normalize_embedded_clause(rhs)

        # Potential patterns:
        patterns = [
            f"if {lhs}, then {rhs}",
            f"{lhs} implies {rhs}",
            f"whenever {lhs}, then {rhs}"
        ]

        # Choose the most fluent pattern rather than picking randomly
        english = stltoeng.choose_best_sentence(patterns)
        return english

class LessThanNode(BooleanOperatorNode):
    symbol = LESS_THAN_SYMBOL
    def __init__(self, left, right):
        super().__init__(LessThanNode.symbol, left, right)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        lhs = self.left.__to_english__().rstrip('.')
        rhs = self.right.__to_english__().rstrip('.')
        
        # Provide alternatives for simple literals
        if type(self.left) is LiteralNode and type(self.right) is LiteralNode:
            patterns = [
                f"{lhs} is less than {rhs}",
                f"there are fewer than {rhs} {lhs}"
            ]
            return stltoeng.choose_best_sentence(patterns)
        
        return f"{lhs} is less than {rhs}"

class LessThanOrEqualNode(BooleanOperatorNode):
    symbol = LESS_THAN_OR_EQUAL_SYMBOL
    def __init__(self, left, right):
        super().__init__(LessThanOrEqualNode.symbol, left, right)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        lhs = self.left.__to_english__().rstrip('.')
        rhs = self.right.__to_english__().rstrip('.')
        
        # Provide alternatives for simple literals
        if type(self.left) is LiteralNode and type(self.right) is LiteralNode:
            patterns = [
                f"{lhs} is less than or equal to {rhs}",
                f"there are at most {rhs} {lhs}"
            ]
            return stltoeng.choose_best_sentence(patterns)
        
        return f"{lhs} is less than or equal to {rhs}"

class GreaterThanNode(BooleanOperatorNode):
    symbol = GREATER_THAN_SYMBOL
    def __init__(self, left, right):
        super().__init__(GreaterThanNode.symbol, left, right)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        lhs = self.left.__to_english__().rstrip('.')
        rhs = self.right.__to_english__().rstrip('.')
        
        # Provide alternatives for simple literals
        if type(self.left) is LiteralNode and type(self.right) is LiteralNode:
            patterns = [
                f"{lhs} is greater than {rhs}",
                f"there are more than {rhs} {lhs}"
            ]
            return stltoeng.choose_best_sentence(patterns)
        
        return f"{lhs} is greater than {rhs}"

class GreaterThanOrEqualNode(BooleanOperatorNode):
    symbol = GREATER_THAN_OR_EQUAL_SYMBOL
    def __init__(self, left, right):
        super().__init__(GreaterThanOrEqualNode.symbol, left, right)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        lhs = self.left.__to_english__().rstrip('.')
        rhs = self.right.__to_english__().rstrip('.')
        
        # Provide alternatives for simple literals
        if type(self.left) is LiteralNode and type(self.right) is LiteralNode:
            patterns = [
                f"{lhs} is greater than or equal to {rhs}",
                f"there are at least {rhs} {lhs}"
            ]
            return stltoeng.choose_best_sentence(patterns)
        
        return f"{lhs} is greater than or equal to {rhs}"

class EqualNode(BooleanOperatorNode):
    symbol = EQUAL_SYMBOL
    def __init__(self, left, right):
        super().__init__(EqualNode.symbol, left, right)

    def __to_english__(self):
        x = stltoeng.apply_special_pattern_if_possible(self)
        if x is not None:
            return x
        lhs = self.left.__to_english__().rstrip('.')
        rhs = self.right.__to_english__().rstrip('.')
        
        # Provide alternatives for simple literals
        if type(self.left) is LiteralNode and type(self.right) is LiteralNode:
            patterns = [
                f"{lhs} is equal to {rhs}",
                f"{lhs} equals {rhs}",
                f"{lhs} is {rhs}"
            ]
            return stltoeng.choose_best_sentence(patterns)
        
        return f"{lhs} is equal to {rhs}"


def parse_stl_string(s):
    # Create an input stream from the string
    input_stream = InputStream(s)

    # Create a lexer and a token stream
    lexer = stlLexer(input_stream)
    token_stream = CommonTokenStream(lexer)

    # Create the parser and parse the input
    parser = stlParser(token_stream)
    tree = parser.stlProperty()

    # Create a listener
    listener = stlListenerImpl()

    # Create a ParseTreeWalker and walk the parse tree with the listener
    walker = ParseTreeWalker()
    walker.walk(listener, tree)

    # Get the root of the syntax tree
    root = listener.getRootFormula()

    return root

# Added for debugging purposes - can be removed later
if __name__ == "__main__":
    stl_string = "(F[0, 4]s > 2)&&(G[2, 4]s <= 4)"
    stl_tree = parse_stl_string(stl_string)
    print("Parsed STL Tree:", stl_tree)
    print("English:", stl_tree.__to_english__())
