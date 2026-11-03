from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

# real.estate.unit / real.estate.building / realestate.project's core definitions moved to
# isky_18_realestate_developer_unit_inventory (Level 0). The auto-create-analytic-account logic
# inside their create()/write() overrides depends on account.analytic.plan's is_unit/is_building/
# is_project flags, which live in isky_18_realestate_developer_accounting (Level 1). Level 0 can't
# depend on Level 1, so this logic stays here (an extension of the Level 0 models) for now - it
# moves wherever Accounting's own restructuring phase puts it later.
#
# NOTE: write() on RealEstateBuilding and RealestateProject below does not return the result of
# super().write(vals) - that's a pre-existing bug carried over unchanged from the original code,
# not something introduced by this move. Flagged, not fixed, since fixing it wasn't part of this task.


class RealEstateUnit(models.Model):
    _inherit = 'real.estate.unit'

    @api.model_create_multi
    def create(self, vals_list):
        unit_plan = self.env['account.analytic.plan'].search([('is_unit', '=', True)], limit=1)
        for vals in vals_list:
            if vals.get('system_code') and not vals.get('analytic_account_id'):
                if not unit_plan:
                    raise ValidationError(
                        _("No analytic plan found with 'is_unit' flag. Please configure an analytic plan for units."))

                analytic_account = self.env['account.analytic.account'].create({
                    'name': vals.get('system_code'),
                    'plan_id': unit_plan.id,
                })
                vals['analytic_account_id'] = analytic_account.id

        return super(RealEstateUnit, self).create(vals_list)

    def write(self, vals):
        unit_plan = self.env['account.analytic.plan'].search([('is_unit', '=', True)], limit=1)

        for rec in self:
            system_code = vals.get('system_code')
            if system_code:
                if rec.analytic_account_id:
                    rec.analytic_account_id.write({'name': system_code})
                else:
                    if not unit_plan:
                        raise ValidationError(
                            _("No analytic plan found with 'is_unit' flag. Please configure an analytic plan for units."))

                    analytic_account = self.env['account.analytic.account'].create({
                        'name': system_code,
                        'plan_id': unit_plan.id,
                    })
                    vals['analytic_account_id'] = analytic_account.id

        return super(RealEstateUnit, self).write(vals)


class RealEstateBuilding(models.Model):
    _inherit = 'real.estate.building'

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
            if system_code:
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


class RealestateProject(models.Model):
    _inherit = 'realestate.project'

    @api.model_create_multi
    def create(self, vals_list):
        project_plan = self.env['account.analytic.plan'].search([('is_project', '=', True)])
        for vals in vals_list:
            if vals.get('system_code') and not vals.get('analytic_account_id'):
                # create analytic account
                analytic_account = self.env['account.analytic.account'].create({
                    'name': vals.get('system_code'),
                    'plan_id': project_plan.id,
                })
                vals['analytic_account_id'] = analytic_account.id
        return super(RealestateProject, self).create(vals_list)

    def write(self, vals):
        for rec in self:
            system_code = vals.get('system_code')
            if system_code:
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
