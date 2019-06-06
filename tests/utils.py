def mock_return_once(m, first_result, rest):
    """
    Sets up mock callable such that it returns a result first the time, and a different result all other times it's called.
    Useful for functions that may be called indefinitely in a while loop
    :param m: the mock object
    :param first_result: value to return 1st time the mock is called
    :param rest: value to return after 1st time the mock is called
    :return:
    """

    def f(*args, **kwargs):
        if f.called:
            return rest

        f.called = True
        return first_result

    f.called = False

    m.side_effect = f
