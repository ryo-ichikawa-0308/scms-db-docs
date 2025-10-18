# scms-db-doc

本書は、[simple-contract-management-system](https://github.com/ryo-ichikawa-0308/simple-contract-management-system)のDB定義ルールを記載したものです。

READMEの原則に従って設計したテーブル設計のサンプルと、それをPrismaコードに自動変換するPythonスクリプト(簡易版)を資産に含みます。スクリプトは簡易版のため、最低限の機能(本プロジェクトで公開している資産のPrismaコード変換)のみをサポートします。

RDBMSはMySQLを前提とします。他のRDBMSを前提とする場合、適宜読み替えが必要な場合があります。

## ディレクトリ構成

- **tables** テーブル一覧及びテーブル設計書
- **er-diagrams** ER図
- **scripts** prismaコード作成のためのスクリプト(簡易版)

※本プロジェクトを[simple-contract-management-system](https://github.com/ryo-ichikawa-0308/simple-contract-management-system)のサブモジュールとしてcloneしている場合、Prisma変換スクリプトを実行するpre-pushが自動設定される想定です。

## 設計書のファイル構成

- **[db-tutorial.md](./db-tutorial.md)** テーブル設計マニュアル。
- **[tables.md](./tables/tables.md)** テーブル一覧。システム内に存在するテーブルの論理名、物理名、概要と作成順を定義する。
- **[users.md](./tables/users.md)** ユーザーテーブルの個別定義書。
- **[services.md](./tables/services.md)** サービステーブルの個別定義書。
- **[user_services.md](./tables/user_sercvices.md)** ユーザー提供サービステーブルの個別定義書。
- **[contracts.md](./tables/contracts.md)** 契約テーブルの個別定義書。

(C)2025 Ryo ICHIKAWA
