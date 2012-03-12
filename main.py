from ndb import context
import calendar
import datetime
import json
import model
import ndb
import re
import webapp2

_MONTH_REGEX = re.compile('^(?P<year>\d{4})-(?P<month>\d{2})$')

class InitialDataHandler(webapp2.RequestHandler):
    def request_month(self):
        month = self.request.params.get('month', None)
        m = _MONTH_REGEX.match(month) if month else None
        if m:
            return datetime.date(int(m.group('year'), 10), int(m.group('month'), 10), 1)
        else:
            return datetime.date.today().replace(day=1)

    @context.toplevel
    def get(self):
        month = self.request_month()
        class_types = ClassType.query().fetch_async()
        classes = Class.query(Class.month == month).fetch_async()
        attendances = Attendance.query(Attendance.klass.month == month
                                       ).fetch_async()
        students = {}
        for attendance in attendances.get_result():
            if attendance.student not in students:
                students[attendance.student] = attendance.student.get_async()
        


class InstallSampleDataHandler(webapp2.RequestHandler):
    @context.toplevel
    def get(self):
        self.response.out.write("""<!DOCTYPE html>
<html>
  <head><title>InstallingSampleData</title></head>
  <body>
    <h1>Installing sample data</h1>
    <form method="post" action="/install_sample_data">
      <p>Are you sure?</p>
      <input value="Yes" type="submit">
      <input value="No" type="button" onclick="window.location.pathname='/'">
    </form>
  </body>
</html>""")

    @context.toplevel
    def post(self):
        yield (model.Student.query().map_async(lambda key: key.delete_async(),
                                               keys_only=True),
               model.Attendance.query().map_async(lambda key: key.delete_async(),
                                                  keys_only=True),
               )

        student1, student2, student3, student4, student5, student6 = yield (
            model.Student(name='First1 Last1').put_async(),
            model.Student(name='First2 Last2').put_async(),
            model.Student(name='First3 Last3').put_async(),
            model.Student(name='First4 Last4').put_async(),
            model.Student(name='First5 Last5').put_async(),
            model.Student(name='First6 Last6').put_async(),
            )
        level1 = model.ClassType(name='Level 1', time=datetime.time(8, 20))
        level2 = model.ClassType(name='Level 2', time=datetime.time(7, 20))
        level3 = model.ClassType(name='Level 3', time=datetime.time(8, 20))
        special_ex = model.ClassType(name='Special Extensions',
                                     time=datetime.time(7, 20))
        this_month = model.Month(month=datetime.date.today())
        this_level1 = model.Class(type=level1, month=this_month)
        this_level2 = model.Class(type=level2, month=this_month)
        this_level3 = model.Class(type=level3, month=this_month)
        this_special_ex = model.Class(type=special_ex, month=this_month)
        thursdays = list(day for day in
                         calendar.Calendar().itermonthdates(
                this_month.month.year, this_month.month.month)
                         if day.weekday() == 3)
        model.Signup(klass=this_level3, student=student3, default_role='Lead',
                     presence=[model.Presence(day=thursdays[0], role='Follow'),
                               model.Presence(day=thursdays[1])]).put_async()
        model.Dropin(klass=this_level2, student=student3, day=thursdays[0],
                     role='Lead').put_async()
        model.Signup(klass=this_special_ex, student=student5,
                     default_role='Follow').put_async()
        model.Signup(klass=this_special_ex, student=student6,
                     default_role='Lead').put_async()
        model.Dropin(klass=this_level1, student=student2, role='Follow',
                     day=thursdays[1]).put_async()
        model.Dropin(klass=this_level1, student=student2, role='Follow',
                     day=thursdays[2]).put_async()
        model.Signup(klass=this_level3, student=student5,
                     default_role='Follow').put_async().get_result()

        self.response.out.write("""<!DOCTYPE html>
<html>
  <head><title>Installed Sample Data</title></head>
  <body>
    <h1>Installed sample data successfully</h1>
    <p><a href="/">Home</a>
  </body>
</html>""")


app = webapp2.WSGIApplication([('/init_data', InitialDataHandler),
                               ('/install_sample_data', InstallSampleDataHandler)],
                              debug=True)
