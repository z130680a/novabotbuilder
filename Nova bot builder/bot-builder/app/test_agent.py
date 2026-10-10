from agent import agent


result = agent.invoke({
    "user_request": """
    یک بات رزرو کارگاه می‌خواهم.
    ظرفیت هر کارگاه ۲۰ نفر باشد.
    کاربران بتوانند ثبت‌نام کنند و ظرفیت باقی‌مانده را ببینند.
    اگر ظرفیت پر شد، وارد لیست انتظار شوند.
    """,
    "bot_spec": None,
    "response": ""
})

print(result["bot_spec"])