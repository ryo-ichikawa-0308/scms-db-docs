
# ユーザー提供サービステーブル定義

## 1.テーブル概要

| 項目           | 内容                                                 | 備考 |
| -------------- | ---------------------------------------------------- | ---- |
| テーブル論理名 | ユーザー提供サービス                                 | -    |
| テーブル物理名 | user_services                                        | -    |
| テーブル概要   | どのユーザーがどのサービスを幾つ提供可能かを管理する | -    |
| テーブル系統   | サービス管理                                         | -    |

## 2.カラム定義

| カラム論理名 | カラム物理名  | 型(桁,精度) | PK  | FK  | UNIQUE | NOTNULL | DEFAULT           | 備考                           |
| ------------ | ------------- | ----------- | --- | --- | ------ | ------- | ----------------- | ------------------------------ |
| ID           | id            | VARCHAR(36) | PK  | -   | -      | NN      | UUID              | -                              |
| ユーザーID   | users_id      | VARCHAR(36) | -   | FK  | UK1    | NN      | -                 | 紐づけ先が一意であることを保証 |
| サービスID   | services_id   | VARCHAR(36) | -   | FK  | UK1    | NN      | -                 | 紐づけ先が一意であることを保証 |
| 在庫数       | stock         | INT         | -   | -   | -      | NN      | 0                 | 負数は不可(ロジックで担保)     |
| 登録日       | registered_at | TIMESTAMP   | -   | -   | -      | NN      | CURRENT_TIMESTAMP | -                              |
| 登録者       | registered_by | VARCHAR(36) | -   | -   | -      | NN      | -                 | -                              |
| 更新日       | updated_at    | TIMESTAMP   | -   | -   | -      | -       | NULL              | -                              |
| 更新者       | updated_by    | VARCHAR(36) | -   | -   | -      | -       | NULL              | -                              |
| 削除フラグ   | is_deleted    | TINYINT(1)  | -   | -   | -      | NN      | 0                 | -                              |

## 3.インデックス定義

| インデックス物理名            | カラム物理名          | UNIQUE | インデックスタイプ | ソート順 | 備考                                    |
| ----------------------------- | --------------------- | ------ | ------------------ | -------- | --------------------------------------- |
| idx_user_services_users_id    | users_id              | NO     | B-Tree             | ASC      | 外部キー/UK構成要素のためのインデックス |
| idx_user_services_services_id | services_id           | NO     | B-Tree             | ASC      | 外部キー/UK構成要素のためのインデックス |
| idx_user_services_unique      | users_id, services_id | YES    | B-Tree             | ASC, ASC | UK1を構成                               |

## 4.外部キー定義

| 外部キー物理名            | 参照元カラム物理名 | 参照先テーブル物理名 | 参照先カラム物理名 | ON DELETE | ON UPDATE | 備考 |
| ------------------------- | ------------------ | -------------------- | ------------------ | --------- | --------- | ---- |
| fk_user_services_users    | users_id           | users                | id                 | NoAction  | NoAction  | -    |
| fk_user_services_services | services_id        | services             | id                 | NoAction  | NoAction  | -    |
