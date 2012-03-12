$(function() {
    "use strict";

    // We turn this to true when we load the initial state out of local
    // storage.
    var loaded = false;
    // We update this when there's a persistent URL parameter.
    var extra_query_params = "";

    ko.bindingHandlers.href = {
        update: function(element, valueAccessor, allBindingsAccessor, viewModel) {
            var href = valueAccessor();
            if (href) href += extra_query_params;
            return ko.bindingHandlers.attr.update(
                element, function(){return {href: href};},
                allBindingsAccessor, viewModel);
        }
    };

    function ParseDay(str) {
        var match = /^(\d+)-(\d+)(?:-(\d+))?$/.exec(str);
        return {
            year: parseInt(match[1]),
            month: parseInt(match[2]),
            day: parseInt(match[3])
        };
    };
    function FormatDay(year, month, day) {
        function PadZeros(num) {
            var result = num + '';
            if (result.length < 2) {
                result = '0' + result;
            }
            return result;
        }
        var result = year + "-" + PadZeros(month);
        if (typeof day != "undefined") {
            return result + "-" + PadZeros(day);
        }
        return result;
    }
    function Today() {
        var now = new Date();
        return FormatDay(now.getFullYear(), now.getMonth() + 1, now.getDate());
    };
    function ThisMonth() {
        var now = new Date();
        return FormatDay(now.getFullYear(), now.getMonth() + 1);
    };
    function EnumerateWeekday(month, day_num) {
        var parsed = ParseDay(month);
        var date = new Date(parsed.year, parsed.month - 1, 1);
        var first_weekday = date.getDay();
        var result = [];
        date.setDate((day_num - first_weekday + 7) % 7 + 1);
        do {
            result.push(FormatDay(parsed.year, parsed.month, date.getDate()));
            date.setDate(date.getDate() + 7);
        } while (date.getMonth() + 1 == parsed.month);
        return result;
    };
    function Thursdays(month) {
        return EnumerateWeekday(month, 4);
    }

    function EditDistance(query, name) {
        query = query.toLowerCase();
        name = name.toLowerCase();
        // First row is 0 to allow matches to start anywhere.
        var next_row = $.map(name, function(){return 0;});
        next_row.push(0);
        for(var i=0;query[i++];) {
            var prev_row = next_row;
            next_row = [i];  // i deletes.
            for(var j=0;name[j++];) {
                next_row[j] = Math.min(
                    prev_row[j-1] + (query[i-1]!=name[j-1]),  // Substitution
                    next_row[j-1] + 1,  // Addition
                    prev_row[j] + 1);  // Deletion
            }
        }
        // Search the whole final row to allow matches to end anywhere.
        return Math.min.apply(null, next_row);
    }

    var displayMonths = "Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec".split(",");
    var roles = ["Lead", "Follow"];

    function StudentInClass(initial_value) {
        if (!initial_value) initial_value = {};
        var self = this;
        self.name = ko.observable(initial_value.name || "");
        self.role = ko.observable(initial_value.role || "Lead");
        self.attendance = ko.observableArray($.map(
            initial_value.attendance || [], function(present) {
                return {present: ko.observable(present)};
            }));
        self.editing = ko.observable(self.name() == "");

        self.toggleEditing = function() {
            self.editing(!self.editing());
        };
    };

    function ClassInfo(initial_value) {
        if (!initial_value) initial_value = {};
        var self = this;
        self.class_name = ko.observable(initial_value.class_name || "");
        self.month = ko.observable();
        self.possible_dates = ko.observableArray();
        self.dates = ko.observableArray();
        self.editing = ko.observable(self.class_name() == "");
        self.students = ko.observableArray($.map(
            initial_value.students || [], function(student) {
                return new StudentInClass(student);
            }));

        // When the month changes, update the dates. Initially assume
        // every Thursday has a class.
        self.month.subscribe(function(newValue) {
            self.possible_dates(Thursdays(newValue));
            self.dates(self.possible_dates().slice());  // Copy the array.
        });
        self.month(initial_value.month || ThisMonth());
        if (initial_value.dates) {
            self.dates(initial_value.dates);
        }

        self.year = ko.computed({
            read: function() {
                return ParseDay(self.month()).year;
            },
            write: function(newValue) {
                self.month(FormatDay(newValue, ParseDay(self.month()).month));
            }
        });
        self.displayMonth = ko.computed({
            read: function() {
                return displayMonths[ParseDay(self.month()).month - 1];
            },
            write: function(newValue) {
                self.month(FormatDay(ParseDay(self.month()).year, displayMonths.indexOf(newValue) + 1));
            }
        });

        self.AddStudent = function() {
            self.students.push(new StudentInClass({
                attendance: $.map(self.dates(), function() { return false })}));
        };

        // Editing
        self.Edit = function() {
            self.editing(true);
            self.month.prevValue = self.month();
            self.dates.prevValue = self.dates().slice();
        };
        self.Save = function() {
            self.editing(false);
            self.dates.sort();
            if (self.dates() != self.dates.prevValue) {
                $.each(self.students(), function(index, student) {
                    var new_attendance = [];
                    $.each(self.dates(), function(index, date) {
                        new_attendance.push({present: ko.observable(false)});
                    });
                    student.attendance(new_attendance);
                });
            }
        };
        self.Cancel = function() {
            self.month(self.month.prevValue);
            self.dates(self.dates.prevValue);
            self.editing(false);
        }
    };

    function StudentInfo(name, classes, date) {
        var self = this;
        self.name = ko.utils.unwrapObservable(name);
        self.date = ko.utils.unwrapObservable(date);
        self.classes = ko.computed(function() {
            // Array of objects containing observables {class_name, role, date's attendance}.
            var result = [];
            $.each(ko.utils.unwrapObservable(classes), function(index, klass) {
                var me_in_class = $.grep(klass.students(), function(student) {
                    return student.name() == name;
                });
                if (me_in_class.length == 0) return;  // continue.
                me_in_class = me_in_class[0];
                var date_index = klass.dates.indexOf(self.date);
                if (date_index == -1) return;  // continue.
                result.push({class_name: klass.class_name,
                             role: me_in_class.role,
                             attendance: me_in_class.attendance()[date_index].present});
            });
            return result;
        }).extend({throttle: 1});
    };

    function Data(initial_value) {
        if (!initial_value) initial_value = {};
        var self = this;
        self.subpage = ko.observable('class_list');
        self.current_class_name = ko.observable();
        self.classes = ko.observableArray($.map(
            initial_value.classes || [], function(klass) {
                return new ClassInfo(klass);
            }));
        self.checkin_query = ko.observable("");
        self.today = ko.observable(Today());

        self.current_class = ko.computed(function() {
            var current_class_name = self.current_class_name();
            return $.grep(self.classes(), function(elem) {
                return elem.class_name() == current_class_name;
            })[0];
        });

        self.todays_classes = ko.computed(function() {
            var today = self.today();
            var classes = [];
            $.each(self.classes(), function(index, klass) {
                if (klass.dates.indexOf(today) >= 0) {
                    classes.push(klass);
                }
            });
            return classes;
        });

        self.all_student_names = ko.computed(function() {
            var students = {};
            $.each(self.todays_classes(), function(index, klass) {
                $.each(klass.students(), function(index, student) {
                    students[student.name()] = student;
                });
            });
            return Object.keys(students).sort();
        });
        self.all_student_names_by_similarity = ko.computed(function() {
            var result = [];
            var checkin_query = self.checkin_query();
            $.each(self.all_student_names(), function(index, name) {
                result.push({name: name,
                             distance: EditDistance(checkin_query, name)});
            });
            return result.sort(function(a, b) {
                if (a.distance != b.distance) {
                    return a.distance - b.distance;
                }
                return a.name.localeCompare(b.name);
            });
        }).extend({throttle:100});
        self.selected_students = ko.computed(function() {
            var all_student_names_by_similarity = self.all_student_names_by_similarity();
            if (all_student_names_by_similarity.length == 0) return all_student_names_by_similarity;
            var min_distance = all_student_names_by_similarity[0].distance;
            // Assume students more than twice as far as the closest
            // student aren't what we were trying to type.
            var max_distance = min_distance * 2;
            return $.map($.grep(
                all_student_names_by_similarity, function(elem) {
                    return elem.distance <= max_distance;
                }), function(elem) {
                    return new StudentInfo(elem.name, self.todays_classes, self.today)
                });
        });

        // Constants
        self.displayMonths = displayMonths;
        self.roles = roles;

        self.AddClass = function() {
            self.classes.push(new ClassInfo());
        };

        Sammy(function() {
            this.get('#:subpage', function() {
                self.subpage(this.params['subpage']);
                self.current_class_name(this.params['class']);
                extra_query_params = "";
                if (this.params['today']) {
                    self.today(this.params['today']);
                    extra_query_params = "&today=" + this.params['today'];
                }
            });

            this.get('', function() { this.app.runRoute('get', '#class_list') });
        }).run();
    }
    var view_model = new Data(JSON.parse(localStorage.getItem('lindy_checkin.920special')));
    ko.applyBindings(view_model);

    // Save to local storage on changes:
    ko.computed(function() {
        var js = {
            classes: $.map(
                view_model.classes(), function(klass) {
                    return {
                    class_name: klass.class_name(),
                    month: klass.month(),
                    dates: klass.dates(),
                    students: $.map(
                        klass.students(), function(student) {
                            return {
                                name: student.name(),
                                role: student.role(),
                                attendance: $.map(student.attendance(), function(elem) {
                                    return elem.present(); })
                            };
                        }),
                    };
                }),
        };
        var json = JSON.stringify(js);
        console.log('Saving data: ', json);
        try {
            localStorage.setItem('lindy_checkin.920special', json);
        } catch(e) {
            console.warn("Could not save data to local storage:", e);
        }
    }).extend({throttle: 1});
});