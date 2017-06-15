import inspect


class Augmenter:
    """
    Add functionality to classes imported elsewhere.
    This totally isn't bad practice at all.
    """

    def __init__(self):
        self.classes = {}
        self.properties = {}  # anything in this dict is added as a property

    def add(self, base_class: type):
        """
        Add a class to be augmented.
        """
        def wrapper(cls):
            self.classes[cls] = base_class
            return cls
        return wrapper

    def __call__(self):
        """
        Augment all classes.
        """
        for cls, base_class in self.classes.items():
            for k in inspect.getmembers(cls):
                if inspect.isfunction(k[1]) or isinstance(k[1], property):
                    setattr(base_class, *k)
                elif not k[0].startswith('__'):
                    setattr(base_class, k[0], property(lambda _: k[1]))
            for k, v in self.properties.items():
                if k.startswith('__'):
                    n = f'_{base_class.__name__}{k}'
                else:
                    n = k
                setattr(base_class, n, property(v))


augmenter = Augmenter()

from . import context
from . import command
from . import message


