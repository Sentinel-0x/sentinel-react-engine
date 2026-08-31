import ast

class SecurityASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []
        self.banned_modules = {'os', 'sys', 'subprocess', 'shutil', 'socket', 'ctypes', 'pickle', 'pty', 'fcntl'}
        self.banned_functions = {'system', 'popen', 'eval', 'exec', 'compile', 'getattr', 'setattr', '__import__'}

    def visit_Import(self, node):
        for alias in node.names:
            base_name = alias.name.split('.')[0]
            if base_name in self.banned_modules:
                self.violations.append(f"Banned module import detected: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_name = node.module.split('.')[0]
            if base_name in self.banned_modules:
                self.violations.append(f"Banned import from module detected: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in self.banned_functions:
                self.violations.append(f"Banned function call detected: {node.func.id}()")
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in self.banned_functions or attr_name in {'system', 'popen', 'run', 'call', 'check_output', 'exec', 'eval'}:
                self.violations.append(f"High-risk method call detected: .{attr_name}()")
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id in self.banned_modules:
                    self.violations.append(f"Banned module attribute access/call: {node.func.value.id}.{attr_name}")
        self.generic_visit(node)

def inspect_code_safety(code_str: str) -> list:
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return [f"SyntaxError in code: {e}"]
    visitor = SecurityASTVisitor()
    visitor.visit(tree)
    return visitor.violations
