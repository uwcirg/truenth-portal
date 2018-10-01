from ..database import db


class ValueQuantity(db.Model):
    __tablename__ = 'value_quantities'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(80))
    units = db.Column(db.String(80))
    system = db.Column(db.String(255))
    code = db.Column(db.String(80))

    def __init__(self, value=None, units=None, system=None, code=None):
        self.value = value
        self.units = units
        self.system = system
        self.code = code
        if units == 'boolean':
            # If given an integer (as some FHIR compliant libraries require
            # for Value Quantity), and the units are set to boolean, convert
            # based on classic truth value.
            try:
                self.value = int(value) != 0
            except (TypeError, ValueError) as e:
                if value is None or isinstance(value, basestring):
                    pass
                else:
                    raise e

    def __str__(self):
        """Print friendly format for logging, etc."""
        components = ','.join(
            [str(x) for x in (self.value, self.units, self.system, self.code)
             if x is not None])
        return "ValueQuantity " + components

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        d = {}
        for i in ("value", "units", "system", "code"):
            if getattr(self, i):
                d[i] = getattr(self, i)
        return {"valueQuantity": d}

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, existing ValueQuantity (matches on
        value, units and system alone).  Populates self.id if found,
        adds to database first if not.

        """
        if self.id:
            return self

        lookup_value = self.value and str(self.value) or None
        match = self.query.filter_by(
            value=lookup_value, units=self.units, system=self.system).first()
        if not match:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        elif self is not match:
            self = db.session.merge(match)
        return self
