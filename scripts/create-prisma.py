import pandas as pd
import re
import json
import os
import io
import logging
from typing import Dict, Any, List
from tqdm import tqdm # 進捗表示のためにtqdmを使用

# ----------------------------------------------------------------
# 1. ロギング設定とヘルパー関数
# ----------------------------------------------------------------

LOG_DIR = 'logs'
LOG_INFO_FILE = os.path.join(LOG_DIR, 'conversion_info.log')
LOG_ERROR_FILE = os.path.join(LOG_DIR, 'conversion_errors.log')

# グローバルなエラー状態フラグ
GLOBAL_ERROR_OCCURRED = False

def setup_logging():
    """ログファイルとコンソールへのロギングを設定する"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # ロガーの初期化
    logger = logging.getLogger('PrismaGenerator')
    logger.setLevel(logging.INFO)

    # 既存のハンドラをクリア
    if logger.hasHandlers():
        logger.handlers.clear()

    # INFOログファイルハンドラ
    info_handler = logging.FileHandler(LOG_INFO_FILE, mode='w', encoding='utf-8')
    info_handler.setLevel(logging.INFO)
    info_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    info_handler.setFormatter(info_formatter)
    logger.addHandler(info_handler)

    # ERRORログファイルハンドラ
    error_handler = logging.FileHandler(LOG_ERROR_FILE, mode='w', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)

    # コンソールハンドラ (すべてのレベルを出力)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger

LOGGER = setup_logging()

def log_info(message: str):
    """情報メッセージをコンソールとログファイルに出力する"""
    LOGGER.info(message)

def log_error(message: str, exit_on_error: bool = False):
    """エラーメッセージをコンソールとログファイルに出力し、グローバルエラーフラグを立てる"""
    global GLOBAL_ERROR_OCCURRED
    GLOBAL_ERROR_OCCURRED = True
    LOGGER.error(message)
    if exit_on_error:
        exit(1)

def to_pascal_case(snake_str: str) -> str:
    """snake_caseをPascalCaseに変換する (モデル名用)"""
    return ''.join(word.capitalize() for word in snake_str.split('_'))

def to_camel_case(snake_str: str) -> str:
    """snake_caseをcamelCaseに変換する (リレーションフィールド名用)"""
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])

# ----------------------------------------------------------------
# 2. MarkdownパースとDataFrame変換 (4.1)
# ----------------------------------------------------------------

def get_markdown_table_to_df(markdown_content: str, section_title: str) -> pd.DataFrame | None:
    """
    指定されたセクションタイトルのMarkdownテーブルをPandas DataFrameに変換する。
    """
    # 該当セクションのコンテンツを抽出
    pattern = re.escape(section_title) + r'\s*\n\s*\|.*?\n\s*\|-+\s*\|[\s\S]*?(\n\n|$)';
    match = re.search(pattern, markdown_content, re.DOTALL)

    if not match:
        log_info(f"セクション '{section_title}' が見つかりませんでした。")
        return None

    table_content = match.group(0)
    
    # 区切り線 (|---|---|) とヘッダ行より前の内容を削除
    lines = table_content.strip().split('\n')
    start_index = -1
    for i, line in enumerate(lines):
        if re.match(r'^\s*\|-+\s*\|', line):
            start_index = i
            break
    
    if start_index == -1:
        log_error(f"セクション '{section_title}' でテーブルの区切り行が見つかりません。")
        return None

    # ヘッダ行とデータ行のみを抽出して結合
    table_lines = [lines[start_index - 1]] + lines[start_index + 1:]
    
    # データをStringIOに渡し、pandasで読み込む
    try:
        df = pd.read_csv(io.StringIO('\n'.join(table_lines)), sep='|', skipinitialspace=True)
        
        # 4.1 処理内容に基づきDataFrameをクリーンアップ
        df.columns = df.columns.str.strip()
        
        # すべての文字列データをトリム
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.strip()
        
        # 先頭と末尾の空カラムを削除
        df = df.iloc[:, 1:-1]
        df.columns = df.columns.str.strip()

        # NaNや空文字列の行を削除（Markdownテーブルの空行対応）
        df.dropna(how='all', inplace=True)
        
        return df
    except Exception as e:
        log_error(f"セクション '{section_title}' のMarkdownテーブル変換中にエラーが発生しました: {e}")
        return None

# ----------------------------------------------------------------
# 3. テーブル一覧ファイルの解析 (4.2)
# ----------------------------------------------------------------

def parse_tables_overview(markdown_path: str, config: Dict[str, Any]) -> pd.DataFrame | None:
    """
    tables/tables.mdを解析し、全テーブルの概要DataFrameを返す。
    """
    log_info(f"テーブル一覧ファイル '{markdown_path}' の解析を開始します。")
    
    try:
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        log_error(f"テーブル一覧ファイルの読み込みに失敗しました: {e}", exit_on_error=True)
        return None

    # すべての##セクションを抽出し、Markdownテーブルをパース
    sections_raw = content.split('##')[1:]
    sections = [f"## {s.strip()}" for s in sections_raw if s.strip()]
    all_dfs = []
    
    expected_cols = list(config['validation_rules']['tables_overview_columns'].values())
    
    if not sections:
        log_error("テーブル一覧ファイル内に '##' で始まるセクションが見つかりませんでした。", exit_on_error=True)
        return None
        
    for section_content in tqdm(sections, desc="テーブル一覧ファイルのセクション解析"):
        # セクションタイトルを抽出 (## タイトル)
        section_title_match = re.search(r'^##\s*(.+)', section_content, re.MULTILINE)
        if section_title_match:
            section_title = section_title_match.group(1).strip()
            
            # MarkdownテーブルをDataFrameに変換
            df_section = get_markdown_table_to_df(section_content, f"## {section_title}")
            
            if df_section is not None and not df_section.empty:
                # 期待されるカラムの確認と再配置
                missing_cols = [col for col in expected_cols if col not in df_section.columns]
                for col in missing_cols:
                    df_section[col] = pd.NA
                
                df_section = df_section[expected_cols]
                all_dfs.append(df_section)
    
    if not all_dfs:
        log_error("有効なテーブル定義がテーブル一覧ファイルから抽出されませんでした。", exit_on_error=True)
        return None
        
    # 全テーブルのDataFrameを結合
    overview_df = pd.concat(all_dfs, ignore_index=True)
    
    # Markdownリンクから物理名とファイルパスを抽出
    def extract_link_data(link_str):
        match = re.search(r'\[(.*?)\]\((.*?)\)', str(link_str))
        if match:
            return match.group(1), match.group(2)
        return str(link_str), None

    # 一時的にリンクデータを保持
    link_data = overview_df[config['validation_rules']['tables_overview_columns']['TABLE_PHYSICAL_NAME']].apply(extract_link_data)
    
    # 物理名を抽出した値で上書きし、ファイルパスを新規カラムとして追加
    overview_df['__TABLE_PHYSICAL_NAME_CLEAN'] = [d[0] for d in link_data]
    overview_df['__FILE_PATH'] = [d[1] for d in link_data]

    # テーブル作成順序の一意性チェック
    sort_col = config['validation_rules']['tables_overview_columns']['TABLE_SORT']
    if overview_df[sort_col].duplicated().any():
        log_error("テーブル一覧ファイル内で 'テーブル作成順序' の値に重複があります。")
        
    log_info(f"テーブル一覧ファイルの解析が完了しました。計 {len(overview_df)} テーブルを検出。")
    return overview_df

# ----------------------------------------------------------------
# 4. 個別テーブルの解析とバリデーション (4.3)
# ----------------------------------------------------------------

def validate_and_parse_table(
    table_name_clean: str, 
    overview_row: pd.Series, 
    config: Dict[str, Any], 
    all_table_names: List[str],
    all_index_names: set,
    all_fk_names: set,
    db_docs_dir: str # db-docsディレクトリのパスを受け取る
) -> Dict[str, Any] | None:
    """
    個別のテーブル定義ファイルを読み込み、バリデーションと解析を行う。
    """
    # tablesディレクトリからの相対パスでファイルパスを構築
    # overview_row['__FILE_PATH'] は 'users.md' のような値
    table_file_path = os.path.join(db_docs_dir, 'tables', os.path.basename(overview_row['__FILE_PATH'] or f"{table_name_clean}.md"))
    log_info(f"-> テーブル '{table_name_clean}' ({table_file_path}) の検証を開始します...")

    try:
        with open(table_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        log_error(f"ファイル '{table_file_path}' の読み込みに失敗しました: {e}")
        return None

    # 各セクションをパース
    parsed_sections: Dict[str, pd.DataFrame] = {}
    validation_config = config['validation_rules']
    
    for key, title in validation_config['table_overview_sections'].items():
        df = get_markdown_table_to_df(content, title)
        if df is None:
            log_error(f"テーブル '{table_name_clean}' の必須セクション '{title}' が見つかりませんでした。")
            return None
        parsed_sections[key] = df
    
    # --- 4.3.1: ファイル名と概要の一致チェック ---
    try:
        # 1.テーブル概要セクションから情報を抽出
        overview_section_df = parsed_sections['OVERVIEW']

        # 概要DFを key-value形式に変換
        overview_map = overview_section_df.set_index(validation_config['table_overview_section_columns']['ITEM']).to_dict()['内容']
        
        # ファイル名と物理名の一致
        if overview_map[validation_config['table_overview_section_rows']['TABLE_PHYSICAL_NAME']] != table_name_clean:
            log_error(f"テーブル '{table_name_clean}': ファイル名と '1.テーブル概要' で定義された物理名が一致しません。")

        # tables.mdの概要情報との一致検証
        if overview_map[validation_config['table_overview_section_rows']['TABLE_NAME']] != overview_row[validation_config['tables_overview_columns']['TABLE_NAME']]:
            log_error(f"テーブル '{table_name_clean}': 論理名が tables.md の概要と一致しません。")
            
    except Exception as e:
        log_error(f"テーブル '{table_name_clean}': 概要情報の検証中にエラーが発生しました: {e}")
        return None

    # --- 4.3.2: 2.カラム定義のバリデーション ---
    column_df = parsed_sections['COLUMN_DEFINITION']
    col_map = validation_config['column_definition_columns']
    col_rules = validation_config['column_rules']

    # 必須監査カラムチェック
    for audit_col in validation_config['audit_columns']:
        col_name = audit_col['name']
        match = column_df[column_df[col_map['COLUMN_PHYSICAL_NAME']] == col_name]
        if match.empty:
            log_error(f"テーブル '{table_name_clean}': 必須監査カラム '{col_name}' が見つかりません。")
            continue
        row = match.iloc[0]
        
        # 型チェック (正規表現を使用)
        type_match = re.match(audit_col['type_regex'], str(row[col_map['TYPE']]).strip(), re.IGNORECASE)
        if not type_match:
            log_error(f"テーブル '{table_name_clean}': 監査カラム '{col_name}' の型 '{row[col_map['TYPE']]}' が要件と一致しません。")

        # NOTNULLチェック
        if str(row[col_map['NOTNULL']]) != audit_col['notnull']:
            log_error(f"テーブル '{table_name_clean}': 監査カラム '{col_name}' の NOTNULL が '{audit_col['notnull']}' ではありません。")

        # DEFAULTチェック
        if str(row[col_map['DEFAULT']]).strip() != audit_col['default']:
            # 'DEFAULT'が 'CURRENT_TIMESTAMP' の場合、正規表現でより柔軟にチェックする
            if audit_col['default'] != 'CURRENT_TIMESTAMP' or not re.match(r'^(CURRENT_TIMESTAMP|NOW\(\))$', str(row[col_map['DEFAULT']]).strip(), re.IGNORECASE):
                 log_error(f"テーブル '{table_name_clean}': 監査カラム '{col_name}' の DEFAULT が '{audit_col['default']}' と一致しません。")

    # カラム論理名/物理名の一意性、空チェック
    if column_df[col_map['COLUMN_NAME']].duplicated().any() or column_df[col_map['COLUMN_NAME']].isna().any():
        log_error(f"テーブル '{table_name_clean}': カラム論理名に重複または空の値があります。")
    if column_df[col_map['COLUMN_PHYSICAL_NAME']].duplicated().any() or column_df[col_map['COLUMN_PHYSICAL_NAME']].isna().any():
        log_error(f"テーブル '{table_name_clean}': カラム物理名に重複または空の値があります。")
        
    pk_cols = column_df[column_df[col_map['PK']] == 'PK']
    
    # PKが単一の場合
    if len(pk_cols) == 1 and pk_cols.iloc[0][col_map['COLUMN_PHYSICAL_NAME']] == 'id':
        if pk_cols.iloc[0][col_map['FK']] != col_rules['NA_MARK']:
             log_error(f"テーブル '{table_name_clean}': 単一PK 'id' は外部キーであってはなりません。")

    # PKが複合の場合のチェックは省略（設計書に従い複合IDの存在と規則をチェックするが、具体的な複合規則の定義がないため、ここではIDの有無のみ確認）
    if len(pk_cols) > 1 and not (any(re.match(col_rules['PK_PHYSICAL_NAME'], c) for c in pk_cols[col_map['COLUMN_PHYSICAL_NAME']])):
        log_error(f"テーブル '{table_name_clean}': 複合PKの場合、PKカラムの命名規則 '{col_rules['PK_PHYSICAL_NAME']}' に合致しないカラムがあります。")

    # NOTNULLとDEFAULTのチェック
    for _, row in column_df.iterrows():
        if row[col_map['NOTNULL']] == 'NN' and str(row[col_map['DEFAULT']]).strip().upper() == 'NULL':
            log_error(f"テーブル '{table_name_clean}': NOTNULL='NN' のカラム '{row[col_map['COLUMN_PHYSICAL_NAME']]}' の DEFAULT が 'NULL' です。")

    # ナチュラルキーチェック (4.3.2の後半)
    for _, row in column_df.iterrows():
        col_phys_name = row[col_map['COLUMN_PHYSICAL_NAME']]
        if re.match(col_rules['NK_PHYSICAL_NAME'], col_phys_name):
            is_fk = row[col_map['FK']] == 'FK'
            is_pk = row[col_map['PK']] == 'PK'
            is_unique = re.match(col_rules['UNIQUE'], str(row[col_map['UNIQUE']])) and str(row[col_map['UNIQUE']]) != col_rules['NA_MARK']
            is_nn = row[col_map['NOTNULL']] == 'NN'
            is_self_nk = col_phys_name == f"{table_name_clean}_no"

            is_unique_required = not (is_fk and not is_self_nk and not is_pk)

            if is_unique_required:
                if not (is_unique or is_pk) or not is_nn:
                    log_error(f"テーブル '{table_name_clean}', NK '{col_phys_name}': UNIQUEが必須です。UNIQUE('UKx'または'PK')かつNOTNULL('NN')でなければなりません。")
            else:
                if not is_nn:
                    log_error(f"テーブル '{table_name_clean}', NK '{col_phys_name}': UNIQUEが必須ではない場合でも、NOTNULL('NN')は必須です。")


    # --- 4.3.3: 3.インデックス定義のバリデーション ---
    index_df = parsed_sections['INDEX_DEFINITION']
    index_map = validation_config['index_definition_columns']
    index_rules = validation_config['index_rules']
    
    for _, row in index_df.iterrows():
        idx_name = str(row[index_map['INDEX_NAME']])
        
        # 物理名重複チェック（全テーブル間）
        if idx_name in all_index_names:
            log_error(f"テーブル '{table_name_clean}', インデックス '{idx_name}': 他のテーブルでインデックス名が重複しています。")
        all_index_names.add(idx_name)

        # 命名規則チェック
        if not re.match(index_rules['INDEX_NAME'], idx_name):
            log_error(f"テーブル '{table_name_clean}', インデックス '{idx_name}': 命名規則 '{index_rules['INDEX_NAME']}' に違反しています。")
            
        # カラム存在チェック
        idx_cols = [c.strip() for c in str(row[index_map['COLUMN_PHYSICAL_NAME']]).split(',')]
        for c in idx_cols:
            if c not in column_df[col_map['COLUMN_PHYSICAL_NAME']].values:
                log_error(f"テーブル '{table_name_clean}', インデックス '{idx_name}': カラム '{c}' はテーブルに存在しません。")
                
        # B-tree/Hashとソート順のチェック
        idx_type = str(row[index_map['TYPE']])
        idx_sort = str(row[index_map['SORT']])
        if idx_type == 'B-tree' and idx_sort == index_rules['SORT'].split('|')[-1].strip('^$()'): # '-'に対応
             log_error(f"テーブル '{table_name_clean}', インデックス '{idx_name}': B-treeインデックスにはソート順が必要です。")
        if idx_type == 'Hash' and idx_sort != index_rules['SORT'].split('|')[-1].strip('^$()'): # '-'に対応
             log_error(f"テーブル '{table_name_clean}', インデックス '{idx_name}': Hashインデックスにはソート順は不要です ('-')。")


    # --- 4.3.4: 4.外部キー定義のバリデーション ---
    fk_df = parsed_sections['FK_DEFINITION']
    fk_map = validation_config['foreign_key_definition_columns']
    fk_rules = validation_config['fk_rules']
    
    defined_fk_cols = set()
    
    for _, row in fk_df.iterrows():
        fk_name = str(row[fk_map['FK_NAME']])
        source_col = str(row[fk_map['SOURCE_COLUMN']])
        dest_table = str(row[fk_map['DEST_TABLE']])
        
        # 外部キー名重複チェック（全テーブル間）
        if fk_name in all_fk_names:
            log_error(f"テーブル '{table_name_clean}', FK '{fk_name}': 他のテーブルで外部キー名が重複しています。")
        all_fk_names.add(fk_name)

        # 参照元カラムが'FK'マークされていること
        source_col_row = column_df[column_df[col_map['COLUMN_PHYSICAL_NAME']] == source_col]
        if source_col_row.empty or source_col_row.iloc[0][col_map['FK']] != 'FK':
            log_error(f"テーブル '{table_name_clean}', FK '{fk_name}': 参照元カラム '{source_col}' はカラム定義で 'FK' としてマークされていません。")
        
        defined_fk_cols.add(source_col)
        
        # ON DELETE/ON UPDATEのチェック
        if not re.match(fk_rules['ON_DELETE'], str(row[fk_map['ON_DELETE']])):
            log_error(f"テーブル '{table_name_clean}', FK '{fk_name}': ON DELETE の値が不正です。")
        if not re.match(fk_rules['ON_UPDATE'], str(row[fk_map['ON_UPDATE']])):
            log_error(f"テーブル '{table_name_clean}', FK '{fk_name}': ON UPDATE の値が不正です。")

        # 参照先テーブルの存在チェック
        if dest_table not in all_table_names:
            log_error(f"テーブル '{table_name_clean}', FK '{fk_name}': 参照先テーブル '{dest_table}' がテーブル一覧に存在しません。")

    # 'FK'マークされているすべてのカラムが外部キー定義に記載されていること
    marked_fk_cols = column_df[column_df[col_map['FK']] == 'FK'][col_map['COLUMN_PHYSICAL_NAME']].values
    if not set(marked_fk_cols).issubset(defined_fk_cols):
        missing_fks = set(marked_fk_cols) - defined_fk_cols
        log_error(f"テーブル '{table_name_clean}': カラム定義で 'FK' とマークされているカラム {missing_fks} が外部キー定義に記載されていません。")
        
    log_info(f"-> テーブル '{table_name_clean}' の検証を完了しました。")

    # 解析されたデータを統合して返す
    return {
        'overview': overview_map,
        'columns': column_df,
        'indexes': index_df,
        'foreign_keys': fk_df
    }

# ----------------------------------------------------------------
# 5. Prismaスキーマ生成 (4.4)
# ----------------------------------------------------------------

def convert_to_prisma_model(
    table_name: str, 
    table_data: Dict[str, Any], 
    config: Dict[str, Any], 
    all_tables_data: Dict[str, Any]
) -> str | None:
    """
    解析されたテーブル定義データからPrismaスキーマのモデル定義文字列を生成する。
    """
    columns_df = table_data['columns']
    fk_df = table_data['foreign_keys']
    
    prisma_schema: List[str] = []
    
    model_name = to_pascal_case(table_name)
    table_logical_name = table_data['overview'][config['validation_rules']['table_overview_section_rows']['TABLE_NAME']]
    
    # モデル定義開始とコメント付与 (4.4)
    prisma_schema.append(f"/// {table_logical_name}")
    prisma_schema.append(f"model {model_name} {{")

    # カラム定義の生成
    pk_cols: List[str] = []
    unique_constraints: Dict[str, List[str]] = {}
    
    # リレーションフィールド名の重複チェック用
    relation_fields_used: set = set()

    for _, row in columns_df.iterrows():
        col_name_jp = str(row[config['validation_rules']['column_definition_columns']['COLUMN_NAME']])
        col_phys_name = str(row[config['validation_rules']['column_definition_columns']['COLUMN_PHYSICAL_NAME']])
        col_type_str = str(row[config['validation_rules']['column_definition_columns']['TYPE']])
        is_pk = row[config['validation_rules']['column_definition_columns']['PK']] == 'PK'
        is_fk = row[config['validation_rules']['column_definition_columns']['FK']] == 'FK'
        is_unique_val = str(row[config['validation_rules']['column_definition_columns']['UNIQUE']])
        is_notnull = row[config['validation_rules']['column_definition_columns']['NOTNULL']] == 'NN'
        default_val = str(row[config['validation_rules']['column_definition_columns']['DEFAULT']]).strip()
        
        # 1. 型マッピング
        type_parts = re.split(r'\(|\)', col_type_str.split('(')[0].strip())
        mysql_type = type_parts[0].upper()
        
        prisma_type = config['type_mappings'].get(mysql_type, 'String') # 見つからなければStringをデフォルトとする
        
        # Prisma型に合わせた特殊アノテーション
        prisma_attrs: List[str] = []
        db_type_attr = ''

        # VARCHAR(X)などの桁数定義 (@db.VarChar(X))
        size_match = re.search(r'\((.*?)\)', col_type_str)
        if size_match and mysql_type in ['VARCHAR', 'CHAR', 'DECIMAL']:
            # DECIMAL(P,S)やVARCHAR(X)に対応
            db_type_attr = f"@db.{mysql_type}({size_match.group(1)})"
            if mysql_type == 'DECIMAL':
                prisma_type = 'Float' # DECIMALはFloatまたはDecimalにマップするが、ここではFloatとする
                db_type_attr = f"@db.Decimal({size_match.group(1)})"

        # 2. Null許容 (?)
        nullability = '' if is_notnull else '?'

        # 3. PK, UNIQUE, DEFAULT, UPDATEDAT
        if is_pk:
            pk_cols.append(col_phys_name)
            prisma_attrs.append('@id')
            if default_val == 'auto_increment' and prisma_type in ['Int', 'BigInt']:
                prisma_attrs.append('@default(autoincrement())')
                
        # 複合ユニーク制約の処理 (UKx)
        if re.match(r'UK\d{1,2}', is_unique_val):
            if is_unique_val not in unique_constraints:
                unique_constraints[is_unique_val] = []
            unique_constraints[is_unique_val].append(col_phys_name)
        
        # @unique (単一カラムユニーク)
        elif is_unique_val == 'UK': # 単一ユニークキーは通常はPK/UKxと競合しないが、念のため
             prisma_attrs.append('@unique')

        # @updatedAt
        if col_phys_name == 'updated_at':
            prisma_attrs.append('@updatedAt')
        
        # @default
        elif not is_pk and default_val not in ['-', 'auto_increment', 'NULL']:
            if prisma_type == 'String':
                prisma_attrs.append(f"@default(\"{default_val}\")")
            elif prisma_type == 'DateTime' and default_val.upper() in ['CURRENT_TIMESTAMP', 'NOW()']:
                 prisma_attrs.append("@default(now())")
            else:
                prisma_attrs.append(f"@default({default_val})")
        
        # 4. FKとリレーションの処理
        if is_fk:
            # 外部キー定義から対応する行を検索
            fk_row_match = fk_df[fk_df[config['validation_rules']['foreign_key_definition_columns']['SOURCE_COLUMN']] == col_phys_name]
            
            if not fk_row_match.empty:
                fk_row = fk_row_match.iloc[0]
                dest_table_phys = fk_row[config['validation_rules']['foreign_key_definition_columns']['DEST_TABLE']]
                dest_table_model = to_pascal_case(dest_table_phys)
                
                # リレーションフィールド名の生成
                fk_name = str(fk_row[config['validation_rules']['foreign_key_definition_columns']['FK_NAME']])
                relation_field_name = to_camel_case(fk_name.replace('fk_', ''))
                
                if relation_field_name in relation_fields_used:
                    log_error(f"テーブル '{table_name}': リレーションフィールド名 '{relation_field_name}' が重複しています。FK名 '{fk_name}' を修正してください。", exit_on_error=True)
                    return None
                relation_fields_used.add(relation_field_name)

                on_delete = str(fk_row[config['validation_rules']['foreign_key_definition_columns']['ON_DELETE']]).upper()
                on_update = str(fk_row[config['validation_rules']['foreign_key_definition_columns']['ON_UPDATE']]).upper()
                
                # リレーションアノテーションの構築
                relation_attrs = f"fields:[{col_phys_name}], references:[{fk_row[config['validation_rules']['foreign_key_definition_columns']['DEST_COLUMN']]}]"
                if on_delete != 'NO ACTION':
                    relation_attrs += f", onDelete: {on_delete}"
                if on_update != 'NO ACTION':
                    relation_attrs += f", onUpdate: {on_update}"
                
                # リレーションフィールドの追加 (FKカラムの下に追加)
                prisma_schema.append(f"  {relation_field_name} {dest_table_model} @relation({relation_attrs})")

        # カラムコメントと本体の出力
        attrs_str = ' '.join([attr for attr in prisma_attrs if attr])
        
        # カラムコメント (4.4)
        prisma_schema.append(f"  /// {col_name_jp}")
        # 本体: 物理名 型 Null可否 属性 DB型
        prisma_schema.append(f"  {col_phys_name} {prisma_type}{nullability} {attrs_str} {db_type_attr}".strip())
    
    # --- 複合制約の定義 ---
    
    # 複合PK (@@id)
    if len(pk_cols) > 1:
        pk_cols_str = ', '.join(pk_cols)
        prisma_schema.append(f"\n  @@id([ {pk_cols_str} ])")
        
    # 複合UNIQUE (@@unique)
    for _, cols in unique_constraints.items():
        cols_str = ', '.join(cols)
        prisma_schema.append(f"  @@unique([ {cols_str} ])")

    # --- 逆リレーション (Inverse Relations) の追加 ---
    for target_name, target_data in all_tables_data.items():
        # 自分を参照している外部キーを検索
        target_fks = target_data['foreign_keys']
        inverse_fks = target_fks[target_fks[config['validation_rules']['foreign_key_definition_columns']['DEST_TABLE']] == table_name]

        for _, fk_row in inverse_fks.iterrows():
            # 逆リレーションフィールド名を生成 (モデル名 + Suffix)
            fk_name = str(fk_row[config['validation_rules']['foreign_key_definition_columns']['FK_NAME']])
            
            # リレーションフィールド名からFK名を決定 (重複防止のため、FK名 + TargetModelSuffix)
            base_relation_name = to_camel_case(fk_name.replace('fk_', ''))
            
            # リレーションフィールド名は、テーブル名（複数形）とする (例: User.reservations)
            inverse_field_name = to_camel_case(target_name) + 's' 

            # リレーション名の調整 (自己参照や多重リレーションの場合に必要)
            relation_name = ""
            if base_relation_name != to_camel_case(table_name):
                 relation_name = f", name: \"{base_relation_name}\""

            # 逆リレーションを追加 (例: reservations Reservation[])
            prisma_schema.append(f"  {inverse_field_name} {to_pascal_case(target_name)}[]{relation_name}")

    prisma_schema.append(f"\n  @@map(\"{table_name}\")") # DBテーブル名のアノテーション
    prisma_schema.append("}")
    
    return "\n".join(prisma_schema)

# ----------------------------------------------------------------
# 6. メイン処理 (3. 処理概要)
# ----------------------------------------------------------------

def main():
    """スクリプトのメイン処理"""
    log_info("--- Prismaスキーマ自動生成スクリプトを開始します ---")
    
    # 0. パス定義 (スクリプトの実行場所に関わらず、ファイル位置を正確に特定する)
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.json')
    
    DB_DOCS_DIR = os.path.dirname(SCRIPT_DIR)
    TABLES_MD_PATH = os.path.join(DB_DOCS_DIR, 'tables', 'tables.md')
    
    PROJECT_ROOT_DIR = os.path.dirname(DB_DOCS_DIR)
    OUTPUT_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, 'sandbox', 'prisma')

    OUTPUT_MODEL_DIR = os.path.join(OUTPUT_BASE_DIR, 'model')
    
    # 1. 設定ファイルの読み込み
    try:
        config = load_config(CONFIG_PATH)
    except Exception as e:
        log_error(f"設定ファイルの読み込みまたはパースに失敗しました: {e} (パス: {CONFIG_PATH})", exit_on_error=True)
        return

    # 2. テーブル一覧ファイルの解析
    overview_df = parse_tables_overview(TABLES_MD_PATH, config)
    if overview_df is None:
        log_error("テーブル一覧ファイルの解析に失敗しました。処理を終了します。", exit_on_error=True)
        return

    all_table_names = overview_df['__TABLE_PHYSICAL_NAME_CLEAN'].tolist()
    all_tables_data: Dict[str, Any] = {}
    all_index_names: set = set()
    all_fk_names: set = set()
    
    # 3. 個別テーブル定義ファイルの解析とバリデーション (テーブル作成順序順に処理)
    # ソート順で処理することで、参照先のテーブルが先に定義されることをシミュレート（必須ではないが推奨）
    sorted_df = overview_df.sort_values(by=config['validation_rules']['tables_overview_columns']['TABLE_SORT'])
    
    log_info(f"\n--- 個別テーブル定義ファイル ({len(sorted_df)}件) の解析とバリデーションを開始します ---")
    
    for _, row in tqdm(sorted_df.iterrows(), total=len(sorted_df), desc="テーブル検証"):
        table_phys_name = row['__TABLE_PHYSICAL_NAME_CLEAN']
        
        # db-docsのルートパスを渡す
        parsed_data = validate_and_parse_table(
            table_phys_name, 
            row, 
            config, 
            all_table_names,
            all_index_names,
            all_fk_names,
            DB_DOCS_DIR 
        )
        
        if parsed_data:
            all_tables_data[table_phys_name] = parsed_data
    
    if GLOBAL_ERROR_OCCURRED:
        log_error("\n致命的なバリデーションエラーが発生しました。Prismaスキーマの生成を中止します。", exit_on_error=True)
        return

    # 4. Prismaスキーマの生成
    log_info("\n--- Prismaスキーマモデル定義の生成を開始します ---")
    model_schemas: Dict[str, str] = {}
    
    for table_name, data in tqdm(all_tables_data.items(), desc="Prismaモデル生成"):
        schema = convert_to_prisma_model(table_name, data, config, all_tables_data)
        if schema:
            model_schemas[table_name] = schema
        else:
            log_error(f"テーブル '{table_name}' のモデル生成に失敗しました。")
            
    if GLOBAL_ERROR_OCCURRED:
        log_error("\n致命的なエラーが発生したため、ファイル出力を中止します。", exit_on_error=True)
        return
        
    # 5. Prismaスキーマファイルの出力 (3. 処理概要 Step 5)
    log_info("\n--- Prismaスキーマファイルの出力処理を開始します ---")
    
    # 出力ディレクトリの作成
    os.makedirs(OUTPUT_MODEL_DIR, exist_ok=True)
    
    imported_models: List[str] = []

    # 5.1 モデルファイル (.prisma) の書き込み
    for table_name, schema in model_schemas.items():
        model_name = to_pascal_case(table_name)
        file_path = os.path.join(OUTPUT_MODEL_DIR, f"{model_name}.prisma")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(schema)
            # base.prismaからの相対パスとしてimport文を生成
            imported_models.append(f"@import ./model/{model_name}.prisma")
            log_info(f"モデルファイルを出力しました: {file_path}")
        except Exception as e:
            log_error(f"モデルファイル '{file_path}' の書き込みに失敗しました: {e}")

    # 5.2 メインファイル (base.prisma) の書き込み
    BASE_PRISMA_CONTENT = f"""
// ----------------------------------------------------------------
// Prisma Schema Main File (base.prisma) - Auto Generated
// ----------------------------------------------------------------

datasource db {{
  provider = "mysql"
  url      = env("DATABASE_URL")
}}

generator client {{
  provider = "prisma-client-js"
}}

// --- Model Imports (npx prisma-import) ---
{os.linesep.join(imported_models)}
"""
    base_file_path = os.path.join(OUTPUT_BASE_DIR, 'base.prisma')
    try:
        with open(base_file_path, 'w', encoding='utf-8') as f:
            f.write(BASE_PRISMA_CONTENT.strip())
        log_info(f"メインファイルを出力しました: {base_file_path}")
    except Exception as e:
        log_error(f"メインファイル '{base_file_path}' の書き込みに失敗しました: {e}")

    log_info("\n--- Prismaスキーマ自動生成スクリプトを完了しました ---")
    
    if GLOBAL_ERROR_OCCURRED:
        log_error(f"スクリプト実行中にエラーが発生しました。終了コード 1 で終了します。詳細: {LOG_ERROR_FILE}")
        exit(1)

# 設定ファイルを読み込むヘルパー関数 (try-exceptでエラーを捕捉)
def load_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

if __name__ == "__main__":
    
    # スクリプトの実行場所に関わらず、ファイル位置を正確に特定する
    # SCRIPT_DIR: /path/to/db-docs/scripts
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    # DB_DOCS_DIR: /path/to/db-docs
    DB_DOCS_DIR = os.path.dirname(SCRIPT_DIR)
    
    # 必須入力ファイルのパスを定義
    CONFIG_PATH_MOCK = os.path.join(SCRIPT_DIR, 'config.json')
    TABLES_MD_PATH_MOCK = os.path.join(DB_DOCS_DIR, 'tables', 'tables.md')
    TABLES_DIR_MOCK = os.path.join(DB_DOCS_DIR, 'tables')
    
    # 実行に必要なモックの入力ファイルが存在しない場合、作成を促す
    if not os.path.exists(TABLES_MD_PATH_MOCK):
        print("--- ⚠️ 必須入力ファイルのモックを作成します ⚠️ ---")
        os.makedirs(TABLES_DIR_MOCK, exist_ok=True)
        
        # tables.md のモック
        mock_tables_md = """
# テーブル一覧

## ユーザー管理
| テーブル論理名 | テーブル物理名 | 概要 | テーブル作成順序 | 備考 |
|---|---|---|---|---|
| ユーザー情報 | [users](./users.md) | システム利用者の基本情報 | 10 | - |

## 予約管理
| テーブル論理名 | テーブル物理名 | 概要 | テーブル作成順序 | 備考 |
|---|---|---|---|---|
| 予約情報 | [reservations](./reservations.md) | ユーザーの予約履歴 | 20 | - |
"""
        with open(TABLES_MD_PATH_MOCK, 'w', encoding='utf-8') as f:
            f.write(mock_tables_md)
            print(f"{TABLES_MD_PATH_MOCK} (モック) を作成しました。")

        # users.md のモック (参照元)
        mock_users_md = """
# ユーザー情報

## 1.テーブル概要
| 項目 | 内容 | 備考 |
|---|---|---|
| テーブル論理名 | ユーザー情報 | - |
| テーブル物理名 | users | - |
| テーブル概要 | システムの利用者情報 | - |
| テーブル系統 | ユーザー管理 | - |

## 2.カラム定義
| カラム論理名 | カラム物理名 | 型(桁,精度) | PK | FK | UNIQUE | NOTNULL | DEFAULT | 備考 |
|---|---|---|---|---|---|---|---|---|
| ユーザーID | id | INT | PK | - | - | NN | auto_increment | 主キー |
| ユーザー名 | name | VARCHAR(255) | - | - | - | NN | - | 利用者名 |
| 登録日 | registered_at | TIMESTAMP | - | - | - | NN | CURRENT_TIMESTAMP | 登録日時 |
| 登録者 | registered_by | VARCHAR(255) | - | - | - | NN | - | 登録者ID |
| 更新日 | updated_at | TIMESTAMP | - | - | - | NN | CURRENT_TIMESTAMP | 更新日時 |
| 更新者 | updated_by | VARCHAR(255) | - | - | - | NN | - | 更新者ID |
| 削除フラグ | is_deleted | TINYINT | - | - | - | NN | 0 | 削除状態 |

## 3.インデックス定義
| インデックス物理名 | カラム物理名 | UNIQUE | インデックスタイプ | ソート順 | 備考 |
|---|---|---|---|---|---|
| idx_user_name | name | - | B-tree | ASC | 氏名による検索用 |

## 4.外部キー定義
| 外部キー物理名 | 参照元カラム物理名 | 参照先テーブル物理名 | 参照先カラム物理名 | ON DELETE | ON UPDATE | 備考 |
|---|---|---|---|---|---|---|
"""
        with open(os.path.join(TABLES_DIR_MOCK, 'users.md'), 'w', encoding='utf-8') as f:
            f.write(mock_users_md)
            print(f"{os.path.join(TABLES_DIR_MOCK, 'users.md')} (モック) を作成しました。")
            
        # reservations.md のモック (参照先として使用)
        mock_reservations_md = """
# 予約情報

## 1.テーブル概要
| 項目 | 内容 | 備考 |
|---|---|---|
| テーブル論理名 | 予約情報 | - |
| テーブル物理名 | reservations | - |
| テーブル概要 | ユーザーの予約履歴 | - |
| テーブル系統 | 予約管理 | - |

## 2.カラム定義
| カラム論理名 | カラム物理名 | 型(桁,精度) | PK | FK | UNIQUE | NOTNULL | DEFAULT | 備考 |
|---|---|---|---|---|---|---|---|---|
| 予約ID | id | INT | PK | - | - | NN | auto_increment | 主キー |
| ユーザーID | users_id | INT | - | FK | - | NN | - | users.idへの外部キー |
| 予約日時 | reservation_date | DATETIME | - | - | - | NN | - | 予約時刻 |
| 登録日 | registered_at | TIMESTAMP | - | - | - | NN | CURRENT_TIMESTAMP | 登録日時 |
| 登録者 | registered_by | VARCHAR(255) | - | - | - | NN | - | 登録者ID |
| 更新日 | updated_at | TIMESTAMP | - | - | - | NN | CURRENT_TIMESTAMP | 更新日時 |
| 更新者 | updated_by | VARCHAR(255) | - | - | - | NN | - | 更新者ID |
| 削除フラグ | is_deleted | TINYINT | - | - | - | NN | 0 | 削除状態 |

## 3.インデックス定義
| インデックス物理名 | カラム物理名 | UNIQUE | インデックスタイプ | ソート順 | 備考 |
|---|---|---|---|---|---|
| idx_res_user | users_id | - | B-tree | ASC | ユーザー別検索 |

## 4.外部キー定義
| 外部キー物理名 | 参照元カラム物理名 | 参照先テーブル物理名 | 参照先カラム物理名 | ON DELETE | ON UPDATE | 備考 |
|---|---|---|---|---|---|---|
| fk_res_user | users_id | users | id | CASCADE | NO ACTION | ユーザーが削除されたら予約も削除 |
"""
        with open(os.path.join(TABLES_DIR_MOCK, 'reservations.md'), 'w', encoding='utf-8') as f:
            f.write(mock_reservations_md)
            print(f"{os.path.join(TABLES_DIR_MOCK, 'reservations.md')} (モック) を作成しました。")
        print("--- 続行するために、必要な変更を加えてスクリプトを実行してください ---")


    if not os.path.exists(CONFIG_PATH_MOCK):
        print(f"致命的エラー: 設定ファイル '{CONFIG_PATH_MOCK}' が見つかりません。先に config.json を作成してください。")
        exit(1)
        
    main()
