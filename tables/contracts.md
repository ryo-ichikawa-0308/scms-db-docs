
# 契約テーブル定義

## 1.テーブル概要

| 項目           | 内容                                                 | 備考 |
| -------------- | ---------------------------------------------------- | ---- |
| テーブル論理名 | 契約                                 | -    |
| テーブル物理名 | contracts                                        | -    |
| テーブル概要   | どのユーザーがどのサービスを幾つ契約したかを管理する | -    |
| テーブル系統   | 契約管理                                         | -    |

## 2.カラム定義

| カラム論理名           | カラム物理名     | 型(桁,精度)  | PK  | FK  | UNIQUE | NOTNULL | DEFAULT           | 備考                       |
| ---------------------- | ---------------- | ------------ | --- | --- | ------ | ------- | ----------------- | -------------------------- |
| ID                     | id               | CHAR(36)     | PK  | -   | -      | NN      | UUID              | -                          |
| ユーザーID             | users_id         | CHAR(36)     | -   | FK  | -      | NN      | -                 | -                          |
| ユーザー提供サービスID | user_services_id | CHAR(36)     | -   | FK  | -      | NN      | -                 | -                          |
| 契約数                 | quantity         | INTEGER      | -   | -   | -      | NN      | 0                 | 負数は不可(ロジックで担保) |
| 登録日時               | registered_at    | TIMESTAMP(3) | -   | -   | -      | NN      | CURRENT_TIMESTAMP | -                          |
| 登録者                 | registered_by    | CHAR(36)     | -   | -   | -      | NN      | -                 | -                          |
| 更新日時               | updated_at       | TIMESTAMP(3) | -   | -   | -      | -       | NULL              | -                          |
| 更新者                 | updated_by       | CHAR(36)     | -   | -   | -      | -       | NULL              | -                          |
| 削除フラグ             | is_deleted       | TINYINT(1)   | -   | -   | -      | NN      | 0                 | -                          |

## 3.インデックス定義

| インデックス物理名   | カラム物理名     | UNIQUE | インデックスタイプ | ソート順 | 備考 |
| -------------------- | ---------------- | ------ | ------------------ | -------- | ---- |
| idx_users_id         | users_id         | NO     | B-Tree             | ASC      | -    |
| idx_user_services_id | user_services_id | NO     | B-Tree             | ASC      | -    |

## 4.外部キー定義

| 外部キー物理名             | 参照元カラム物理名 | 参照先テーブル物理名 | 参照先カラム物理名 | ON DELETE | ON UPDATE | 備考 |
| -------------------------- | ------------------ | -------------------- | ------------------ | --------- | --------- | ---- |
| fk_contracts_users         | users_id           | users                | id                 | NoAction  | NoAction  | -    |
| fk_contracts_user_services | user_services_id   | user_services        | id                 | NoAction  | NoAction  | -    |
