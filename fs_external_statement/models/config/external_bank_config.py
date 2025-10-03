from odoo import api, fields, models


class ExternalBankConfig(models.Model):
    _name = "external.bank.config"

    name = fields.Char(
        string='Nombre'
    )
    trade_header_config_ids = fields.One2many(
        'trade.header.config',
        'external_bank_config_id',
        string='Configuraciónes de Cabeceras de Comercios'
    )
    settlement_header_config_ids = fields.One2many(
        'settlement.header.config',
        'external_bank_config_id',
        string='Configuraciónes de Cabeceras de Liquidaciónes'
    )
    transaction_detail_config_ids = fields.One2many(
        'transaction.detail.config',
        'external_bank_config_id',
        string='Configuraciónes de Detalles de Transacciones'
    )
    settlement_tax_config_ids = fields.One2many(
        'settlement.tax.config',
        'external_bank_config_id',
        string='Configuración de Impuestos'
    )