import base64
from odoo.exceptions import UserError
import logging
import pandas as pd
import io
from datetime import datetime

_logger = logging.getLogger(__name__)

# TODO - SEGUIR CON EL DETALLE DE LA TRANSACCIÓN

class ExternalStatementFileProcessor:
    """Servicio para procesar archivos de Extractos Bancarios Externos"""

    def __init__(self, env):
        self.env = env

    def process_file(self, file_content, filename, external_bank_config_id, field_type):
        """Procesa el archivo de Extractos Bancarios Externos y devuelve los datos estructurados"""
        if not file_content:
            raise UserError("No se proporcionó contenido de archivo")

        # Decodificar contenido
        decoded_file = base64.b64decode(file_content)

        if field_type == 'txt':
            data_str = decoded_file.decode('UTF-8')
            lines = [line for line in data_str.splitlines() if line.strip()]
            df_lines = pd.DataFrame({'line': lines})

        elif field_type == 'csv':
            data_str = decoded_file.decode('UTF-8')
            data_io = io.StringIO(data_str)
            df_lines = pd.read_csv(data_io, sep=",")
            lines = df_lines.astype(str).agg(",".join, axis=1).tolist()  # convertir filas en "líneas"

        elif field_type in ('xls', 'xlsx'):
            data_io = io.BytesIO(decoded_file)
            df_lines = pd.read_excel(data_io)  # pandas decide motor según extensión y disponibilidad
            lines = df_lines.astype(str).agg(",".join, axis=1).tolist()

        else:
            raise UserError(f"Tipo de archivo no soportado: {field_type}")

        return self._parse_lines(lines, df_lines, filename, external_bank_config_id, field_type)

    def _parse_lines(self, lines, df_lines, filename, external_bank_config_id, field_type):
        """Parsea las líneas del archivo y devuelve una estructura de datos"""
        result = {
            'trade_header': {},
            'settlements': [],
            'transactions': [],
            'trailers': []
        }

        result['trade_header'] = self._parse_trade_header(df_lines, filename, external_bank_config_id, field_type)
        result['settlements'] = self._parse_settlement(df_lines, external_bank_config_id, field_type)
        result['transactions'] = self._parse_transaction2(df_lines, external_bank_config_id, field_type) # TODO AGREGAR SI TIENE DECIMALES Y CUANTOS
        result['trailers'] = self._parse_trailer2(df_lines, external_bank_config_id, field_type)
        _logger.info(f'trailers -> {result["trailers"]}')
        # last_product = None
        # if field_type == 'txt':
        #     for line in lines[1:]:
        #         if line.startswith('2'):
        #             settlement = self._parse_settlement(line)
        #             result['settlements'].append(settlement)
        #             last_product = settlement.get('product')
        #         elif line.startswith('3'):
        #             result['transactions'].append(self._parse_transaction(line))
        #         elif line.startswith('8'):
        #             result['trailers'].append(self._parse_trailer(line, last_product))

        return result

    def _parse_trade_header_txt_pandas(self, trade_header_dict, trade_header_field_config_ids, df_lines):
        """
        df_lines: DataFrame con columna 'line' que contiene todas las líneas del archivo.
        """
        _logger.info(f'df_lines -> {df_lines}')
        for field_config_id in trade_header_field_config_ids:
            start_with = field_config_id.start_with
            line_number = field_config_id.line_number

            if not start_with and not line_number:
                raise UserError(
                    f'La configuración de la linea "{field_config_id.name}" debe tener un "Numero de linea (.txt)" '
                    f'o un "Caracter de comienzo de linea (.txt)"'
                )

            if start_with:
                line_series = df_lines[df_lines['line'].str.startswith(start_with)]
                line = line_series['line'].iloc[0] if not line_series.empty else None
            else:
                if 1 <= line_number <= len(df_lines):
                    line = df_lines.iloc[line_number - 1]['line']
                else:
                    line = None

            if line:
                trade_header_dict[field_config_id.destination_field_id.name] = line[
                    field_config_id.starting_position:field_config_id.end_position
                ]
        return trade_header_dict

    def _parse_trade_header_xls_pandas(self, trade_header_dict, trade_header_field_config_ids, df_lines):
        """
        df_lines: DataFrame con columna 'line' que contiene todas las líneas del archivo.
        """
        for field_config_id in trade_header_field_config_ids:
            row = field_config_id.row
            col = field_config_id.col

            if not row or not col:
                raise UserError(
                    f'La configuración de la linea "{field_config_id.name}" debe tener una "Fila" '
                    f'y una "Columna"'
                )

            value = False
            if 1 <= row <= len(df_lines) and 1 <= col <= len(df_lines):
                value = df_lines.iat[row - 1, col - 1]

            if value:
                trade_header_dict[field_config_id.destination_field_id.name] = value
        return trade_header_dict

    def _parse_trade_header(self, df_lines, filename, external_bank_config_id, field_type):
        """Parsea la línea de encabezado del archivo usando pandas"""
        trade_header_config_id = external_bank_config_id.trade_header_config_ids.filtered(
            lambda l: l.field_type == field_type
        )[:1]
        if not trade_header_config_id:
            raise UserError(
                f'No se ha encontrado ninguna "Configuración de Cabecera de Comercio" con el tipo "{field_type}"'
            )

        trade_header_field_config_ids = self.env['trade.header.field.config'].search([
            ('trade_header_config_id', '=', trade_header_config_id.id)
        ])
        if not trade_header_field_config_ids:
            raise UserError(
                f'No se ha encontrado ningún "Campo de Configuración de Cabecera de Comercio" '
                f'para la Configuración de Cabecera de Comercio: "{trade_header_config_id.name}"'
            )

        trade_header_dict = {'filename_external_statement': filename}
        if field_type == 'txt':
            trade_header_dict = self._parse_trade_header_txt_pandas(
                trade_header_dict, trade_header_field_config_ids, df_lines
            )
        elif field_type in ('xls', 'xlsx'):
            trade_header_dict = self._parse_trade_header_xls_pandas(
                trade_header_dict, trade_header_field_config_ids, df_lines
            )

        _logger.info(f'trade_header_dict -> {trade_header_dict}')
        return trade_header_dict

    def _parse_settlement_header_txt_pandas(self, settlement_header_field_config_ids, df_lines, settlement_header_config):
        settlement_header_lines = []
        if settlement_header_config.search_type == 'txt_sw':
            for df_line in df_lines['line']:
                settlement_header_dict = {}
                for field_config_id in settlement_header_field_config_ids:
                    start_with = field_config_id.start_with
                    if not start_with:
                        raise UserError(
                            f'La configuración de la linea "{field_config_id.name}" debe tener un '
                            f'"Caracter de comienzo de linea (.txt)"'
                        )
                    if start_with and df_line.startswith(start_with):
                        settlement_header_dict.update({
                            field_config_id.destination_field_id.name:
                                df_line[field_config_id.starting_position:field_config_id.end_position]
                        })
                if settlement_header_dict:
                    settlement_header_lines.append(settlement_header_dict)
        elif settlement_header_config.search_type == 'txt_ln':
            settlement_header_dict = {}
            for field_config_id in settlement_header_field_config_ids:
                line_number = field_config_id.line_number
                if not line_number:
                    raise UserError(
                        f'La configuración de la linea "{field_config_id.name}" debe tener un "Numero de linea (.txt)"'
                    )
                line = False
                if 1 <= line_number <= len(df_lines):
                    line = df_lines.iloc[line_number - 1]['line']
                if line:
                    settlement_header_dict.update({
                            field_config_id.destination_field_id.name: line[
                            field_config_id.starting_position:field_config_id.end_position
                        ]
                    })
            settlement_header_lines.append(settlement_header_dict)
        return settlement_header_lines

    def _parse_settlement_header_xls_pandas(
            self, settlement_header_field_config_ids, df_lines, settlement_header_config
    ):
        settlement_header_lines = []
        # Caso excel_rc: filas y columnas específicas
        if settlement_header_config.search_type == 'excel_rc':
            settlement_header_dict = {}
            for field_config_id in settlement_header_field_config_ids:
                row = field_config_id.row
                col = field_config_id.col
                if not row or not col:
                    raise UserError(
                        f'La configuración de la linea "{field_config_id.name}" debe tener una "Fila" '
                        f'y una "Columna"'
                    )
                value = False
                if 1 <= row <= len(df_lines) and 1 <= col <= len(df_lines.columns):
                    value = df_lines.iat[row - 1, col - 1]

                if value:
                    settlement_header_dict[field_config_id.destination_field_id.name] = value
            settlement_header_lines.append(settlement_header_dict)
        # Casos excel_init_with y excel_init_with_date
        elif settlement_header_config.search_type in ('excel_init_with', 'excel_init_with_date'):
            # 1. Buscar el field de liquidación
            liquidation_field = next(
                (f for f in settlement_header_field_config_ids if getattr(f, "is_liquidation_number", False)),
                None
            )
            if not liquidation_field or not liquidation_field.col:
                raise UserError(
                    f'Es obligatorio definir un campo con "is_liquidation_number" y "col"'
                )
            # 2. Filtrar filas según el tipo
            matched_rows = []
            for _, row in df_lines.iterrows():
                raw_value = row.iloc[liquidation_field.col - 1]
                if settlement_header_config.search_type == "excel_init_with":
                    # Filtrar por start_with
                    if not liquidation_field.start_with:
                        raise UserError(f'El campo de liquidación necesita "start_with" para este tipo de búsqueda')
                    if str(raw_value).startswith(liquidation_field.start_with):
                        matched_rows.append(row)
                else:  # excel_init_with_date
                    # Solo intentamos parsear si hay formatos definidos
                    if not liquidation_field.origin_date_format or not liquidation_field.dest_date_format:
                        raise UserError(f'El campo de liquidación necesita formatos de fecha definidos')
                    try:
                        parsed_date = datetime.strptime(str(raw_value), liquidation_field.origin_date_format)
                        # Normalizamos
                        row.iloc[liquidation_field.col - 1] = parsed_date.strftime(liquidation_field.dest_date_format)
                        matched_rows.append(row)
                    except (ValueError, TypeError):
                        # Ignoramos filas que no sean fechas válidas
                        continue
            matched_rows = pd.DataFrame(matched_rows, columns=df_lines.columns) if matched_rows else pd.DataFrame(
                columns=df_lines.columns)
            # 3. Detectar campos de agrupación
            group_by_fields = [
                f.destination_field_id.name
                for f in settlement_header_field_config_ids
                if getattr(f, "group_by", False)
            ]
            seen_keys = set()
            # 4. Recorrer cada fila encontrada
            for _, row in matched_rows.iterrows():
                row_dict = {}
                # Guardamos siempre el número de liquidación
                liquidation_value = row.iloc[liquidation_field.col - 1]
                row_dict[liquidation_field.destination_field_id.name] = liquidation_value
                # Guardamos los otros campos
                for f_config in settlement_header_field_config_ids:
                    if f_config is liquidation_field:
                        continue
                    c = f_config.col
                    if c and 1 <= c <= len(row):
                        value = row.iloc[c - 1]
                        # Si el campo es fecha → convertir
                        if settlement_header_config.search_type == "excel_init_with_date" and f_config.origin_date_format and f_config.dest_date_format:
                            try:
                                parsed_date = datetime.strptime(str(value), f_config.origin_date_format)
                                value = parsed_date.strftime(f_config.dest_date_format)
                            except (ValueError, TypeError):
                                # Ignoramos campos de fecha no válidos
                                continue
                        row_dict[f_config.destination_field_id.name] = value
                # Clave de agrupación
                key = tuple(row_dict.get(c) for c in group_by_fields) if group_by_fields else None
                # Solo agregamos si la clave no existe
                if key is None or key not in seen_keys:
                    if key is not None:
                        seen_keys.add(key)
                    settlement_header_lines.append(row_dict)
        return settlement_header_lines

    def _parse_settlement(self, df_lines, external_bank_config_id, field_type):
        """Parsea una Cabecera de Liquidación"""
        settlement_header_config_id = external_bank_config_id.settlement_header_config_ids.filtered(
            lambda l: l.field_type == field_type
        )[:1]
        if not settlement_header_config_id:
            raise UserError(
                f'No se ha encontrado ninguna "Configuración de Cabecera de Liquidación" con el tipo "{field_type}"'
            )

        settlement_header_field_config_ids = self.env['settlement.header.field.config'].search([
            ('settlement_header_config_id', '=', settlement_header_config_id.id)
        ])
        if not settlement_header_field_config_ids:
            raise UserError(
                f'No se ha encontrado ningún "Campo de Configuración de Cabecera de Liquidación" '
                f'para la Configuración de Cabecera de Liquidación: "{settlement_header_config_id.name}"'
            )
        settlement_header_lines = []
        if field_type == 'txt':
            settlement_header_lines = self._parse_settlement_header_txt_pandas(
                settlement_header_field_config_ids, df_lines, settlement_header_config_id
            )
        elif field_type in ('xls', 'xlsx'):
            settlement_header_lines = self._parse_settlement_header_xls_pandas(
                settlement_header_field_config_ids, df_lines, settlement_header_config_id
            )
        return settlement_header_lines


    def _parse_transaction_detail_txt_pandas(self,  transaction_detail_field_config_ids, df_lines, transaction_detail_config):
        transaction_detail_lines = []
        if transaction_detail_config.search_type == 'txt_sw':
            for df_line in df_lines['line']:
                transaction_detail_dict = {}
                for field_config_id in transaction_detail_field_config_ids:
                    start_with = field_config_id.start_with
                    if not start_with:
                        raise UserError(
                            f'La configuración de la linea "{field_config_id.name}" debe tener un '
                            f'"Caracter de comienzo de linea (.txt)"'
                        )
                    if start_with and df_line.startswith(start_with):
                        transaction_detail_dict.update({
                            field_config_id.destination_field_id.name:
                                df_line[field_config_id.starting_position:field_config_id.end_position]
                        })
                if transaction_detail_dict:
                    transaction_detail_lines.append(transaction_detail_dict)
        return transaction_detail_lines


    #TODO CONTEMPLAT CASO EN DONDE TENGA EN LUNERO DE LIQUIDACION REPETIDO POR FILA PERO NO SEA DATE
    def _parse_transaction_detail_xls_pandas(
            self, transaction_detail_field_config_ids, df_lines, transaction_detail_config
    ):
        """
        Paso 1 -> excel_fixed_liquidation seguir por este caso
        Paso 2 -> excel_init_with_date
        Paso 3 -> ...
        """
        transaction_detail_lines = []

        # Validación inicial: solo dos tipos soportados
        if transaction_detail_config.search_type not in ('excel_init_with_date', 'excel_fixed_liquidation'):
            return transaction_detail_lines

        def build_row_dict(row, main_field, field_configs):
            """Construye un diccionario para una fila, asignando valores según configuración."""
            # Acceso por índice para el campo principal
            main_col_index = main_field.col - 1
            main_value = row[main_col_index] if 0 <= main_col_index < len(row) else None

            row_dict = {
                main_field.destination_field_id.name: main_value
            }

            for f_config in field_configs:
                if f_config.id == main_field.id or not f_config.col:
                    continue
                col_index = f_config.col - 1
                if 0 <= col_index < len(row):
                    value = row[col_index]  # Acceso por índice
                    row_dict[f_config.destination_field_id.name] = None if pd.isna(value) else value
            return row_dict

        if transaction_detail_config.search_type == 'excel_init_with_date':
            # Buscar campo de liquidación
            liquidation_field = next((f for f in transaction_detail_field_config_ids if f.is_liquidation_number), None)
            if not liquidation_field:
                raise UserError('Debes configurar un campo de liquidación')

            if not liquidation_field.col:
                raise UserError('Es obligatorio definir un campo con "is_liquidation_number" y "col"')

            if not (liquidation_field.origin_date_format and liquidation_field.dest_date_format):
                raise UserError('El campo de liquidación necesita formatos de fecha definidos')

            matched_rows = []
            for row in df_lines.itertuples(index=False):
                raw_value = getattr(row, df_lines.columns[liquidation_field.col - 1])
                try:
                    parsed_date = datetime.strptime(str(raw_value), liquidation_field.origin_date_format)
                    values = list(row)
                    values[liquidation_field.col - 1] = parsed_date.strftime(liquidation_field.dest_date_format)
                    matched_rows.append(values)
                except (ValueError, TypeError):
                    continue  # Ignorar filas no válidas

            matched_df = pd.DataFrame(matched_rows, columns=df_lines.columns)
            for row in matched_df.itertuples(index=False):
                transaction_detail_lines.append(
                    build_row_dict(row, liquidation_field, transaction_detail_field_config_ids))

        elif transaction_detail_config.search_type == 'excel_fixed_liquidation':
            # Campo fijo de liquidación en celda [2,2]
            fixed_row, fixed_col = 2, 2
            liquidation_value = None
            if 1 <= fixed_row <= len(df_lines) and 1 <= fixed_col <= len(df_lines.columns):
                liquidation_value = df_lines.iat[fixed_row - 1, fixed_col - 1]

            # Campo de liquidación tipo fila
            liquidation_field_row = next(
                (f for f in transaction_detail_field_config_ids if
                 f.is_liquidation_number and f.liquidation_type == 'row'),
                None
            )
            _logger.info(f'liquidation_field_row -> {liquidation_field_row}')

            matched_rows = []
            for row in df_lines.itertuples(index=False):
                # Obtener el valor por índice de columna en lugar de por nombre
                col_index = liquidation_field_row.col - 1
                if 0 <= col_index < len(row):
                    row_value = row[col_index]  # Acceso por índice
                    if row_value == liquidation_value:
                        matched_rows.append(row)
            _logger.info(f'matched_rows -> {matched_rows}')

            matched_df = pd.DataFrame(matched_rows, columns=df_lines.columns)
            for row in matched_df.itertuples(index=False):
                transaction_detail_lines.append(
                    build_row_dict(row, liquidation_field_row, transaction_detail_field_config_ids))

        return transaction_detail_lines

    def _parse_transaction2(self, df_lines, external_bank_config_id, field_type):
        transaction_detail_config_id = external_bank_config_id.transaction_detail_config_ids.filtered(
            lambda l: l.field_type == field_type
        )[:1]
        if not transaction_detail_config_id:
            raise UserError(
                f'No se ha encontrado ninguna "Configuración de Detalle de Transacción" con el tipo "{field_type}"'
            )
        transaction_detail_field_config_ids = self.env['transaction.detail.field.config'].search([
            ('transaction_detail_config_id', '=', transaction_detail_config_id.id)
        ])
        if not transaction_detail_field_config_ids:
            raise UserError(
                f'No se ha encontrado ningún "Campo de Configuración de Detalle de Transacción" '
                f'para la Configuración de Detalle de Transacción: "{transaction_detail_config_id.name}"'
            )
        transaction_detail_lines = []
        if field_type == 'txt':
            transaction_detail_lines = self._parse_transaction_detail_txt_pandas(
                transaction_detail_field_config_ids, df_lines, transaction_detail_config_id
            )
        elif field_type in ('xls', 'xlsx', 'csv'):
            transaction_detail_lines = self._parse_transaction_detail_xls_pandas(
                transaction_detail_field_config_ids, df_lines, transaction_detail_config_id
            )

        return transaction_detail_lines

    def _parse_transaction(self, line):
        """Parsea una línea de transacción"""
        return {
            'operation_date': self._parse_date(line[61:69]),
            'cover_terminal_posnet': int(line[82:91]),
            'summary_lot_posnet': int(line[91:94]),
            'coupon_posnet': int(line[94:99]),
            'total': float(f'{line[103:114]}.{line[114:116]}'),
            'card_number': line[152:171],
            'settlement_number': line[54:61],
        }

    def _parse_settlement_tax_txt_pandas(self, settlement_tax_ids, df_lines, settlement_tax_config_id):
        settlement_tax_lines = []
        if settlement_tax_config_id.search_type == 'txt_sw':
            for df_line in df_lines['line']:
                settlement_tax_dict = {}
                for field_config_id in settlement_tax_ids:
                    start_with = field_config_id.start_with
                    if not start_with:
                        raise UserError(
                            f'La configuración de la linea "{field_config_id.name}" debe tener un '
                            f'"Caracter de comienzo de linea (.txt)"'
                        )
                    if start_with and df_line.startswith(start_with):
                        tax_line_amounts = []
                        if field_config_id.field_type == 'base':
                            settlement_tax_dict.update({
                                field_config_id.destination_field_id.name:
                                    df_line[field_config_id.starting_position:field_config_id.end_position]
                            })

                        #TODO SEGUIR POR ACA
                        elif field_config_id.field_type == 'tax':
                            for settlement_tax_line_id in field_config_id.settlement_tax_line_ids:
                                init = settlement_tax_line_id.starting_position
                                long = settlement_tax_line_id.long
                                amount_str = df_line[init:init + long - 1]
                                decimals_amount = settlement_tax_line_id.decimals_amount
                                # TODO: PARAMETRIZAR OBTENCION DE SIGNO
                                sign_str = df_line[init + long - 1:init + long]
                                sign = 1 if sign_str == '1' else -1
                                tax_line_amounts.append(
                                    float(f'{amount_str[:-decimals_amount]}.{amount_str[-decimals_amount:]}') * sign
                                )
                                ########
                            settlement_tax_dict.update({
                                'settlement_tax_id': field_config_id.id,
                                'total': sum(tax_line_amounts)
                            })
                if settlement_tax_dict:
                    settlement_tax_lines.append(settlement_tax_dict)

        return settlement_tax_lines

    def _parse_settlement_tax_xls_pandas(self, settlement_tax_ids, df_lines, settlement_tax_config_id):
        """
        if settlement_header_config.search_type == 'excel_rc':
            settlement_header_dict = {}
            for field_config_id in settlement_header_field_config_ids:
                row = field_config_id.row
                col = field_config_id.col
                if not row or not col:
                    raise UserError(
                        f'La configuración de la linea "{field_config_id.name}" debe tener una "Fila" '
                        f'y una "Columna"'
                    )
                value = False
                if 1 <= row <= len(df_lines) and 1 <= col <= len(df_lines.columns):
                    value = df_lines.iat[row - 1, col - 1]

                if value:
                    settlement_header_dict[field_config_id.destination_field_id.name] = value
            settlement_header_lines.append(settlement_header_dict)
        """
        settlement_tax_lines = []
        if settlement_tax_config_id.search_type == 'excel_rc':
            settlement_tax_dict = {}
            for field_config_id in settlement_tax_ids:
                if field_config_id.field_type == 'base':
                    row = field_config_id.row
                    col = field_config_id.col
                    if not row or not col:
                        raise UserError(
                            f'La configuración de la linea "{field_config_id.name}" debe tener una "Fila" '
                            f'y una "Columna"'
                        )
                    value = False
                    if 1 <= row <= len(df_lines) and 1 <= col <= len(df_lines.columns):
                        value = df_lines.iat[row - 1, col - 1]
                    if value:
                        settlement_tax_dict[field_config_id.destination_field_id.name] = value
                if field_config_id.field_type == 'tax':
                    tax_line_amounts = []
                    for settlement_tax_line_id in field_config_id.settlement_tax_line_ids:
                        row = settlement_tax_line_id.row
                        col = settlement_tax_line_id.col
                        if not row or not col:
                            raise UserError(
                                f'La configuración de la linea "{field_config_id.name}" debe tener una "Fila" '
                                f'y una "Columna"'
                            )
                        value = False
                        if 1 <= row <= len(df_lines) and 1 <= col <= len(df_lines.columns):
                            value = df_lines.iat[row - 1, col - 1]
                        if value:
                            tax_line_amounts.append(
                                float(value)
                            )

                    settlement_tax_dict.update({
                        'settlement_tax_id': field_config_id.id,
                        'total': sum(tax_line_amounts)
                    })
            if settlement_tax_dict:
                settlement_tax_lines.append(settlement_tax_dict)
        elif settlement_tax_config_id.search_type == 'excel_tax_name':
            settlement_tax_dict = {}
            for field_config_id in settlement_tax_ids:
                if field_config_id.field_type == 'base':
                    row = field_config_id.row
                    col = field_config_id.col
                    if not row or not col:
                        raise UserError(
                            f'La configuración de la linea "{field_config_id.name}" debe tener una "Fila" '
                            f'y una "Columna"'
                        )
                    value = False
                    if 1 <= row <= len(df_lines) and 1 <= col <= len(df_lines.columns):
                        value = df_lines.iat[row - 1, col - 1]
                    if value:
                        settlement_tax_dict[field_config_id.destination_field_id.name] = value
                elif field_config_id.field_type == 'tax':
                    tax_line_amounts = []
                    for settlement_tax_line_id in field_config_id.settlement_tax_line_ids:
                        positions_amount = settlement_tax_line_id.positions_amount
                        direction = settlement_tax_line_id.direction
                        tax_name = settlement_tax_line_id.tax_name
                        value = False

                        match = df_lines.isin([tax_name])
                        if match.any().any():
                            row_idx, col_idx = match.stack()[match.stack()].index[0]

                            if direction == "Up":
                                target_row, target_col = row_idx - positions_amount, col_idx
                            elif direction == "Down":
                                target_row, target_col = row_idx + positions_amount, col_idx
                            elif direction == "Left":
                                target_row, target_col = row_idx, col_idx - positions_amount
                            elif direction == "Right":
                                target_row, target_col = row_idx, col_idx + positions_amount
                            else:
                                raise UserError(f"Dirección desconocida: {direction}")
                        # 4) Si se encontró valor numérico, lo guardo
                        if value:
                            tax_line_amounts.append(float(value))
                    settlement_tax_dict.update({
                        'settlement_tax_id': field_config_id.id,
                        'total': sum(tax_line_amounts)
                    })
            if settlement_tax_dict:
                settlement_tax_lines.append(settlement_tax_dict)
        elif settlement_tax_config_id.search_type == 'sum_col_row':
            base_field = next((f for f in settlement_tax_ids if f.field_type == 'base'), None)
            if not base_field or not getattr(base_field, 'col', None):
                raise UserError('Para search_type "sum_col_row" es obligatorio definir un campo "base" con "col"')

            base_col_idx = base_field.col - 1

            def normalize_settlement_value(raw_value):
                if pd.isna(raw_value):
                    return None
                s = str(raw_value).strip()
                if getattr(base_field, 'origin_date_format', None) and getattr(base_field, 'dest_date_format',
                                                                               None):
                    try:
                        parsed = datetime.strptime(s, base_field.origin_date_format)
                        return parsed.strftime(base_field.dest_date_format)
                    except (ValueError, TypeError):
                        return s
                return s

            def parse_number(val):
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return 0.0
                s = str(val).strip()
                if s == '':
                    return 0.0
                for token in ['$', '€', 'USD', 'ARS', ' ']:
                    s = s.replace(token, '')
                if s.count('.') > 0 and s.count(',') > 0:
                    s = s.replace('.', '').replace(',', '.')
                else:
                    s = s.replace(',', '.')
                try:
                    return float(s)
                except Exception:
                    return 0.0

            settlement_map = {}

            for row_idx in range(len(df_lines)):
                try:
                    settlement_raw = df_lines.iat[row_idx, base_col_idx]
                except Exception:
                    continue
                settlement_key = normalize_settlement_value(settlement_raw)
                if not settlement_key:
                    continue

                if settlement_key not in settlement_map:
                    settlement_map[settlement_key] = {}

                for settlement_tax in settlement_tax_ids:
                    if settlement_tax.field_type != 'tax':
                        continue
                    tax_total = settlement_map[settlement_key].get(settlement_tax.id, 0.0)
                    for tax_line in settlement_tax.settlement_tax_line_ids:
                        if not getattr(tax_line, 'col', None):
                            continue
                        col_idx = tax_line.col - 1
                        if 0 <= col_idx < len(df_lines.columns):
                            raw_val = df_lines.iat[row_idx, col_idx]
                            tax_total += parse_number(raw_val)
                    if tax_total:
                        settlement_map[settlement_key][settlement_tax.id] = tax_total

            # Convertir a formato compatible con _create_trailers
            for settlement_key, taxes in settlement_map.items():
                for tid, total in taxes.items():
                    settlement_tax_lines.append({
                        'settlement_number': settlement_key,
                        'settlement_tax_id': tid,
                        'total': total
                    })

        return settlement_tax_lines

    def _parse_trailer2(self, df_lines, external_bank_config_id, field_type):
        settlement_tax_config_id = external_bank_config_id.settlement_tax_config_ids.filtered(
            lambda l: l.field_type == field_type
        )[:1]
        if not settlement_tax_config_id:
            raise UserError(
                f'No se ha encontrado ninguna "Configuración de Impuesto" con el tipo "{field_type}"'
            )

        _logger.info(f'settlement_tax_config_id -> {settlement_tax_config_id}')
        settlement_tax_ids = self.env['settlement.tax'].search([
            ('settlement_tax_config_id', '=', settlement_tax_config_id.id)
        ])
        if not settlement_tax_ids:
            raise UserError(
                f'No se ha encontrado ningún "Campo de Configuración de Impuestos" '
                f'para la Configuración de Impuestos: "{settlement_tax_config_id.name}"'
            )

        settlement_tax_lines = []
        if field_type == 'txt':
            settlement_tax_lines = self._parse_settlement_tax_txt_pandas(
                settlement_tax_ids, df_lines, settlement_tax_config_id
            )
        elif field_type in ('xls', 'xlsx', 'csv'):
            settlement_tax_lines = self._parse_settlement_tax_xls_pandas(
                settlement_tax_ids, df_lines, settlement_tax_config_id
            )

        return settlement_tax_lines


    def _parse_trailer(self, line, last_product):
        """Parsea los trailers de impuesto"""
        external_statement_payment_method = self.env['external.statement.payment.methods'].search([
            ('name', '=', last_product)
        ], limit=1)
        settlement_tax_ids = self.env['settlement.tax'].search([
            ('active', '=', True), ('journal_ids', 'in', [external_statement_payment_method.journal_id.id])
        ])
        tax_dict = {
            'settlement_number': line[54:61],
            'settlement_trailers': []
        }
        for settlement_tax_id in settlement_tax_ids:
            tax_line_amounts = []
            for settlement_tax_line_id in settlement_tax_id.settlement_tax_line_ids:
                init = settlement_tax_line_id.starting_position
                long = settlement_tax_line_id.long
                amount_str = line[init:init + long - 1]
                decimals_amount = settlement_tax_line_id.decimals_amount
                sign_str = line[init + long - 1:init + long]
                sign = 1 if sign_str == '1' else -1
                tax_line_amounts.append(
                    float(f'{amount_str[:-decimals_amount]}.{amount_str[-decimals_amount:]}') * sign
                )
            tax_dict['settlement_trailers'].append((settlement_tax_id.id, sum(tax_line_amounts)))
        return tax_dict

    def _parse_date(self, date_str):
        """Convierte una cadena de fecha al formato de Odoo"""
        if not date_str or len(date_str) != 8 or not date_str.isdigit():
            return False

        try:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])

            # Validación básica de fecha
            if not (1 <= month <= 12 and 1 <= day <= 31):
                return False

            return f"{year:04d}-{month:02d}-{day:02d}"

        except (ValueError, TypeError):
            raise UserError('La fecha de una trasacción del extracto no es valida')
