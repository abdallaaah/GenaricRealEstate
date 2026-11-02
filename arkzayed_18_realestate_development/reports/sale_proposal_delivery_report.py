# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class SaleProposalDeliveryReport(models.Model):
    _name = 'sale.proposal.delivery.report'
    _description = 'Unit Delivery Report'
    _auto = False
    _order = 'delivery_date asc'

    sale_proposal_id = fields.Many2one('sale.proposal', string='Contract', readonly=True)
    name = fields.Char(string='Contract Reference', readonly=True)

    customer_id = fields.Many2one('res.partner', string='Customer', readonly=True)

    unit_id = fields.Many2one('real.estate.unit', string='Unit', readonly=True)
    unit_number = fields.Char(string='Unit Number', readonly=True)

    delivery_date = fields.Date(string='Delivery Date', readonly=True)
    remaining_days = fields.Integer(string='Remaining Days', readonly=True)

    remaining_days_range = fields.Selection([
        ('overdue', 'Overdue'),
        ('0_30', '0 - 30 Days'),
        ('31_60', '31 - 60 Days'),
        ('61_90', '61 - 90 Days'),
        ('91_120', '91 - 120 Days'),
        ('121_150', '121 - 150 Days'),
        ('151_180', '151 - 180 Days'),
        ('181_210', '181 - 210 Days'),
        ('211_240', '211 - 240 Days'),
        ('241_270', '241 - 270 Days'),
        ('271_300', '271 - 300 Days'),
        ('301_330', '301 - 330 Days'),
        ('331_360', '331 - 360 Days'),
        ('over_360', 'Over 360 Days'),
    ], string='Days Left (30-Day Range)', readonly=True)

    state = fields.Char(string='Contract Stage', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    sp.id AS id,
                    sp.id AS sale_proposal_id,
                    sp.name AS name,
                    sp.customer_id AS customer_id,
                    sp.unit_id AS unit_id,
                    u.system_code AS unit_number,
                    sp.delivery_date AS delivery_date,
                    (sp.delivery_date - CURRENT_DATE) AS remaining_days,
                    CASE
                        WHEN sp.delivery_date IS NULL THEN NULL
                        WHEN (sp.delivery_date - CURRENT_DATE) < 0 THEN 'overdue'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 30 THEN '0_30'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 60 THEN '31_60'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 90 THEN '61_90'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 120 THEN '91_120'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 150 THEN '121_150'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 180 THEN '151_180'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 210 THEN '181_210'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 240 THEN '211_240'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 270 THEN '241_270'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 300 THEN '271_300'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 330 THEN '301_330'
                        WHEN (sp.delivery_date - CURRENT_DATE) <= 360 THEN '331_360'
                        ELSE 'over_360'
                    END AS remaining_days_range,
                    sp.state AS state,
                    sp.company_id AS company_id
                FROM sale_proposal sp
                LEFT JOIN real_estate_unit u ON u.id = sp.unit_id
                WHERE sp.state NOT IN ('draft', 'draft_contract', 'cancelled', 'terminated')
            )
        """ % self._table)