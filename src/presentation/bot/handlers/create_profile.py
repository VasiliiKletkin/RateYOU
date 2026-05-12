import asyncio
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.profile.create_profile import CreateProfileUseCase
from src.application.profile.dto import CreateProfileRequest
from src.application.profile.get_profile import GetMyProfileUseCase
from src.domain.profile.exceptions import (
    InvalidAge,
    InvalidBio,
    InvalidName,
    ProfileAlreadyExists,
)
from src.domain.profile.value_objects import Age, Bio, Name, Photos
from src.presentation.bot.keyboards import (
    gender_keyboard,
    gender_preference_keyboard,
    share_location_keyboard,
)
from src.presentation.bot.states import CreateProfile

# How long to wait after the last photo arrives before finalizing the
# profile. Handles both gallery uploads (media_group_id set, photos arrive
# within ~200-500ms) and "send a few photos one-by-one" flows.
_MEDIA_GROUP_DEBOUNCE_SECONDS = 1.2

# Per-chat photo buffer. The handler that wins the "first photo for this
# chat" race takes ownership: it sleeps for the debounce window, then pops
# the buffer and finalizes. Late handlers for the same chat just append
# and exit.
_media_buffers: dict[int, list[str]] = {}

router = Router(name="create_profile")


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(_("Nothing to cancel."))
        return
    await state.clear()
    await message.answer(_("Cancelled."))


@router.message(Command("create"))
async def cmd_create(
    message: Message,
    state: FSMContext,
    register_user: FromDishka[RegisterUserUseCase],
    get_my_profile: FromDishka[GetMyProfileUseCase],
) -> None:
    if message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(telegram_id=message.from_user.id)
    )
    if (await get_my_profile.execute(user.id)) is not None:
        await message.answer(_("You already have a profile."))
        return

    await state.set_data({"user_id": str(user.id)})
    await state.set_state(CreateProfile.waiting_for_name)
    await message.answer(_("Let's create your profile.\nWhat's your name?"))


@router.message(CreateProfile.waiting_for_name)
async def process_name(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer(_("Please send text."))
        return
    try:
        name = Name(message.text)
    except InvalidName:
        await message.answer(_("❌ Name must be 1-50 non-empty characters. Try again:"))
        return
    await state.update_data(name=name.value)
    await state.set_state(CreateProfile.waiting_for_age)
    await message.answer(_("How old are you?"))


@router.message(CreateProfile.waiting_for_age)
async def process_age(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer(_("Please send a number."))
        return
    try:
        age = Age(int(message.text.strip()))
    except ValueError:
        await message.answer(_("❌ That's not a number. Try again:"))
        return
    except InvalidAge:
        await message.answer(_("❌ Age must be between 18 and 100. Try again:"))
        return
    await state.update_data(age=age.value)
    await state.set_state(CreateProfile.waiting_for_gender)
    await message.answer(_("Pick gender:"), reply_markup=gender_keyboard())


@router.callback_query(
    F.data.startswith("gender:"),
    CreateProfile.waiting_for_gender,
)
async def process_gender(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
        return
    gender = callback.data.removeprefix("gender:")
    if gender not in ("male", "female"):
        await callback.answer(_("Invalid choice"))
        return
    await state.update_data(gender=gender)
    await state.set_state(CreateProfile.waiting_for_gender_preference)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            _("Who would you like to rate?"),
            reply_markup=gender_preference_keyboard(),
        )
    await callback.answer()


@router.callback_query(
    F.data.startswith("genderpref:"),
    CreateProfile.waiting_for_gender_preference,
)
async def process_gender_preference(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if callback.data is None:
        await callback.answer()
        return
    preference = callback.data.removeprefix("genderpref:")
    if preference not in ("male", "female", "any"):
        await callback.answer(_("Invalid choice"))
        return
    await state.update_data(gender_preference=preference)
    await state.set_state(CreateProfile.waiting_for_location)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            _("Share your location — it's used to find nearby profiles:"),
            reply_markup=share_location_keyboard(_("📍 Share location")),
        )
    await callback.answer()


@router.message(F.location, CreateProfile.waiting_for_location)
async def process_location(message: Message, state: FSMContext) -> None:
    if message.location is None:
        return
    await state.update_data(
        location_lat=message.location.latitude,
        location_lon=message.location.longitude,
    )
    await state.set_state(CreateProfile.waiting_for_bio)
    await message.answer(
        _("Tell something about yourself (or /skip):"),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CreateProfile.waiting_for_location)
async def process_location_invalid(message: Message) -> None:
    await message.answer(_("Please share a location to continue."))


@router.message(Command("skip"), CreateProfile.waiting_for_bio)
async def skip_bio(message: Message, state: FSMContext) -> None:
    await state.update_data(bio="", photos=[])
    await state.set_state(CreateProfile.waiting_for_photo)
    await message.answer(
        _("Send up to {max} photos:").format(max=Photos.MAX_COUNT)
    )


@router.message(CreateProfile.waiting_for_bio)
async def process_bio(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer(_("Please send text or /skip."))
        return
    try:
        bio = Bio(message.text)
    except InvalidBio:
        await message.answer(_("❌ Bio is too long (max 500 chars). Try again or /skip:"))
        return
    await state.update_data(bio=bio.value, photos=[])
    await state.set_state(CreateProfile.waiting_for_photo)
    await message.answer(
        _("Send up to {max} photos:").format(max=Photos.MAX_COUNT)
    )


async def _finalize_create(
    message: Message,
    state: FSMContext,
    create_profile: CreateProfileUseCase,
) -> None:
    data = await state.get_data()
    photos: list[str] = data.get("photos", [])
    if "user_id" not in data:
        # State was cleared between buffering and flushing (e.g. /cancel).
        return
    try:
        profile = await create_profile.execute(
            CreateProfileRequest(
                owner_id=UUID(data["user_id"]),
                name=data["name"],
                age=data["age"],
                gender=data["gender"],
                gender_preference=data["gender_preference"],
                bio=data["bio"],
                photo_file_ids=tuple(photos),
                location=(data["location_lat"], data["location_lon"]),
            )
        )
    except ProfileAlreadyExists:
        await message.answer(_("You already have a profile."))
        await state.clear()
        return

    await state.clear()
    await message.answer(
        _(
            "<b>✅ Profile created!</b>\n"
            "Name: {name}\n"
            "Age: {age}\n"
            "Send /feed to start rating profiles."
        ).format(name=profile.name, age=profile.age)
    )


@router.message(F.photo, CreateProfile.waiting_for_photo)
async def collect_photo(
    message: Message,
    state: FSMContext,
    create_profile: FromDishka[CreateProfileUseCase],
) -> None:
    if not message.photo:
        return
    photo_file_id = message.photo[-1].file_id
    chat_id = message.chat.id

    is_leader = chat_id not in _media_buffers
    buf = _media_buffers.setdefault(chat_id, [])
    if len(buf) < Photos.MAX_COUNT:
        buf.append(photo_file_id)

    if not is_leader:
        return

    await asyncio.sleep(_MEDIA_GROUP_DEBOUNCE_SECONDS)
    photos = _media_buffers.pop(chat_id, [])[: Photos.MAX_COUNT]
    if not photos:
        return
    await state.update_data(photos=photos)
    await _finalize_create(message, state, create_profile)


@router.message(CreateProfile.waiting_for_photo)
async def process_photo_invalid(message: Message) -> None:
    await message.answer(_("Please send a photo (not text)."))
