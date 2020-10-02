from hedwig.conf import settings


def unconfigure() -> None:
    """
    If settings were configured, un-configure them - useful for testing only.
    """
    settings.clear_cache()
    settings._user_settings = None
