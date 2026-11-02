from odoo import api, fields, models, tools

CONTRACT_EXCLUDED = ('draft', 'cancelled', 'terminated')
RESERVATION_EXCLUDED = ('draft', 'cancelled', 'expired')

# (field, header) in the order of the inventory template; the list views and the Excel export both use these
UNIT_PART = [('unit_code', 'Unit Code'), ('project_name', 'Boulevard'), ('building_name', 'Building #'), ('unit_subtype', 'Unit Type'),
             ('floor_name', 'Floor')]
PRICE_PART = [('unit_price', 'Unit Price'), ('price_per_meter', 'PRICE/METER'), ('unit_status', 'Status')]
DEAL_PART = [('reservation_date', 'Reservation Date'), ('contract_date', 'Contract Date'), ('sold_price', 'Sold Price'),
             ('payment_plan', 'Payment Plan'), ('discount_percentage', 'Discount %'), ('down_payment', 'Downpayment'),
             ('dp_percentage', 'DP %'), ('maintenance', 'Maintenance'), ('maintenance_percentage', 'Maint. %'),
             ('contract_type', 'Contract Type'), ('payment_type', 'Payment Type'),
             ('sales', 'Sales'), ('sales_manager', 'Sales Manager'), ('sales_director', 'Sales Director'), ('source', 'Source'),
             ('brokerage', 'Brokerage'), ('agent_name', 'Agent Name'),
             ('client_name', 'Client Name'), ('client_arabic_name', 'Arabic Client Name'), ('address', 'Address'),
             ('national_id', 'ID Number/Passport No'), ('mobile', 'Mobile'), ('email', 'Email'), ('nationality', 'Nationality'),
             ('reservation_serial', 'Reservation Serial'), ('contract_ref', 'Contract'), ('contract_status', 'Contract Status'),
             ('commission_paid', 'Commission Paid'), ('quarter', 'Quarter'), ('year', 'Year'), ('month', 'Month'), ('m2_price', 'M2 Price')]
RESIDENTIAL_AREAS = [('net_area', 'NET AREA'), ('gross_area', 'GROSS AREA'), ('garden_area', 'Garden'), ('land_area', 'Land')]
ADMIN_RETAIL_AREAS = [('indoor_net_area', 'INDOOR NET AREA'), ('indoor_gross_area', 'INDOOR GROSS AREA'), ('gross_area', 'TOTAL GROSS AREA')]
COLUMNS = {
    'residential': UNIT_PART + RESIDENTIAL_AREAS + PRICE_PART + DEAL_PART,
    'admin_retail': UNIT_PART + ADMIN_RETAIL_AREAS + PRICE_PART + DEAL_PART,
}
# Medical has few sold units: only the columns that have data
MEDICAL_EMPTY = {'contract_date', 'payment_plan', 'discount_percentage', 'down_payment', 'dp_percentage', 'contract_type', 'sales_director',
                 'brokerage', 'agent_name', 'client_arabic_name', 'email', 'nationality', 'contract_ref', 'contract_status',
                 'commission_paid', 'month'}
COLUMNS['medical'] = [c for c in UNIT_PART + ADMIN_RETAIL_AREAS + PRICE_PART + [('block_reason', 'Block Reason')] + DEAL_PART
                      if c[0] not in MEDICAL_EMPTY]
SHEET_NAME = {'residential': 'RESIDENTIAL', 'admin_retail': 'Retail & Admin', 'medical': 'Medical'}
KIND_DOMAIN = {'residential': [('unit_type', '=', 'residential')],
               'admin_retail': [('unit_type', 'in', ['office', 'retail'])],
               'medical': [('unit_type', '=', 'medical')]}


class EngineerInventory(models.Model):
    """One row per unit with its current contract (or reservation when there is no contract yet)."""
    _name = 'ark.engineer.inventory'
    _description = 'Engineer Menu unit inventory'
    _auto = False
    _rec_name = 'unit_code'
    _order = 'project_name, building_name, unit_code'

    unit_id = fields.Many2one('real.estate.unit', string='Unit', readonly=True)
    unit_code = fields.Char('Unit Code', readonly=True)
    unit_type = fields.Selection(lambda self: self.env['real.estate.unit']._fields['unit_type'].selection, 'Type', readonly=True)
    unit_subtype = fields.Char('Unit Type', readonly=True)
    project_id = fields.Many2one('realestate.project', 'Project', readonly=True)
    project_name = fields.Char('Boulevard', readonly=True)
    building_id = fields.Many2one('real.estate.building', 'Building', readonly=True)
    building_name = fields.Char('Building #', readonly=True)
    floor_id = fields.Many2one('floor', 'Floor Record', readonly=True)
    floor_name = fields.Char('Floor', readonly=True)
    net_area = fields.Float('Net Area', readonly=True)
    gross_area = fields.Float('Gross Area', readonly=True)
    indoor_net_area = fields.Float('Indoor Net Area', readonly=True)
    indoor_gross_area = fields.Float('Indoor Gross Area', readonly=True)
    outdoor_gross_area = fields.Float('Outdoor Gross Area', readonly=True)
    garden_area = fields.Float('Garden', readonly=True)
    land_area = fields.Float('Land', readonly=True)
    unit_price = fields.Float('Unit Price', readonly=True)
    price_per_meter = fields.Float('Price / Meter', readonly=True)
    unit_status = fields.Selection(lambda self: self.env['real.estate.unit']._fields['unit_status'].selection, 'Status', readonly=True)
    block_reason = fields.Char('Block Reason', readonly=True)
    reservation_date = fields.Date('Reservation Date', readonly=True)
    reservation_serial = fields.Char('Reservation Serial', readonly=True)
    contract_date = fields.Date('Contract Date', readonly=True)
    contract_ref = fields.Char('Contract', readonly=True)
    contract_status = fields.Selection(lambda self: self.env['sale.proposal']._fields['state'].selection, 'Contract Status', readonly=True)
    contract_type = fields.Selection(lambda self: self.env['sale.proposal']._fields['contract_type'].selection, 'Contract Type', readonly=True)
    sold_price = fields.Float('Sold Price', readonly=True)
    payment_plan = fields.Char('Payment Plan', readonly=True)
    payment_type = fields.Char('Payment Type', readonly=True)
    discount_percentage = fields.Float('Discount %', readonly=True)
    down_payment = fields.Float('Downpayment', readonly=True)
    dp_percentage = fields.Float('DP %', readonly=True)
    maintenance = fields.Float('Maintenance', readonly=True)
    maintenance_percentage = fields.Float('Maint. %', readonly=True)
    sales = fields.Char('Sales', readonly=True)
    sales_manager = fields.Char('Sales Manager', readonly=True)
    sales_director = fields.Char('Sales Director', readonly=True)
    source = fields.Char('Source', readonly=True)
    brokerage = fields.Char('Brokerage', readonly=True)
    agent_name = fields.Char('Agent Name', readonly=True)
    client_name = fields.Char('Client Name', readonly=True)
    client_arabic_name = fields.Char('Arabic Client Name', readonly=True)
    address = fields.Char('Address', readonly=True)
    national_id = fields.Char('ID Number/Passport No', readonly=True)
    mobile = fields.Char('Mobile', readonly=True)
    email = fields.Char('Email', readonly=True)
    nationality = fields.Char('Nationality', readonly=True)
    commission_paid = fields.Float('Commission Paid', readonly=True)
    quarter = fields.Char('Quarter', readonly=True)
    year = fields.Char('Year', readonly=True)
    month = fields.Char('Month', readonly=True)
    m2_price = fields.Float('M2 Price', readonly=True)

    def init(self):
        env = self.env
        Proposal, Reservation = env['sale.proposal'], env['real.estate.sale.reservation']

        def names_from(owner_field, owner_table, key_col, model):
            """string_agg of the partner names behind a many2many of a contract or reservation."""
            f = model._fields.get(owner_field)
            if f is None or f.type != 'many2many':
                return None
            return f.relation, f.column1, f.column2, f.comodel_name

        def m2m_names(model, field, via_member=False):
            info = names_from(field, None, None, model)
            if not info:
                return "SELECT NULL::int AS key, NULL::text AS names WHERE false"
            rel, c1, c2, comodel = info
            if via_member:
                return ("SELECT r.%s AS key, string_agg(DISTINCT p.name, ', ' ORDER BY p.name) AS names FROM %s r "
                        "JOIN broker_team_member m ON m.id = r.%s JOIN res_partner p ON p.id = m.partner_id GROUP BY r.%s" % (c1, rel, c2, c1))
            return ("SELECT r.%s AS key, string_agg(DISTINCT p.name, ', ' ORDER BY p.name) AS names FROM %s r "
                    "JOIN res_partner p ON p.id = r.%s GROUP BY r.%s" % (c1, rel, c2, c1))

        res_commission_col = Reservation._fields['commission_ids'].inverse_name
        reservation_col = res_commission_col if res_commission_col in env['realestate.commission']._fields else 'sale_reservation_id'
        commission = lambda col: """
            SELECT c.%(col)s AS key,
                   string_agg(DISTINCT p.name, ', ' ORDER BY p.name) FILTER (WHERE c.jop_position = 'Sales Person') AS sales,
                   string_agg(DISTINCT p.name, ', ' ORDER BY p.name) FILTER (WHERE c.jop_position = 'Sales Manager') AS manager,
                   string_agg(DISTINCT p.name, ', ' ORDER BY p.name) FILTER (WHERE c.jop_position IN ('Director', 'Sales Sector Manager')) AS director
              FROM realestate_commission c
              JOIN res_users u ON u.id = c.employee_id
              JOIN res_partner p ON p.id = u.partner_id
             WHERE c.%(col)s IS NOT NULL
          GROUP BY c.%(col)s""" % {'col': col}

        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW ark_engineer_inventory AS (
            WITH ctr AS (
                SELECT DISTINCT ON (unit_id) * FROM sale_proposal
                 WHERE unit_id IS NOT NULL AND state NOT IN %(ctr_bad)s ORDER BY unit_id, id DESC
            ), res AS (
                SELECT DISTINCT ON (unit_id) * FROM real_estate_sale_reservation
                 WHERE unit_id IS NOT NULL AND state NOT IN %(res_bad)s ORDER BY unit_id, id DESC
            ), com_c AS (%(com_c)s), com_r AS (%(com_r)s),
            brk_c AS (%(brk_c)s), brk_r AS (%(brk_r)s), agt_c AS (%(agt_c)s),
            clm AS (
                SELECT k.sale_proposal_id AS key,
                       string_agg(DISTINCT p.name, ', ' ORDER BY p.name) FILTER (WHERE k.claim_type = 'broker') AS brokers,
                       string_agg(DISTINCT p.name, ', ' ORDER BY p.name) FILTER (WHERE k.claim_type IN ('agent', 'ambassador')) AS agents
                  FROM broker_claim k JOIN res_partner p ON p.id = k.broker_company
                 WHERE k.state <> 'cancelled' AND k.sale_proposal_id IS NOT NULL GROUP BY k.sale_proposal_id
            ),
            paid AS (
                SELECT sale_proposal_id AS key, SUM(commission_amount) AS amount FROM broker_claim
                 WHERE state = 'paid' AND sale_proposal_id IS NOT NULL GROUP BY sale_proposal_id
            )
            SELECT u.id AS id,
                   u.id AS unit_id,
                   COALESCE(NULLIF(u.system_code, ''), u.name) AS unit_code,
                   u.unit_type AS unit_type,
                   COALESCE(apt.name, vil.name, lof.name, off.name, med.name,
                            initcap(replace(COALESCE(NULLIF(u.retail_type, ''), NULLIF(u.residential_type, ''), u.unit_type), '_', ' '))) AS unit_subtype,
                   u.project_id AS project_id, prj.name AS project_name,
                   u.building_id AS building_id, bld.name AS building_name,
                   u.floor_id AS floor_id, flr.name AS floor_name,
                   NULLIF(u.indoor_net_area, 0) AS net_area,
                   NULLIF(u.unit_area, 0) AS gross_area,
                   NULLIF(u.indoor_net_area, 0) AS indoor_net_area,
                   NULLIF(u.indoor_gross_area, 0) AS indoor_gross_area,
                   NULLIF(u.outdoor_gross_area, 0) AS outdoor_gross_area,
                   NULLIF(u.outdoor_gross_area, 0) AS garden_area,
                   NULLIF(u.landed_area, 0) AS land_area,
                   NULLIF(u.total_price_unit, 0) AS unit_price,
                   CASE WHEN u.unit_area > 0 AND u.total_price_unit > 0 THEN u.total_price_unit / u.unit_area END AS price_per_meter,
                   u.unit_status AS unit_status,
                   blk.name AS block_reason,
                   res.reservation_start_date AS reservation_date,
                   res.name AS reservation_serial,
                   ctr.contract_issue_date AS contract_date,
                   ctr.name AS contract_ref,
                   ctr.state AS contract_status,
                   ctr.contract_type AS contract_type,
                   COALESCE(NULLIF(ctr.price_after_discount, 0), NULLIF(res.price_after_discount, 0)) AS sold_price,
                   COALESCE(itp.name, rit.name) AS payment_plan,
                   res.payment_method AS payment_type,
                   COALESCE(NULLIF(ctr.discount_percentage, 0), NULLIF(res.discount_percentage, 0)) AS discount_percentage,
                   COALESCE(NULLIF(ctr.down_payment, 0), NULLIF(res.down_payment, 0)) AS down_payment,
                   CASE WHEN COALESCE(NULLIF(ctr.price_after_discount, 0), NULLIF(res.price_after_discount, 0)) > 0
                        THEN COALESCE(NULLIF(ctr.down_payment, 0), NULLIF(res.down_payment, 0))
                             / COALESCE(NULLIF(ctr.price_after_discount, 0), NULLIF(res.price_after_discount, 0)) * 100 END AS dp_percentage,
                   COALESCE(NULLIF(ctr.maintenance_price, 0), NULLIF(res.maintenance_price, 0)) AS maintenance,
                   COALESCE(NULLIF(ctr.maintenance_percentage, 0), NULLIF(res.maintenance_percentage, 0)) AS maintenance_percentage,
                   COALESCE(com_c.sales, com_r.sales) AS sales,
                   COALESCE(com_c.manager, com_r.manager) AS sales_manager,
                   COALESCE(com_c.director, com_r.director) AS sales_director,
                   initcap(COALESCE(NULLIF(ctr.referred_by, ''), NULLIF(res.referred_by, ''))) AS source,
                   COALESCE(rp.name, clm.brokers, brk_c.names, brk_r.names) AS brokerage,
                   COALESCE(clm.agents, agt_c.names) AS agent_name,
                   cust.name AS client_name,
                   NULLIF(ctr.brand_name, '') AS client_arabic_name,
                   COALESCE(NULLIF(ctr.address_1, ''), NULLIF(res.customer_street, '')) AS address,
                   COALESCE(NULLIF(ctr.national_id, ''), NULLIF(res.customer_national_id, '')) AS national_id,
                   COALESCE(NULLIF(ctr.mobile, ''), NULLIF(cust.mobile, ''), NULLIF(cust.phone, '')) AS mobile,
                   COALESCE(NULLIF(ctr.email, ''), NULLIF(res.customer_email, ''), NULLIF(cust.email, '')) AS email,
                   COALESCE(cn.name ->> 'en_US', cn.name ->> 'ar_001') AS nationality,
                   paid.amount AS commission_paid,
                   CASE WHEN COALESCE(res.reservation_start_date, ctr.contract_issue_date) IS NOT NULL
                        THEN 'Q' || to_char(COALESCE(res.reservation_start_date, ctr.contract_issue_date), 'Q') END AS quarter,
                   to_char(COALESCE(res.reservation_start_date, ctr.contract_issue_date), 'YYYY') AS year,
                   to_char(ctr.contract_issue_date, 'Mon') AS month,
                   CASE WHEN u.unit_area > 0 AND COALESCE(NULLIF(ctr.price_after_discount, 0), NULLIF(res.price_after_discount, 0)) > 0
                        THEN COALESCE(NULLIF(ctr.price_after_discount, 0), NULLIF(res.price_after_discount, 0)) / u.unit_area END AS m2_price
              FROM real_estate_unit u
         LEFT JOIN realestate_project prj ON prj.id = u.project_id
         LEFT JOIN real_estate_building bld ON bld.id = u.building_id
         LEFT JOIN floor flr ON flr.id = u.floor_id
         LEFT JOIN block_reason blk ON blk.id = u.reason_id AND u.unit_status IN ('blocked', 'on_hold_ma')
         LEFT JOIN residential_sub_type apt ON apt.id = u.apartment_type_id
         LEFT JOIN residential_sub_type vil ON vil.id = u.villa_type_id
         LEFT JOIN residential_sub_type lof ON lof.id = u.loft_type_id
         LEFT JOIN office_type off ON off.id = u.office_type_id
         LEFT JOIN medical_type med ON med.id = u.medical_type_id
         LEFT JOIN ctr ON ctr.unit_id = u.id
         LEFT JOIN res ON res.unit_id = u.id
         LEFT JOIN com_c ON com_c.key = ctr.id
         LEFT JOIN com_r ON com_r.key = res.id
         LEFT JOIN brk_c ON brk_c.key = ctr.id
         LEFT JOIN brk_r ON brk_r.key = res.id
         LEFT JOIN agt_c ON agt_c.key = ctr.id
         LEFT JOIN paid ON paid.key = ctr.id
         LEFT JOIN installment_template itp ON itp.id = ctr.installment_template_id
         LEFT JOIN installment_template rit ON rit.id = res.installment_template_id
         LEFT JOIN res_partner rp ON rp.id = COALESCE(ctr.referred_by_partner_id, res.referred_by_partner_id)
         LEFT JOIN clm ON clm.key = ctr.id
         LEFT JOIN res_partner cust ON cust.id = COALESCE(ctr.customer_id, res.customer_id)
         LEFT JOIN res_country cn ON cn.id = cust.country_id
             WHERE u.active
            )
        """ % {
            'ctr_bad': "('draft', 'cancelled', 'terminated')",
            'res_bad': "('draft', 'cancelled', 'expired')",
            'com_c': commission('sale_proposal_id'),
            'com_r': commission(reservation_col),
            'brk_c': m2m_names(Proposal, 'broker_ids'),
            'brk_r': m2m_names(Reservation, 'broker_ids'),
            'agt_c': m2m_names(Proposal, 'agent_commission_ids', via_member=True),
        })
