# MyGuest v2 Detailed ERD

This version is the technical companion to the simplified ERD. It shows the
actual database tables, the key columns on each table, and the relationship
cardinality using classic ERD notation.

## Detailed Schema

```mermaid
erDiagram
    USERS ||--o{ CLIENTS : owns
    USERS ||--o{ SERVICES : defines
    CLIENTS ||--o| COLOR_CHARTS : has_profile
    CLIENTS ||--o{ FORMULAS : logs
    FORMULAS ||--o{ FORMULA_IMAGES : stores
    FORMULAS ||--o{ FORMULA_SERVICES : includes
    SERVICES ||--o{ FORMULA_SERVICES : links

    USERS {
        int id PK
        string firebase_uid UK nullable
        string email UK
        string first_name nullable
        string last_name nullable
        string photo_url nullable
        datetime created_at
        datetime updated_at
    }

    CLIENTS {
        int id PK
        int owner_user_id FK
        string first_name
        string last_name
        string email nullable
        string phone nullable
        date birthday nullable
        string client_type nullable
        text notes nullable
        datetime created_at
        datetime updated_at
    }

    COLOR_CHARTS {
        int id PK
        int client_id FK UK
        string porosity nullable
        string hair_texture nullable
        string elasticity nullable
        string scalp_condition nullable
        string natural_level nullable
        string desired_level nullable
        string contrib_pigment nullable
        string gray_front nullable
        string gray_sides nullable
        string gray_back nullable
        string skin_depth nullable
        string skin_tone nullable
        string eye_color nullable
        datetime created_at
        datetime updated_at
    }

    FORMULAS {
        int id PK
        int client_id FK
        string service_type nullable
        text notes nullable
        int price_cents nullable
        datetime service_at
        datetime created_at
        datetime updated_at
    }

    FORMULA_IMAGES {
        int id PK
        int formula_id FK
        string storage_provider
        text public_url nullable
        string object_key nullable
        string file_name
        datetime created_at
        datetime updated_at
    }

    SERVICES {
        int id PK
        int owner_user_id FK
        string name
        string normalized_name
        int sort_order
        int default_price_cents nullable
        int default_return_weeks nullable
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    FORMULA_SERVICES {
        int id PK
        int formula_id FK
        int service_id FK
        string service_label_snapshot
        int position
        datetime created_at
        datetime updated_at
    }
```

## Notation

- `||` = exactly one
- `o|` = zero or one
- `o{` = zero or many
- `PK` = primary key
- `FK` = foreign key
- `UK` = unique key / unique constrained field

## Important Constraints

- `users.email` is unique.
- `users.firebase_uid` is unique and nullable.
- `color_charts.client_id` is unique, making the client-to-color-chart
  relationship one-to-zero-or-one.
- `services` enforces uniqueness on `(owner_user_id, normalized_name)`.
- `formula_services` enforces uniqueness on:
  - `(formula_id, service_id)`
  - `(formula_id, position)`

## Modeling Notes

- `formula_services` is the normalized multi-service join table for appointment
  logs.
- `formulas.service_type` remains present for legacy compatibility and
  transitional payload support.
- `formula_images` supports both URL-based and object-key-based storage
  references.
