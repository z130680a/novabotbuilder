from pydantic import BaseModel, Field, AliasChoices


class BotSpec(BaseModel):
    bot_name: str = Field(
        min_length=1,
        max_length=100,
    )

    purpose: str = Field(
        min_length=1,
    )

    capacity: int = Field(
        gt=0,
    )

    features: list[str] = Field(
        default_factory=list,
    )

    missing_information: list[str] = Field(
        default_factory=list,
    )

    event_date: str = ""

    event_time: str = Field(
        default="",
        validation_alias=AliasChoices(
            "event_time",
            "start_time",
        ),
    )

    event_end_time: str = ""