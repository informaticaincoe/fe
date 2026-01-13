from odoo import models, api, fields, _
import logging

_logger = logging.getLogger(__name__)

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

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.codigo} - {rec.valor}" if rec.codigo is not None else rec.valor
            result.append((rec.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            args = ['|', ('valor', operator, name), ('codigo', operator, name)] + args
        records = self.search(args, limit=limit)
        return records.name_get()

class TipoOperacion(models.Model):
    _name = "account.tipo.operacion"
    _description = "Tipo de Operacion"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.codigo} - {rec.valor}" if rec.codigo is not None else rec.valor
            result.append((rec.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            args = ['|', ('valor', operator, name), ('codigo', operator, name)] + args
        records = self.search(args, limit=limit)
        _logger.info("SIT name_search args=%s", args)
        return records.name_get()

class ClasificacionFacturacion(models.Model):
    _name = "account.clasificacion.facturacion"
    _description = "Calificación"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.codigo} - {rec.valor}" if rec.codigo is not None else rec.valor
            result.append((rec.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            args = ['|', ('valor', operator, name), ('codigo', operator, name)] + args
        records = self.search(args, limit=limit)
        _logger.info("SIT name_search args=%s", args)
        return records.name_get()

class Sector(models.Model):
    _name = "account.sector"
    _description = "Sector"
    _rec_name = "valor"

    codigo = fields.Integer("Código")
    valor = fields.Char("Valor")

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.codigo} - {rec.valor}" if rec.codigo is not None else rec.valor
            result.append((rec.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            args = ['|', ('valor', operator, name), ('codigo', operator, name)] + args
        records = self.search(args, limit=limit)
        return records.name_get()

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