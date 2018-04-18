import re

import hedwig


class CustomValidator(hedwig.MessageValidator):
    # simplistic check: 17 alphanumeric characters except i, o, q
    _vin_re = re.compile("^[a-hj-npr-z0-9]{17}$")

    @staticmethod
    @hedwig.MessageValidator.checker.checks('vin')
    def check_vin(instance) -> bool:
        if not isinstance(instance, str):
            return True
        return bool(CustomValidator._vin_re.match(instance))
