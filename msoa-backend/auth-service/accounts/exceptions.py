from rest_framework.views import exception_handler


def _to_text(data):
    if isinstance(data, dict):
        for value in data.values():
            return _to_text(value)
    if isinstance(data, (list, tuple)) and data:
        return _to_text(data[0])
    return str(data)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        message = _to_text(response.data)
        response.data = {"message": message, "error": message}
    return response