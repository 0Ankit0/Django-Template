import inflection


class DomainException(Exception):
    """Base exception for all domain-specific exceptions that converts exception to snake_case."""

    @property
    def code(self):
        return inflection.underscore(self.__class__.__name__)
