from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ConstructionProgress(models.Model):
    _name = 'arkzayed.construction.progress'
    _description = 'Construction Progress Update'
    _order = 'date desc, id desc'

    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    percent = fields.Float(string='Progress %', required=True, digits=(16, 1))
    note = fields.Char(string='Note')
    unit_id = fields.Many2one('real.estate.unit', string='Unit', ondelete='cascade', index=True)
    building_id = fields.Many2one('real.estate.building', string='Building', ondelete='cascade', index=True)
    target = fields.Char(string='Updated', compute='_compute_target')
    user_id = fields.Many2one('res.users', string='Updated By', default=lambda self: self.env.user, readonly=True)

    @api.depends('unit_id', 'building_id')
    def _compute_target(self):
        for rec in self:
            rec.target = rec.unit_id.system_code or rec.building_id.system_code or ''

    @api.constrains('percent')
    def _check_percent(self):
        for rec in self:
            if not 0 <= rec.percent <= 100:
                raise ValidationError(_("Progress must be between 0 and 100."))

    @api.constrains('unit_id', 'building_id')
    def _check_target(self):
        for rec in self:
            if bool(rec.unit_id) == bool(rec.building_id):
                raise ValidationError(_("An update belongs to either a unit or a building."))

    def _check_can_update(self):
        user = self.env.user
        # Phase 5: this read used to name the monolith's copy of the group. Backlog #9 moved all
        # three construction groups into this module's own security.xml, so has_group() answered
        # False for everyone and a Progress Manager silently lost the bypass the group exists for.
        if self.env.su or user.has_group(
                'isky_18_realestate_developer_construction.group_progress_manager'):
            return
        for rec in self:
            engineers = (rec.unit_id.responsible_engineer_id | rec.unit_id.building_id.responsible_engineer_id
                         | rec.building_id.responsible_engineer_id)
            if user not in engineers:
                raise UserError(_(
                    "Only the responsible engineer can update the progress of %s.", rec.target or _("this record")))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if bool(vals.get('unit_id')) == bool(vals.get('building_id')):
                raise ValidationError(_("An update belongs to either a unit or a building."))
        records = super().create(vals_list)
        records._check_can_update()
        return records
