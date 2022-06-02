from decimal import Decimal

from saleor.payment.gateways.utils import get_supported_currencies
from tabby.utils import (
    _call_tabby_get,
    _call_tabby_post,
    _error_response,
    _success_response,
    get_default_gateway_response,
    get_exc_message,
)


def confirm_and_capture_payment(
    payment_information, config
):
    """Retrieve a payment using the Tabby client."""
    # Retrieve a payment -> https://docs.tabby.ai/#operation/getPayment

    error = (
        False
        if payment_information.currency
        in get_supported_currencies(config=config, gateway_name=config.gateway_name)
        else True
    )
    from saleor.payment import TransactionKind

    response = get_default_gateway_response(transaction_kind=TransactionKind.CAPTURE)

    if not error:
        from saleor.payment.models import Payment

        payment = Payment.objects.get(pk=payment_information.payment_id)
        tabby_response = _call_tabby_get(
            config=config, endpoint="payments/{id}".format(id=payment.token)
        )
        payment.psp_reference = (
            tabby_response.get("order").get("reference_id")
            if tabby_response and tabby_response.get("order")
            else None
        )
        payment.save(update_fields=["psp_reference"])

        is_valid_payment_id = tabby_response.get("id") == payment.token
        tabby_status = tabby_response.get("status") in ["AUTHORIZED", "CLOSED"]
        if (
            tabby_status
            and is_valid_payment_id
            # and tabby_response.get("currency") == payment_information.currency
            and Decimal(tabby_response.get("amount")) == payment_information.amount
        ):
            response = _success_response(
                token=payment.token,
                action_required=False,
                kind=TransactionKind.CAPTURE,
                payment_response=tabby_response,
                amount=payment_information.amount,
                currency=payment_information.currency,
                customer_id=payment_information.customer_id,
            )
        else:
            exc_message = get_exc_message(tabby_response=tabby_response)
            response = _error_response(
                exc=exc_message,
                action_required=True,
                raw_response=tabby_response,
                kind=TransactionKind.CAPTURE,
                payment_info=payment_information,
            )

    return response


def refund_payment(
    payment_information, config
):
    """Refund a payment using the Tabby client.

    But it is first check if the given payment instance is supported
    by the gateway.
    It first retrieves a `charge` transaction to retrieve the
    payment id to refund. And return an error with a failed transaction
    if the there is no such transaction, or if an error
    from Tabby occurs during the refund.
    """
    # Refund a payment -> https://docs.tabby.ai/#operation/postPaymentRefund
    error = (
        False
        if payment_information.currency
        in get_supported_currencies(config=config, gateway_name=config.gateway_name)
        else True
    )
    from saleor.payment import TransactionKind

    response = get_default_gateway_response(transaction_kind=TransactionKind.REFUND)

    if not error:
        from saleor.payment.models import Payment

        payment = Payment.objects.get(pk=payment_information.payment_id)
        tabby_response = _call_tabby_post(
            config=config,
            endpoint="payments/{id}/refunds".format(id=payment.token),
            data={"amount": str(round(payment_information.amount, 2))},
        )
        if (
            tabby_response.get("id") == payment.token
            and len(tabby_response.get("refunds")) > 0
            and tabby_response.get("status") == "CLOSED"
        ):
            response = _success_response(
                token=payment.token,
                action_required=False,
                kind=TransactionKind.REFUND,
                payment_response=tabby_response,
                amount=payment_information.amount,
                currency=payment_information.currency,
                customer_id=payment_information.customer_id,
            )
            from saleor.payment import ChargeStatus

            payment.charge_status = ChargeStatus.FULLY_REFUNDED
            payment.save(update_fields=["charge_status"])
            from saleor.plugins.manager import get_plugins_manager

            manager = get_plugins_manager()
            from saleor.order.actions import cancel_order

            cancel_order(payment.order, None, None, manager)  # type: ignore
        else:
            response = _error_response(
                action_required=True,
                raw_response=tabby_response,
                kind=TransactionKind.REFUND,
                payment_info=payment_information,
                exc=get_exc_message(tabby_response=tabby_response),
            )

    return response


def process_payment(
    payment_information, config
):
    return confirm_and_capture_payment(
        payment_information=payment_information, config=config
    )


def confirm_payment(
    payment_information, config
):
    return confirm_and_capture_payment(
        payment_information=payment_information, config=config
    )


def capture(payment_information, config):
    return confirm_and_capture_payment(
        payment_information=payment_information, config=config
    )


def refund(payment_information, config):
    return refund_payment(payment_information=payment_information, config=config)
