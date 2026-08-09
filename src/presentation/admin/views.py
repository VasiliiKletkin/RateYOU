from starlette_admin import StringField
from starlette_admin.contrib.sqla import ModelView


class UserAdmin(ModelView):
    label = "Users"
    icon = "fa fa-user"
    fields = [
        "id",
        "telegram_id",
        "username",
        "notifications_enabled",
        "role",
        "is_banned",
        "ban_reason",
        "banned_at",
        "language",
        "created_at",
    ]
    searchable_fields = ["telegram_id"]
    sortable_fields = ["created_at", "telegram_id", "role"]


class AcquisitionSourceAdmin(ModelView):
    label = "Sources"
    icon = "fa fa-bullhorn"
    # Source dictionary: campaign tags AND referrers, unified. A row with
    # `referrer` set is a person (code = their telegram_id, auto-created
    # when their first invitee arrives); a row without is a campaign tag
    # (auto-created on first arrival, or pre-created here before a campaign
    # starts). Tag codes must be lowercase latin, digits, `_` or `-` — the
    # bot lowercases arrivals, so an uppercase entry would just gain a
    # lowercase twin.
    fields = [
        "id",
        "code",
        "referrer",
        "created_at",
    ]
    searchable_fields = ["code"]
    sortable_fields = ["created_at", "code"]


class AcquisitionAdmin(ModelView):
    label = "Acquisition"
    icon = "fa fa-user-tag"
    # One row per user: which source brought them in (`source` renders as a
    # link to the dictionary row). Written once at registration; the only
    # column that ever changes is `rewarded_at` — the referral-reward
    # lifecycle (NULL = pending, set = paid; always NULL for campaign
    # sources). The funnel itself is read with SQL (`make funnel`).
    fields = [
        "user_id",
        "source",
        "created_at",
        "rewarded_at",
    ]
    sortable_fields = ["created_at", "rewarded_at"]
    fields_default_sort = [("created_at", True)]  # DESC


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


class ProfilePhotoAdmin(ModelView):
    label = "Profile Photos"
    icon = "fa fa-image"
    fields = ["id", "profile_id", "file_id", "position"]
    sortable_fields = ["profile_id", "position"]
    searchable_fields = ["file_id"]


class RatingAdmin(ModelView):
    label = "Ratings"
    icon = "fa fa-star"
    # `rater` / `rated` render as links to the User rows (same pattern as
    # ReferralAdmin's referrer/referee) instead of bare UUID columns.
    fields = [
        "id",
        "rater",
        "rated",
        "score",
        "created_at",
        "updated_at",
    ]
    sortable_fields = ["created_at", "score"]
    fields_default_sort = [("created_at", True)]  # DESC


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


class SubscriptionAdmin(ModelView):
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
