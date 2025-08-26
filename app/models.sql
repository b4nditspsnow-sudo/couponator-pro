PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  ref1_id INTEGER,
  ref2_id INTEGER,
  joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS balances (
  user_id INTEGER PRIMARY KEY,
  amount INTEGER NOT NULL DEFAULT 0  -- копейки
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  kind TEXT NOT NULL,               -- 'reward_ref1','reward_ref2','owner_income','manual'
  amount INTEGER NOT NULL,          -- копейки; >0 начисление, <0 списание
  meta TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clicks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  offer_id TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  buyer_id INTEGER NOT NULL,
  offer_id TEXT NOT NULL,
  price INTEGER NOT NULL,           -- рубли (для простоты)
  status TEXT NOT NULL DEFAULT 'pending',   -- 'pending','delivered','canceled'
  code TEXT,                        -- выданный одноразовый код
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
