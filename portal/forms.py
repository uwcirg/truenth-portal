from flask_wtf import FlaskForm as _FlaskForm


class FlaskForm(_FlaskForm):
    """Compatibility wrapper for Flask-WTF / WTForms integration.

    Flask-WTF 1.2.x expects WTForms 3's ``Form.validate(extra_validators=...)``,
    but this project currently uses WTForms 2.2.x whose ``Form.validate`` does
    not accept keyword arguments. Override ``validate_on_submit`` so that
    ``extra_validators`` is not passed as a keyword argument.
    """

    def validate_on_submit(self, extra_validators=None):
        """Call ``validate`` only if the form is submitted.

        The ``extra_validators`` argument is accepted for API compatibility but
        ignored, since the underlying WTForms 2.2.x ``Form.validate`` method
        does not accept it.
        """

        return self.is_submitted() and self.validate()

