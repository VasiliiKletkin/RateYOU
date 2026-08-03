from aiogram.fsm.state import State, StatesGroup


class CreateProfile(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_gender = State()
    waiting_for_gender_preference = State()
    waiting_for_location = State()
    waiting_for_bio = State()
    waiting_for_photo = State()


class SetSearchLocation(StatesGroup):
    """Standalone city picker for the feed's search origin.

    Separate from CreateProfile: a user sets a search area to browse without
    ever creating a profile of their own.
    """

    waiting_for_location = State()


class EditProfile(StatesGroup):
    choosing_field = State()
    editing_name = State()
    editing_age = State()
    editing_gender = State()
    editing_location = State()
    editing_bio = State()
    editing_photo = State()
