"""
SSLCommerz integration (replaces payment_checkout.php / payment_success.php).

Differences from the PHP version, all on purpose:
  * store id / password come from settings, not from the source code;
  * TLS certificates are verified;
  * a PENDING Payment row is written *before* the customer is sent to the
    gateway, and the success callback only trusts what the gateway's
    validation API says about that transaction.  The PHP version read the
    package, employer and number of posts from the query string, so anyone
    could edit the URL and credit themselves.
"""
import json
import urllib.parse
import urllib.request

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import BuyPackage, Payment, uniqid


class GatewayError(Exception):
    pass


def _base_url():
    host = "sandbox" if settings.SSLCOMMERZ_SANDBOX else "securepay"
    return f"https://{host}.sslcommerz.com"


def _request(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    try:
        with urllib.request.urlopen(url, data=body, timeout=30) as response:
            return json.loads(response.read().decode())
    except Exception as exc:                      # network, HTTP or JSON error
        raise GatewayError("Failed to connect with SSLCommerz") from exc


def create_payment(employer, package):
    return Payment.objects.create(
        employer=employer,
        package=package,
        package_name=package.name,
        numberofpost=package.numberofpost,
        amount=package.price,
        transid=f"CC_{uniqid()}{uniqid()}",
    )


def start_session(payment, success_url, fail_url, cancel_url):
    """Ask SSLCommerz for a hosted payment page; returns the URL to send the customer to."""
    employer = payment.employer
    result = _request(f"{_base_url()}/gwprocess/v4/api.php", {
        "store_id": settings.SSLCOMMERZ_STORE_ID,
        "store_passwd": settings.SSLCOMMERZ_STORE_PASSWORD,
        "total_amount": str(payment.amount),
        "currency": "BDT",
        "tran_id": payment.transid,
        "success_url": success_url,
        "fail_url": fail_url,
        "cancel_url": cancel_url,
        "cus_name": employer.name,
        "cus_email": employer.email,
        "cus_phone": employer.mobile,
        "cus_add1": employer.location,
        "cus_city": employer.location,
        "cus_country": "Bangladesh",
        "shipping_method": "NO",
        "product_name": f"{payment.package_name} job post package",
        "product_category": "Job posting",
        "product_profile": "non-physical-goods",
    })
    url = result.get("GatewayPageURL")
    if not url:
        raise GatewayError(result.get("failedreason") or "SSLCommerz did not return a payment page")
    return url


def validate(payment, val_id):
    """Confirm with SSLCommerz that this transaction was really paid in full."""
    query = urllib.parse.urlencode({
        "val_id": val_id,
        "store_id": settings.SSLCOMMERZ_STORE_ID,
        "store_passwd": settings.SSLCOMMERZ_STORE_PASSWORD,
        "format": "json",
    })
    result = _request(f"{_base_url()}/validator/api/validationserverAPI.php?{query}")
    try:
        paid = float(result.get("currency_amount") or result.get("amount") or 0)
    except (TypeError, ValueError):
        paid = 0
    ok = (
        result.get("status") in ("VALID", "VALIDATED")
        and result.get("tran_id") == payment.transid
        and result.get("currency_type", "BDT") == "BDT"
        and paid >= float(payment.amount)
    )
    return ok, result.get("card_type", "")


@transaction.atomic
def complete(payment_id, card_type):
    """Mark a payment VALID and credit the posts.  Safe to call twice."""
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status != Payment.PENDING:
        return False
    payment.status = Payment.VALID
    payment.cardtype = card_type
    payment.transtime = timezone.now()
    payment.save(update_fields=["status", "cardtype", "transtime"])

    BuyPackage.objects.get_or_create(employer=payment.employer)
    BuyPackage.objects.filter(employer=payment.employer).update(
        numberofpost=F("numberofpost") + payment.numberofpost,
        amount=F("amount") + payment.amount,
    )
    return True


def close(payment, status):
    """Record a failed or cancelled attempt (only if it is still pending)."""
    Payment.objects.filter(pk=payment.pk, status=Payment.PENDING).update(status=status)
