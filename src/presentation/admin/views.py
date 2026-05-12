from starlette.requests import Request
from starlette_admin import StringField
from starlette_admin.contrib.sqla import ModelView


class UserAdmin(ModelView):
    label = "Users"
    icon = "fa fa-user"
    fields = [
        "id",
        "telegram_id",
        "role",
        "is_banned",
        "ban_reason",
        "banned_at",
        "language",
        "created_at",
    ]
    searchable_fields = ["telegram_id"]
    sortable_fields = ["created_at", "telegram_id"]

    # Users are created via the bot's RegisterUserUseCase, not from admin.
    def can_create(self, request: Request) -> bool:
        return False


class ProfileAdmin(ModelView):
    label = "Profiles"
    icon = "fa fa-id-card"
    fields = [
        "id",
        "owner_id",
        "name",
        "age",
        "gender",
        "bio",
        # Photos live in `profile_photos` (1:N). List view: just a count.
        # Detail view: full file_id list with positions.
        StringField(
            "photos_display",
            label="Photos",
            read_only=True,
            exclude_from_detail=True,
        ),
        StringField(
            "photos_detail",
            label="Photos",
            read_only=True,
            exclude_from_list=True,
        ),
        "is_visible",
        # `location` itself is a PostGIS WKBElement — Starlette-Admin can't
        # render it. `location_display` (@property on ORM) returns "lat, lon".
        # Wrapped in StringField because the SQLA converter only resolves
        # mapped columns by name; property names are unknown to it.
        StringField("location_display", label="Location", read_only=True),
        "created_at",
        "updated_at",
    ]
    searchable_fields = ["name"]
    sortable_fields = ["created_at", "age"]

    def can_create(self, request: Request) -> bool:
        return False


class ProfilePhotoAdmin(ModelView):
    label = "Profile Photos"
    icon = "fa fa-image"
    fields = ["id", "profile_id", "file_id", "position"]
    sortable_fields = ["profile_id", "position"]
    searchable_fields = ["file_id"]

    # Photos are managed via bot /create and /edit — admin is read-only to
    # avoid orphaning rows or violating the (profile_id, position) constraint.
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False


class RatingAdmin(ModelView):
    label = "Ratings"
    icon = "fa fa-star"
    fields = [
        "id",
        "rater_id",
        "rated_id",
        "score",
        "created_at",
        "updated_at",
    ]
    sortable_fields = ["created_at", "score"]

    def can_create(self, request: Request) -> bool:
        return False

    # Ratings are owned by domain logic — no manual tweaks from admin.
    def can_edit(self, request: Request) -> bool:
        return False


class ProfileScoreSummaryAdmin(ModelView):
    label = "Score Summaries"
    icon = "fa fa-chart-line"
    fields = [
        "rated_id",
        "average_score",
        "rating_count",
        "updated_at",
    ]
    sortable_fields = ["average_score", "rating_count"]

    # Projection — recomputed by RateUserUseCase; any manual edit would
    # diverge from the underlying ratings.
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False


class SearchPreferencesAdmin(ModelView):
    label = "Search Preferences"
    icon = "fa fa-sliders"
    fields = [
        "user_id",
        "gender_preference",
        "min_rating",
        "created_at",
        "updated_at",
    ]
    sortable_fields = ["updated_at"]

    # Rows are created lazily by the bot (/create or first /settings access);
    # admin shouldn't manufacture orphaned rows.
    def can_create(self, request: Request) -> bool:
        return False


class SubscriptionAdmin(ModelView):
    label = "Subscriptions"
    icon = "fa fa-crown"
    fields = [
        "owner_id",
        "tier",
        "expires_at",
        "is_revoked",
        "updated_at",
    ]
    sortable_fields = ["expires_at", "updated_at"]


class TransactionAdmin(ModelView):
    label = "Transactions"
    icon = "fa fa-money-bill"
    fields = [
        "id",
        "payer_id",
        "amount",
        "currency",
        "provider",
        "purpose",
        "status",
        "external_id",
        "created_at",
        "updated_at",
    ]
    searchable_fields = ["status", "purpose"]
    sortable_fields = ["created_at", "amount"]

    # State transitions only via Payment use cases.
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False
