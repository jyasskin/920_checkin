from google.appengine.ext import db
from google.appengine.ext import ndb
import calendar
import datetime
import json
import logging
import model
import re
import webapp2

_MONTH_REGEX = re.compile('^(?P<year>\d{4})-(?P<month>\d{2})$')


def to_json(obj):
    return obj.to_json()


@ndb.transactional
def initialize_classes(month, class_types):
    db_month = model.Month.get_or_insert_async(month.key.id())
    existing_classes = model.Class.query(ancestor=month.key
                                         ).fetch_async()

    # Compute new classes while we're trying to fetch any
    # existing classes.
    new_classes = []
    thursdays = month.Thursdays()
    for class_type in class_types:
        new_classes.append(model.Class(parent=month.key,
                                       type=class_type.key,
                                       days=thursdays))

    # Ensure month object exists. Unlike put()s, this doesn't get
    # completed at the end of the transaction.
    db_month.get_result()

    if existing_classes.get_result():
        # If there are already classes in this month,
        # don't insert new ones.
        return existing_classes.get_result()

    ndb.put_multi_async(new_classes)
    return new_classes


class InitialDataHandler(webapp2.RequestHandler):
    def request_month(self):
        month = self.request.params.get('month', None)
        m = _MONTH_REGEX.match(month) if month else None
        if m:
            return datetime.date(int(m.group('year'), 10), int(m.group('month'), 10), 1)
        else:
            return datetime.date.today().replace(day=1)

    @ndb.toplevel
    def get(self):
        month = model.Month.fromdate(self.request_month())
        month_data = ndb.Query(ancestor=month.key).fetch_async()
        students = model.Student.query().fetch_async()
        class_types = model.ClassType.query().fetch_async()

        json_data = dict(month=month,
                         students=students.get_result(),
                         class_types=class_types.get_result(),
                         classes=[], signups=[])

        for elem in month_data.get_result():
            if isinstance(elem, model.Class):
                json_data['classes'].append(elem)
            elif isinstance(elem, model.Signup):
                json_data['signups'].append(elem)
            elif isinstance(elem, model.Month):
                pass  # The month is already included.
            else:
                logging.error('Unexpected data type: {0}({1})'.format(
                        type(elem), str(elem)))

        if not json_data['classes']:
            # No classes for this month yet; initialize them from class_types.
            try:
                json_data['classes'] = initialize_classes(
                    month, class_types.get_result())
            except db.TransactionFailedError:
                logging.error('Class insertion failed multiple times, '
                              'assuming classes were inserted by another task.')
                json_data['classes'] = model.Class.query(ancestor=month.key
                                                         ).fetch()
        self.response.content_type = 'application/json'
        indent, separators = None, (',', ':')
        if self.request.params.get('prettyprint'):
            indent, separators = 2, (', ', ': ')
        json.dump(json_data, self.response, default=to_json,
                  indent=indent, separators=separators)


class InstallSampleDataHandler(webapp2.RequestHandler):
    @ndb.toplevel
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

    @ndb.toplevel
    def post(self):
        yield (model.Student.query().map_async(
                lambda key: key.delete_async(), keys_only=True),
               model.Signup.query().map_async(
                lambda key: key.delete_async(), keys_only=True),
               model.Class.query().map_async(
                lambda key: key.delete_async(), keys_only=True),
               model.ClassType.query().map_async(
                lambda key: key.delete_async(), keys_only=True),
               )

        level1 = model.ClassType(name='Level 1', time=datetime.time(20, 20))
        level2 = model.ClassType(name='Level 2', time=datetime.time(19, 20))
        level3 = model.ClassType(name='Level 3', time=datetime.time(20, 20))
        special_ex = model.ClassType(name='Special Extensions',
                                     time=datetime.time(19, 20))

        (student1, student2, student3, student4, student5, student6,
         level1_key, level2_key, level3_key, special_ex_key) = yield (
            model.Student(name='First1 Last1').put_async(),
            model.Student(name='First2 Last2').put_async(),
            model.Student(name='First3 Last3').put_async(),
            model.Student(name='First4 Last4').put_async(),
            model.Student(name='First5 Last5').put_async(),
            model.Student(name='First6 Last6').put_async(),
            level1.put_async(), level2.put_async(),
            level3.put_async(), special_ex.put_async(),
            )
        this_month = model.Month.fromdate(datetime.date.today().replace(day=1))
        (this_level1, this_level2, this_level3, this_special_ex
         ) = initialize_classes(
            this_month, [level1, level2, level3, special_ex])
        thursdays = this_month.Thursdays()
        model.MonthSignup(parent=this_month.key,
                          klass=this_level3.key, student=student3, default_role='Lead',
                          presence=[model.Presence(day=thursdays[0], role='Follow'),
                                    model.Presence(day=thursdays[1])]).put_async()
        model.DaySignup(parent=this_month.key,
                        klass=this_level2.key, student=student3, day=thursdays[0],
                        role='Lead').put_async()
        model.MonthSignup(parent=this_month.key,
                          klass=this_special_ex.key, student=student5,
                          default_role='Follow').put_async()
        model.MonthSignup(parent=this_month.key,
                          klass=this_special_ex.key, student=student6,
                          default_role='Lead').put_async()
        model.DaySignup(parent=this_month.key,
                        klass=this_level1.key, student=student2, role='Follow',
                        day=thursdays[1]).put_async()
        model.DaySignup(parent=this_month.key,
                        klass=this_level1.key, student=student2, role='Follow',
                        day=thursdays[2]).put_async()
        model.MonthSignup(parent=this_month.key,
                          klass=this_level3.key, student=student5,
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
