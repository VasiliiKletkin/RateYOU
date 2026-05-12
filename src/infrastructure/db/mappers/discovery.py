from src.domain.discovery.entities import SearchPreferences
from src.domain.discovery.value_objects import MinRating
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.discovery import SearchPreferencesORM


def search_preferences_to_orm(prefs: SearchPreferences) -> SearchPreferencesORM:
    return SearchPreferencesORM(
        user_id=prefs.user_id.value,
        gender_preference=prefs.gender_preference,
        min_rating=prefs.min_rating.value,
        created_at=prefs.created_at,
        updated_at=prefs.updated_at,
    )


def orm_to_search_preferences(orm: SearchPreferencesORM) -> SearchPreferences:
    return SearchPreferences(
        user_id=UserId(orm.user_id),
        gender_preference=orm.gender_preference,
        min_rating=MinRating(orm.min_rating),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )
