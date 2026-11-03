from odoo import api, fields, models


class AttachmentType(models.Model):
    _name = 'attachment.type'

    name = fields.Char()



class AttachmentTypeLine(models.Model):
    _name = 'attachment.type.line'

    attachment_type_id = fields.Many2one('attachment.type')
    expiry_date = fields.Date()
    attachment = fields.Binary()

    hr_employee_id = fields.Many2one('hr.employee')
