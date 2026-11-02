from odoo import fields, models, api


class QualifiedStageWizard(models.TransientModel):
    _name = 'qualified.stage.wizard'
    _description = 'Wizard for Qualified Stage Fields'

    lead_id = fields.Many2one('crm.lead', string='Lead')

    priority = fields.Selection(
        selection=[('', ''), ('0', 'Very Low'), ('1', 'Not Interested'), ('2', 'Hesitate'), ('3', 'Hot')],
        string='Rating')
    unit_type = fields.Selection([
        ('administrative', 'Administrative'),
        ('apartment', 'Apartment'),
        ('bank', 'Bank'),
        ('beach_house', 'Beach House'),
        ('bridge_villa', 'Bridge Villa'),
        ('building', 'Building'),
        ('cabanas', 'Cabanas'),
        ('cabin', 'Cabin'),
        ('cafe', 'Cafe'),
        ('chalet', 'Chalet'),
        ('cinema', 'Cinema'),
        ('clinic', 'Clinic'),
        ('clinic_center', 'Clinic Center'),
        ('condo', 'Condo'),
        ('corner_loft', 'Corner Loft'),
        ('duplex', 'Duplex'),
        ('factory', 'Factory'),
        ('family_house', 'Family House'),
        ('farm', 'Farm'),
        ('food_beverages', 'Food & Beverages'),
        ('garden_villa', 'Garden Villa'),
        ('gas_station', 'Gas Station'),
        ('ground_apartment', 'Ground Apartment'),
        ('ground_chalet', 'Ground Chalet'),
        ('ground_floor', 'Ground Floor'),
        ('ground_villa', 'Ground Villa'),
        ('gym', 'Gym'),
        ('hospital', 'Hospital'),
        ('hotel_apartment', 'Hotel Apartment'),
        ('house', 'House'),
        ('house_boat', 'House Boat'),
        ('hyper_market', 'Hyper Market'),
        ('i_apartment', 'I-Apartment'),
        ('i_villa', 'I-Villa'),
        ('industrial', 'Industrial'),
        ('junior_chalet', 'Junior Chalet'),
        ('junior_loft', 'Junior Loft'),
        ('land', 'Land'),
        ('loft', 'Loft'),
        ('mall', 'Mall'),
        ('medical_center', 'Medical Center'),
        ('medical_offices', 'Medical Offices'),
        ('millennial_apartment', 'Millennial Apartment'),
        ('office_space', 'Office Space'),
        ('one_story_villa', 'One Story Villa'),
        ('palace', 'Palace'),
        ('panoramic_loft', 'Panoramic Loft'),
        ('park_villa', 'Park Villa'),
        ('parking', 'Parking'),
        ('penthouse', 'Penthouse'),
        ('pharmacy', 'Pharmacy'),
        ('project', 'Project'),
        ('public_area', 'Public Area'),
        ('quadro_villa', 'Quadro Villa'),
        ('quatro', 'Quatro'),
        ('residential', 'Residential'),
        ('restaurant', 'Restaurant'),
        ('retail', 'Retail'),
        ('school', 'School'),
        ('senior_chalet', 'Senior Chalet'),
        ('senior_loft', 'Senior Loft'),
        ('serviced_apartment', 'Serviced Apartment'),
        ('shop', 'Shop'),
        ('show_room', 'Show Room'),
        ('sky_loft', 'Sky Loft'),
        ('sky_villa', 'Sky Villa'),
        ('stand_alone_villa', 'Stand Alone Villa'),
        ('storage', 'Storage'),
        ('store', 'Store'),
        ('studio', 'Studio'),
        ('sun_roof', 'Sun Roof'),
        ('s_villa', 'S-Villa'),
        ('town_house', 'Town House'),
        ('training_course', 'Training Course'),
        ('trio', 'Trio'),
        ('triplex', 'Triplex'),
        ('twin_house', 'Twin House'),
        ('twin_villa', 'Twin Villa'),
        ('typical_apartment', 'Typical Apartment'),
        ('typical_chalet', 'Typical Chalet'),
        ('villa', 'Villa'),
        ('warehouse', 'Warehouse')
    ], string='Unit Type')
    finish_type = fields.Selection([
        ('finished', 'Finished'),
        ('semi_finished', 'Semi-Finished'),
        ('core_shell', 'Core and Shell')
    ])

    min_area = fields.Float(string='Minimum Area')
    max_area = fields.Float(string='Maximum Area')
    min_price = fields.Float(string='Minimum Price')
    max_price = fields.Float(string='Maximum Price')
    qualified_comment = fields.Text()

    def action_confirm(self):
        self.ensure_one()
        if self.lead_id:
            lead_stage_id = self.env.ref('arkzayed_18_realestate_broker.stage_qualified')
            if self._context.get('limited_budget'):
                lead_stage_id = self.env.ref('arkzayed_18_realestate_broker.stage_qualified_limited_budget')
            values = {
                'priority': self.priority,
                'unit_type': self.unit_type,
                'finish_type': self.finish_type,
                'min_area': self.min_area,
                'max_area': self.max_area,
                'min_price': self.min_price,
                'max_price': self.max_price,
                'qualified_comment': self.qualified_comment,
                'lead_stage_id': lead_stage_id.id
            }
            self.lead_id.write(values)
        return {'type': 'ir.actions.act_window_close'}
