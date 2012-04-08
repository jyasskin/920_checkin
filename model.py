from google.appengine.ext.ndb import model, polymodel
import datetime

# The 9:20 Special has 4 types of classes, each of which runs in
# month-long series.  Students can sign up for a month online, they
# can drop in the day of a lesson and pay for just that lesson, or
# they can drop in and pay for the rest of the month.  Once students
# have paid for a month, they can take a different lesson on a
# particular day.  Students sign up for a particular role in a class,
# but they can switch roles just like they switch lessons.
#
# So far, this program ignores the amounts students pay and the fact
# that there's sometimes a 2-month class.


class Student(model.Model):
    # Numeric IDs assigned by the datastore, so in theory we can have
    # two students with the same name.  That'll be very hard to deal
    # with in the UI though.
    name = model.StringProperty(required=True)
    email = model.StringProperty()

    def to_json(self):
        result = dict(id=self.key.id(), name=self.name)
        if self.email is not None:
            result['email'] = self.email
        return result

    def _pre_put_hook(self):
        assert self.key.parent() is None, self.key.parent()

class ClassType(model.Model):
    name = model.StringProperty(required=True)
    time = model.TimeProperty(required=True)  # i.e. 7:20 or 8:20

    def to_json(self):
        return dict(id=self.key.id(), name=self.name,
                    time=self.time.strftime('%H:%M'))

    def _pre_put_hook(self):
        assert self.key.parent() is None, self.key.parent()

class Month(model.Model):
    """Serves as the ancestor for all queries except Students and
    ClassTypes, to let us use transactions and not download too much
    data to the client.

    Entity keys will be of the form "yyyy-mm".
    """
    @classmethod
    def fromdate(cls, month):
        assert isinstance(month, datetime.date), str(type(month))
        return cls(id=month.strftime('%Y-%m'))

    @property
    def year(self):
        return int(self.key.id()[:4])
    @property
    def month(self):
        return int(self.key.id()[5:])

    def Thursdays(self):
        THURSDAY = 3
        ONE_DAY = datetime.timedelta(days=1)
        ONE_WEEK = datetime.timedelta(weeks=1)

        result = []
        month = self.month
        cur = datetime.date(self.year, month, 1)
        while cur.weekday() != THURSDAY:
            # Could just add the right number of days, but this is
            # more clearly correct.
            cur += ONE_DAY
        while cur.month == month:
            result.append(cur)
            cur += ONE_WEEK
        return result

    def to_json(self):
        return self.key.id()

    def _pre_put_hook(self):
        assert self.key.parent() is None, self.key.parent()


class Class(model.Model):
    # Refers to the class information for this class. We fetch all
    # ClassTypes in each use, so the KeyProperty gets looked up
    # locally without extra datastore operations.
    type = model.KeyProperty(ClassType, required=True)
    # Lists the days this class is happening.
    days = model.DateProperty(repeated=True)

    def to_json(self):
        result = dict(type=self.type.id(), days=[])
        for day in self.days:
            result['days'].append(day.isoformat())
        return result

    def _pre_put_hook(self):
        parent = self.key.parent()
        assert parent.kind() == 'Month', parent.kind()
        assert parent.parent() is None, parent.parent()

_ROLE_CHOICES = ('Lead', 'Follow')

class Signup(polymodel.PolyModel):
    """Represents a student paying for a class."""
    klass = model.KeyProperty(Class, required=True)
    student = model.KeyProperty(kind=Student, required=True)

    def to_json(self):
        return {'class': self.klass.id(), 'student': self.student.id()}

    def _pre_put_hook(self):
        parent = self.key.parent()
        assert parent.kind() == 'Month', parent.kind()
        assert parent.parent() is None, parent.parent()

class Presence(model.Model):
    """Not stored directly: records which days a MonthSignup was
    actually used."""
    day = model.DateProperty(required=True)
    # If role is missing, the Signup's default role applies.
    role = model.StringProperty(choices=_ROLE_CHOICES)

    def _pre_put_hook(self):
        raise TypeError('Presence should only be used inside other objects')


class MonthSignup(Signup):
    """Represents that a student has paid for a month (or the rest of
    a month) of class."""
    default_role = model.StringProperty(name='dr', required=True,
                                        choices=_ROLE_CHOICES)
    presence = model.StructuredProperty(Presence, repeated=True)

    def to_json(self):
        result = super(MonthSignup, self).to_json()
        result['role'] = self.default_role
        result['presence'] = []
        for presence in self.presence:
            presence_data = dict(day=presence.day.isoformat())
            if presence.role is not None:
                presence_data['role'] = presence.role
            result['presence'].append(presence_data)
        return result

class DaySignup(Signup):
    """Represents that a student dropped in for a particular lesson
    (class on a day).
    """
    day = model.DateProperty(required=True)
    role = model.StringProperty(required=True, choices=_ROLE_CHOICES)

    def to_json(self):
        result = super(DaySignup, self).to_json()
        result['day'] = self.day.isoformat()
        result['role'] = self.role
        return result
