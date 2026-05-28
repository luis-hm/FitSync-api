import json
import logging


SENSITIVE_KEYS = {
    "access",
    "authorization",
    "cookie",
    "http_authorization",
    "new_password",
    "password",
    "password_confirm",
    "refresh",
    "refresh_token",
    "senha",
    "set-cookie",
    "token",
}
MASK = "***"
MAX_CONTEXT_CHARS = 1000


def get_client_ip(request):
    if not request:
        return None

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def mask_sensitive_data(value):
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                masked[key] = MASK
            else:
                masked[key] = mask_sensitive_data(item)
        return masked

    if isinstance(value, list):
        return [mask_sensitive_data(item) for item in value]

    if isinstance(value, tuple):
        return tuple(mask_sensitive_data(item) for item in value)

    return value


def compact_context(context, max_chars=MAX_CONTEXT_CHARS):
    if not context:
        return ""

    safe_context = mask_sensitive_data(context)
    try:
        context_str = json.dumps(safe_context, ensure_ascii=False, default=str, sort_keys=True)
    except (TypeError, ValueError):
        context_str = str(safe_context)

    if len(context_str) > max_chars:
        return f"{context_str[:max_chars]}... (truncated)"
    return context_str


def request_context(request):
    if not request:
        return {}

    user = getattr(request, "user", None)
    user_id = str(getattr(user, "id", "")) if user and user.is_authenticated else None
    return {
        "method": request.method,
        "path": request.path,
        "ip": get_client_ip(request),
        "user_id": user_id,
    }


def log_security_event(message, request=None, context=None):
    logger = logging.getLogger("apps.security")
    log_context = request_context(request)
    if context:
        log_context.update(context)

    context_str = compact_context(log_context)
    if context_str:
        logger.warning("%s - %s", message, context_str)
    else:
        logger.warning("%s", message)


def log_app_event(message, request=None, context=None):
    logger = logging.getLogger("apps")
    log_context = request_context(request)
    if context:
        log_context.update(context)

    context_str = compact_context(log_context)
    if context_str:
        logger.info("%s - %s", message, context_str)
    else:
        logger.info("%s", message)


def log_error_with_context(message, context=None, exc_info=False):
    logger = logging.getLogger("apps")
    context_str = compact_context(context)
    if context_str:
        logger.error("%s - %s", message, context_str, exc_info=exc_info)
    else:
        logger.error("%s", message, exc_info=exc_info)
