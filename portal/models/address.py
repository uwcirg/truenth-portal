"""Address module

Address data lives in the 'addresses' table.  Several entities link
to address via foreign keys.

"""
from sqlalchemy import Enum
from ..database import db

address_type = Enum('postal', 'physical', 'both', name='address_type',
                    create_type=False)
address_use = Enum('home', 'work', 'temp', 'old', name='address_use',
                   create_type=False)


class Address(db.Model):
    """SQLAlchemy class for `addresses` table"""
    __tablename__ = 'addresses'
    id = db.Column(db.Integer(), primary_key=True)
    use = db.Column('a_use', address_use)
    type = db.Column('a_type', address_type)
    line1 = db.Column(db.Text)
    line2 = db.Column(db.Text)
    line3 = db.Column(db.Text)
    city = db.Column(db.Text)
    district = db.Column(db.Text)
    state = db.Column(db.Text)
    postalCode = db.Column(db.Text)
    country = db.Column(db.Text)

    @property
    def lines(self):
        return '; '.join([el for el in (self.line1, self.line2, self.line3) if
                          el])

    def __str__(self):
        return "Address: {0.use} {0.type} {0.lines} {0.city} {0.district}" \
               " {0.state} {0.postalCode} {0.country}".format(self)

    @classmethod
    def from_fhir(cls, data):
        adr = cls()
        if 'line' in data:
            for i, line in zip(range(1, len(data['line']) + 1), data['line']):
                # in case of 4 or more lines, delimit and append to line3
                if i > 3:
                    adr.line3 = '; '.join((adr.line3, line))
                else:
                    setattr(adr, 'line{}'.format(i), line)

        for attr in ('use', 'type'):
            if attr in data:
                setattr(adr, attr, data[attr].lower())

        for attr in ('city', 'district', 'state', 'postalCode', 'country'):
            if attr in data:
                setattr(adr, attr, data[attr])
        return adr

    def as_fhir(self):
        d = {}
        d['use'] = self.use
        d['type'] = self.type
        lines = []
        for el in self.line1, self.line2, self.line3:
            if el:
                lines.append(el)
        d['line'] = lines
        for attr in ('city', 'district', 'state', 'postalCode', 'country'):
            value = getattr(self, attr, None)
            if value:
                d[attr] = value
        return d
