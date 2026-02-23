class MultitonMeta(type):
    _instances = {}

    def __call__(cls, key: str):
        unique_key = (cls, key)
        if unique_key not in cls._instances:
            cls._instances[unique_key] = super().__call__(key)
        return cls._instances[unique_key]
