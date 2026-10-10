import importlib.util
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

GENERATED_BOT_FILE = (
    BASE_DIR
    / "generated_bots"
    / "generated_bot.py"
)


def load_generated_bot():
    if not GENERATED_BOT_FILE.exists():
        raise FileNotFoundError(
            f"فایل بات تولیدشده پیدا نشد: {GENERATED_BOT_FILE}"
        )

    module_name = "generated_bot_sandbox"

    spec = importlib.util.spec_from_file_location(
        module_name,
        GENERATED_BOT_FILE,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            "امکان بارگذاری generated_bot.py وجود ندارد."
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def run_sandbox(spec: dict) -> dict:
    tests = []

    def add_test(name: str, passed: bool, message: str):
        tests.append({
            "name": name,
            "passed": passed,
            "message": message,
        })

    try:
        bot_module = load_generated_bot()

        add_test(
            "بارگذاری نسخه تولیدشده",
            True,
            "generated_bot.py با موفقیت بارگذاری شد.",
        )

        capacity = int(spec.get("capacity", 10))

        if capacity < 1:
            add_test(
                "بررسی ظرفیت",
                False,
                "ظرفیت کارگاه باید بیشتر از صفر باشد.",
            )

            return {
                "passed": False,
                "tests": tests,
                "message": "ظرفیت نامعتبر است.",
            }

        engine_class = getattr(
            bot_module,
            "ReservationEngine",
            None,
        )

        if engine_class is None:
            add_test(
                "بررسی موتور رزرو",
                False,
                "ReservationEngine در نسخه تولیدشده وجود ندارد.",
            )

            return {
                "passed": False,
                "tests": tests,
                "message": "موتور رزرو پیدا نشد.",
            }

        add_test(
            "بررسی ظرفیت کارگاه",
            True,
            f"ظرفیت کارگاه برای تست {capacity} نفر است.",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            test_data_file = Path(temp_dir) / "data.json"

            engine = engine_class(
                capacity=capacity,
                data_file=test_data_file,
            )

            # شناسه‌ها رشته‌ای هستند تا تست به دیتابیس
            # واقعی شرکت‌کنندگان دست نزند.
            first_user_id = "sandbox_user_1"

            first_user_data = {
                "username": "sandbox_user_1",
                "first_name": "کاربر تست ۱",
                "last_name": "",
                "phone": "",
            }

            result = engine.reserve(
                first_user_id,
                first_user_data,
            )

            if result.get("status") != "registered":
                add_test(
                    "ثبت رزرو",
                    False,
                    "نسخه تولیدشده نتوانست رزرو ثبت کند.",
                )

                return {
                    "passed": False,
                    "tests": tests,
                    "message": "تست ثبت رزرو شکست خورد.",
                }

            add_test(
                "ثبت رزرو",
                True,
                "رزرو با موفقیت ثبت شد.",
            )

            # تکمیل ظرفیت
            for i in range(2, capacity + 1):
                user_id = f"sandbox_user_{i}"

                user_data = {
                    "username": user_id,
                    "first_name": f"کاربر تست {i}",
                    "last_name": "",
                    "phone": "",
                }

                result = engine.reserve(
                    user_id,
                    user_data,
                )

                if result.get("status") != "registered":
                    add_test(
                        "تکمیل ظرفیت",
                        False,
                        f"رزرو کاربر تست {i} موفق نبود.",
                    )

                    return {
                        "passed": False,
                        "tests": tests,
                        "message": "تست تکمیل ظرفیت شکست خورد.",
                    }

            add_test(
                "تکمیل ظرفیت",
                engine.reserved_count() == capacity,
                "ظرفیت کارگاه به‌درستی تکمیل شد.",
            )

            if engine.reserved_count() != capacity:
                return {
                    "passed": False,
                    "tests": tests,
                    "message": "ظرفیت به‌درستی تکمیل نشد.",
                }

            # ورود کاربر اضافی به لیست انتظار
            waiting_user_id = "sandbox_waiting_user"

            waiting_user_data = {
                "username": waiting_user_id,
                "first_name": "کاربر لیست انتظار",
                "last_name": "",
                "phone": "",
            }

            result = engine.reserve(
                waiting_user_id,
                waiting_user_data,
            )

            if result.get("status") != "waitlist":
                add_test(
                    "لیست انتظار",
                    False,
                    "کاربر اضافی وارد لیست انتظار نشد.",
                )

                return {
                    "passed": False,
                    "tests": tests,
                    "message": "تست لیست انتظار شکست خورد.",
                }

            add_test(
                "لیست انتظار",
                True,
                "کاربر اضافی وارد لیست انتظار شد.",
            )

            # لغو رزرو
            result = engine.cancel(first_user_id)

            if result.get("status") != "cancelled":
                add_test(
                    "لغو رزرو",
                    False,
                    "لغو رزرو موفق نبود.",
                )

                return {
                    "passed": False,
                    "tests": tests,
                    "message": "تست لغو رزرو شکست خورد.",
                }

            add_test(
                "لغو رزرو",
                True,
                "رزرو با موفقیت لغو شد.",
            )

            # بررسی جایگزینی نفر اول لیست انتظار
            promoted_user = result.get("promoted")

            promotion_passed = (
                isinstance(promoted_user, dict)
                and str(promoted_user.get("user_id"))
                == waiting_user_id
                and engine.is_reserved(waiting_user_id)
            )

            add_test(
                "جایگزینی لیست انتظار",
                promotion_passed,
                (
                    "کاربر لیست انتظار جایگزین شد."
                    if promotion_passed
                    else "کاربر لیست انتظار جایگزین نشد."
                ),
            )

            if not promotion_passed:
                return {
                    "passed": False,
                    "tests": tests,
                    "message": "تست جایگزینی لیست انتظار شکست خورد.",
                }

        return {
            "passed": True,
            "tests": tests,
            "message": "نسخه تولیدشده با موفقیت تست شد.",
        }

    except Exception as exc:
        add_test(
            "اجرای Sandbox",
            False,
            f"خطای غیرمنتظره: {exc}",
        )

        return {
            "passed": False,
            "tests": tests,
            "message": "Sandbox با خطا متوقف شد.",
        }