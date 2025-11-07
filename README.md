# Simple contract management system データベース定義標準仕様書

## 設計マニュアルとSchema as Codeリファレンス

本書は、[simple-contract-management-system](https://github.com/ryo-ichikawa-0308/simple-contract-management-system)のデータベース定義の標準仕様を記載したものである。

DB設計マニュアル(本プロジェクトの設計ルール/メインコンテンツ)及び、そのルールに従って作成されたテーブル設計のサンプル群を資産に含む。

RDBMSはMySQLを前提とする。他のRDBMSを前提とする場合、適宜読み替えが必要な場合がある。

## 構成要素

| ファイル/ディレクトリ                      | 役割                     | 備考                                                                                                                  |
| ------------------------------------------ | ------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| [db-docs-tutorial.md](db-docs-tutorial.md) | DB設計マニュアル         | 本ドキュメントのメインコンテンツ。テーブル設計手順を定義する。                                                        |
| [tables](./tables/)                        | 設計書サンプル           | DB設計マニュアルに従って記載した、テーブル一覧と個別テーブル定義書。                                                  |
| [er-diagrams](./er-diagrams/)              | 設計書サンプル(ER図)     | テーブルの関係を示したER図。                                                                                          |
| [ai-generated](./ai-generated/)            | 設計書サンプル(JSON)     | 定義サンプルを、[scms-prompts](https://github.com/ryo-ichikawa-0308/scms-prompts)プロンプトによって処理した出力結果。 |
| README.md(本書)                            | ドキュメントの概要と構成 |                                                                                                                       |

## 設計書のファイル構成

- **[db-docs-tutorial.md](./db-docs-tutorial.md)** データベース設計マニュアル。本プロジェクトのメインコンテンツ。

---

- **[tables.md](./tables/tables.md)** テーブル一覧。システム内に存在するテーブルの論理名、物理名、概要と作成順を定義する。
- **[users.md](./tables/users.md)** ユーザーテーブルの個別定義書。
- **[services.md](./tables/services.md)** サービステーブルの個別定義書。
- **[user_services.md](./tables/user_sercvices.md)** ユーザー提供サービステーブルの個別定義書。
- **[contracts.md](./tables/contracts.md)** 契約テーブルの個別定義書。

---

- **[database.json](./ai-generated/database.json)** DB設計書をJSON変換プロンプトで変換したJSONファイル。
- **[schema.prisma](./ai-generated/schema.prisma)** JSON化したDB設計書をPrisma変換プロンプトで変換したPrismaモデルファイル。

(C)2025 Ryo ICHIKAWA
