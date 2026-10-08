import ast

BANNED_MODULES = frozenset({'os', 'sys', 'subprocess', 'shutil', 'socket', 'ctypes', 'pickle', 'pty', 'fcntl'})
BANNED_FUNCTIONS = frozenset({'system', 'popen', 'eval', 'exec', 'compile', 'getattr', 'setattr', '__import__', 'vars', 'globals', 'locals'})


class SecurityASTVisitor(ast.NodeVisitor):
    def __init__(self, allowed_imports=None):
        self.violations = []
        self.banned_modules = set(BANNED_MODULES)
        self.banned_functions = set(BANNED_FUNCTIONS)
        # None = 不启用白名单（保持旧行为）；集合 = 只允许其中的顶层模块
        self.allowed_imports = allowed_imports
        # 追踪被赋值为危险函数/模块的变量名，防止 "e = eval; e(...)" 这类别名绕过
        self.tainted_names = set()

    def _is_banned_name(self, name: str) -> bool:
        return name in self.banned_functions or name in self.banned_modules or name in self.tainted_names

    def visit_Import(self, node):
        for alias in node.names:
            base_name = alias.name.split('.')[0]
            bound_name = alias.asname or base_name
            if base_name in self.banned_modules:
                self.violations.append(f"Banned module import detected: {alias.name}")
                self.tainted_names.add(bound_name)
            elif self.allowed_imports is not None and base_name not in self.allowed_imports:
                self.violations.append(f"Import not permitted by policy: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_name = node.module.split('.')[0]
            if base_name in self.banned_modules:
                self.violations.append(f"Banned import from module detected: {node.module}")
                for alias in node.names:
                    bound_name = alias.asname or alias.name
                    self.tainted_names.add(bound_name)
            elif self.allowed_imports is not None and base_name not in self.allowed_imports:
                self.violations.append(f"Import not permitted by policy: {node.module}")
        elif self.allowed_imports is not None:
            self.violations.append("Relative import not permitted by policy")
        self.generic_visit(node)

    def visit_Assign(self, node):
        """追踪赋值：如果右侧是危险函数/模块名（直接引用），标记左侧变量名为污染"""
        is_dangerous_source = False
        if isinstance(node.value, ast.Name) and self._is_banned_name(node.value.id):
            is_dangerous_source = True

        if is_dangerous_source:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.tainted_names.add(target.id)
                    self.violations.append(
                        f"Dangerous alias detected: '{target.id}' assigned from banned name '{node.value.id}'"
                    )
        self.generic_visit(node)

    def visit_Call(self, node):
        called_name = None
        if isinstance(node.func, ast.Name):
            called_name = node.func.id
            if self._is_banned_name(called_name):
                self.violations.append(f"Banned function call detected: {called_name}()")

        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in self.banned_functions or attr_name in {'system', 'popen', 'run', 'call', 'check_output', 'exec', 'eval'}:
                self.violations.append(f"High-risk method call detected: .{attr_name}()")
            if isinstance(node.func.value, ast.Name):
                base = node.func.value.id
                if base in self.banned_modules or base in self.tainted_names:
                    self.violations.append(f"Banned module attribute access/call: {base}.{attr_name}")

        self.generic_visit(node)


def inspect_code_safety(code_str: str, allowed_imports=None) -> list:
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return [f"SyntaxError in code: {e}"]
    visitor = SecurityASTVisitor(
        allowed_imports=None if allowed_imports is None else set(allowed_imports)
    )
    visitor.visit(tree)
    return visitor.violations
