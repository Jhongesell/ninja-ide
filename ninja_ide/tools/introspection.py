# -*- coding: utf-8 -*-
import _ast
import ast

import logging

from ninja_ide.tools.completion import analyzer


logger_imports = logging.getLogger(
    'ninja_ide.tools.introspection.obtaining_imports')
logger_symbols = logging.getLogger(
    'ninja_ide.tools.introspection.obtainint_symbols')


_map_type = {
    _ast.Tuple: 'tuple',
    _ast.List: 'list',
    _ast.Str: 'str',
    _ast.Dict: 'dict',
    _ast.Num: 'int',
    _ast.Call: 'function()',
}


def _parse_assign(symbol):
    assigns = {}
    attributes = {}
    for var in symbol.targets:
        if var.__class__ == ast.Attribute:
            attributes[var.attr] = var.lineno
        elif var.__class__ == ast.Name:
            assigns[var.id] = var.lineno
    return (assigns, attributes)


def _parse_class(symbol, with_docstrings):
    docstring = {}
    attr = {}
    func = {}
    name = symbol.name + '('
    name += ', '.join([
        analyzer.expand_attribute(base) for base in symbol.bases])
    name += ')'
    for sym in symbol.body:
        if sym.__class__ is ast.Assign:
            result = _parse_assign(sym)
            attr.update(result[0])
            attr.update(result[1])
        elif sym.__class__ is ast.FunctionDef:
            result = _parse_function(sym, with_docstrings)
            attr.update(result['attrs'])
            if with_docstrings:
                func[result['name']] = result['lineno']
                docstring[result['lineno']] = result['docstring']
            else:
                func[result['name']] = result['lineno']
    if with_docstrings:
        docstring[symbol.lineno] = ast.get_docstring(symbol, clean=True)
    return {'name': name, 'attributes': attr, 'functions': func,
        'lineno': symbol.lineno, 'docstring': docstring}


def _parse_function(symbol, with_docstrings):
    docstring = ''
    attrs = {}

    func_name = symbol.name + '('
    #We store the arguments to compare with default backwards
    defaults = []
    for value in symbol.args.defaults:
        #TODO: In some cases we can have something like: a=os.path
        defaults.append(value)
    arguments = []
    for arg in reversed(symbol.args.args):
        if arg.id == 'self':
            continue
        argument = arg.id
        if defaults:
            value = defaults.pop()
            arg_default = _map_type.get(value.__class__, None)
            if arg_default is None:
                if value.__class__ is _ast.Attribute:
                    arg_default = analyzer.expand_attribute(value)
                elif value.__class__ is _ast.Name:
                    arg_default = value.id
                else:
                    arg_default = 'object'
            argument += '=' + arg_default
        arguments.append(argument)
    func_name += ', '.join(reversed(arguments))
    if symbol.args.vararg is not None:
        if not func_name.endswith('('):
            func_name += ', '
        func_name += '*' + symbol.args.vararg
    if symbol.args.kwarg is not None:
        if not func_name.endswith('('):
            func_name += ', '
        func_name += '**' + symbol.args.kwarg
    func_name += ')'

    for sym in symbol.body:
        if sym.__class__ is ast.Assign:
            result = _parse_assign(sym)
            attrs.update(result[1])

    if with_docstrings:
        docstring = ast.get_docstring(symbol, clean=True)

    return {'name': func_name, 'lineno': symbol.lineno,
        'attrs': attrs, 'docstring': docstring}


def obtain_symbols(source, with_docstrings=False):
    """Parse a module source code to obtain: Classes, Functions and Assigns."""
    try:
        module = ast.parse(source)
    except:
        logger_symbols.debug("A file contains syntax errors.")
        return {}
    symbols = {}
    globalAttributes = {}
    globalFunctions = {}
    classes = {}
    docstrings = {}

    for symbol in module.body:
        if symbol.__class__ is ast.Assign:
            result = _parse_assign(symbol)
            globalAttributes.update(result[0])
            globalAttributes.update(result[1])
        elif symbol.__class__ is ast.FunctionDef:
            result = _parse_function(symbol, with_docstrings)
            if with_docstrings:
                globalFunctions[result['name']] = result['lineno']
                docstrings[result['lineno']] = result['docstring']
            else:
                globalFunctions[result['name']] = result['lineno']
        elif symbol.__class__ is ast.ClassDef:
            result = _parse_class(symbol, with_docstrings)
            classes[result['name']] = (result['lineno'],
                {'attributes': result['attributes'],
                'functions': result['functions']})
            docstrings.update(result['docstring'])
    if globalAttributes:
        symbols['attributes'] = globalAttributes
    if globalFunctions:
        symbols['functions'] = globalFunctions
    if classes:
        symbols['classes'] = classes
    if docstrings and with_docstrings:
        symbols['docstrings'] = docstrings

    return symbols


def obtain_imports(source='', body=None):
    if source:
        try:
            module = ast.parse(source)
            body = module.body
        except:
            logger_imports.debug("A file contains syntax errors.")
    #Imports{} = {name: asname}, for example = {sys: sysAlias}
    imports = {}
    #From Imports{} = {name: {module: fromPart, asname: nameAlias}}
    fromImports = {}
    for sym in body:
        if type(sym) is ast.Import:
            for item in sym.names:
                imports[item.name] = {'asname': item.asname,
                    'lineno': sym.lineno}
        if type(sym) is ast.ImportFrom:
            for item in sym.names:
                fromImports[item.name] = {'module': sym.module,
                    'asname': item.asname, 'lineno': sym.lineno}
    return {'imports': imports, 'fromImports': fromImports}
