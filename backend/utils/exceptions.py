class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400, payload: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv

class NotFoundException(AppException):
    def __init__(self, message: str = "Recurso não encontrado"):
        super().__init__(message, status_code=404)

class ValidationException(AppException):
    def __init__(self, message: str = "Erro de validação", payload: dict = None):
        super().__init__(message, status_code=400, payload=payload)

class UnauthorizedException(AppException):
    def __init__(self, message: str = "Não autorizado"):
        super().__init__(message, status_code=401)
