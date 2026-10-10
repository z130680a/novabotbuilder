import os
import signal
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

BOT_FILE = (
    BASE_DIR
    / "generated_bots"
    / "generated_bot.py"
)


class BotManager:

    def __init__(self):
        self.process = None


    # =====================================================
    # پیدا کردن همه generated_bot.py های در حال اجرا
    # =====================================================

    def _find_running_bot_pids(self):
        if os.name != "nt":
            return []

        try:

            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        "Get-CimInstance Win32_Process "
                        "-Filter \"Name = 'python.exe'\" | "
                        "Where-Object { "
                        "$_.CommandLine -like '*generated_bot.py*' "
                        "} | "
                        "Select-Object -ExpandProperty ProcessId"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            pids = []

            for line in result.stdout.splitlines():

                line = line.strip()

                if not line:
                    continue

                try:
                    pid = int(line)

                    if pid != os.getpid():
                        pids.append(pid)

                except ValueError:
                    continue

            return sorted(set(pids))

        except Exception:
            return []


    # =====================================================
    # بستن همه نسخه‌های قبلی بات
    # =====================================================

    def _kill_all_running_bots(self):

        pids = self._find_running_bot_pids()

        stopped = []

        for pid in pids:

            try:

                subprocess.run(
                    [
                        "taskkill",
                        "/PID",
                        str(pid),
                        "/T",
                        "/F",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                stopped.append(pid)

            except Exception:
                pass


        # کمی فرصت برای آزاد شدن polling
        if stopped:
            time.sleep(1.5)


        # بررسی مجدد
        remaining = self._find_running_bot_pids()

        return {
            "stopped": stopped,
            "remaining": remaining,
        }


    # =====================================================
    # وضعیت پردازش تحت کنترل همین Manager
    # =====================================================

    def is_running(self):

        if self.process is None:
            return False

        return (
            self.process.poll() is None
        )


    # =====================================================
    # Start
    # =====================================================

    def start_bot(self):

        # حتی اگر این instance بات را نمی‌شناسد،
        # همه نسخه‌های قبلی را بررسی کن.
        cleanup = self._kill_all_running_bots()

        if not BOT_FILE.exists():

            raise FileNotFoundError(
                f"فایل بات پیدا نشد: {BOT_FILE}"
            )


        # اگر بعد از cleanup هنوز پردازشی باقی مانده،
        # اجازه اجرای نسخه جدید را نده.
        if cleanup["remaining"]:

            raise RuntimeError(
                "هنوز یک یا چند پردازش generated_bot.py "
                f"در حال اجرا هستند: {cleanup['remaining']}"
            )


        env = os.environ.copy()


        self.process = subprocess.Popen(
            [
                sys.executable,
                str(BOT_FILE),
            ],
            cwd=str(BASE_DIR),
            env=env,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                if os.name == "nt"
                else 0
            ),
        )


        # کمی صبر برای اینکه process واقعاً بالا بیاید
        time.sleep(0.8)


        if self.process.poll() is not None:

            exit_code = self.process.returncode

            self.process = None

            raise RuntimeError(
                f"بات بلافاصله بعد از اجرا متوقف شد. "
                f"Exit code: {exit_code}"
            )


        return {
            "status": "started",
            "message": "بات با موفقیت اجرا شد.",
            "pid": self.process.pid,
        }


    # =====================================================
    # Stop
    # =====================================================

    def stop_bot(self):

        cleanup = self._kill_all_running_bots()

        self.process = None


        return {
            "status": "stopped",
            "message": "همه نسخه‌های در حال اجرای بات متوقف شدند.",
            "pids": cleanup["stopped"],
        }


    # =====================================================
    # Restart
    # =====================================================

    def restart_bot(self):

        self.stop_bot()

        result = self.start_bot()


        return {
            "status": "restarted",
            "message": "بات با نسخه جدید دوباره اجرا شد.",
            "details": result,
        }


    # =====================================================
    # Status
    # =====================================================

    def status(self):

        pids = self._find_running_bot_pids()


        if pids:

            return {
                "status": "running",
                "pids": pids,
                "count": len(pids),
            }


        return {
            "status": "stopped",
            "pids": [],
            "count": 0,
        }


bot_manager = BotManager()