from odoo import models, fields, api


class RealEstateBuilding(models.Model):
    _name = 'real.estate.building'
    _description = 'Real Estate Building'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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

    @api.depends('parent_source_id')
    def _compute_project_id(self):
        for rec in self:
            source_id = rec.parent_source_id
            print('source_id',source_id)

            if source_id and source_id._name == 'realestate.project':
                rec.project_id = source_id.id
            if source_id and source_id._name == 'zone':
                rec.project_id = source_id.parent_id.id
            elif source_id:
                rec.project_id = False
                while source_id:
                    if source_id._name == 'realestate.project':
                        rec.project_id = source_id.id
                        break
                    project_id = source_id.project_id
                    if project_id:
                        rec.project_id = project_id.id
                        break
                    source_id = source_id.parent_source_id
            else:
                rec.project_id = False


    def compute_building_location(self):
        for rec in self:
            name = ''
            if rec.name:
                name += rec.name
            if rec.parent_source_id and rec.parent_source_id.location:
                name += ',' + rec.parent_source_id.location
            rec.location = name

    @api.depends('abbreviation', 'parent_source_id')
    def compute_unit_system_code(self):
        for rec in self:
            parts = []
            if rec.parent_source_id and rec.parent_source_id._name != 'realestate.project' and rec.parent_source_id.system_code:
                parts.append(rec.parent_source_id.system_code)
            if rec.abbreviation:
                parts.append(rec.abbreviation)
            rec.system_code = "-".join(parts)

    @api.model_create_multi
    def create(self, vals_list):
        building_plan = self.env['account.analytic.plan'].search([('is_building', '=', True)])
        for vals in vals_list:
            if vals.get('system_code') and not vals.get('analytic_account_id'):
                # create analytic account
                analytic_account = self.env['account.analytic.account'].create({
                    'name': vals.get('system_code'),
                    'plan_id': building_plan.id,
                })
                vals['analytic_account_id'] = analytic_account.id
        return super(RealEstateBuilding, self).create(vals_list)

    def write(self, vals):
        for rec in self:
            system_code = vals.get('system_code')
            if system_code :
                if rec.analytic_account_id:
                    rec.analytic_account_id.write({'name': system_code})

                else:
                    project_plan = self.env['account.analytic.plan'].search([('is_project', '=', True)])
                    analytic_account = self.env['account.analytic.account'].create({
                        'name': system_code,
                        'plan_id': project_plan.id,
                    })
                    vals['analytic_account_id'] = analytic_account.id


        result = super(RealEstateBuilding, self).write(vals)