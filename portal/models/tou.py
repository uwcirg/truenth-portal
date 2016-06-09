"""ToU (Terms of Use)  module"""
from ..extensions import db


class ToU(db.Model):
    """SQLAlchemy class for `tou` table"""
    __tablename__ = 'tou'
    id = db.Column(db.Integer(), primary_key=True)

    text = db.Column(db.Text, nullable=False)
    """Actual text the user agreed to"""

    audit_id = db.Column(db.ForeignKey('audit.id'), nullable=False)

    audit = db.relationship('Audit', cascade="save-update", lazy='joined')
    """tracks when and by whom the terms were agreed to"""

    def __str__(self):
        return "ToU ({audit}) {text_snip}".format(
            audit=self.audit, text_snip=self.text[:50])
