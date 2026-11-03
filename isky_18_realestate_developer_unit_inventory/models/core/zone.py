from odoo import fields, models, api


class Zone(models.Model):
    _name = 'zone'
    _description = "Real Estate Zone"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'system_code'

    name = fields.Char()
    abbreviation = fields.Char(string="Code")
    system_code = fields.Char(compute="compute_unit_system_code", store=True)
    parent_id = fields.Many2one('realestate.project', string="Project", required=1)
    location = fields.Char(compute='compute_zone_location')
    project_phases_ids = fields.Many2many('real.estate.project.phase')
    project_type_ids = fields.Many2many('realestate.project.type', string='Type', required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)


    def compute_zone_location(self):
        for rec in self:
            name = ''
            if rec.name:
                name += rec.name
            if rec.parent_id and rec.parent_id.location:
                name += ',' + rec.parent_id.location
            rec.location = name

    @api.depends('abbreviation')
    def compute_unit_system_code(self):
        for rec in self:
            rec.system_code = rec.abbreviation
