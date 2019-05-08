class PartialFailure(Exception):
    """
    Error indicating either send_messages or delete_messages API call failed partially
    """

    def __init__(self, result, *args):
        self.success_count = len(result['Successful'])
        self.failure_count = len(result['Failed'])
        self.result = result
        super().__init__(*args)
