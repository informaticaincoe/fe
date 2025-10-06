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


class TipoOperacion(models.Model):
    _name = "account.tipo.operacion"
    _description = "Tipo de Operacion"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")


class ClasificacionFacturacion(models.Model):
    _name = "account.clasificacion.facturacion"
    _description = "Calificación"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")

class Sector(models.Model):
    _name = "account.sector"
    _description = "Sector"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")

class ClaseDocumento(models.Model):
    _name = "account.clase.documento"
    _description = "clase.documento"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")

class TipoDocumentoIdentificacion(models.Model):
    _name = "account.tipo.documento.identificacion"
    _description = "tipo documento identificacion"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")