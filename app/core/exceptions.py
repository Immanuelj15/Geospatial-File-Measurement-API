"""Domain and application-specific exceptions."""


class AppBaseException(Exception):
    """Base class for all application-specific exceptions."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class FileValidationError(AppBaseException):
    """Raised when an uploaded file violates validation rules."""

    pass


class FileProcessingError(AppBaseException):
    """Raised when parsing or processing of a geospatial file fails."""

    pass


class EntityNotFoundError(AppBaseException):
    """Raised when a requested resource is not found."""

    pass


class CRSTransformationError(AppBaseException):
    """Raised when CRS reprojection fails."""

    pass


class InvalidGeometryError(AppBaseException):
    """Raised when an individual feature geometry is invalid or unprocessable."""

    pass
