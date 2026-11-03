# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.addons.isky_18_realestate_developer_unit_inventory.models.selections import unit_type_selection, residential_type_selection, referred_by_selection, public_area_selection, \
    retail_type_selection, entertainment_type_selection, industrial_type_selection

unit_type_selection = unit_type_selection.copy()
referred_by_selection = referred_by_selection.copy()
unit_type_selection.remove(('gate', 'Gate'))
referred_by_selection.remove(('management', 'Management'))
referred_by_selection.remove(('direct', 'Direct'))


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # acquisition_date = fields.Date()
    referred_by = fields.Selection(selection=referred_by_selection, string="Referred By")
    partner_id = fields.Many2one('res.partner')
    employee_id = fields.Many2one('hr.employee')
    broker_id = fields.Many2one('res.partner', domain="[('is_broker','=',True)]")
    ambassador_id = fields.Many2one('res.partner', string="Ambassador", domain="[('is_ambassador','=',True)]")
    other = fields.Char()
    what_for = fields.Selection(string="Lead Type", selection=[('lease', 'Lease'), ('sales', 'Sales')] , default='sales')
    currency_id = fields.Many2one(comodel_name="res.currency")

    unit_type = fields.Selection(selection=unit_type_selection, string="Unit Type",default='residential')
    public_area = fields.Selection(selection=public_area_selection, string='Public Area')
    retail_type = fields.Selection(selection=retail_type_selection, string='Retail Type')
    office_type_id = fields.Many2one('office.type', string='Office Type')
    residential_type = fields.Selection(selection=residential_type_selection, string='Residential Type')
    entertainment_type = fields.Selection(selection=entertainment_type_selection, string='Entertainment Type')
    industrial_type = fields.Selection(selection=industrial_type_selection, string='Industrial Type')

    has_contract = fields.Boolean(string='Has Contract', compute='_compute_has_contract')

    @api.depends('broker_id')
    def _compute_has_contract(self):
        self.has_contract = False

        broker_ids = self.filtered('broker_id').mapped('broker_id.id')

        if broker_ids:
            contracts = self.env['broker.contract'].search([
                ('broker_company', 'in', broker_ids)
            ])

            brokers_with_contracts = set(contracts.mapped('broker_company.id'))

            for lead in self:
                if lead.broker_id.id in brokers_with_contracts:
                    lead.has_contract = True


class Team(models.Model):
    _inherit = 'crm.team'

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
