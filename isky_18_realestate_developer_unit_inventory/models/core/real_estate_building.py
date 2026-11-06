from odoo import models, fields, api


class RealEstateBuilding(models.Model):
    _name = 'real.estate.building'
    _description = 'Real Estate Building'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'realestate.hierarchy.node.mixin']
    _rec_name = 'system_code'

    name = fields.Char(string='Building Name', required=True)
    abbreviation = fields.Char(string="Code",required=True)
    system_code = fields.Char(compute="compute_unit_system_code", store=True)
    main_gates = fields.Integer(string='Main Gates')
    parking_gates = fields.Integer(string='Parking Gates')
    parent_source_id = fields.Reference([
        ('zone', 'Zone'),
        ('realestate.project', 'Project')
    ], string='Parent reference', required=1)
    location = fields.Char(compute='compute_building_location')
    project_phases_ids = fields.Many2many('real.estate.project.phase')
    project_type_ids = fields.Many2many('realestate.project.type', string='Type', required=True)
    project_id = fields.Many2one('realestate.project', compute="_compute_project_id", store=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    bua = fields.Float(string="BUA",help="built up area")
    analytic_account_id = fields.Many2one(comodel_name="account.analytic.account")

    building_plan = fields.Binary()

    def compute_building_location(self):
        for rec in self:
            name = ''
            if rec.name:
                name += rec.name
            if rec.parent_source_id and rec.parent_source_id.location:
                name += ',' + rec.parent_source_id.location
            rec.location = name

