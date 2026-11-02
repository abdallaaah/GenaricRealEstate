# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools


class MeetingReport(models.Model):
    _name = "crm.meeting.report"
    _description = "CRM Meeting Analysis"
    _auto = False
    _rec_name = 'user_id'
    _order = 'user_id, date_deadline desc'

    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    date_deadline = fields.Date('Meeting Date', readonly=True)
    meeting_count = fields.Integer('Total Meetings', readonly=True)
    meeting_done_count = fields.Integer('Meetings Done', readonly=True)
    meeting_canceled_count = fields.Integer('Meetings Canceled', readonly=True)

    # Date fields for grouping
    year = fields.Char('Year', readonly=True)
    quarter = fields.Char('Quarter', readonly=True)
    month = fields.Char('Month', readonly=True)
    week = fields.Char('Week', readonly=True)
    day = fields.Char('Day', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        meeting = self.env.ref('mail.mail_activity_data_meeting').id
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER() as id,
                    act.user_id as user_id,
                    act.date_deadline as date_deadline,
                    COUNT(act.id) as meeting_count,
                    SUM(CASE WHEN act.active = false AND act.date_done IS NOT NULL THEN 1 ELSE 0 END) as meeting_done_count,
                    SUM(CASE WHEN act.active = false AND act.date_done IS NULL THEN 1 ELSE 0 END) as meeting_canceled_count,
                    EXTRACT(YEAR FROM act.date_deadline)::varchar as year,
                    CONCAT('Q', EXTRACT(QUARTER FROM act.date_deadline)::varchar) as quarter,
                    TO_CHAR(act.date_deadline, 'Month') as month,
                    TO_CHAR(act.date_deadline, 'WW') as week,
                    TO_CHAR(act.date_deadline, 'Day') as day
                FROM
                    mail_activity act
                WHERE
                    act.activity_type_id IN (
                        SELECT id FROM mail_activity_type WHERE id = %s
                    )
                GROUP BY
                    act.user_id,
                    act.date_deadline
            )
        """ % (self._table, meeting))