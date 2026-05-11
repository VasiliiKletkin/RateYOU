class ProfileError(Exception):
    """Base for profile domain errors."""


class ProfileNotFound(ProfileError):
    pass


class ProfileAlreadyExists(ProfileError):
    pass


class InvalidAge(ProfileError):
    pass


class InvalidName(ProfileError):
    pass


class InvalidBio(ProfileError):
    pass


class InvalidGender(ProfileError):
    pass


class InvalidPhoto(ProfileError):
    pass


class InvalidPhotos(ProfileError):
    pass


class InvalidLocation(ProfileError):
    pass
