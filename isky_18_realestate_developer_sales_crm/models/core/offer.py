from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import base64
import io
from PyPDF2 import PdfMerger
from PIL import Image


class OfferOffer(models.Model):
    _name = 'offer.offer'
    _rec_name = 'unit_id'
    _description = 'Real Estate Offer'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    unit_id = fields.Many2one('real.estate.unit', string='Unit', required=True,
                              tracking=True, domain=[('unit_status', '=', 'available')])
    system_code = fields.Char(related='unit_id.system_code', string='System Code',
                              store=True, readonly=True)

    # Installment Plan Fields
    installment_plan_id = fields.Many2one('down.payment.increase', string="Installment Plan")
    installemnt_years = fields.Integer(string="Number of Installment Years",
                                       tracking=True)
    down_payment = fields.Float(string="Down Payment (%)", tracking=True)
    down_payment_date = fields.Date(string="Down Payment Date", tracking=True)
    maintenance_percentage = fields.Float(string="Maintenance Percentage")

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        """Populate fields from selected unit"""
        if self.unit_id:
            self.installment_plan_id = self.unit_id.installment_plan_id
            self.installemnt_years = self.unit_id.installemnt_years
            self.down_payment = self.unit_id.down_payment
            self.down_payment_date = self.unit_id.down_payment_date
            self.maintenance_percentage = self.unit_id.maintenance_percentage

    def _add_document_to_merger(self, merger, document_data, document_name):
        if not document_data:
            return

        try:
            raw_data = base64.b64decode(document_data)
            stream = io.BytesIO(raw_data)

            if raw_data.startswith(b'%PDF-'):
                try:
                    pdf_stream = io.BytesIO(raw_data)
                    merger.append(pdf_stream)
                    return
                except Exception:
                    pass

            try:
                stream.seek(0)
                image = Image.open(stream)
                
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')
                
                img_pdf_stream = io.BytesIO()
                image.save(img_pdf_stream, 'PDF', resolution=100.0)
                img_pdf_stream.seek(0)
                merger.append(img_pdf_stream)
            except Exception as img_e:
                raise ValidationError(_("Could not process '%s' as PDF or Image. Error: %s") % (document_name, str(img_e)))

        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            raise ValidationError(_("Error processing '%s': %s") % (document_name, str(e)))

    def action_print_combined_documents(self):
        """Combine building plan (PDF), unit plan (PNG), and payment plan (PNG) into one PDF"""
        self.ensure_one()

        if not self.unit_id:
            raise ValidationError(_("No unit selected for this offer."))

        unit = self.unit_id

        # Check if all required documents exist
        if not unit.building_id or not unit.building_id.building_plan:
            raise ValidationError(_("Building plan is missing for building: %s") %
                                  (unit.building_id.name if unit.building_id else 'Unknown'))
        if not unit.unit_plan:
            raise ValidationError(_("Unit plan is missing"))
        if not unit.payment_plan:
            raise ValidationError(_("Payment plan is missing"))

        try:
            # Initialize PDF merger
            merger = PdfMerger()

            # 1. Add building plan
            self._add_document_to_merger(merger, unit.building_id.building_plan, _("Building Plan"))

            # 2. Add unit plan
            self._add_document_to_merger(merger, unit.unit_plan, _("Unit Plan"))

            # 3. Add payment plan
            self._add_document_to_merger(merger, unit.payment_plan, _("Payment Plan"))

            # 4. Write merged PDF to output stream
            output_stream = io.BytesIO()
            merger.write(output_stream)
            merger.close()
            output_stream.seek(0)

            # 5. Create attachment
            combined_pdf = base64.b64encode(output_stream.read())
            filename = f"{unit.system_code}_combined_documents.pdf"

            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': combined_pdf,
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })

            # 6. Return action to download/view the PDF
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }

        except Exception as e:
            raise ValidationError(_("Error combining documents: %s") % str(e))
