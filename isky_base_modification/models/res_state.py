# -*- coding: utf-8 -*-

from odoo import fields, models


class Neighborhood(models.Model):
    _name = 'neighborhood.neighborhood'
    _description = 'Neighborhood'

    name = fields.Char(string='Neighborhood', required=True)
    city_id = fields.Many2one('city.city', string='City')


class CityModel(models.Model):
    _name = 'city.city'
    _description = 'City'

    name = fields.Char(string='City', required=True)
    neighborhood_ids = fields.One2many('neighborhood.neighborhood', 'city_id', string='Neighborhoods')
    state_id = fields.Many2one('res.country.state', string='Governorate')
    country_id = fields.Many2one('res.country', string='Country')


class ResState(models.Model):
    _inherit = 'res.country.state'

    city_ids = fields.One2many('city.city', 'state_id', string='Cities')
