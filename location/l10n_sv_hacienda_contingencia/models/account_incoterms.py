from odoo import fields, models, api, _

class AccountIncoterms(models.Model):
    _inherit = "account.incoterms"

    codigo_mh = fields.Char("Código Hacienda")

    def actualizar_codigo_mh(self):
        codigos = {
            'EXW': '01',
            'FCA': '02',
            'CPT': '03',
            'CIP': '04',
            'DAP': '05',
            'DPU': '06',
            'DDP': '07',
            'FAS': '08',
            'FOB': '09',
            'CFR': '10',
            'CIF': '11',
        }
        for incoterm in self.search([]):
            if incoterm.code in codigos:
                incoterm.codigo_mh = codigos[incoterm.code]
