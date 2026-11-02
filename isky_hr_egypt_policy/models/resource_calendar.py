# -*-	coding:	utf-8	-*-
from odoo import models, fields, api, _
from datetimerange import DateTimeRange
from datetime import datetime, time
from pytz import utc

WEEK_DAYS = [('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'), ('3', 'Thursday'),
             ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday')]


class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    is_broken = fields.Boolean(string='Is Broken')

    @api.onchange('hour_from', 'hour_to')
    def _onchange_hours(self):
        if not self.is_broken:
            super(ResourceCalendarAttendance, self)._onchange_hours()


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    def get_work_days_with_hours_dict(self, date_from, date_to, calendar=False, shift=False):
        day_from = datetime.combine(fields.Date.from_string(date_from), time.min)
        day_to = datetime.combine(fields.Date.from_string(date_to), time.max)

        # naive datetimes are made explicit in UTC
        if not day_from.tzinfo:
            day_from = day_from.replace(tzinfo=utc)
        if not day_to.tzinfo:
            day_to = day_to.replace(tzinfo=utc)

        calendar = calendar if calendar else self

        # get weekends per shift
        weekends_list = []
        if shift:
            for weekend in shift.weekend_days_ids:
                weekends_list.append(dict(WEEK_DAYS)[weekend.week_of_day])

        # get work dates from employee calendar
        work_days_dict = {}
        company = self.env.user.company_id
        resource_calendar = company.resource_calendar_id

        # intervals = resource_calendar._work_intervals(day_from, day_to)
        intervals = resource_calendar._work_intervals_batch(day_from, day_to)
        work_intervals = [(start, stop) for start, stop, meta in intervals[False]]

        for start, stop in work_intervals:
            if start.date().strftime("%A") not in weekends_list:
                if start.date() == stop.date():
                    if start.date() in work_days_dict:
                        work_days_dict[start.date()]['periods'].append((start, stop))
                    else:
                        work_days_dict[start.date()] = {
                            'periods': [(start, stop)]
                        }
                else:
                    # work schedule contains break of two days
                    part1_start = start
                    part1_end = datetime.combine(start.date(), time.max)
                    if part1_start.date() in work_days_dict:
                        work_days_dict[part1_start.date()]['periods'].append((part1_start, part1_end))
                    else:
                        work_days_dict[part1_start.date()] = {
                            'work_periods': [(part1_start, part1_end)]
                        }

                    part2_start = datetime.combine(stop.date(), time.min)
                    part2_end = stop
                    if part2_start.date() in work_days_dict:
                        work_days_dict[part2_start.date()]['work_periods'].append((part2_start, part2_end))
                    else:
                        work_days_dict[part2_start.date()] = {
                            'work_periods': [(part2_start, part2_end)]
                        }
        return work_days_dict

    # get intersection hours between two ranges
    def get_datetime_period_intersection_hours(self, range1, range2):
        range1_start = range1[0]
        range1_end = range1[1]
        range2_start = range2[0]
        range2_end = range2[1]
        time_range1 = DateTimeRange(range1_start, range1_end)
        time_range2 = DateTimeRange(range2_start, range2_end)
        if time_range1.is_intersection(time_range2):
            d2 = min(range2_end, range1_end)
            d1 = max(range2_start, range1_start)
            delta = d2 - d1
            seconds = delta.seconds if delta.seconds >= 0 else 0
            days = delta.days if delta.days >= 0 else 0
            total_hours = ((seconds / (60.0 * 60.0)) + (days * 24))
            return {'range': (d1, d2), 'hours': total_hours}
        else:
            return {'range': False, 'hours': 0.0}

    # check day is working or not
    def check_working_day(self, date_from, date_to, shift=False):
        is_working_day = False
        work_days_with_hours_dict = self.get_work_days_with_hours_dict(date_from, date_to, shift=shift)
        if (date_from.date() == date_to.date()) and date_from.date() in work_days_with_hours_dict:
            is_working_day = True
        return is_working_day

    # check day is weekend or not
    def check_day_is_weekend(self, day, shift=False):
        is_weekend = True

        # get weekends per shift
        weekends_list = []
        if shift:
            for weekend in shift.weekend_days_ids:
                weekends_list.append(dict(WEEK_DAYS)[weekend.week_of_day])

        for attendance_day in self.attendance_ids:
            if day.strftime("%A") == dict(WEEK_DAYS)[attendance_day.dayofweek] and not day.strftime(
                    "%A") in weekends_list:
                is_weekend = False
        return is_weekend

    # check day is global leave or not
    def check_day_is_global_leave(self, day):
        is_global_leave = False
        for record in self:
            for global_leave in record.global_leave_ids:
                if global_leave.date_from.date() <= day.date() <= global_leave.date_to.date():
                    is_global_leave = True
        return is_global_leave
