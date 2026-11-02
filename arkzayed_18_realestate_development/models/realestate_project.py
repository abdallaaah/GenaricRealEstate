from odoo import fields, models, api


class RealestateProject(models.Model):
    """specify Project details with relation of project type"""

    _name = 'realestate.project'
    _description = "Real Estate Project"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Name', required=True)
    abbreviation = fields.Char(string="Code", required=True)
    system_code = fields.Char(compute="compute_unit_system_code", store=True)
    purchase_date = fields.Date('Date')
    construction_date = fields.Date('Construction Date')
    launching_date = fields.Date('Launching Date')
    total_area = fields.Integer('Plot Area', help='Total Area With m2')
    bua = fields.Integer('BUA')
    main_owner = fields.Char('Owner')
    project_type_ids = fields.Many2many('realestate.project.type', string='Type', required=True)
    project_plan = fields.Binary(string='Plan')
    license = fields.Binary(string='License')
    permits = fields.Binary('permits')
    contracts = fields.Binary('Contracts')
    feature_ids = fields.Many2many('real.estate.feature')
    facility_ids = fields.Many2many('real.estate.facility')
    nearby_connectivity_ids = fields.Many2many('real.estate.nearby.connectivity')
    project_phases_ids = fields.Many2many('real.estate.project.phase')
    location = fields.Char(compute='compute_location')
    guide_line = fields.Binary('Guide Line')
    handbook = fields.Binary('Handbook')
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    analytic_account_id = fields.Many2one(comodel_name="account.analytic.account")

    def compute_location(self):
        for rec in self:
            rec.location = rec.name
    @api.depends('abbreviation')
    def compute_unit_system_code(self):
        for rec in self:
            rec.write({'system_code':rec.abbreviation})

    @api.model_create_multi
    def create(self, vals_list):
        project_plan = self.env['account.analytic.plan'].search([('is_project', '=', True)])
        for vals in vals_list:
            if vals.get('system_code') and not vals.get('analytic_account_id'):
                #create analytic account
                analytic_account = self.env['account.analytic.account'].create({
                    'name': vals.get('system_code'),
                    'plan_id': project_plan.id,
                })
                vals['analytic_account_id'] = analytic_account.id
        return super(RealestateProject, self).create(vals_list)


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


        result = super(RealestateProject, self).write(vals)
