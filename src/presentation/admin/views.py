from starlette_admin import StringField
from starlette_admin.contrib.sqla import ModelView


class UserAdmin(ModelView):
    identity = "users"
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
        "referred_by_user_id",
        "created_at",
    ]
    searchable_fields = ["telegram_id"]
    sortable_fields = ["created_at", "telegram_id"]


class ProfileAdmin(ModelView):
    identity = "profiles"
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


class ProfilePhotoAdmin(ModelView):
    identity = "profile_photos"
    label = "Profile Photos"
    icon = "fa fa-image"
    fields = ["id", "profile_id", "file_id", "position"]
    sortable_fields = ["profile_id", "position"]
    searchable_fields = ["file_id"]


class RatingAdmin(ModelView):
    identity = "ratings"
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


class ProfileScoreSummaryAdmin(ModelView):
    identity = "profile_score_summaries"
    label = "Score Summaries"
    icon = "fa fa-chart-line"
    fields = [
        "rated_id",
        "average_score",
        "rating_count",
        "updated_at",
    ]
    sortable_fields = ["average_score", "rating_count"]


class SearchPreferencesAdmin(ModelView):
    identity = "search_preferences"
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


class SubscriptionAdmin(ModelView):
    identity = "subscriptions"
    label = "Subscriptions"
    icon = "fa fa-crown"
    # Append-only ledger of granted premium periods. Each row = one grant
    # (purchase / bonus / ...). A user typically has many over time; current
    # premium state is derived by projecting the active set.
    fields = [
        "id",
        "owner",
        "tier",
        "source",
        "transaction",
        "starts_at",
        "expires_at",
        "is_revoked",
        "created_at",
    ]
    sortable_fields = ["created_at", "expires_at"]
    fields_default_sort = [("created_at", True)]  # DESC


class TransactionAdmin(ModelView):
    identity = "transactions"
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


class ReferralAdmin(ModelView):
    identity = "referrals"
    label = "Referrals"
    icon = "fa fa-user-plus"
    # Append-only: each row marks one paid-out referral (referee created
    # their profile and BONUS Subscriptions were issued to both sides).
    # The row's existence is the «rewarded» state — no status column.
    fields = [
        "id",
        "referrer",
        "referee",
        "created_at",
    ]
    sortable_fields = ["created_at"]
    fields_default_sort = [("created_at", True)]  # DESC
