# Portal feature codes shared between the controllers (which check them) and
# res.config.settings (which exposes them as checkboxes). Models must not import
# from controllers, so these live here and controllers import from models instead.
PORTAL_FEATURE_CRM = 'crm_leads'
PORTAL_FEATURE_UNITS = 'real_estate_units'
PORTAL_FEATURE_PERMISSION_REQUESTS = 'permission_requests'
