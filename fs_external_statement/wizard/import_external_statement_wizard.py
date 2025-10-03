from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
from ..utils.file_processor import ExternalStatementFileProcessor

_logger = logging.getLogger(__name__)


class ImportExternalStatementWizard(models.TransientModel):
    _name = "import.external_statement.wizard"
    _description = "Importar Extractos Bancarios Externos"

    file_external_statement = fields.Binary(
        string='Archivo de Extracto Bancario Externo',
        required=True,
        help="Suba el archivo de liquidación del Extracto Bancario Externo"
    )
    filename_external_statement = fields.Char('Nombre del Archivo')
    external_bank_config_id = fields.Many2one(
        'external.bank.config',
        string='Configuración del Banco Externo',
        required=True
    )
    field_type = fields.Selection([
        ('txt', '.txt'), ('csv', '.csv'), ('xls', '.xls'), ('xlsx', '.xlsx')
    ], string='Tipo de Archivo', required=True)

    def action_import(self):
        """Acción principal para importar el archivo"""
        self.ensure_one()
        if not self.file_external_statement:
            raise UserError("Por favor seleccione un archivo para importar")

        # Procesar archivo
        file_processor = ExternalStatementFileProcessor(self.env)
        data = file_processor.process_file(self.file_external_statement, self.filename_external_statement, self.external_bank_config_id, self.field_type)

        # Validar datos
        if not data.get('trade_header'):
            raise UserError("El archivo no contiene un encabezado válido")
        # Verificar si ya existe un registro con el mismo nombre de archivo
        existing_headers = self.env['trade.header'].search([
            ('filename_external_statement', '=', data['trade_header'].get('filename_external_statement', ''))
        ])
        if existing_headers:
            raise UserError(
                f"Ya existe un archivo con el mismo nombre: {data['trade_header'].get('filename_external_statement', '')}"
            )

        # Crea los el header, settlements, transactions y trailers
        trade_header = self._create_trade_header(data['trade_header'])
        self._create_settlements(
            trade_header, data.get('settlements', []), data.get('transactions', []), data.get('trailers', [])
        )
        return {
            'name': 'Cabecera de Comercio',
            'view_mode': 'form',
            'res_model': 'trade.header',
            'res_id': trade_header.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def _create_trade_header(self, header_data):
        """Crea el registro de Trade Header"""
        return self.env['trade.header'].create({
            'name': header_data.get('name', 'N/A'),
            'file_external_statement': self.file_external_statement,
            'commerce_number': header_data.get('commerce_number', ''),
            'filename_external_statement': header_data.get('filename_external_statement', ''),
        })

    def _create_settlements(self, trade_header, settlements_data, transactions_data, trailers_data):
        """Crea los registros de Settlement y Transaction"""
        # Agrupar transacciones por número de liquidación
        transactions_by_settlement = {}
        for tx in transactions_data:
            settlement_num = tx['settlement_number']
            if settlement_num not in transactions_by_settlement:
                transactions_by_settlement[settlement_num] = []
            transactions_by_settlement[settlement_num].append(tx)

        trailers_by_settlement = {}
        for tlr in trailers_data:
            settlement_num = tlr['settlement_number']
            if settlement_num not in trailers_by_settlement:
                trailers_by_settlement[settlement_num] = []
            trailers_by_settlement[settlement_num].append(tlr)

        _logger.info(f'trailers_by_settlement -> {trailers_by_settlement}')
        # Crear asentamientos con sus transacciones
        for settlement_data in settlements_data:
            settlement_num = settlement_data['settlement_number']
            tx_data = transactions_by_settlement.get(settlement_num, [])
            tlr_data = trailers_by_settlement.get(settlement_num, [])

            # Obtener el metodo de pago del Extracto Bancario Externo
            external_statement_payment_method = self.env['external.statement.payment.methods'].search([
                ('name', '=', settlement_data.get('product', ''))
            ], limit=1)

            journal_id = (
                external_statement_payment_method.journal_id.id
                if external_statement_payment_method and external_statement_payment_method.journal_id
                else False
            )
            if not journal_id:
                raise UserError(
                    f'No se ha encontrado un diario en el metodo de pago "{external_statement_payment_method.name}" | {settlement_data.get("product", "")}'
                )

            # Crear asentamiento
            settlement = self.env['settlement.header'].create({
                'name': settlement_data['name'],
                'product': settlement_data['product'],
                'settlement_number': settlement_num,
                'trade_header_id': trade_header.id,
                'journal_id': journal_id,
            })

            # Crear transacciones (ya filtradas por settlement_number)
            if tx_data:
                self._create_transactions(settlement, tx_data)
            if tlr_data:
                self._create_trailers(settlement, tlr_data)

    def _create_transactions(self, settlement, transactions_data):
        """Crea los registros de Transaction para un Settlement"""
        tx_vals = []
        for tx in transactions_data:
            tx_vals.append({
                'operation_date': tx.get('operation_date') or fields.Date.today(),# TODO, AGREGAR EL CORRECTO FORMATEADO
                'cover_terminal_posnet': tx.get('cover_terminal_posnet'),
                'summary_lot_posnet': tx.get('summary_lot_posnet'),
                'coupon_posnet': tx.get('coupon_posnet'),
                'total': tx.get('total').replace('.', '').replace(',', '.') if isinstance(tx.get('total'), str) else tx.get('total'),
                'card_number': tx.get('card_number'),
                'settlement_header_id': settlement.id,
            })

        # Crear transacciones en lote para mejor rendimiento
        if tx_vals:
            self.env['transaction.detail'].create(tx_vals)

    def _create_trailers(self, settlement, trailer_data_list):
        """Crea los registros de Transaction para un Settlement"""
        _logger.info(f'trailer_data_list -> {trailer_data_list}')
        trl_vals = []
        for trailer in trailer_data_list:
            trl_vals.append({
                'settlement_tax_id': trailer.get('settlement_tax_id'),
                'settlement_number': trailer.get('settlement_number'),
                'total': trailer.get('total'),
                'settlement_header_id': settlement.id
            })
        # Crear transacciones en lote para mejor rendimiento
        if trl_vals:
            self.env['settlement.trailer.tax'].create(trl_vals)