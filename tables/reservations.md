
# 予約情報定義書

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
| ユーザーID | user_id | INT | - | FK | - | NN | - | users.idへの外部キー |
| 予約日時 | reservation_date | DATETIME | - | - | - | NN | - | 予約時刻 |
| 登録日 | registered_at | TIMESTAMP | - | - | - | NN | CURRENT_TIMESTAMP | 登録日時 |
| 登録者 | registered_by | VARCHAR(255) | - | - | - | NN | - | 登録者ID |
| 更新日 | updated_at | TIMESTAMP | - | - | - | NN | CURRENT_TIMESTAMP | 更新日時 |
| 更新者 | updated_by | VARCHAR(255) | - | - | - | NN | - | 更新者ID |
| 削除フラグ | is_deleted | TINYINT | - | - | - | NN | 0 | 削除状態 |

## 3.インデックス定義

| インデックス物理名 | カラム物理名 | UNIQUE | インデックスタイプ | ソート順 | 備考 |
|---|---|---|---|---|---|
| idx_res_user | user_id | - | B-tree | ASC | ユーザー別検索 |

## 4.外部キー定義

| 外部キー物理名 | 参照元カラム物理名 | 参照先テーブル物理名 | 参照先カラム物理名 | ON DELETE | ON UPDATE | 備考 |
|---|---|---|---|---|---|---|
| fk_res_user | user_id | users | id | CASCADE | NO ACTION | ユーザーが削除されたら予約も削除 |
