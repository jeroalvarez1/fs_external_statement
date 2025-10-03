from odoo import api, fields, models


class TradeHeaderConfig(models.Model):
    _name = "trade.header.config"

    name = fields.Char(compute='_compute_name', string='Nombre')
    external_bank_config_id = fields.Many2one(
        'external.bank.config',
        string='Configuración del Banco Externo',
        required=True
    )
    field_type = fields.Selection([
        ('txt', '.txt'), ('csv', '.csv'), ('xls', '.xls'), ('xlsx', '.xlsx')
    ], string='Tipo de Archivo', required=True)
    field_config_ids = fields.One2many(
        'trade.header.field.config',
        'trade_header_config_id',
        string='Campos de Configuración',
    )

    @api.depends('external_bank_config_id', 'field_type')
    def _compute_name(self):
        for record in self:
            record.name = f'{record.external_bank_config_id.name}-{record.field_type}'