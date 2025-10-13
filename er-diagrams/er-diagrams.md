# simple-contract-management-system ER 図

```mermaid
erDiagram
    users ||--o{ user_services :""
    users ||--o{ contracts :""
    services ||--o{ user_services :""
    user_services ||--o{ contracts :""
```
