from clarifier import generate_questions


bot_spec = {
    "bot_name": "بات رزرو کارگاه",
    "purpose": "رزرو کارگاه",
    "capacity": 20,
    "features": [
        "ثبت نام",
        "رزرو",
        "نمایش ظرفیت",
        "لیست انتظار"
    ],
    "missing_information": [
        "تاریخ و ساعت کارگاه",
        "نحوه انتقال از لیست انتظار",
        "امکان لغو رزرو"
    ]
}

questions = generate_questions(bot_spec)

for question in questions:
    print(question)