from odoo import fields, models


class ResConfiguration(models.Model):
    _name = "res.configuration"
    _description = 'Service Configuration Parameters'

    company_id = fields.Many2one("res.company", string="Company", help="Company used for the import")
    #url = fields.Char(string='URL del Servicio')
    pwd = fields.Char(string='Contraseña')
    value_type = fields.Selection([
        ('text', 'Texto'),
        ('int', 'Número Entero'),
        ('float', 'Decimal'),
        ('bool', 'Booleano'),
        ('json', 'JSON'),
    ], string='Tipo de Valor', default='text')
    value_text = fields.Text(string='Valor')
    description = fields.Text(string='Descripción')
    create_date = fields.Datetime(string='Fecha de creación', readonly=True)
    active = fields.Boolean(default=True)
    clave = fields.Text(string='Clave')
