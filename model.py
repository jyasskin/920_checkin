from ndb import model, polymodel

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

class ClassType(model.Model):
    name = model.StringProperty(required=True)
    time = model.TimeProperty(required=True)  # i.e. 7:20 or 8:20

class Class(model.Model):
    type = model.StructuredProperty(ClassType, required=True)
    month = model.DateProperty(
        required=True, validator=lambda prop, value: value.replace(day=1))

_ROLE_CHOICES = ('Lead', 'Follow')

class Attendance(polymodel.PolyModel):
    klass = model.StructuredProperty(Class, required=True)
    student = model.KeyProperty(kind=Student, required=True)

class Presence(model.Model):
    day = model.DateProperty(required=True)
    # If role is missing, the Signup's default role applies.
    role = model.StringProperty(choices=_ROLE_CHOICES)

class Signup(Attendance):
    """Represents that a student has paid for a month (or the rest of
    a month) of class."""
    default_role = model.StringProperty(name='dr', required=True,
                                        choices=_ROLE_CHOICES)
    presence = model.StructuredProperty(Presence, repeated=True)

class Dropin(Attendance):
    """Represents that a student dropped in for a particular lesson
    (class on a day).
    """
    day = model.DateProperty(required=True)
    role = model.StringProperty(required=True, choices=_ROLE_CHOICES)
