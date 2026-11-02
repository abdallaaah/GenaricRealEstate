from odoo import fields, models


class CashReportWizard(models.TransientModel):
    _name = 'arkzayed.cash.report.wizard'
    _description = 'Cash Report Options'

    include_draft = fields.Boolean(
        string='Count Draft cheques as expected inflows', default=False,
        help="Draft cheques are registered but not yet received. Leave off for a prudent view.")

    def action_print(self):
        self.ensure_one()
        data = {'include_draft': self.include_draft}
        return self.env.ref('arkzayed_18_realestate_development.action_report_cash').report_action(self, data=data)