import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "generated_bots"
    / "workshops.json"
)


def _ensure_file():
    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not DATA_FILE.exists():
        DATA_FILE.write_text(
            "[]",
            encoding="utf-8",
        )


def load_workshops():
    _ensure_file()

    try:
        content = DATA_FILE.read_text(
            encoding="utf-8"
        )

        data = json.loads(content)

        if not isinstance(data, list):
            return []

        return data

    except Exception:
        return []


def save_workshops(workshops):
    _ensure_file()

    DATA_FILE.write_text(
        json.dumps(
            workshops,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _spec_to_dict(spec):
    if isinstance(spec, dict):
        return dict(spec)

    if hasattr(spec, "model_dump"):
        return spec.model_dump()

    if hasattr(spec, "dict"):
        return spec.dict()

    raise TypeError(
        "spec باید dict یا Pydantic model باشد."
    )


def add_workshop(
    spec,
    owner_user_id=None,
    creator_ip="",
    creator_country="",
    creator_city="",
):
    workshops = load_workshops()

    data = _spec_to_dict(spec)

    next_id = 1

    if workshops:
        next_id = max(
            int(item.get("id", 0))
            for item in workshops
        ) + 1

    workshop = {
        "id": next_id,
        "owner_user_id": owner_user_id,
        "creator_ip": creator_ip,
        "creator_country": creator_country,
        "creator_city": creator_city,
        **data,
    }

    workshops.append(workshop)

    save_workshops(workshops)

    return workshop


def get_workshop(workshop_id):
    workshop_id = int(workshop_id)

    for workshop in load_workshops():
        if int(workshop.get("id", 0)) == workshop_id:
            return workshop

    return None


def get_user_workshops(user_id):
    user_id = int(user_id)

    return [
        workshop
        for workshop in load_workshops()
        if workshop.get("owner_user_id") is not None
        and int(workshop.get("owner_user_id")) == user_id
    ]


def get_all_workshops():
    return load_workshops()


def update_workshop(workshop_id, new_spec):
    workshops = load_workshops()

    workshop_id = int(workshop_id)

    new_data = _spec_to_dict(new_spec)

    for index, workshop in enumerate(workshops):

        if int(workshop.get("id", 0)) != workshop_id:
            continue

        updated = dict(workshop)

        # اطلاعات مالک حفظ می‌شوند
        updated.update(new_data)

        updated["id"] = workshop["id"]
        updated["owner_user_id"] = workshop.get(
            "owner_user_id"
        )

        updated["creator_ip"] = workshop.get(
            "creator_ip",
            "",
        )

        updated["creator_country"] = workshop.get(
            "creator_country",
            "",
        )

        updated["creator_city"] = workshop.get(
            "creator_city",
            "",
        )

        workshops[index] = updated

        save_workshops(workshops)

        return updated

    return None


def delete_workshop(workshop_id):
    workshops = load_workshops()

    workshop_id = int(workshop_id)

    original_count = len(workshops)

    workshops = [
        workshop
        for workshop in workshops
        if int(workshop.get("id", 0)) != workshop_id
    ]

    if len(workshops) == original_count:
        return False

    save_workshops(workshops)

    return True





def is_workshop_active(workshop_id):
    """
    بررسی می‌کند کارگاه وجود دارد و غیرفعال نشده است.
    اگر فیلد active وجود نداشته باشد، کارگاه فعال فرض می‌شود.
    """
    workshop = get_workshop(workshop_id)

    if workshop is None:
        return False

    return workshop.get("active", True) is not False
