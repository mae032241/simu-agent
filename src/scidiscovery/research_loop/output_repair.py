"""Author-correctable final response failures, never integrity or I/O failures."""


class OutputRepairRequired(ValueError):
    """A known completed turn needs a corrected response in its original session."""

    def __init__(self, code, diagnostic):
        self.code = code
        self.diagnostic = diagnostic[:512]
        super().__init__(self.diagnostic)

    def request(self):
        return dict(code=self.code, diagnostic=self.diagnostic)
