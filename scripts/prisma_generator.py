import pandas as pd
import re
import json
import os
import io
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging
import stringcase

# --- 定数と設定の動的解決 ---
# スクリプト自身のディレクトリ
SCRIPT_DIR = Path(__file__).resolve().parent

# プロジェクトのルートディレクトリ /workspace/db-docs
PROJECT_ROOT = Path(SCRIPT_DIR).parent

# 親プロジェクト(ワークスペース)のルート /workspace
WORKSPACE_ROOT = PROJECT_ROOT.parent

# 入力ファイル
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.json')  # scripts/config.json
TABLES_MD_PATH = os.path.join(PROJECT_ROOT, 'tables', 'tables.md') # tables/tables.md

# 出力/ログファイル
LOG_DIR = os.path.join(WORKSPACE_ROOT, 'logs/db-docs')
OUTPUT_BASE_DIR = os.path.join(WORKSPACE_ROOT, 'sandbox', 'prisma') # sandbox/prisma
OUTPUT_MODEL_DIR = os.path.join(OUTPUT_BASE_DIR, 'model')
BASE_PRISMA_FILE = os.path.join(OUTPUT_BASE_DIR, 'base.prisma')


# --- グローバル変数 ---
config: Dict[str, Any] = {}
all_tables_fk_data: Dict[str, List[Dict]] = {}
all_table_names: Dict[str, str] = {} # {物理名: モデル名}
all_model_names: List[str] = []
all_fk_names: List[str] = []
global_error_count = 0

# --- ロギング設定関数 ---

def setup_logging():
    """
    loggingモジュールを設定する。
    """
    # 既存のロガー設定をクリア (複数回実行された場合のため)
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    # ロガーの設定
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger()
    
    # 1. コンソールハンドラ (INFO以上)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(console_handler)

    # 2. ファイルハンドラ (INFO以上)
    info_file_handler = logging.FileHandler(os.path.join(LOG_DIR, 'conversion_info.log'), encoding='utf-8')
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(info_file_handler)

    # 3. ファイルハンドラ (WARN以上)
    error_file_handler = logging.FileHandler(os.path.join(LOG_DIR, 'conversion_warn.log'), encoding='utf-8')
    error_file_handler.setLevel(logging.WARNING)
    error_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(error_file_handler)
    
    # 4. ファイルハンドラ (ERROR以上)
    error_file_handler = logging.FileHandler(os.path.join(LOG_DIR, 'conversion_error.log'), encoding='utf-8')
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(error_file_handler)

# --- ユーティリティ関数 ---

def log_error_and_count(message: str):
    """エラーメッセージをlog_error_and_countで出力し、グローバルカウンタをインクリメントする"""
    global global_error_count
    global_error_count += 1
    logging.error(message)

def parse_type_and_length(type_str: str) -> Dict[str, Any]:
    """型(桁,精度)から型名、桁数、精度を抽出 (4.3)"""
    result = {'type': type_str, 'length': None, 'precision': None}
    
    match_dims = re.search(r'(\w+)\s*\(([\d,\s]+)\)', type_str)
    if match_dims:
        base_type = match_dims.group(1).upper()
        dims = [d.strip() for d in match_dims.group(2).split(',')]
        
        result['type'] = base_type
        if base_type in ['CHAR', 'VARCHAR']:
            result['length'] = int(dims[0])
        elif base_type == 'DECIMAL':
            if len(dims) == 2:
                result['length'] = int(dims[0])
                result['precision'] = int(dims[1])
            else:
                pass # バリデーションエラーは呼び出し元で処理
        
    return result
def get_markdown_table_to_df(content: str, section_title: str) -> pd.DataFrame:
    """
    Markdownのセクションからテーブルを抽出しDataFrameに変換する。
    セクションタイトルでコンテンツを分割し、該当セクション内の最初のテーブルを抽出する、より堅牢なロジック。
    """
    
    # 1. contentを '##' で分割し、セクションヘッダーとそのコンテンツのペアを作成
    # '##' の前の内容 (ファイル先頭の # タイトルなど) は無視する
    sections = re.split(r'(^##\s+.*)', content, flags=re.MULTILINE | re.IGNORECASE)
    
    # セクションヘッダーとそのコンテンツをマッピング {ヘッダー名: コンテンツ}
    section_map = {}
    current_section_title = None
    for item in sections:
        item = item.strip()
        if not item:
            continue
            
        if item.startswith('##'):
            current_section_title = item
            section_map[current_section_title] = ""
        elif current_section_title is not None:
            # ヘッダーに続くコンテンツを結合
            section_map[current_section_title] += item + "\n"

    # 2. section_titleで始まるセクションの内容を抽出
    # section_title は '## ユーザー管理' の形式で渡される
    target_content = section_map.get(section_title.strip())

    if not target_content:
        return pd.DataFrame()
    # 3. DataFrameに変換
    try:
        df = pd.read_csv(io.StringIO(target_content), sep='|', skipinitialspace=True)
    except pd.errors.ParserError:
        return pd.DataFrame()

    # 余分なセパレータ行（|---|---|...）を削除
    df = df.iloc[1:]

    # カラム名とセル内の文字列から空白文字をトリム
    df.columns = [col.strip() for col in df.columns]
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x, axis=1)
    
    # Unnamed:で始まる完全に空のカラムを削除
    df = df.loc[:, ~df.columns.str.startswith('Unnamed:')]

    return df.reset_index(drop=True)

def find_markdown_sections(content: str) -> List[str]:
    """Markdownコンテンツからレベル2のヘッダー(## ...)を抽出する"""
    # ## で始まり、改行まで続く文字列を非貪欲に検索
    sections = re.findall(r'^##\s+.*', content, re.MULTILINE)
    return sections


# --- バリデーションと解析関数 ---

def validate_and_parse_table(table_physical_name: str) -> Optional[Dict[str, Any]]:
    """個別テーブル定義ファイルを解析しバリデーション (4.3)"""
    # tables/{テーブル物理名}.md のパスをPROJECT_ROOTから解決
    table_file_path = os.path.join(PROJECT_ROOT, 'tables', f'{table_physical_name}.md')
    
    if not os.path.exists(table_file_path):
        log_error_and_count(f"テーブル定義ファイル '{table_file_path}' が見つかりません。")
        return None

    logging.info(f"テーブル '{table_physical_name}' の解析を開始...")
    with open(table_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    table_data = {'physical_name': table_physical_name, 'model_name': stringcase.pascalcase(table_physical_name)}
    
    # 1. テーブル概要のチェック
    sections = config['validation_rules']['table_overview_sections']
    df_overview = get_markdown_table_to_df(content, sections['OVERVIEW'])
    if df_overview.empty:
        log_error_and_count(f"'{table_physical_name}' のセクション '{sections['OVERVIEW']}' が見つからないか、不正です。")
        return None
    
    logging.info("簡易版のため、テーブル概要のチェックは省略し、正しいものとします。")
    overview_map = df_overview.set_index(config['validation_rules']['table_overview_section_columns']['ITEM'])['内容'].to_dict()
    table_data['logical_name'] = overview_map.get('テーブル論理名', '')

    # 2. カラム定義のチェック
    df_cols = get_markdown_table_to_df(content, sections['COLUMN_DEFINITION'])
    if df_cols.empty:
        log_error_and_count(f"'{table_physical_name}' のセクション '{sections['COLUMN_DEFINITION']}' が見つからないか、不正です。")
        return None

    parsed_columns = []
    fk_list = []
    
    for _, row in df_cols.iterrows():
        col_data = row.to_dict()
        col_phys_name = col_data['カラム物理名']
        
        # 型(桁,精度)のパースとチェック (4.3)
        parsed_type_info = parse_type_and_length(col_data['型(桁,精度)'])
        base_type = parsed_type_info['type']
        col_data['base_type'] = base_type
        col_data['length'] = parsed_type_info['length']
        col_data['precision'] = parsed_type_info['precision']
        
        if base_type == 'DECIMAL' and col_data['precision'] is not None and col_data['length'] is not None:
            if col_data['precision'] > col_data['length']:
                log_error_and_count(f"'{table_physical_name}.{col_phys_name}': DECIMAL型で精度({col_data['precision']})が桁数({col_data['length']})を超えています。")

        # FKのリストアップ
        if col_data['FK'] == 'FK':
            fk_list.append(col_phys_name)
        
        # NOT NULL and DEFAULT NULL チェック
        if col_data['NOTNULL'] == 'NN' and col_data['DEFAULT'].upper() in ['NULL']:
            log_error_and_count(f"'{table_physical_name}.{col_phys_name}': NOT NULL('NN')ですが、DEFAULT値が'NULL'です。")
        
        logging.info("簡易版のため、NOT NULL以外のFK項目チェックは省略し、正しいものとします。")

        parsed_columns.append(col_data)

    table_data['columns'] = parsed_columns

    # 3. インデックス定義のチェック
    df_idx = get_markdown_table_to_df(content, sections['INDEX_DEFINITION'])
    logging.info("簡易版のため、インデックスのチェックは省略し、正しいものとします。")
    table_data['indexes'] = df_idx.to_dict('records') if not df_idx.empty else []

    # 4. 外部キー定義のチェック
    df_fk = get_markdown_table_to_df(content, sections['FK_DEFINITION'])
    logging.info("簡易版のため、外部キーのチェックは省略し、正しいものとします。")
    table_data['foreign_keys'] = df_fk.to_dict('records') if not df_fk.empty else []
        
    # グローバルなFK情報に追加 (逆リレーション生成用)
    all_tables_fk_data[table_physical_name] = table_data['foreign_keys']

    return table_data

# --- Prisma生成関数 ---

def generate_prisma_model(table_data: Dict[str, Any], all_fk_data: Dict[str, List[Dict]]) -> str:
    """解析されたデータからPrismaモデル文字列を生成 (4.4)"""
    model_name = table_data['model_name']
    table_physical_name = table_data['physical_name']
    
    # 1. ヘッダーと@@map
    prisma_code = f"/// {table_data['logical_name']}\n"
    prisma_code += f"model {model_name} {{\n"
    prisma_code += f"  @@map(\"{table_physical_name}\")\n"

    # 2. カラムの定義
    for col in table_data['columns']:
        col_phys_name = col['カラム物理名']
        col_logical_name = col['カラム論理名']
        field_name = stringcase.camelcase(col_phys_name)
        
        base_type = col['base_type']
        prisma_type = config['type_mappings'].get(base_type, 'String')
        
        annotations = []
        comment = f" /// {col_logical_name}"
        
        annotations.append(f"@map(\"{col_phys_name}\")")

        nullable = '' if col['NOTNULL'] == 'NN' else '?'
            
        if col['PK'] == 'PK':
            annotations.append("@id")
            # VARCHAR(36) and DEFAULT UUIDの場合 @default(uuid())
            if base_type == 'VARCHAR' and col['length'] == 36 and col['DEFAULT'].upper() == 'UUID':
                annotations.append("@default(uuid())")
        
        default_val = col['DEFAULT']
        if col['PK'] != 'PK' and default_val not in ['-', 'NULL']:
            if prisma_type == 'String':
                annotations.append(f"@default(\"{default_val}\")")
            elif prisma_type == 'Boolean': 
                annotations.append(f"@default({'true' if default_val == '1' else 'false'})")
            elif prisma_type == "DateTime" and default_val.upper() == 'CURRENT_TIMESTAMP':
                annotations.append("@default(now())")
            else:
                annotations.append(f"@default({default_val})")
        
        if col_phys_name == 'updated_at':
            annotations.append("@updatedAt")
    

        if base_type in ['CHAR', 'VARCHAR'] and col['length'] is not None:
            annotations.append(f"@db.VarChar({col['length']})")
        elif base_type == 'DECIMAL' and col['length'] is not None and col['precision'] is not None:
            annotations.append(f"@db.Decimal({col['length']}, {col['precision']})")

        prisma_code += f"  {field_name} {prisma_type}{nullable} {' '.join(annotations)}{comment}\n"

    # 3. リレーションフィールドの定義 (順リレーション)
    for fk in table_data['foreign_keys']:
        fk_name = fk['外部キー物理名']
        source_col_phys = fk['参照元カラム物理名']
        dest_table_phys = fk['参照先テーブル物理名']
        
        relation_field_name = stringcase.camelcase(fk_name.replace('fk_', ''))
        dest_model_name = stringcase.pascalcase(dest_table_phys)
        fk_field_name = stringcase.camelcase(source_col_phys)

        relation_annotation = (
            f'@relation("{fk_name}", fields: [{fk_field_name}], references: [{fk["参照先カラム物理名"]}], '
            f'onDelete: {fk["ON DELETE"]}, onUpdate: {fk["ON UPDATE"]})'
        )

        prisma_code += f"  {relation_field_name} {dest_model_name} {relation_annotation}\n"

    # 4. 逆リレーションフィールドの定義
    for referring_table_phys, fks in all_fk_data.items():
        if referring_table_phys == table_physical_name:
            continue
        
        referring_model_name = stringcase.pascalcase(referring_table_phys)
        
        for fk in fks:
            if fk['参照先テーブル物理名'] == table_physical_name:
                fk_name = fk['外部キー物理名']
                rev_field_name = 'rev' + stringcase.pascalcase(fk_name.replace('fk_', ''))
                
                prisma_code += f"  {rev_field_name} {referring_model_name}[] @relation(\"{fk_name}\")\n"

    # 5. 複合制約 (@@id, @@unique, @@index)
    pk_cols = [col['カラム物理名'] for col in table_data['columns'] if col['PK'] == 'PK']
    if len(pk_cols) > 1:
        pk_fields = ', '.join(f'"{c}"' for c in pk_cols)
        prisma_code += f"\n  @@id([ {pk_fields} ])\n"

    uk_groups = {}
    for col in table_data['columns']:
        uk_mark = col['UNIQUE']
        if uk_mark.startswith('UK'):
            if uk_mark not in uk_groups:
                uk_groups[uk_mark] = []
            uk_groups[uk_mark].append(stringcase.camelcase(col['カラム物理名']))

    uk_defined_indexes = []
    
    for uk_mark, uk_cols in uk_groups.items():
        fields = ', '.join(f'{c}' for c in uk_cols)
        prisma_code += f"  @@unique([ {fields} ], name: \"{uk_mark.lower()}\")\n"
        uk_defined_indexes.append(sorted(uk_cols))

    if table_data['indexes']:
        for idx in table_data['indexes']:
            idx_cols = [c.strip() for c in idx['カラム物理名'].split(',')]
            
            if sorted(idx_cols) in uk_defined_indexes:
                 logging.warning(f"'{table_physical_name}' のインデックス '{idx['インデックス物理名']}' はUK/@@uniqueと重複するためスキップ。")
                 continue
            
            if idx['UNIQUE'] == 'YES':
                 logging.warning(f"'{table_physical_name}' のインデックス '{idx['インデックス物理名']}' はUNIQUEですが、@@uniqueでカバーされていません。手動確認が必要です。")
                 continue
                 
            fields_with_sort = ', '.join(f'{stringcase.camelcase(c)}' for c in idx_cols)
            index_type = ""
            if idx['インデックスタイプ'] == 'Hash':
                 index_type = ", type: Hash"

            prisma_code += f"  @@index([ {fields_with_sort} ], name: \"{idx['インデックス物理名']}\"{index_type})\n"

    # 6. 閉じる
    prisma_code += "}\n"
    return prisma_code

# --- メイン処理 ---

def main():
    global config
    
    # 0. 初期化と設定の読み込み
    try:
        # ログディレクトリの準備
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        else:
             # 既存ログの削除
            for f in os.listdir(LOG_DIR):
                os.remove(os.path.join(LOG_DIR, f))
        
        # config.jsonの読み込み
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # 出力ディレクトリの準備
        if not os.path.exists(OUTPUT_MODEL_DIR):
            os.makedirs(OUTPUT_MODEL_DIR)
        
        # ロガー初期化
        setup_logging()
            
    except Exception as e:
        print(f"初期設定ファイルの読み込み/初期化に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    # 1. テーブル一覧ファイルの解析 (4.2)
    try:
        with open(TABLES_MD_PATH, 'r', encoding='utf-8') as f:
            tables_md_content = f.read()
        
        # Markdownファイルからすべてのレベル2セクションヘッダーを動的に取得
        sections_to_parse = find_markdown_sections(tables_md_content)
        
        if not sections_to_parse:
            log_error_and_count(f"テーブル一覧ファイル '{TABLES_MD_PATH}' から有効なテーブル管理セクション ('## ...') が見つかりませんでした。")
            sys.exit(1)
            
        table_overview_dfs = []
        for section in sections_to_parse:
            # 動的に取得したセクション名を使ってテーブルを抽出
            df = get_markdown_table_to_df(tables_md_content, section) 
            if not df.empty:
                table_overview_dfs.append(df)
        
        if not table_overview_dfs:
            log_error_and_count(f"テーブル一覧ファイル '{TABLES_MD_PATH}' から有効なテーブル情報が抽出できませんでした。")
            sys.exit(1)
            
        df_all_tables = pd.concat(table_overview_dfs, ignore_index=True)

        # テーブル物理名から[]を外し、モデル名への変換に必要なクリーンな名前を取得
        def extract_physical_name(name):
            match = re.search(r'\[(.*?)\]', name)
            return match.group(1) if match else name
            
        df_all_tables['テーブル物理名_clean'] = df_all_tables['テーブル物理名'].apply(extract_physical_name)
        
        global all_table_names, all_model_names
        unique_phys_names = df_all_tables['テーブル物理名_clean'].loc[
            (df_all_tables['テーブル物理名_clean'] != '') & 
            (df_all_tables['テーブル物理名_clean'] != 'None')
        ].unique().tolist()

        all_table_names = {
            name: name
            for name in unique_phys_names 
        }
        all_model_names = [stringcase.pascalcase(phys_name) for phys_name in all_table_names.keys()]

        # テーブル作成順序でソート
        sorted_table_names = df_all_tables.sort_values(by='テーブル作成順序')['テーブル物理名_clean'].tolist()

    except Exception as e:
        log_error_and_count(f"テーブル一覧ファイルの解析中にエラーが発生しました: {e}")
        sys.exit(1)

    # 2. 個別テーブル定義ファイルの解析とバリデーション
    parsed_table_data = []
    
    for table_phys_name in sorted_table_names:
        data = validate_and_parse_table(table_phys_name)
        if data:
            parsed_table_data.append(data)
            
    if global_error_count > 0:
        log_error_and_count(f"致命的なエラーが {global_error_count} 件検出されたため、Prismaコード生成を中止します。")
        sys.exit(1)
        
    logging.info("--- 全テーブルの解析とバリデーションが完了しました ---")

    # 3. Prismaスキーマの生成と出力
    logging.info("Prismaスキーマの生成と出力...")
    model_imports = []
    
    for data in parsed_table_data:
        # モデルコードの生成
        model_code = generate_prisma_model(data, all_tables_fk_data)
        model_name = data['model_name']
        model_filename = f'{model_name}.prisma'
        
        # @import パスはbase.prismaからの相対パス
        model_imports.append(f'@import ./model/{model_filename}')
        
        # モデルファイル出力 (絶対パス)
        try:
            with open(os.path.join(OUTPUT_MODEL_DIR, model_filename), 'w', encoding='utf-8') as f:
                f.write(model_code)
            logging.info(f"モデルファイル '{model_filename}' を出力しました。")
        except Exception as e:
            log_error_and_count(f"モデルファイル '{model_filename}' の出力中にエラーが発生しました: {e}")

    # base.prisma ファイルの生成 (絶対パス)
    base_prisma_content = (
        "datasource db {\n"
        "  provider = \"mysql\"\n"
        "  url      = env(\"DATABASE_URL\")\n"
        "}\n\n"
        "generator client {\n"
        "  provider = \"prisma-client-js\"\n"
        "}\n\n"
    )
    base_prisma_content += '\n'.join(model_imports)
    
    try:
        with open(BASE_PRISMA_FILE, 'w', encoding='utf-8') as f:
            f.write(base_prisma_content)
        logging.info(f"メインスキーマファイル '{BASE_PRISMA_FILE}' を出力しました。")
    except Exception as e:
        log_error_and_count(f"メインスキーマファイル '{BASE_PRISMA_FILE}' の出力中にエラーが発生しました: {e}")

    logging.info(f"--- 処理が完了しました。エラー: {global_error_count} 件 ---")

if __name__ == '__main__':
    main()
