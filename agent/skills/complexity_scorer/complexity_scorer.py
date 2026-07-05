import ast
import re
from typing import Dict, Any

class ComplexityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.cyclomatic = 1
        self.max_nesting = 0
        self.current_nesting = 0
        self.function_lengths = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Calculate function length (lines)
        length = (node.end_lineno - node.lineno) if hasattr(node, 'end_lineno') else 1
        self.function_lengths.append(length)
        
        # Track nesting
        self.current_nesting += 1
        self.max_nesting = max(self.max_nesting, self.current_nesting)
        
        self.generic_visit(node)
        self.current_nesting -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)

    def visit_If(self, node: ast.If):
        self.cyclomatic += 1
        self.current_nesting += 1
        self.max_nesting = max(self.max_nesting, self.current_nesting)
        
        self.generic_visit(node)
        self.current_nesting -= 1

    def visit_For(self, node: ast.For):
        self.cyclomatic += 1
        self.current_nesting += 1
        self.max_nesting = max(self.max_nesting, self.current_nesting)
        
        self.generic_visit(node)
        self.current_nesting -= 1

    def visit_While(self, node: ast.While):
        self.cyclomatic += 1
        self.current_nesting += 1
        self.max_nesting = max(self.max_nesting, self.current_nesting)
        
        self.generic_visit(node)
        self.current_nesting -= 1

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        self.cyclomatic += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        # Each 'and' or 'or' adds 1 decision point
        self.cyclomatic += len(node.values) - 1
        self.generic_visit(node)

def score_file_complexity(content: str, filename: str) -> Dict[str, Any]:
    """Score the complexity of a single file."""
    lines = content.splitlines()
    total_lines = len(lines)
    
    if not content.strip():
        return {
            "cyclomatic": 1,
            "max_nesting": 0,
            "avg_function_length": 0,
            "total_lines": 0
        }

    # For Python files, use AST parsing
    if filename.endswith(".py"):
        try:
            tree = ast.parse(content)
            visitor = ComplexityVisitor()
            visitor.visit(tree)
            
            avg_func_len = sum(visitor.function_lengths) / len(visitor.function_lengths) if visitor.function_lengths else 0
            
            return {
                "cyclomatic": visitor.cyclomatic,
                "max_nesting": visitor.max_nesting,
                "avg_function_length": round(avg_func_len, 2),
                "total_lines": total_lines
            }
        except Exception:
            # Fall back to regex parsing on syntax errors
            pass

    # Regex/line fallback for non-python or unparseable python files
    decisions = len(re.findall(r"\bif\b|\bfor\b|\bwhile\b|\bexcept\b|\band\b|\bor\b", content))
    cyclomatic = 1 + decisions
    
    # Indentation-based nesting approximation
    max_nesting = 0
    for line in lines:
        leading_spaces = len(line) - len(line.lstrip())
        nesting = leading_spaces // 4
        max_nesting = max(max_nesting, nesting)
        
    return {
        "cyclomatic": cyclomatic,
        "max_nesting": max_nesting,
        "avg_function_length": 0,  # difficult to guess without parser
        "total_lines": total_lines
    }

def score_complexity(files: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Compute complexity metrics for a dictionary of {filename: content}."""
    report = {}
    for filename, content in files.items():
        report[filename] = score_file_complexity(content, filename)
    return report
