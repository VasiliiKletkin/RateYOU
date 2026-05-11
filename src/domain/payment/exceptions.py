class PaymentError(Exception):
    """Base for payment domain errors."""


class TransactionNotFound(PaymentError):
    pass


class InvalidMoney(PaymentError):
    pass


class InvalidStatusTransition(PaymentError):
    pass


class UnsupportedProvider(PaymentError):
    pass
