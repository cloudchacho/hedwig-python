import importlib


def import_class(dotted_path):
    if not dotted_path:
        raise ImportError(f"{dotted_path} is not defined")
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError as err:
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err

    module = importlib.import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as err:
        raise ImportError(f"Module '{module_path}' does not define a '{class_name}' attribute/class") from err
