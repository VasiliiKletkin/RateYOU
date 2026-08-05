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
    """Browse onboarding: gender preference, then the feed's search origin.

    Separate from CreateProfile: a user sets these to browse without ever
    creating a profile of their own. The gender step only runs on first
    onboarding (/start, /feed with no location yet); /setcity re-enters at
    the location step directly.
    """

    waiting_for_gender_preference = State()
    waiting_for_location = State()


class EditProfile(StatesGroup):
    choosing_field = State()
    editing_name = State()
    editing_age = State()
    editing_gender = State()
    editing_location = State()
    editing_bio = State()
    editing_photo = State()
