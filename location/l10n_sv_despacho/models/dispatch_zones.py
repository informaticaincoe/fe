from odoo import models, fields

class DispatchZones(models.Model):
    _name = "dispatch.zones"
    # _description = 'Zonas de despacho'
    # _inherit = ['mail.thread', 'mail.activity.mixin'] # chatter + actividades
    #
    # dpto_id = fields.Many2many('res.country.state', 'dispatch_zone_state_rel', 'zone_id', 'state_id', string="Departamento", required=True, domain="[('country_id.code', '=', 'SV')]")
    # munic_id = fields.Many2many('res.municipality', string="Municipios", required=True, domain="[('dpto_id', 'in', dpto_id)]")
    name = fields.Char(string="Name", required=True, help="Nombre de la zona", )

    zone_line_ids = fields.One2many(
        'dispatch.zone.line',
        'zone_id',
        string="Distribución Geográfica"
    )
