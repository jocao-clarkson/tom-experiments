import logging

REDACT_KEYS = {"card_number", "cvv", "email", "billing_email", "api_key"}


class RedactingFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, dict):
            record.args = {
                k: ("[redacted]" if k in REDACT_KEYS else v)
                for k, v in record.args.items()
            }
        for key in REDACT_KEYS:
            if hasattr(record, key):
                setattr(record, key, "[redacted]")
        return True


def get_logger(name):
    logger = logging.getLogger(name)
    if not any(isinstance(f, RedactingFilter) for f in logger.filters):
        logger.addFilter(RedactingFilter())
    return logger
