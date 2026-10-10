from llm import llm


def generate_questions(bot_spec: dict) -> list[str]:
    prompt = f"""
تو یک Agent سازنده بات تلگرام هستی.

مشخصات فعلی بات:
{bot_spec}

از بین اطلاعات ناقص، فقط مهم‌ترین سؤال‌هایی را بپرس که
برای ساخت نسخه اول بات واقعاً ضروری هستند.

حداکثر 4 سؤال.
سؤال‌ها باید کوتاه، واضح و قابل پاسخ برای یک صاحب کسب‌وکار باشند.

فقط سؤال‌ها را به صورت یک لیست شماره‌دار برگردان.
"""

    result = llm.invoke(prompt)

    return [
        line.strip()
        for line in result.content.splitlines()
        if line.strip()
    ]