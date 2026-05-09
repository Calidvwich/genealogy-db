-- 1. 创建用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 创建族谱表
CREATE TABLE genealogies (
    clan_id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    surname VARCHAR(20),
    revised_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    creator_id INTEGER REFERENCES users(id)
);

-- 3. 创建协作表
CREATE TABLE collaborations (
    clan_id INTEGER REFERENCES genealogies(clan_id),
    user_id INTEGER REFERENCES users(id),
    PRIMARY KEY (clan_id, user_id)
);

-- 4. 创建成员表 (注意父子引用的外键)
CREATE TABLE members (
    member_id BIGINT PRIMARY KEY,
    clan_id INTEGER REFERENCES genealogies(clan_id),
    name VARCHAR(50) NOT NULL,
    gender CHAR(1) CHECK (gender IN ('M', 'F')),
    birth_year INT,
    death_year INT,
    father_id BIGINT REFERENCES members(member_id),
    mother_id BIGINT REFERENCES members(member_id),
    generation_num INT,
    bio TEXT
);

-- 5. 创建索引优化性能
CREATE INDEX idx_members_father ON members(father_id);
CREATE INDEX idx_members_clan_name ON members(clan_id, name);