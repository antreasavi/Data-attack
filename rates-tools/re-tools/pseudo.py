"""Rough stack-based pseudo-decompiler for CPython 3.11 bytecode (via xdis).
Output: per code object, per source line, a reconstructed statement where possible."""
import sys
from xdis.load import load_module
from xdis import get_opcode
from xdis.bytecode import Bytecode

BINOPS = {0: '+', 1: '&', 2: '//', 3: '<<', 4: '@', 5: '*', 6: '%', 7: '|', 8: '**', 9: '>>', 10: '-', 11: '/', 12: '^',
          13: '+=', 14: '&=', 15: '//=', 16: '<<=', 17: '@=', 18: '*=', 19: '%=', 20: '|=', 21: '**=', 22: '>>=', 23: '-=', 24: '/=', 25: '^='}


def is_code(x):
    return hasattr(x, 'co_code') and hasattr(x, 'co_name')


def r(x):
    if is_code(x):
        return f'<code {x.co_name}>'
    s = repr(x)
    return s if len(s) < 400 else s[:400] + '...'


def decomp(co, opc, out, indent=''):
    args = co.co_varnames[:co.co_argcount + co.co_kwonlyargcount]
    out.append(f'\n{indent}def {co.co_qualname if hasattr(co, "co_qualname") else co.co_name}({", ".join(args)}):   # line {co.co_firstlineno}')
    doc = co.co_consts[0] if co.co_consts and isinstance(co.co_consts[0], str) else None
    if doc and '\n' in doc or (doc and len(doc) > 40):
        out.append(f'{indent}    """{doc.strip()[:1500]}"""')
    stack = []
    kw = None
    line = None
    buf = []
    ind = indent + '    '

    def emit(s):
        buf.append(s)

    def flush():
        if buf:
            out.append(f'{ind}L{line}: ' + ' ; '.join(buf))
            buf.clear()

    def pop(n=1):
        res = []
        for _ in range(n):
            res.append(stack.pop() if stack else '?')
        return res[::-1]

    try:
        instrs = list(Bytecode(co, opc).get_instructions(co))
    except Exception as e:
        out.append(f'{ind}<disasm error {e}>')
        return
    for ins in instrs:
        if ins.starts_line is not None and ins.starts_line != line:
            if stack and buf == [] and False:
                pass
            flush()
            line = ins.starts_line
        if ins.is_jump_target:
            emit(f'@{ins.offset}:')
        op = ins.opname
        a = ins.argval
        try:
            if op in ('RESUME', 'NOP', 'CACHE', 'PRECALL', 'PUSH_NULL', 'COPY_FREE_VARS', 'MAKE_CELL', 'EXTENDED_ARG', 'RETURN_GENERATOR'):
                continue
            elif op in ('LOAD_CONST',):
                if is_code(a):
                    stack.append(f'<code {a.co_name}>')
                else:
                    stack.append(r(a))
            elif op in ('LOAD_FAST', 'LOAD_NAME', 'LOAD_DEREF', 'LOAD_CLASSDEREF', 'LOAD_CLOSURE'):
                stack.append(str(a))
            elif op == 'LOAD_GLOBAL':
                stack.append(str(a).replace('NULL + ', ''))
            elif op in ('LOAD_ATTR', 'LOAD_METHOD'):
                o = pop()[0]
                stack.append(f'{o}.{a}')
            elif op in ('STORE_FAST', 'STORE_NAME', 'STORE_GLOBAL', 'STORE_DEREF'):
                v = pop()[0]
                emit(f'{a} = {v}')
            elif op == 'STORE_ATTR':
                o, v = pop()[0], None
                v = pop()[0]
                emit(f'{o}.{a} = {v}')
            elif op == 'STORE_SUBSCR':
                v, o, k = None, None, None
                k = pop()[0]; o = pop()[0]; v = pop()[0]
                emit(f'{o}[{k}] = {v}')
            elif op == 'DELETE_SUBSCR':
                k = pop()[0]; o = pop()[0]
                emit(f'del {o}[{k}]')
            elif op in ('DELETE_FAST', 'DELETE_NAME', 'DELETE_GLOBAL'):
                emit(f'del {a}')
            elif op == 'KW_NAMES':
                kw = a
            elif op == 'CALL':
                n = ins.arg
                argsv = pop(n)
                f = pop()[0]
                if kw:
                    k = len(kw)
                    pos = argsv[:n - k]
                    kws = [f'{kk}={vv}' for kk, vv in zip(kw, argsv[n - k:])]
                    argsv = pos + kws
                    kw = None
                stack.append(f'{f}({", ".join(map(str, argsv))})')
            elif op == 'CALL_FUNCTION_EX':
                kwargs = pop()[0] if ins.arg & 1 else None
                ar = pop()[0]
                f = pop()[0]
                stack.append(f'{f}(*{ar}' + (f', **{kwargs})' if kwargs else ')'))
            elif op == 'BINARY_OP':
                b = pop()[0]; x = pop()[0]
                stack.append(f'({x} {BINOPS.get(ins.arg, "?")} {b})')
            elif op == 'COMPARE_OP':
                b = pop()[0]; x = pop()[0]
                stack.append(f'({x} {a} {b})')
            elif op == 'IS_OP':
                b = pop()[0]; x = pop()[0]
                stack.append(f'({x} {"is not" if ins.arg else "is"} {b})')
            elif op == 'CONTAINS_OP':
                b = pop()[0]; x = pop()[0]
                stack.append(f'({x} {"not in" if ins.arg else "in"} {b})')
            elif op == 'UNARY_NOT':
                stack.append(f'(not {pop()[0]})')
            elif op == 'UNARY_NEGATIVE':
                stack.append(f'(-{pop()[0]})')
            elif op == 'BINARY_SUBSCR':
                k = pop()[0]; o = pop()[0]
                stack.append(f'{o}[{k}]')
            elif op == 'BUILD_SLICE':
                parts = pop(ins.arg)
                stack.append(':'.join('' if p == 'None' else str(p) for p in parts))
            elif op == 'BUILD_TUPLE':
                stack.append('(' + ', '.join(map(str, pop(ins.arg))) + (',)' if ins.arg == 1 else ')'))
            elif op == 'BUILD_LIST':
                stack.append('[' + ', '.join(map(str, pop(ins.arg))) + ']')
            elif op == 'BUILD_SET':
                stack.append('{' + ', '.join(map(str, pop(ins.arg))) + '}')
            elif op == 'LIST_EXTEND' or op == 'SET_UPDATE':
                v = pop()[0]; l = pop()[0]
                stack.append(f'{l[:-1]}{", " if len(l) > 2 else ""}*{v}]' if l.startswith('[') else f'{l}+{v}')
            elif op == 'LIST_TO_TUPLE':
                stack.append('tuple(' + pop()[0] + ')')
            elif op == 'BUILD_MAP':
                items = pop(2 * ins.arg)
                stack.append('{' + ', '.join(f'{items[i]}: {items[i + 1]}' for i in range(0, len(items), 2)) + '}')
            elif op == 'BUILD_CONST_KEY_MAP':
                keys = pop()[0]
                vals = pop(ins.arg)
                try:
                    ks = eval(keys)
                except Exception:
                    ks = [keys] * len(vals)
                stack.append('{' + ', '.join(f'{k!r}: {v}' for k, v in zip(ks, vals)) + '}')
            elif op == 'DICT_UPDATE' or op == 'DICT_MERGE':
                v = pop()[0]; d = pop()[0]
                stack.append(f'{{**{d}, **{v}}}')
            elif op == 'FORMAT_VALUE':
                spec = pop()[0] if (ins.arg & 4) else ''
                v = pop()[0]
                stack.append('{' + str(v) + (':' + spec.strip("'") if spec else '') + '}')
            elif op == 'BUILD_STRING':
                parts = pop(ins.arg)
                s = ''.join(p[1:-1] if (p.startswith("'") and p.endswith("'")) else p for p in map(str, parts))
                stack.append(f'f"{s}"')
            elif op == 'POP_TOP':
                v = pop()[0]
                if '(' in str(v) or True:
                    emit(f'{v}')
            elif op == 'RETURN_VALUE':
                emit(f'return {pop()[0]}')
            elif op == 'YIELD_VALUE':
                stack.append(f'(yield {pop()[0]})')
            elif op in ('POP_JUMP_FORWARD_IF_FALSE', 'POP_JUMP_BACKWARD_IF_FALSE', 'POP_JUMP_IF_FALSE'):
                emit(f'if not {pop()[0]}: goto {a}')
            elif op in ('POP_JUMP_FORWARD_IF_TRUE', 'POP_JUMP_BACKWARD_IF_TRUE', 'POP_JUMP_IF_TRUE'):
                emit(f'if {pop()[0]}: goto {a}')
            elif op in ('POP_JUMP_FORWARD_IF_NONE', 'POP_JUMP_BACKWARD_IF_NONE'):
                emit(f'if {pop()[0]} is None: goto {a}')
            elif op in ('POP_JUMP_FORWARD_IF_NOT_NONE', 'POP_JUMP_BACKWARD_IF_NOT_NONE'):
                emit(f'if {pop()[0]} is not None: goto {a}')
            elif op == 'JUMP_IF_FALSE_OR_POP':
                v = stack[-1] if stack else '?'
                emit(f'[{v} and ...] (else goto {a})')
                pop()
            elif op == 'JUMP_IF_TRUE_OR_POP':
                v = stack[-1] if stack else '?'
                emit(f'[{v} or ...] (else goto {a})')
                pop()
            elif op in ('JUMP_FORWARD', 'JUMP_BACKWARD', 'JUMP_BACKWARD_NO_INTERRUPT', 'JUMP_ABSOLUTE'):
                emit(f'goto {a}')
            elif op == 'GET_ITER':
                stack.append(f'iter({pop()[0]})')
            elif op == 'FOR_ITER':
                it = stack[-1] if stack else '?'
                emit(f'for-next {it} (exhausted->{a})')
                stack.append('<item>')
            elif op == 'UNPACK_SEQUENCE':
                v = pop()[0]
                for i in range(ins.arg - 1, -1, -1):
                    stack.append(f'{v}[{i}]')
            elif op == 'UNPACK_EX':
                v = pop()[0]
                for i in range(ins.arg & 0xff + 1):
                    stack.append(f'{v}[*{i}]')
            elif op == 'MAKE_FUNCTION':
                c = pop()[0]
                if ins.arg & 8: pop()
                if ins.arg & 4: pop()
                if ins.arg & 2: pop()
                if ins.arg & 1: pop()
                stack.append(f'func{c}')
            elif op == 'LOAD_BUILD_CLASS':
                stack.append('__build_class__')
            elif op == 'IMPORT_NAME':
                pop(2)
                stack.append(f'import {a}')
            elif op == 'IMPORT_FROM':
                m = stack[-1] if stack else '?'
                stack.append(f'{m}.{a}')
            elif op == 'IMPORT_STAR':
                emit(f'from {pop()[0]} import *')
            elif op == 'COPY':
                stack.append(stack[-ins.arg] if len(stack) >= ins.arg else '?')
            elif op == 'SWAP':
                if len(stack) >= ins.arg:
                    stack[-1], stack[-ins.arg] = stack[-ins.arg], stack[-1]
            elif op == 'PUSH_EXC_INFO':
                emit('except-handler:')
                stack.append('<exc>')
            elif op == 'CHECK_EXC_MATCH':
                t = pop()[0]
                emit(f'except {t}?')
                stack.append(f'match({t})')
            elif op in ('POP_EXCEPT', 'RERAISE'):
                emit(op.lower())
            elif op == 'RAISE_VARARGS':
                emit('raise ' + ', '.join(map(str, pop(ins.arg))))
            elif op == 'BEFORE_WITH':
                v = pop()[0]
                emit(f'with {v}:')
                stack.append('<with-exit>')
                stack.append(f'<as {v}>')
            elif op == 'LIST_APPEND':
                v = pop()[0]
                emit(f'append {v}')
            elif op == 'SET_ADD':
                emit(f'set-add {pop()[0]}')
            elif op == 'MAP_ADD':
                v = pop()[0]; k = pop()[0]
                emit(f'map-add {k}: {v}')
            elif op == 'GET_LEN':
                stack.append(f'len({stack[-1] if stack else "?"})')
            elif op == 'UNARY_INVERT':
                stack.append(f'(~{pop()[0]})')
            else:
                emit(f'<{op} {ins.argrepr}>')
        except Exception as e:
            emit(f'<ERR {op} {e}>')
    flush()
    for c in co.co_consts:
        if is_code(c):
            decomp(c, opc, out, indent + '    ')


def main():
    path, dst = sys.argv[1], sys.argv[2]
    res = load_module(path)
    ver, co, is_pypy = res[0], res[3], res[4]
    opc = get_opcode(ver, is_pypy)
    out = [f'# pseudo-decompiled {path}']
    decomp(co, opc, out)
    open(dst, 'w', encoding='utf8').write('\n'.join(out))


main()
