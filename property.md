"collaborations" "clan_id" "integer" "⭐ 主键 (PK)"

"collaborations" "clan_id" "integer" "🔗 外键 (FK)" "genealogies.clan_id"

"collaborations" "user_id" "integer" "🔗 外键 (FK)" "users.id"

"collaborations" "user_id" "integer" "⭐ 主键 (PK)"

"genealogies" "clan_id" "integer" "⭐ 主键 (PK)"

"genealogies" "title" "character varying"

"genealogies" "surname" "character varying"

"genealogies" "revised_at" "timestamp without time zone"

"genealogies" "creator_id" "integer" "🔗 外键 (FK)" "users.id"

"members" "member_id" "bigint" "⭐ 主键 (PK)"

"members" "clan_id" "integer" "🔗 外键 (FK)" "genealogies.clan_id"

"members" "name" "character varying"

"members" "gender" "character"

"members" "birth_year" "integer"

"members" "death_year" "integer"

"members" "father_id" "bigint" "🔗 外键 (FK)" "members.member_id"

"members" "mother_id" "bigint" "🔗 外键 (FK)" "members.member_id"

"members" "generation_num" "integer"

"members" "bio" "text"

"members" "id_pic" "text"

"users" "id" "integer" "⭐ 主键 (PK)"

"users" "user_id" "character varying" "💎 唯一约束 (Unique)"

"users" "password_hash" "character varying"

"users" "username" "character varying"

"users" "created_at" "timestamp without time zone"