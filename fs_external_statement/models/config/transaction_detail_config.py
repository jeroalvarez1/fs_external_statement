from odoo import api, fields, models
from odoo.exceptions import ValidationError

class TransactionDetailConfig(models.Model):
    _name = "transaction.detail.config"

    name = fields.Char(compute='_compute_name', string='Nombre')
    external_bank_config_id = fields.Many2one(
        'external.bank.config',
        string='Configuración del Banco Externo'
    )
    field_type = fields.Selection([
        ('txt', '.txt'), ('csv', '.csv'), ('xls', '.xls'), ('xlsx', '.xlsx')
    ], string='Tipo de Archivo')
    search_type = fields.Selection([
        ('txt_sw', '.txt Caracter de comienzo de linea'), ('excel_fixed_liquidation', 'Excel, liquidación fija'),
        ('excel_init_with_date', 'Excel, comienza con fecha')
    ], string='Tipo de búsqueda')
    field_config_ids = fields.One2many(
        'transaction.detail.field.config',
        'transaction_detail_config_id',
        string='Campos de Configuración',
    )

    @api.depends('external_bank_config_id', 'field_type')
    def _compute_name(self):
        for record in self:
            record.name = f'{record.external_bank_config_id.name or ""}-{record.field_type or ""}'