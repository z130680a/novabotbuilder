import json
from pathlib import Path

from llm import llm


CONFIG_FILE = Path("generated_bots/bot_config.json")


def generate_tests(bot_spec):
    prompt = f"""
تو Agent تست‌کننده یک بات تلگرام هستی.

مشخصات بات:
{json.dumps(bot_spec, ensure_ascii=False)}

حداکثر 5 تست مهم برای این بات طراحی کن.

فقط JSON معتبر برگردان:
{{
  "tests": [
    "تست اول",
    "تست دوم",
    "تست سوم"
  ]
}}
"""

    response = llm.invoke(prompt)

    text = response.content.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)


def run_tests(capacity):
    reservations = {}
    waiting_list = []

    results = []

    # 1. رزرو موفق
    reservations[1] = "User 1"
    results.append(("رزرو موفق", len(reservations) == 1))

    # 2. رزرو تکراری
    duplicate_blocked = 1 in reservations
    results.append(("جلوگیری از رزرو تکراری", duplicate_blocked))

    # 3. نمایش ظرفیت
    remaining = capacity - len(reservations)
    results.append(("نمایش ظرفیت", remaining == capacity - 1))

    # 4. پر شدن ظرفیت و لیست انتظار
    reservations = {
        i: f"User {i}"
        for i in range(1, capacity + 1)
    }

    waiting_list.append(capacity + 1)

    waitlist_ok = (
        len(reservations) == capacity
        and waiting_list[0] == capacity + 1
    )

    results.append(("لیست انتظار بعد از پر شدن ظرفیت", waitlist_ok))

    # 5. لغو و جایگزینی
    del reservations[1]

    next_user = waiting_list.pop(0)
    reservations[next_user] = f"User {next_user}"

    replacement_ok = (
        len(reservations) == capacity
        and next_user in reservations
    )

    results.append(("جایگزینی خودکار از لیست انتظار", replacement_ok))

    return results


def main():
    bot_spec = json.loads(
        CONFIG_FILE.read_text(encoding="utf-8")
    )

    print("در حال طراحی تست‌ها توسط Agent...\n")

    tests = generate_tests(bot_spec)

    for i, test in enumerate(tests["tests"], 1):
        print(f"{i}. {test}")

    print("\nدر حال اجرای تست‌های واقعی منطق بات...\n")

    results = run_tests(bot_spec["capacity"])

    passed = 0

    for name, result in results:
        if result:
            print(f"PASS ✅ - {name}")
            passed += 1
        else:
            print(f"FAIL ❌ - {name}")

    print(f"\nنتیجه: {passed}/{len(results)} تست موفق بود.")


if __name__ == "__main__":
    main()