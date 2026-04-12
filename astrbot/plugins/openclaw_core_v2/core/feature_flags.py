from data.plugins._shared_feature_flags import (
    create_feature_flags,
    disable_feature as disable_feature_value,
    enable_feature as enable_feature_value,
    get_feature_status as get_feature_status_value,
    is_feature_enabled as is_feature_enabled_value,
)

FEATURE_FLAGS = create_feature_flags()


def is_feature_enabled(flag_name):
    return is_feature_enabled_value(FEATURE_FLAGS, flag_name)


def enable_feature(flag_name):
    enable_feature_value(FEATURE_FLAGS, flag_name)


def disable_feature(flag_name):
    disable_feature_value(FEATURE_FLAGS, flag_name)


def get_feature_status():
    return get_feature_status_value(FEATURE_FLAGS)
