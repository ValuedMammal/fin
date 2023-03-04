-- .schema --

-- primary key tables --
CREATE TABLE user (
   id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, 
   username TEXT NOT NULL UNIQUE, 
   hash TEXT NOT NULL, 
   cash NUMERIC NOT NULL DEFAULT 1000000.00
);
CREATE TABLE asset (
   id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
   class TEXT,
   symbol TEXT NOT NULL UNIQUE,
   name TEXT NOT NULL,
   price NUMERIC
);
CREATE TABLE trade (
   id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
   type TEXT,
   user_id INTEGER,
   asset_id INTEGER,
   qty NUMERIC,
   price NUMERIC,
   time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
   FOREIGN KEY (user_id) REFERENCES user(id),
   FOREIGN KEY (asset_id) REFERENCES asset(id)
);
CREATE TABLE skull (
   id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
   name TEXT NOT NULL UNIQUE,
   description TEXT NOT NULL
);
CREATE TABLE settings (
    user_id INTEGER NOT NULL,
    theme TEXT NOT NULL DEFAULT 'light',
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- join tables --
CREATE TABLE holding (
   asset_id INTEGER,
   user_id INTEGER,
   qty NUMERIC,
   FOREIGN KEY (asset_id) REFERENCES asset(id),
   FOREIGN KEY (user_id) REFERENCES user(id),
   UNIQUE (asset_id,user_id)
);
CREATE TABLE badge (
   skull_id INTEGER,
   user_id INTEGER,
   FOREIGN KEY (skull_id) REFERENCES skull(id),
   FOREIGN KEY (user_id) REFERENCES user(id),
   UNIQUE (skull_id,user_id)
);