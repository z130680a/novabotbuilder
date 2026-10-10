import ipaddress
import json
import os
import urllib.error
import urllib.request

from fastapi import Request


TRUSTED_PROXIES = {
    item.strip()
    for item in os.getenv(
        "NOVA_TRUSTED_PROXIES",
        ""
    ).split(",")
    if item.strip()
}


def get_client_ip(request: Request) -> str:
    """
    در حالت عادی IP مستقیم درخواست را برمی‌گرداند.
    X-Forwarded-For فقط برای Proxyهای مورد اعتماد پذیرفته می‌شود.
    """

    direct_ip = ""

    if request.client:
        direct_ip = request.client.host or ""

    if direct_ip in TRUSTED_PROXIES:
        forwarded = request.headers.get(
            "x-forwarded-for"
        )

        if forwarded:
            candidates = [
                x.strip()
                for x in forwarded.split(",")
            ]

            for candidate in candidates:
                try:
                    ipaddress.ip_address(candidate)
                    return candidate
                except ValueError:
                    continue

    return direct_ip


def lookup_ip(ip: str) -> dict:
    result = {
        "ip": ip,
        "country": "",
        "city": "",
        "region": "",
        "timezone": "",
    }

    try:
        parsed = ipaddress.ip_address(ip)

        # برای localhost و private IP
        # نمی‌توان جغرافیای عمومی قابل اتکا گرفت.
        if parsed.is_private or parsed.is_loopback:
            return result

        url = f"https://ipapi.co/{ip}/json/"

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NovaBotBuilder/1.0"
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=4,
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

        result["country"] = (
            data.get("country_name")
            or data.get("country_code")
            or ""
        )

        result["city"] = data.get("city") or ""
        result["region"] = data.get("region") or ""
        result["timezone"] = data.get("timezone") or ""

    except (
        ValueError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ):
        pass

    return result