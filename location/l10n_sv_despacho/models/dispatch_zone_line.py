from odoo import models, fields


class DispatchZoneLine(models.Model):
    _name = "dispatch.zone.line"
    _description = "Línea de Departamento y Municipios"

    zone_id = fields.Many2one('dispatch.zones', ondelete='cascade')

    # Campo 1: El Departamento (Uno por fila)
    dpto_id = fields.Many2one(
        'res.country.state',
        string="Departamento",
        required=True,
        domain="[('country_id.code', '=', 'SV')]"
    )

    # Campo 2: Los Municipios de ESE departamento
    munic_ids = fields.Many2many(
        'res.municipality',
        string="Municipios",
        # Aquí el dominio usa dpto_id (el de esta fila)
        domain="[('dpto_id', '=', dpto_id)]"
    )