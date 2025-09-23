from odoo import models, api, fields, _

class TipoIngreso(models.Model):
    _name = "account.tipo.ingreso"
    _description = "Tipo de Ingreso"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")

class TipoCostoGasto(models.Model):
    _name = "account.tipo.costo.gasto"
    _description = "Tipo de Costo/Gasto"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")

