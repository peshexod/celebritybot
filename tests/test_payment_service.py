import pytest

from bot.services.payment_service import PaymentConfigurationError, PaymentService


def test_validate_yookassa_credentials_accepts_test_secret() -> None:
    shop_id, secret_key = PaymentService._validate_credentials(" 123456 ", '"test_secret_key"')

    assert shop_id == "123456"
    assert secret_key == "test_secret_key"


def test_validate_yookassa_credentials_rejects_non_numeric_shop_id() -> None:
    with pytest.raises(PaymentConfigurationError, match="numeric shop id"):
        PaymentService._validate_credentials("shop_123", "test_secret")


def test_validate_yookassa_credentials_rejects_oauth_token() -> None:
    with pytest.raises(PaymentConfigurationError, match="OAuth token"):
        PaymentService._validate_credentials("123456", "y0_AQAAAAAExampleOAuth")
