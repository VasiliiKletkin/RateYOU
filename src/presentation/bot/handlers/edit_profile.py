import asyncio
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.profile.dto import EditProfileRequest
from src.application.profile.edit_profile import EditProfileUseCase
from src.application.profile.get_profile import GetMyProfileUseCase
from src.domain.profile.exceptions import (
    InvalidAge,
    InvalidBio,
    InvalidName,
    ProfileNotFound,
)
from src.domain.profile.value_objects import Age, Bio, Name, Photos
from src.presentation.bot.i18n import normalize_language
from src.presentation.bot.keyboards import (
    edit_menu_keyboard,
    gender_keyboard,
    share_location_keyboard,
)
from src.presentation.bot.states import EditProfile

_MEDIA_GROUP_DEBOUNCE_SECONDS = 1.2
# Mirror of the /create-side buffer, kept module-local so the two FSM flows
# don't interfere. Key: chat_id. Single-photo and gallery uploads share
# the same debounce path.
_edit_media_buffers: dict[int, list[str]] = {}

router = Router(name="edit_profile")


async def _show_menu(message: Message, state: FSMContext, header: str) -> None:
    await state.set_state(EditProfile.choosing_field)
    await message.answer(header, reply_markup=edit_menu_keyboard())


async def _apply_edit(
    message: Message,
    state: FSMContext,
    edit_uc: EditProfileUseCase,
    *,
    name: str | None = None,
    age: int | None = None,
    gender: str | None = None,
    bio: str | None = None,
    photo_file_ids: tuple[str, ...] | None = None,
    location: tuple[float, float] | None = None,
) -> None:
    data = await state.get_data()
    profile_id_str = data.get("profile_id")
    if profile_id_str is None:
        await message.answer(_("Session lost. Use /edit again."))
        await state.clear()
        return
    try:
        await edit_uc.execute(
            EditProfileRequest(
                profile_id=UUID(str(profile_id_str)),
                name=name,
                age=age,
                gender=gender,
                bio=bio,
                photo_file_ids=photo_file_ids,
                location=location,
            )
        )
    except ProfileNotFound:
        await message.answer(_("Profile not found."))
        await state.clear()
        return
    if location is not None:
        # The reply keyboard from share_location is still showing — clear it
        # before the inline menu reappears.
        await message.answer(_("Location updated."), reply_markup=ReplyKeyboardRemove())
    await _show_menu(message, state, _("Updated. Pick another field or [Done]:"))


@router.message(Command("edit"))
async def cmd_edit(
    message: Message,
    state: FSMContext,
    register_user: FromDishka[RegisterUserUseCase],
    get_my_profile: FromDishka[GetMyProfileUseCase],
) -> None:
    if message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=message.from_user.id,
            language=normalize_language(message.from_user.language_code),
        )
    )
    profile = await get_my_profile.execute(user.id)
    if profile is None:
        await message.answer(_("No profile to edit. Use /create first."))
        return
    await state.set_data({"profile_id": str(profile.id)})
    await _show_menu(message, state, _("Pick a field to edit:"))


@router.callback_query(F.data.startswith("edit_field:"), EditProfile.choosing_field)
async def on_choose_field(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        await callback.answer()
        return
    field = callback.data.removeprefix("edit_field:")

    if field == "done":
        await state.clear()
        await callback.message.answer(_("Saved. /feed to keep rating."))
        await callback.answer()
        return

    next_states = {
        "name": EditProfile.editing_name,
        "age": EditProfile.editing_age,
        "gender": EditProfile.editing_gender,
        "location": EditProfile.editing_location,
        "bio": EditProfile.editing_bio,
        "photo": EditProfile.editing_photo,
    }
    if field not in next_states:
        await callback.answer(_("Unknown field"))
        return
    await state.set_state(next_states[field])

    prompts = {
        "name": _("Send new name:"),
        "age": _("Send new age (18-100):"),
        "gender": _("Pick gender:"),
        "location": _("Share your new location:"),
        "bio": _("Send new bio (or /skip to clear):"),
        "photo": _("Send up to {max} new photos:").format(max=Photos.MAX_COUNT),
    }
    if field == "gender":
        await callback.message.answer(prompts[field], reply_markup=gender_keyboard())
    elif field == "location":
        await callback.message.answer(
            prompts[field],
            reply_markup=share_location_keyboard(_("📍 Share location")),
        )
    elif field == "photo":
        # Reset the accumulator — old edit attempts (if any) shouldn't leak in.
        await state.update_data(edit_photos=[])
        await callback.message.answer(prompts[field])
    else:
        await callback.message.answer(prompts[field])
    await callback.answer()


@router.message(EditProfile.editing_name)
async def process_edit_name(
    message: Message,
    state: FSMContext,
    edit_profile: FromDishka[EditProfileUseCase],
) -> None:
    if message.text is None:
        await message.answer(_("Please send text."))
        return
    try:
        Name(message.text)
    except InvalidName:
        await message.answer(_("❌ Name must be 1-50 non-empty characters. Try again:"))
        return
    await _apply_edit(message, state, edit_profile, name=message.text)


@router.message(EditProfile.editing_age)
async def process_edit_age(
    message: Message,
    state: FSMContext,
    edit_profile: FromDishka[EditProfileUseCase],
) -> None:
    if message.text is None:
        await message.answer(_("Please send a number."))
        return
    try:
        age_value = int(message.text.strip())
        Age(age_value)
    except ValueError:
        await message.answer(_("❌ That's not a number. Try again:"))
        return
    except InvalidAge:
        await message.answer(_("❌ Age must be between 18 and 100. Try again:"))
        return
    await _apply_edit(message, state, edit_profile, age=age_value)


@router.callback_query(F.data.startswith("gender:"), EditProfile.editing_gender)
async def process_edit_gender(
    callback: CallbackQuery,
    state: FSMContext,
    edit_profile: FromDishka[EditProfileUseCase],
) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        await callback.answer()
        return
    gender = callback.data.removeprefix("gender:")
    if gender not in ("male", "female"):
        await callback.answer(_("Invalid"))
        return
    await callback.answer()
    await _apply_edit(callback.message, state, edit_profile, gender=gender)


@router.message(Command("skip"), EditProfile.editing_bio)
async def skip_edit_bio(
    message: Message,
    state: FSMContext,
    edit_profile: FromDishka[EditProfileUseCase],
) -> None:
    await _apply_edit(message, state, edit_profile, bio="")


@router.message(EditProfile.editing_bio)
async def process_edit_bio(
    message: Message,
    state: FSMContext,
    edit_profile: FromDishka[EditProfileUseCase],
) -> None:
    if message.text is None:
        await message.answer(_("Please send text or /skip to clear."))
        return
    try:
        Bio(message.text)
    except InvalidBio:
        await message.answer(_("❌ Bio is too long (max 500 chars). Try again or /skip:"))
        return
    await _apply_edit(message, state, edit_profile, bio=message.text)


@router.message(F.photo, EditProfile.editing_photo)
async def collect_edit_photo(
    message: Message,
    state: FSMContext,
    edit_profile: FromDishka[EditProfileUseCase],
) -> None:
    if not message.photo:
        return
    photo_file_id = message.photo[-1].file_id
    chat_id = message.chat.id

    is_leader = chat_id not in _edit_media_buffers
    buf = _edit_media_buffers.setdefault(chat_id, [])
    if len(buf) < Photos.MAX_COUNT:
        buf.append(photo_file_id)

    if not is_leader:
        return

    await asyncio.sleep(_MEDIA_GROUP_DEBOUNCE_SECONDS)
    photos = _edit_media_buffers.pop(chat_id, [])[: Photos.MAX_COUNT]
    if not photos:
        return
    await _apply_edit(message, state, edit_profile, photo_file_ids=tuple(photos))


@router.message(EditProfile.editing_photo)
async def process_edit_photo_invalid(message: Message) -> None:
    await message.answer(_("Please send a photo."))


@router.message(F.location, EditProfile.editing_location)
async def process_edit_location(
    message: Message,
    state: FSMContext,
    edit_profile: FromDishka[EditProfileUseCase],
) -> None:
    if message.location is None:
        return
    await _apply_edit(
        message,
        state,
        edit_profile,
        location=(message.location.latitude, message.location.longitude),
    )


@router.message(EditProfile.editing_location)
async def process_edit_location_invalid(message: Message) -> None:
    await message.answer(_("Please share a location."))
